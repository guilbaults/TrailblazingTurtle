import requests
import configparser
import os
import time

# This is script is taking the submited script once it start on a compute
# node and send it to the userportal so it can be stored in a database


def send_job(jobid):
    with open('/var/spool/slurmd/job{}/slurm_script'.format(jobid),
              'r') as f:
        content = f.read()[:script_length]

    requests.post('{}/api/jobscripts/'.format(host),
                  json={'id_job': int(jobid), 'submit_script': content},
                  headers={'Authorization': 'Token ' + token})


config = configparser.ConfigParser()
config.read('/root/api_config.ini')
token = config['api']['token']
host = config['api']['host']
script_length = int(config['api']['script_length'])

jobs = set()

while True:
    listing = os.listdir('/var/spool/slurmd/')
    updated_jobs = set()
    for job in filter(lambda x: 'job' in x, listing):
        jobid = int(job[3:])
        updated_jobs.add(jobid)

        if jobid not in jobs:
            # This is a new job
            send_job(jobid)

    jobs = updated_jobs
    time.sleep(5)
