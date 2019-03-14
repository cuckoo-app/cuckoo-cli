import requests
from requests.auth import HTTPBasicAuth
from pprint import pprint

r = requests.get('http://127.0.0.1:8000/api/jobs/',
                 auth=HTTPBasicAuth('bryan', 'password'))
pprint(r.json())


# payload = {'command': 'python count.py', 'status': 'RU'}
# post = requests.post('http://127.0.0.1:8000/api/jobs/',
#                      data=payload,
#                      auth=HTTPBasicAuth('bryan', 'password'))
# pprint(post.json())


payload = {'command': 'python count.py', 'status': 'SU'}
post = requests.put('http://127.0.0.1:8000/api/jobs/by-job/4',
                    data=payload,
                    auth=HTTPBasicAuth('bryan', 'password'))
pprint(post.json())
