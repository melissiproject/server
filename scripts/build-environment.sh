#!/bin/sh

pip -E env install -r deps.pip
pip -E env install -e git://gitorious.org/melissi/librsync.git#egg=melissi-librsync
pip -E env install -e git://gitorious.org/melissi/django-mongopiston.git#egg=melissi-mongopiston
pip -E env install -e git://gitorious.org/melissi/mongoengine.git#egg=melissi-mongoengine

echo "You can now activate your environment by typing:"
echo "~$ source env/bin/activate"
echo "Enviroment build complete."
