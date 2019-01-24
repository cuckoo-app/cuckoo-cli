import subprocess
import sys
import time
from datetime import datetime
import dateutil.parser
import json
from requests.auth import HTTPBasicAuth
from pprint import pprint
import psutil


# def findProcessIdByName(processName):
#     '''
#     Get a list of all the PIDs of a all the running process whose name contains
#     the given string processName
#     '''
#
#     listOfProcessObjects = []
#
#     #Iterate over the all the running process
#     for proc in psutil.process_iter():
#         try:
#             pinfo = proc.as_dict(attrs=['pid', 'name', 'create_time'])
#             # Check if process name contains the given name string.
#             if processName.lower() in pinfo['name'].lower():
#                 listOfProcessObjects.append(pinfo)
#         except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
#             pass
#
#     return listOfProcessObjects

# def findProcessIdByName(pid):
#     '''
#     Get the process with matching pid
#     '''
#
#     #Iterate over the all the running process
#     for proc in psutil.process_iter():
#         try:
#             pinfo = proc.as_dict(attrs=['pid', 'name', 'create_time', 'cmdline', 'status'])
#             # pinfo = proc.as_dict()
#             # Check if process name contains the given name string.
#             if int(pid) == int(pinfo['pid']):
#                 return pinfo
#         except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
#             pass
#
#     return -1

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
        update_period = int(sys.argv[2])
    pid = int(sys.argv[1])

    update_period = 2
    machine = 'My Macbook Pro'

    p = psutil.Process(pid)
    pprint(p)
    print('PID:', p.pid)
    print(p.name(), p.create_time())

    start_date = datetime.utcfromtimestamp(p.create_time()).isoformat()

    date_modified, runtime = get_current_times(start_date)
    payload = {
        'command': ' '.join(p.cmdline()),
        'status': 'running',
        'machine': machine,
        'dateCreated': start_date,
        'dateModified': date_modified,
        'runtime': runtime,
    }

    while p.is_running():
        print('Still running!')
        payload['status'] = 'running'
        date_modified, runtime = get_current_times(start_date)
        payload['runtime'] = runtime
        payload['dateModified'] = date_modified
        pprint(payload)
        time.sleep(update_period)
    # retcode = p.wait()
    # print('Exit code:', retcode)
    # print('Exit code:', p.poll())

    payload['status'] = 'success'
    date_modified, runtime = get_current_times(start_date)
    payload['runtime'] = runtime
    payload['dateModified'] = date_modified
    pprint(payload)
