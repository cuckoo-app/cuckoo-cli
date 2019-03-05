#!/usr/bin/env python3

import sys
import time
from pprint import pprint
import psutil
import subprocess
import os
import errno
import uuid

import argparse

import config

import auth
import aws_resources
import datetime_utils
import email_notifications
import track


def main():
    cuckoo_dir = '%s/.cuckoo' % os.path.expanduser('~')
    try:
        os.makedirs(cuckoo_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    # Key for storing stdout text to file
    stdout_key = '%s.txt' % str(uuid.uuid4())
    stdout_filename = '%s/%s' % (cuckoo_dir, stdout_key)

    command = sys.argv[1]
    stage = sys.argv[2]

    update_period = 2

    print('Connecting to server...')

    # Grab resource keys from config
    region = config.attr[stage]['region']
    user_pool_id = config.attr[stage]['user_pool_id']
    app_client_id = config.attr[stage]['app_client_id']
    identity_pool_id = config.attr[stage]['identity_pool_id']
    bucket_name = config.attr[stage]['bucket_name']

    # Handles login and gets aws access keys
    user_keys = auth.login(
         region=region,
         user_pool_id=user_pool_id,
         app_client_id=app_client_id,
         identity_pool_id=identity_pool_id
    )
    username = user_keys['username']
    machine = user_keys['machine']
    aws_access_keys = user_keys['aws_access_keys']
    identity_id = user_keys['identity_id']

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
        'stdout': stdout_key,
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
    f = open(stdout_filename, 'a+')
    f.write('$ %s\n' % (command))
    f.close()

    buffer = ""
    start = time.time()
    for line in p.stdout:
        if time.time() - start >= update_period:
            print('Buffered! (Not sent)', [buffer])
            f = open(stdout_filename, 'a+')
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
    f = open(stdout_filename, 'a+')
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
    s3.meta.client.upload_file(stdout_filename,
                               bucket_name,
                               'private/%s/%s' % (identity_id, stdout_key))
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
        subprocess.call(['rm', stdout_filename])
    except Exception as e:
        raise e

    ses_client = aws_resources.ses_client(
        aws_access_keys
    )
    email_notifications.send_completion_email(ses_client, payload)


if __name__ == '__main__':
    # Log in if user config isn't saved
    aws_credentials = auth.interactive_login(
        region=config.attr['dev']['region'],
        user_pool_id=config.attr['dev']['user_pool_id'],
        app_client_id=config.attr['dev']['app_client_id'],
        identity_pool_id=config.attr['dev']['identity_pool_id']
    )

    parser = argparse.ArgumentParser(description='Track completion of your jobs!')
    parser.add_argument(
        '-c',
        '--command',
        '-n',
        '--new',
        nargs='+',
        help='Full command to track',
    )
    # May potentially support multiple processes
    parser.add_argument(
        '-a',
        '--attach',
        '-e',
        '--existing',
        nargs=1,
        type=int,
        help='PID of existing job to track',
    )

    args = parser.parse_args()

    if args.command and args.attach:
        parser.error('Please specify only one command or process to track.')
    elif args.command is None and args.attach is None:
        pass
    elif args.command:
        joined_command = ' '.join(args.command)
        print(joined_command)
        track.track_new(joined_command, aws_credentials)
    elif args.attach:
        print(args.attach)
        track.track_existing(args.attach, aws_credentials)
    else:
        parser.error('Something went wrong!')
