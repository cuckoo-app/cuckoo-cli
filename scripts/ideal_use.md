### CLI

If no config file in ~/.cuckoo:

```
$ cuckoo
Please login:
Login: user
Password: ********
```

If incorrect credentials provided:

```
$ cuckoo
Incorrect credentials provided -- please login in:
Login: user
Password: ********
```


With successful credentials, should give:

```
$ cuckoo
Usage: cuckoo [command] [args]
```

Normal usage would just be

```
$ cuckoo "echo 'Hello, world!'"
```

### In script or Jupyter notebooks

To import:

```
import cuckoo
```

This would require setting up the ~/.cuckoo directory; you can do this at the command line by simply running `cuckoo`. There is no inline login option because this is inherently insecure to place your login credentials inside your scripts.

To initialize a clock:

```
cuckoo_clock = cuckoo.Clock()
```

To notify or track:

```
job_id = cuckoo_clock.job_start()
.
.
cuckoo_clock.notify(job_id, method='email')
.
.
cuckoo_clock.job_end(job_id)
```
