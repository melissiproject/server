#!/bin/sh

pip -E env install -r deps.pip
pip -E env install -e git://github.com/melissiproject/librsync.git#egg=librsync
# pip -E env install -e git://github.com/melissiproject/mongoengine.git#egg=mongoengine
# pip -E env install -e git://github.com/melissiproject/django-piston.git#egg=django-piston

# pip -E env install -e git://github.com/mozilla/django-piston.git
pip install -e hg+https://bitbucket.org/jespern/django-piston/#egg=django-piston

echo "You can now activate your environment by typing:"
echo "~$ source env/bin/activate"
echo "Enviroment build complete."
