import subprocess
import sys
import time
import requests
import json
from requests.auth import HTTPBasicAuth
from pprint import pprint

if __name__ == '__main__':
    if len(sys.argv) == 3:
        command = sys.argv[1]
        update_period = int(sys.argv[2])
    else:
        command = 'python count.py'
        update_period = 2
    p = subprocess.Popen(command.split())
    print('PID:', p.pid)

    payload = {'command': command, 'status': 'RU'}
    r = requests.post('http://127.0.0.1:8000/api/jobs/',
                      data=payload,
                      auth=HTTPBasicAuth('bryan', 'password'))
    print(r)
    try:
        response = r.json()
    except json.JSONDecodeError as e:
        payload = {'command': command, 'status': 'ER'}
        r = requests.post('http://127.0.0.1:8000/api/jobs/',
                          data=payload,
                          auth=HTTPBasicAuth('bryan', 'password'))
        raise e
    pprint(response)
    job_id = response['id']

    while p.poll() is None:
        print('Still running!', p.poll())
        payload = {'command': command, 'status': 'RU'}
        r = requests.put('http://127.0.0.1:8000/api/jobs/%s' % job_id,
                            data=payload,
                            auth=HTTPBasicAuth('bryan', 'password'))
        response = r.json()
        pprint(response)
        time.sleep(update_period)
    # retcode = p.wait()
    # print('Exit code:', retcode)
    print('Exit code:', p.poll())
    print('Still running!', p.poll())
    payload = {'command': command, 'status': 'SU'}
    r = requests.put('http://127.0.0.1:8000/api/jobs/%s' % job_id,
                        data=payload,
                        auth=HTTPBasicAuth('bryan', 'password'))
    response = r.json()
    pprint(response)
