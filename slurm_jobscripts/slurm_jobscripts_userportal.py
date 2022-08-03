import requests
import configparser
import os
import time

# This is script is taking the submited script on the slurmctld server
# and send it to the userportal so it can be stored in a database


def send_job(jobid):
    try:
        with open('/var/spool/slurmctld/hash.{mod}/job.{jobid}/script'.format(mod=jobid % 10, jobid=jobid),
                  'r') as f:
            content = f.read()[:script_length].strip('\x00')
            requests.post('{}/api/jobscripts/'.format(host),
                          json={'id_job': int(jobid), 'submit_script': content},
                          headers={'Authorization': 'Token ' + token})

    except UnicodeDecodeError:
        # Ignore problems with wrond file encoding
        pass
    except FileNotFoundError:
        # The script disappeared before we could read it
        pass


config = configparser.ConfigParser()
config.read('/root/api_config.ini')
token = config['api']['token']
host = config['api']['host']
script_length = int(config['api']['script_length'])

jobs = set()

while True:
    updated_jobs = set()
    for mod in range(10):
        listing = os.listdir('/var/spool/slurmctld/hash.{mod}'.format(mod=mod))
        for job in filter(lambda x: 'job' in x, listing):
            jobid = int(job[4:])
            updated_jobs.add(jobid)

            if jobid not in jobs:
                # This is a new job
                send_job(jobid)

    jobs = updated_jobs
    time.sleep(5)
