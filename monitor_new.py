import sys
import time
from datetime import datetime
import dateutil.parser
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

import config


def get_current_times(start_time):
    # Start time in ISO 8601
    now_date = datetime.utcnow().isoformat()

    diff = dateutil.parser.parse(now_date) - dateutil.parser.parse(start_date)
    # print(diff, type(diff))

    s = diff.total_seconds()
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    runtime = ('{:02}:{:02}:{:02}'
               .format(int(hours), int(minutes), int(seconds)))

    return now_date, runtime


if __name__ == '__main__':
    if len(sys.argv) == 4:
        command = sys.argv[1]
        update_period = int(sys.argv[2])
        stage = sys.argv[3]
    else:
        command = 'python count.py'
        update_period = 2
        stage = 'dev'

    machine = 'My Macbook Pro'

    # filename = command.replace(' ', '_') + '-' + str(uuid.uuid4()) + '.txt'
    cuckoo_dir = '%s/.cuckoo' % os.path.expanduser('~')
    storage_key = '%s.txt' % str(uuid.uuid4())
    try:
        os.makedirs(cuckoo_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    filename = '%s/%s' % (cuckoo_dir, storage_key)

    print('Connecting to server...')

    idp_client = boto3.client('cognito-idp')
    identity_client = boto3.client('cognito-identity')

    username = config.attr[stage]['username']
    password = config.attr[stage]['password']
    region = config.attr[stage]['region']
    user_pool_id = config.attr[stage]['user_pool_id']
    app_client_id = config.attr[stage]['app_client_id']
    identity_pool_id = config.attr[stage]['identity_pool_id']
    bucket_name = config.attr[stage]['bucket_name']

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

    # Set up access to AWS resources
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('%s-jobs' % stage)

    s3 = boto3.resource('s3')

    job_id = str(uuid.uuid4())
    start_date = datetime.utcnow().isoformat()
    date_modified, runtime = get_current_times(start_date)
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
        'unread': 'true',
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
            print('Buffered!', [buffer])
            f = open(filename, 'a+')
            f.write(buffer)
            f.close()

            payload['jobStatus'] = 'running'
            date_modified, runtime = get_current_times(start_date)
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
    date_modified, runtime = get_current_times(start_date)
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
