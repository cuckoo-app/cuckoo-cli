import sys
import time
from pprint import pprint
import psutil
import subprocess
import os
import errno
import boto3
from botocore.client import ClientError
import warrant
from warrant.aws_srp import AWSSRP
import uuid
import json
import getpass

import config

import auth
import aws_resources
import datetime_utils
import email_notifications


if __name__ == '__main__':
    # filename = command.replace(' ', '_') + '-' + str(uuid.uuid4()) + '.txt'
    cuckoo_dir = '%s/.cuckoo' % os.path.expanduser('~')
    storage_key = '%s.txt' % str(uuid.uuid4())
    try:
        os.makedirs(cuckoo_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    try:
        with open('%s/config.json' % cuckoo_dir, 'r') as f:
            cuckoo_config = json.load(f)
            username = cuckoo_config['username']
            password = cuckoo_config['password']
            machine = cuckoo_config['machine']
    except FileNotFoundError:
        print('No configuration file found.')
        username = input('Username: ')
        password = getpass.getpass('Password: ')
        machine = input('Enter a custom label for this machine: ')
        cuckoo_config = {
            'username': username,
            'password': password,
            'machine': machine,
        }
        with open('%s/config.json' % cuckoo_dir, 'w') as f:
            json.dump(cuckoo_config, f)

    command = sys.argv[1]
    stage = sys.argv[2]

    update_period = 2

    filename = '%s/%s' % (cuckoo_dir, storage_key)

    print('Connecting to server...')

    region = config.attr[stage]['region']
    user_pool_id = config.attr[stage]['user_pool_id']
    app_client_id = config.attr[stage]['app_client_id']
    identity_pool_id = config.attr[stage]['identity_pool_id']
    bucket_name = config.attr[stage]['bucket_name']

    aws_access_key_id = 'AKIAIOSFODNN7EXAMPLE'
    aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'

    idp_client = boto3.client('cognito-idp', region_name=region,
        aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    identity_client = boto3.client('cognito-identity', region_name=region)

    aws = AWSSRP(username=username,
                 password=password,
                 pool_id=user_pool_id,
                 client_id=app_client_id,
                 client=idp_client)
    tokens = aws.authenticate_user()
    access_token = tokens['AuthenticationResult']['AccessToken']
    id_token = tokens['AuthenticationResult']['IdToken']
    refresh_token = tokens['AuthenticationResult']['RefreshToken']
    identity_id = identity_client.get_id(IdentityPoolId=identity_pool_id,
        Logins={'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id): id_token})['IdentityId']
    credentials = identity_client.get_credentials_for_identity(IdentityId=identity_id,
        Logins={'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id): id_token})

    access_key_id = credentials['Credentials']['AccessKeyId']
    secret_key = credentials['Credentials']['SecretKey']
    session_token = credentials['Credentials']['SessionToken']

    aws_access_keys = {
        'aws_access_key_id': access_key_id,
        'aws_secret_access_key': secret_key,
        'aws_session_token': session_token,
    }

    # Set up access to AWS resources
    dynamodb = aws_resources.dynamodb_resource(
        aws_access_keys
    )
    table = dynamodb.Table('%s-jobs' % stage)

    s3 = aws_resources.s3_resource(
        aws_access_keys
    )

    job_id = str(uuid.uuid4())
    start_date = datetime_utils.get_start_date()
    date_modified, runtime = datetime_utils.get_current_times(start_date)
    payload = {
        'userId': identity_id,
        'jobId': job_id,
        'command': command,
        'jobStatus': 'running',
        'machine': machine,
        'dateCreated': start_date,
        'dateModified': date_modified,
        'runtime': runtime,
        'stdout': storage_key,
        'unread': True,
    }

    # ACTUALLY START SUBPROCESS
    my_env = os.environ.copy()
    my_env['PYTHONUNBUFFERED'] = '1'
    p = psutil.Popen(command.split(),
                     env=my_env,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT,
                     bufsize=1,
                     universal_newlines=True)
    print('Subprocess PID:', p.pid)

    # Send initial information to database and create stdout file
    response = table.put_item(
        Item=payload
    )
    pprint(payload)
    f = open(filename, 'a+')
    f.write('$ %s\n' % (command))
    f.close()

    buffer = ""
    start = time.time()
    for line in p.stdout:
        if time.time() - start >= update_period:
            print('Buffered! (Not sent)', [buffer])
            f = open(filename, 'a+')
            f.write(buffer)
            f.close()

            payload['jobStatus'] = 'running'
            date_modified, runtime = datetime_utils.get_current_times(start_date)
            payload['runtime'] = runtime
            payload['dateModified'] = date_modified
            pprint(payload)

            buffer = ""
            start = time.time()
        sys.stdout.write(line)
        buffer += line
    print('Buffered!', [buffer])
    f = open(filename, 'a+')
    f.write(buffer)
    f.close()

    print('Exit code:', p.poll())

    if p.returncode == 0:
        payload['jobStatus'] = 'success'
    else:
        payload['jobStatus'] = 'error'
    date_modified, runtime = datetime_utils.get_current_times(start_date)
    payload['runtime'] = runtime
    payload['dateModified'] = date_modified
    s3.meta.client.upload_file(filename,
                               bucket_name,
                               'private/%s/%s' % (identity_id, storage_key))
    response = table.update_item(
        Key={
            'userId': payload['userId'],
            'jobId': payload['jobId'],
        },
        UpdateExpression=("SET dateModified = :dateModified, "
                          + "jobStatus = :jobStatus, runtime = :runtime, "
                          + "stdout = :stdout, unread = :unread"),
        ExpressionAttributeValues={
          ':dateModified': payload['dateModified'],
          ':jobStatus': payload['jobStatus'],
          ':runtime': payload['runtime'],
          ':stdout': payload['stdout'],
          ':unread': payload['unread'],
        },
        ReturnValues="ALL_NEW"
    )
    pprint(payload)

    try:
        subprocess.call(['rm', filename])
    except Exception as e:
        raise e

    ses_client = aws_resources.ses_client(
        aws_access_keys
    )
    email_notifications.send_completion_email(ses_client, payload)
