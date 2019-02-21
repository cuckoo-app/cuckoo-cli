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
import json
import getpass

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

def send_email(command,
    job_status,
    machine,
    date_modified,
    runtime,
    aws_access_key_id,
    aws_secret_access_key,
    aws_session_token):

    SENDER = "Cuckoo CL <bbrzycki@berkeley.edu>"
    RECIPIENT = "bbrzycki@berkeley.edu"
    REGION="us-east-1"
    # CONFIGURATION_SET = "ConfigSet"

    # The subject line for the email.
    SUBJECT = "Your job finished!"

    if job_status == 'success':
        SUBJECT = 'Your job finished successfully!'

        summary = "Your job '%s' completed at %s (UTC) on machine '%s' with no errors." % (command, date_modified, machine)
        body = "The job's total runtime was %s (hh:mm:ss)." % (runtime)

        html_summary = "Your job <strong>%s</strong> completed at <strong>%s</strong> (UTC) on machine <strong>%s</strong> with no errors." % (command, date_modified, machine)
        html_body = "The job's total runtime was <strong>%s</strong> (hh:mm:ss)." % (runtime)
    elif job_status == 'error':
        SUBJECT = 'Your job exited with an error'

        summary = "Your job '%s' exited at %s (UTC) on machine '%s' with an error." % (command, date_modified, machine)
        body = "The job's total runtime was %s (hh:mm:ss)." % (runtime)

        html_summary = "Your job <strong>%s</strong> exited at <strong>%s</strong> (UTC) on machine <strong>%s</strong> with an error." % (command, date_modified, machine)
        html_body = "The job's total runtime was <strong>%s</strong> (hh:mm:ss)." % (runtime)
    else:
        sys.exit('Invalid status: %s' % job_status)

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = ("%s\r\n"
                 "%s\r\n"
                 "Cuckoo CL"
                ) % (summary, body)

    # The HTML body of the email.
    BODY_HTML = """<html>
    <head></head>
    <body>
      <p>%s</p>
      <p>%s</p>
      <p>Cuckoo CL</p>
    </body>
    </html>
                """ % (html_summary, html_body)

    # The character encoding for the email.
    CHARSET = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses',
        region_name=REGION,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token)

    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
            # If you are not using a configuration set, comment or delete the
            # following line
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])


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


    # Set up access to AWS resources
    dynamodb = boto3.resource('dynamodb',
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token)
    table = dynamodb.Table('%s-jobs' % stage)

    s3 = boto3.resource('s3',
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token)

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
            date_modified, runtime = get_current_times(start_date)
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

    send_email(command=payload['command'],
        job_status=payload['jobStatus'],
        machine=payload['machine'],
        date_modified=payload['dateModified'],
        runtime=payload['runtime'],
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token)
