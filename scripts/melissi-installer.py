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
    'mysql':'PyMySQL',
    'postgresql':'psycopg2',
    'librsync':'-e git://github.com/melissiproject/librsync.git#egg=librsync',
    'django-piston':'-e git://github.com/django-piston/django-piston.git#egg=django-piston',
    }


def _install(pkg):
    # execute command,
    # silence output export only errors to install.log
    COMMAND = "pip -E env install %s"
    status, output = commands.getstatusoutput(COMMAND % pkg)

    _printer(output, fileonly=True)

    if status != 0:
        sys.exit("Failed while installing %s "
                 "Checking %s for details" % (pkg, LOGFILE)
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

    # restart script with --install
    os.execv(sys.argv[0], (sys.argv[0], "--install",))

def install(mysql=False, postgresql=False):
    _printer("Installing Packages: ")

    basic_packages = ('django', 'south', 'django-mptt',
                      'django-extensions', 'librsync',
                      'django-piston')

    for pkg in basic_packages:
        _printer("%s, " % pkg)
        _install(PACKAGES[pkg])

    if mysql:
        _printer("mysql, ")
        _install(PACKAGES['mysql'])

    if postgresql:
        _printer("postgresql, ")
        _install(PACKAGES['postgresql'])

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

    (options, _) = parser.parse_args()

    if (options.install and options.upgrade):
        sys.exit("You can't use both --install and --upgrade options. "
                 "Use --help for instructions")

    if (not options.install and not options.upgrade):
        sys.exit("You must you at least --install or --upgrade. "
                 "Use --help for instructions")

    if options.upgrade:
        if (options.mysql or options.postgresql):
            sys.exit("--upgrade can't be combined with other options")

        else:
          upgrade()

    elif options.install:
        install(mysql=options.mysql, postgresql=options.postgresql)

if __name__ == "__main__":
    main()
