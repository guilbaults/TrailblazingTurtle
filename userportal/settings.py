import os.path
import glob

# From https://code.djangoproject.com/wiki/SplitSettings#UsingalistofconffilesTransifex
# Settings are loaded in alphabetical order from the settings directory
# *-local.py files are can be used to override settings, they are in .gitignore

conffiles = glob.glob(os.path.join(os.path.dirname(__file__), 'settings', '*.py'))
conffiles.sort()
for f_path in conffiles:
    with open(f_path) as f:
        code = compile(f.read(), f_path, 'exec')
        exec(code)
