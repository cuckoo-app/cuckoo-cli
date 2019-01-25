import sys
import time
from datetime import datetime
import dateutil.parser
import json
from requests.auth import HTTPBasicAuth
from pprint import pprint
import psutil
import subprocess
import os

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

    my_env = os.environ.copy()
    my_env['PYTHONUNBUFFERED'] = '1'
    p = psutil.Popen(command.split(),
                     env=my_env,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT,
                     bufsize=1,
                     universal_newlines=True)
    print('PID:', p.pid)

    start_date = datetime.utcnow().isoformat()
    date_modified, runtime = get_current_times(start_date)
    payload = {
        'command': command,
        'status': 'running',
        'machine': machine,
        'dateCreated': start_date,
        'dateModified': date_modified,
        'runtime': runtime,
    }

    filename = 'test.txt'
    os.system('rm %s' % filename)

    buffer = ""
    start = time.time()
    for line in p.stdout:
        if time.time() - start >= update_period:
            print('Buffered!', [buffer])
            f = open(filename, 'a+')
            f.write(buffer)
            f.close()
            buffer = ""
            start = time.time()
        sys.stdout.write(line)
        buffer += line
    print('Buffered!', [buffer])
    f = open(filename, 'a+')
    f.write(buffer)
    f.close()

    # while p.is_running():
    # while p.poll() is None:
    # for line in p.stdout:
    #     print(line, end='')
        # print('Still running!', p.poll())
        # payload['status'] = 'running'
        # date_modified, runtime = get_current_times(start_date)
        # payload['runtime'] = runtime
        # payload['dateModified'] = date_modified
        # pprint(payload)
        # time.sleep(update_period)
    # retcode = p.wait()
    # print('Exit code:', retcode)
    print('Exit code:', p.poll())

    payload['status'] = 'success'
    date_modified, runtime = get_current_times(start_date)
    payload['runtime'] = runtime
    payload['dateModified'] = date_modified
    pprint(payload)
