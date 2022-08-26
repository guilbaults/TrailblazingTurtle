import re
from django.utils.translation import gettext as _


class Comment(object):
    def __init__(self, comment, severity='info', url=None, line_number=0):
        self.comment = comment
        self.severity = severity
        self.url = url
        self.line_number = line_number

    def __repr__(self):
        return self.comment

    def display_severity(self):
        # For display with Bootstrap alert classes
        if self.severity == 'info':
            return 'list-group-item-info'
        elif self.severity == 'warning':
            return 'list-group-item-warning'
        elif self.severity == 'critical':
            return 'list-group-item-danger'
        else:
            return None


class Module(object):
    def __init__(self, module_str):
        self.name, self.version = module_str.split('/')

    def __repr__(self):
        return '{}/{}'.format(self.name, self.version)

    def __eq__(self, other):
        return self.name == other.name and self.version == other.version

    def __hash__(self):
        return hash((self.name, self.version))


def find_loaded_modules(jobscript):
    try:
        modules_str = []
        for line in jobscript.split('\n'):
            match = re.search(r'^\s*module load\s+(.*)$', line)
            if match:
                for module_str in match.group(1).split():
                    if module_str not in modules_str:
                        # only add unique modules, in order they are loaded
                        modules_str.append(module_str)
        modules = []
        for module_str in modules_str:
            modules.append(Module(module_str))
        return modules
    except: # noqa
        raise ValueError('Could not parse jobscript to find loaded modules')


def analyze_with_module_gromacs(jobscript, modules, job):
    comments = []
    tres = job.parse_tres_req()
    line_number = 0
    nodes_count = len(job.nodes())
    for line in jobscript.split('\n'):
        line_number += 1
        if tres['total_cores'] > 1:
            # handle binary names for both 4.x and 5.x
            match = re.search(r'^(.*)(gmx|gmx_mpi|gmx_d|gmx_d_mpi|mdrun_mpi|mdrun_mpi_d)\s+mdrun\s+(.*)$', line)
            if match:
                if 'srun' in match.group(1) or 'mpirun' in match.group(1) or 'mpiexec' in match.group(1):
                    # srun, mpirun, or mpiexec is used
                    pass
                else:
                    comments.append(Comment(
                        _('GROMACS is used without srun or mpirun/mpiexec'),
                        'warning',
                        'https://docs.alliancecan.ca/wiki/GROMACS#Whole_nodes',
                        line_number=line_number))
                nt_match = re.search(r'-nt\s+(\d+)', match.group(3))
                if nt_match:
                    if int(nt_match.group(1)) != tres['total_cores']:
                        comments.append(Comment(
                            _('GROMACS is used with -nt {} instead of -nt {}').format(nt_match.group(1), tres['total_cores']),
                            'critical',
                            'https://manual.gromacs.org/documentation/5.1/onlinehelp/gmx-mdrun.html#options',
                            line_number=line_number))
        if nodes_count > 1:
            match = re.search(r'^(.*)(gmx|gmx_d)\s+mdrun\s+(.*)$', line)
            if match:
                comments.append(Comment(
                    _('Multiple nodes are used without the MPI binary'),
                    'critical',
                    'https://docs.alliancecan.ca/wiki/GROMACS',
                    line_number=line_number))
        match_grompp = re.search(r'^(.*)(gmx|gmx_mpi|gmx_d|gmx_d_mpi|mdrun_mpi|mdrun_mpi_d)\s+grompp\s+(.*)$', line)
        if match_grompp:
            comments.append(Comment(
                _('GROMACS preprocessor should be used on a login node'),
                'warning',
                line_number=line_number))
    return comments


def analyze_with_module_amber(jobscript, modules, job):
    comments = []
    line_number = 0
    gpu_count = job.gpu_count()
    nodes_count = len(job.nodes())
    for line in jobscript.split('\n'):
        line_number += 1
        if gpu_count > 0:
            if 'pmemd.MPI' in line:
                comments.append(Comment(
                    _('CPU version of Amber is used on a GPU node'),
                    'critical',
                    'https://docs.alliancecan.ca/wiki/AMBER#Single_GPU_job',
                    line_number=line_number))
        else:
            if 'pmemd.cuda' in line:
                comments.append(Comment(
                    _('GPU version of Amber is used on a CPU node'),
                    'critical',
                    'https://docs.alliancecan.ca/wiki/AMBER#Single_CPU_job',
                    line_number=line_number))
        if nodes_count > 1:
            if 'pmemd' in line and 'srun' not in line:
                comments.append(Comment(
                    _('Multiple nodes are used in this job but AMBER is not started with srun'),
                    'critical',
                    'https://docs.alliancecan.ca/wiki/AMBER',
                    line_number=line_number))

    return comments


def analyze_with_module_lammps(jobscript, modules, job):
    comments = []
    line_number = 0
    tres = job.parse_tres_req()
    for line in jobscript.split('\n'):
        line_number += 1
        if tres['total_cores'] > 1:
            if 'lmp' in line and 'srun' not in line:
                comments.append(Comment(
                    _('LAMMPS is used without srun'),
                    'critical',
                    'https://docs.alliancecan.ca/wiki/LAMMPS#Example_of_input_file',
                    line_number=line_number))
    return comments


def analyze_bash(jobscript):
    comments = []
    line_number = 0
    for line in jobscript.split('\n'):
        line_number += 1
        if 'sleep' in line:
            comments.append(Comment(
                _('sleep command is used'), 'critical', None, line_number=line_number))
        if 'conda activate' in line:
            comments.append(Comment(
                _('conda environment is used'),
                'critical',
                'https://docs.alliancecan.ca/wiki/Anaconda',
                line_number=line_number))
    return comments


def analyze_jobscript(jobscript, modules, job):
    comments = []
    comments += analyze_bash(jobscript)
    for module in modules:
        if module.name == 'gromacs':
            comments += analyze_with_module_gromacs(jobscript, modules, job)
        if module.name == 'amber':
            comments += analyze_with_module_amber(jobscript, modules, job)
        if module.name == 'lammps-omp':
            comments += analyze_with_module_lammps(jobscript, modules, job)
    return comments
