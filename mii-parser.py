import subprocess
import argparse

# Parse the command line arguments
parser = argparse.ArgumentParser(description='Convert mii output to regex')
parser.add_argument('-d', '--duplicates', action='store_true', help='show duplicates')
parser.add_argument('-p', '--pretty', action='store_true', help='pretty print')
parser.add_argument('-o', '--output', action='store_true', help='print output for the config file')
args = parser.parse_args()

# Run the CLI command and capture the output
output = subprocess.check_output(["mii", "list"], universal_newlines=True)

softwares = {'python': set(), 'R': set()}

for line in output.splitlines():
    try:
        soft_version = line.strip().split('/')
        software = soft_version[0]
        version = soft_version[1]
    except IndexError:
        continue

    show = subprocess.check_output(["mii", "show", line], universal_newlines=True)
    if 'empty result set' in show:
        continue

    # rename and group some softwares
    if software in ['python3', 'python2', 'python-build-bundle', 'pip']:
        software = 'python'
    if software in ['rstudio-server']:
        software = 'R'
    if software in ['namd-ofi', 'namd-ucx', 'namd-multicore', 'namd-ucx-smp', 'namd-ofi-smp']:
        software = 'namd'
    if software in ['starccm-mixed']:
        software = 'starccm'
    if software in ['gromacs-plumed', 'gromacs-cp2k', 'gromacs-ramd', 'gromacs-colvars']:
        software = 'gromacs'
    if software in ['petsc-pardiso-64bits', 'petsc-pardiso', 'petsc-64bits']:
        software = 'petsc'
    if software in ['vtk-mpi']:
        software = 'vtk'
    if software in ['hdf-fortran']:
        software = 'hdf'
    if software in ['blast+', 'rmblast']:
        software = 'blast'
    if software in ['fftw-mpi']:
        software = 'fftw'
    if software in ['meryl-lookup', 'meryl-import']:
        software = 'meryl'
    if software in ['paraview-offscreen-gpu', 'paraview-offscreen']:
        software = 'paraview'
    if software in ['openbabel-omp']:
        software = 'openbabel'
    if software in ['geant4-seq', 'geant4-topasmc3.9']:
        software = 'geant4'
    if software in ['hdf5-mpi']:
        software = 'hdf5'
    if software in ['netcdf-mpi']:
        software = 'netcdf'
    if software in ['phylobayes-mpi']:
        software = 'phylobayes'
    if software in ['ansysedt']:
        software = 'ansys'
    if software in ['hpcspades']:
        software = 'spades'
    if software in ['ambertools']:
        software = 'amber'
    if software in ['cudacore', 'nvhpc']:
        software = 'cuda'
    if software in ['mysql', 'mariadb']:
        software = 'mysql'
    if software in ['perl-no-thread']:
        software = 'perl'
    if software in ['wrf-co2', 'wrf-cmaq']:
        software = 'wrf'
    if software in ['scotch-no-thread']:
        software = 'scotch'
    if software in ['cfour-mpi']:
        software = 'cfour'
    if software in ['chapel-multicore', 'chapel-ucx', 'chapel-ofi']:
        software = 'chapel'
    if software in ['metis-64idx']:
        software = 'metis'
    if software in ['raxml-pthreads']:
        software = 'raxml'
    if software in ['mafft-mpi']:
        software = 'mafft'
    if software in ['flexiblascore']:
        software = 'flexiblas'
    if software in ['ls-dyna-mpi']:
        software = 'ls-dyna'

    if software not in softwares:
        softwares[software] = set()  # set of binaries

    for binary in show.splitlines()[1:]:
        binary = binary.strip()
        if binary.startswith('f2py'):
            continue
        if 'python' in binary or binary.startswith('pip') or binary.startswith('easy_install'):
            software = 'python'
        if binary == 'Rscript' or binary == 'R':
            software = 'R'
        softwares[software].add(binary)

    if software in ['openmpi', 'intelmpi', 'dpc++', 'clang', 'llvm', 'intel', 'intelmpi', 'libfabric', 'gcccore']:
        del softwares[software]
    # ignore some softwares that seems to repackage the whole world or have too many binaries
    if software in ['afni', 'ansys', 'masurca', 'minc-toolkit']:
        del softwares[software]

if args.pretty:
    for software in sorted(softwares.keys()):
        print(software + ":")
        for binary in sorted(softwares[software]):
            print("  " + binary)
        print()

if args.duplicates:
    duplicates = {}
    for software in softwares:
        binaries = softwares[software]
        for binary in binaries:
            if binary not in duplicates:
                duplicates[binary] = set()
            duplicates[binary].add(software)
    print("Duplicates:")
    for binary in duplicates:
        if len(duplicates[binary]) > 1:
            print(binary + ":")
            for software in duplicates[binary]:
                print("  " + software)
            print()

if args.output:
    for software in sorted(softwares.keys(), key=lambda x: len(softwares[x])):
        if len(softwares[software]) == 0:
            continue
        # add quotes on each binary
        softwares[software] = ['"' + binary + '"' for binary in softwares[software]]
        print("    ('{software}', [{bins}]),".format(
            software=software,
            bins=','.join(sorted(softwares[software]))))
