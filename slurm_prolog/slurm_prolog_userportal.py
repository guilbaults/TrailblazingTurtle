import requests
import configparser
import os
import sys

# This is script is taking the submited script once it start on a compute
# node  and send it to the userportal so it can be stored in a database

config = configparser.ConfigParser()
config.read('api_config.ini')
token = config['api']['token']
host = config['api']['host']
script_length = int(config['api']['script_length'])
jobid = os.environ.get('SLURM_JOB_ID')
if jobid is None:
    print('SLURM_JOB_ID is not defined')
    sys.exit(1)

try:
    with open('/var/spool/slurmd/job{}/slurm_script'.format(jobid),
              'r') as f:
        content = f.read()[:script_length]
except FileNotFoundError:
    print('Submit script not found')
    sys.exit(2)

r = requests.post('{}/api/jobscripts/'.format(host),
                  json={'id_job': int(jobid), 'submit_script': content},
                  headers={'Authorization': 'Token ' + token})
