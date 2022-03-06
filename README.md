## Learn@VCS Tasks Integrator

***Automatically fetch assignments from learn@vcs and add them to Google Tasks***

### Usage Notes

**Do use virtualenv when running the script.**

```text
usage: main.py [-h] [--debug] [--daystart DAYSTART] --username USERNAME --password PASSWORD [--listname LISTNAME]

Integrates learn@vcs with Google Tasks

options:
  -h, --help           show this help message and exit
  --debug
  --daystart DAYSTART  The day to start on 'Day.A' or 'Day.B', this will only take effect when --ab is present
  --username USERNAME  learn@VCS username
  --password PASSWORD  learn@VCS password
  --listname LISTNAME  The name of the tasklist to add assignments to
```
