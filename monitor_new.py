import sys
import time
from datetime import datetime
import dateutil.parser
from pprint import pprint
import psutil
import subprocess
import os
import boto3
import warrant
from warrant.aws_srp import AWSSRP
import uuid


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
    if len(sys.argv) == 3:
        command = sys.argv[1]
        update_period = int(sys.argv[2])
    else:
        command = 'python count.py'
        update_period = 2

    machine = 'My Macbook Pro'

    # filename = command.replace(' ', '_') + '-' + str(uuid.uuid4()) + '.txt'
    filename = str(uuid.uuid4()) + '.txt'

    print('Connecting to server...')

    idp_client = boto3.client('cognito-idp')
    identity_client = boto3.client('cognito-identity')


    username = 'bryan'
    password = 'Passw0rd!'
    region = 'us-east-2'
    user_pool_id = 'us-east-2_tz3KicE71'
    app_client_id = '3031326c8q6css5nde2sr0icus'
    identity_pool_id = 'us-east-2:27b329a5-fd3a-4119-9f50-35c1d19054c4'


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

    s3 = boto3.resource('s3')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('jobs')

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
        'stdout': filename,
    }
    response = table.put_item(
        Item=payload
    )
    pprint(payload)

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
            payload['stdout'] = filename
            s3.meta.client.upload_file(filename,
                                       'cuckoo-app-uploads',
                                       'private/%s/%s' % (identity_id, filename))
            response = table.update_item(
                Key={
                    'userId': payload['userId'],
                    'jobId': payload['jobId'],
                },
                UpdateExpression=("SET dateModified = :dateModified, "
                                  + "jobStatus = :jobStatus, runtime = :runtime, "
                                  + "stdout = :stdout"),
                ExpressionAttributeValues={
                  ':dateModified': payload['dateModified'],
                  ':jobStatus': payload['jobStatus'],
                  ':runtime': payload['runtime'],
                  ':stdout': payload['stdout'],
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
                               'cuckoo-app-uploads',
                               'private/%s/%s' % (identity_id, filename))
    response = table.update_item(
        Key={
            'userId': payload['userId'],
            'jobId': payload['jobId'],
        },
        UpdateExpression=("SET dateModified = :dateModified, "
                          + "jobStatus = :jobStatus, runtime = :runtime, "
                          + "stdout = :stdout"),
        ExpressionAttributeValues={
          ':dateModified': payload['dateModified'],
          ':jobStatus': payload['jobStatus'],
          ':runtime': payload['runtime'],
          ':stdout': payload['stdout'],
        },
        ReturnValues="ALL_NEW"
    )
    pprint(payload)

    try:
        subprocess.call(['rm', filename])
    except Exception as e:
        raise e
