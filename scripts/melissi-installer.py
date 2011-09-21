#!/usr/bin/env python
#
# This is the melissi installer script
#
# Use me you install and upgrade melissi hives

import sys
import os
import commands
from optparse import OptionParser

LOGFILE = "install.log"
PACKAGES = {
    'django':'django',
    'south':'south',
    'django-mptt':'django-mptt',
    'django-extensions':'django_extensions',
    'mysql':'mysql-python',
    'postgresql':'psycopg2',
    'librsync':'-e git://github.com/melissiproject/librsync.git#egg=librsync',
    'gunicorn':'gunicorn',
    }
PIPCOMMAND = "pip-python" if os.path.exists("/usr/bin/pip-python") else "pip"

def _install(pkg):
    # execute command,
    # silence output export only errors to install.log
    COMMAND = "%s -E env install %s" % (PIPCOMMAND, "%s")
    status, output = commands.getstatusoutput(COMMAND % pkg)

    _printer(output, fileonly=True)

    if status != 0:
        sys.exit("Failed while installing %s. "
                 "Check %s for details" % (pkg, LOGFILE)
                 )

def _printer(text, newline=False, fileonly=False):
    if not fileonly:
        print text,

        if newline:
            print ""

    with open(LOGFILE, "a+") as f:
        f.write(text)
        if newline:
            f.write('\n')

    sys.stdout.flush()

def upgrade():
    # upgrade git
    _printer("Updating source")
    status, output = commands.getstatusoutput("git pull origin master")

    _printer(output, fileonly=True)

    if status != 0:
        sys.exit("Failed update source. "
                 "Check %s for details" % (LOGFILE))

def install(mysql=False, postgresql=False, gunicorn=False):
    _printer("Installing Packages: ")

    basic_packages = ('django', 'south', 'django-mptt',
                      'django-extensions', 'librsync',
                      )

    for pkg in basic_packages:
        _printer("%s, " % pkg)
        _install(PACKAGES[pkg])

    if mysql:
        _printer("mysql, ")
        _install(PACKAGES['mysql'])

    if postgresql:
        _printer("postgresql, ")
        _install(PACKAGES['postgresql'])

    if gunicorn:
        _printer("gunicorn, ")
        _install(PACKAGES['gunicorn'])

    _printer("", newline=True)
    _printer("Environment built successfully")

def main():
    parser = OptionParser()
    parser.add_option("-i", "--install",
                      help="Install your hive",
                      default=False,
                      action="store_true"
                      )
    parser.add_option("-u", "--upgrade",
                      help="Upgrade your hive",
                      action="store_true",
                      default=False,
                      )
    parser.add_option("--mysql",
                      help="Add MySQL backend",
                      action="store_true",
                      default=False,
                      )
    parser.add_option("--postgresql",
                      help="Add PostgreSQL backend",
                      action="store_true",
                      default=False,
                      )
    parser.add_option("--gunicorn",
                      help="Add gunicorn server",
                      action="store_true",
                      default=False,
                      )

    (options, _) = parser.parse_args()

    if (options.install and options.upgrade):
        sys.exit("You can't use both --install and --upgrade options. "
                 "Use --help for instructions")

    if (not options.install and not options.upgrade):
        sys.exit("You must you at least --install or --upgrade. "
                 "Use --help for instructions")

    if options.upgrade:
        if (options.mysql or options.postgresql or options.gunicorn):
            sys.exit("--upgrade can't be combined with other options")

        else:
          upgrade()

    elif options.install:
        install(mysql=options.mysql,
                postgresql=options.postgresql,
                gunicorn=options.gunicorn)

if __name__ == "__main__":
    main()
