#!/bin/bash
set -e

INSTALLDIR=/srv/melissi/
LOGFILE=$INSTALLDIR/logs/melissi.log
NUM_WORKERS=3
USER=melissi
GROUP=melissi
SOCKET="unix:$INSTALLDIR/sockets/$1"


if [ ! -d "$INSTALLDIR/logs" ]; then
    mkdir "$INSTALLDIR/logs"
fi

if [ ! -d "$INSTALLDIR/sockets/" ]; then
    mkdir "$INSTALLDIR/sockets/"
fi

cd $INSTALLDIR/server/melisi/
source ../env/bin/activate
exec ../env/bin/gunicorn_django -w $NUM_WORKERS --user=$USER --group=$GROUP --log-level=info --log-file=$LOGFILE --bind $SOCKET 2>> $LOGFILE settings.py
