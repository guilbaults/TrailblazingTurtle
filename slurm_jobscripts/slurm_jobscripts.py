import requests
import configparser
import os
import time
import argparse
import logging

# This is script is taking the submitted script on the slurmctld server
# and send it to the userportal so it can be stored in a database


def send_job(jobid):
    try:
        with open('{spool}/hash.{mod}/job.{jobid}/script'.format(
                spool=spool,
                mod=jobid % 10,
                jobid=jobid), 'r') as f:
            content = f.read()[:script_length].strip('\x00')
            logging.debug('Job script {}: {}'.format(jobid, content[:100]))  # Only log first 100 characters into DEBUG log
            r = requests.post('{}/api/jobscripts/'.format(host),
                              json={'id_job': int(jobid), 'submit_script': content},
                              headers={'Authorization': 'Token ' + token})
            if r.status_code != 201:
                if r.status_code == 401:
                    logging.error('Token is invalid')
                elif 'job script with this id job already exists' in r.text:
                    logging.debug('Job script already exists')
                else:
                    logging.error('Job script {} not saved: {}'.format(jobid, r.text))

    except UnicodeDecodeError:
        # Ignore problems with wrong file encoding
        pass
    except FileNotFoundError:
        # The script disappeared before we could read it
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config',
        help='Path to the config file (default: %(default)s)',
        type=str,
        default='/etc/slurm/slurm_jobscripts.ini')
    parser.add_argument('--verbose', help='Verbose output', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    config = configparser.ConfigParser()
    logging.debug('Reading config file: {}'.format(args.config))
    config.read(args.config)
    token = config['api']['token']
    host = config['api']['host']
    script_length = int(config['api']['script_length'])
    spool = config['slurm']['spool']

    jobs = set()

    while True:
        updated_jobs = set()
        for mod in range(10):
            try:
                listing = os.listdir('{spool}/hash.{mod}'.format(spool=spool, mod=mod))
            except FileNotFoundError:
                logging.debug('hash.{mod} does not exist yet'.format(mod=mod))
                continue
            for job in filter(lambda x: 'job' in x, listing):
                jobid = int(job[4:])  # parse the jobid (job.12345 -> 12345)
                updated_jobs.add(jobid)

                if jobid not in jobs:
                    logging.debug('New job: {}'.format(jobid))
                    send_job(jobid)

        jobs = updated_jobs
        time.sleep(5)
