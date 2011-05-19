#!/bin/sh

pip -E env install -r deps.pip
pip -E env install -e git://github.com/melissiproject/librsync.git#egg=librsync
pip -E env install -e git://github.com/melissiproject/mongoengine.git#egg=mongoengine
pip -E env install -e git://github.com/melissiproject/django-piston.git#egg=django-piston

echo "You can now activate your environment by typing:"
echo "~$ source env/bin/activate"
echo "Enviroment build complete."
