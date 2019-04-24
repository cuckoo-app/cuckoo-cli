import sys
import time
from pprint import pprint
import psutil
import subprocess
import os
import uuid

try:
    from . import config
    from . import auth
    from . import aws_resources
    from . import datetime_utils
    from . import email_notifications
except ImportError:
    import config
    import auth
    import aws_resources
    import datetime_utils
    import email_notifications


CUCKOO_DIR = config.cuckoo_dir
# USER_CONFIG = config.user_config_fn
STAGE = config.stage


def track_new(command,
              aws_credentials,
              store_stdout=False,
              save_filename=None,
              store_db=False,
              send_email=False,
              verbose=False):
    # Key for storing stdout text to file
    if save_filename or store_stdout:
        stdout_key = '%s.txt' % str(uuid.uuid4())
        stdout_filename = '%s/%s' % (CUCKOO_DIR, stdout_key)
    else:
        stdout_key = None

    update_period = 2

    # Set up access to AWS resources
    aws_access_keys = aws_credentials['aws_access_keys']
    if store_db:
        dynamodb = aws_resources.dynamodb_resource(
            aws_access_keys
        )
        table = dynamodb.Table('%s-jobs' % STAGE)

    if store_stdout:
        s3 = aws_resources.s3_resource(
            aws_access_keys
        )

    job_id = str(uuid.uuid4())
    start_date = datetime_utils.get_start_date()
    date_modified, runtime, _ = datetime_utils.get_current_times(start_date)
    payload = {
        'userId': aws_credentials['identity_id'],
        'jobId': job_id,
        'command': command,
        'jobStatus': 'running',
        'machine': aws_credentials['machine'],
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
    print('Subprocess PID: %s\n' % p.pid)

    # Send initial information to database and create stdout file
    if store_db:
        response = table.put_item(
            Item=payload
        )
    if verbose:
        pprint(payload)
    if save_filename or store_stdout:
        f = open(stdout_filename, 'a+')
        f.write('$ %s\n' % (command))
        f.close()

    buffer = ""
    start = time.time()
    for line in p.stdout:
        if time.time() - start >= update_period:
            if verbose:
                print('Buffered! (Not sent)', [buffer])
            if save_filename or store_stdout:
                f = open(stdout_filename, 'a+')
                f.write(buffer)
                f.close()

            payload['jobStatus'] = 'running'
            date_modified, runtime, _ = datetime_utils.get_current_times(start_date)
            payload['runtime'] = runtime
            payload['dateModified'] = date_modified
            if verbose:
                pprint(payload)

            buffer = ""
            start = time.time()
        sys.stdout.write(line)
        buffer += line
    if verbose:
        print('Buffered!', [buffer])
    if save_filename or store_stdout:
        f = open(stdout_filename, 'a+')
        f.write(buffer)
        f.close()

    if verbose:
        print('Exit code:', p.poll())

    if p.returncode == 0:
        payload['jobStatus'] = 'success'
    else:
        payload['jobStatus'] = 'error'
    date_modified, runtime, runtime_s = datetime_utils.get_current_times(start_date)

    print('')
    if runtime_s < 60:
        sys.exit('Job exited in less than a minute -- no need to track!')

    # Make sure credentials are still valid
    aws_credentials = auth.login()

    payload['runtime'] = runtime
    payload['dateModified'] = date_modified
    if store_stdout:
        s3.meta.client.upload_file(
            stdout_filename,
            aws_credentials['bucket_name'],
            'private/%s/%s' % (aws_credentials['identity_id'], stdout_key)
        )
    if store_db:
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
    if verbose:
        pprint(payload)

    if save_filename or store_stdout:
        if save_filename:
            subprocess.call(['cp', stdout_filename, save_filename])
        try:
            subprocess.call(['rm', stdout_filename])
        except Exception as e:
            raise e

    if send_email:
        ses_client = aws_resources.ses_client(
            aws_access_keys
        )
        email_notifications.send_completion_email(ses_client, payload)


def track_existing(pid,
                   aws_credentials,
                   store_db=False,
                   send_email=False,
                   verbose=False):
    # Does not support stdout tracking
    stdout_key = None
    update_period = 2

    # Set up access to AWS resources
    aws_access_keys = aws_credentials['aws_access_keys']
    if store_db:
        dynamodb = aws_resources.dynamodb_resource(
            aws_access_keys
        )
        table = dynamodb.Table('%s-jobs' % STAGE)

    # Create process based on PID and grab relevant information
    p = psutil.Process(pid)
    job_id = str(uuid.uuid4())
    command = ' '.join(p.cmdline())
    start_date = datetime_utils.get_start_date(p.create_time())
    date_modified, runtime, _ = datetime_utils.get_current_times(start_date)
    payload = {
        'userId': aws_credentials['identity_id'],
        'jobId': job_id,
        'command': command,
        'jobStatus': 'running',
        'machine': aws_credentials['machine'],
        'dateCreated': start_date,
        'dateModified': date_modified,
        'runtime': runtime,
        'stdout': stdout_key,
        'unread': True,
    }

    # Send initial information to database and create stdout file
    if store_db:
        response = table.put_item(
            Item=payload
        )
    if verbose:
        pprint(payload)

    start = time.time()
    while p.is_running():
        if time.time() - start >= update_period:
            payload['jobStatus'] = 'running'
            date_modified, runtime, _ = datetime_utils.get_current_times(start_date)
            payload['runtime'] = runtime
            payload['dateModified'] = date_modified
            if verbose:
                pprint(payload)

            start = time.time()

    payload['jobStatus'] = 'finished'

    date_modified, runtime, runtime_s = datetime_utils.get_current_times(start_date)

    print('')
    if runtime_s < 60:
        sys.exit('Job exited in less than a minute -- no need to track!')

    # Make sure credentials are still valid
    aws_credentials = auth.login()

    payload['runtime'] = runtime
    payload['dateModified'] = date_modified
    if store_db:
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
    if verbose:
        pprint(payload)

    if send_email:
        ses_client = aws_resources.ses_client(
            aws_access_keys
        )
        email_notifications.send_completion_email(ses_client, payload)
