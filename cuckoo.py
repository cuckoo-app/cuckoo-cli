import subprocess
import time

command = ['python', 'count.py']
p = subprocess.Popen(command)
print('PID:', p.pid)
while p.poll() is None:
    print('Still running!', p.poll())
    time.sleep(2)
# retcode = p.wait()
# print('Exit code:', retcode)
print(p.poll())
