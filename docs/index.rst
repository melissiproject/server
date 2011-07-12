.. Melissi Server documentation master file, created by
   sphinx-quickstart on Thu Jul  7 12:25:22 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Melissi Server's documentation!
==========================================

.. Contents:

.. .. toctree::
..    :maxdepth: 2

Installing
==========

To host your own melissi server (aka *Hive*)
--------------------------------------------

Melissi is a cloud storage server written in Django. Each server is
called a *Hive*.

Ultimattely the *hives* will be able to communicate with each other,
forming a *federated* network of cloud storage servers. You will have
control of your data and your infrastracture and still be able to
share files with others, even if they live in different hives.

If you want can host your own hive and be the master of you data and
your infrastracture, then this document is for you.

If you just want a place to store your data then you can use a hive
controlled by someone else. You can join a hive controlled by your
friends, your university or your company.


Things To Know
--------------

1. Melissi server is currently *alpha* software. Things may and will
change drastically, as the project evolves and matures.

2. You shouldn't trust melissi to backup your data. Melissi is a
storage platform not a backup platform.

3. If things go bad, or you get stuck feel free to ping us at
`@melissiproject <http://www.twitter.com/melissiproject>`_, or
#melissiproject on freenode.

4. Please fill `bug reports on github
<https://github.com/melissiproject/server/issues>`_, the more the bug
reports and better the software will be.


Preparing You System
--------------------

To install your own hive:

1. **Make sure you have a recent Python installed.**

   Most distributions come with python preinstalled, so probably you need
   to do nothing. Check if you have python using the following command

   ::

   ~$ python --version

2. **Install virtualenv and pip**

   Virtualenv creates a virtual python environment, in which we will
   install melissi and all its dependencies (e.g. Django). This way
   your melissi installation won't conflict with any other python
   projects / installs you may have on your server. PIP is a package
   manager for python.

   - For *Debian* systems

     ::

     ~$ sudo apt-get install python-pip python-virtualenv

   - For *Fedora* system

     ::

     ~$ su -c "yum install python-pip python-virtualenv"

3. **Install git**

   We use git to version our code. To get the latest melissi source
   code you need to install git.

   - For *Debian* systems

     ::

     ~$ sudo apt-get install git

   - For *Fedora* systems

     ::

     ~$ su -c "yum install git"

4. **Install librsync**

   To reduce bandwidth needs librsync is used for calculating
   patches. You need to install librsync development libraries to
   build python-librsync module.

   - For *Debian* systems

   ::

   ~$ sudo apt-get install librsync-dev

   - For *Fedora* systems

   ::

   ~$ su -c "yum install librsync-devel"

     .. _extra-packages:
4. **Installing Extra Packages** (Optional)

   Because we are building melissi inside a virtual enviroment you
   will need to download some extra packages to be able to compile
   some python modules, such as the MySQL-python

   - **Mysql on Debian Systems**

     Install python development files, needed to build python mysql
     connector.

       ::

       ~$ sudo apt-get install python-dev

     Install MySQL

       ::

       ~$ sudo apt-get install mysql-server libmysqlclient-dev

   - **PosteSQL on Debian Systems**

     Install python and postgresql development files, needed to build
     python postgresql connector.

       ::

       ~$ sudo apt-get install python-dev

     Install PostgreSQL

       ::

       ~$ sudo apt-get install postgresql libpg-dev

   - **Mysql on Fedora**

     Install python development files, needed to build python mysql
     connector.

       ::

       ~$ su -c "yum install python-devel"

     Install MySQL

       ::

       ~$ su -c "yum install mysql mysql-devel"

   - **PosteSQL on Fedora**

     Install python and postgresql development files, needed to build
     python postgresql connector.

       ::

       ~$ su -c "yum install python-devel"

     Install PostgreSQL

       ::

       ~$ su -c "yum install postgresql postgresql-devel"


Getting Melissi Source
----------------------

You can get the source from our git repository.

1. Move to the directory you want to install melissi

   ::

   ~$ mkdir /srv/melissi
   ~$ cd /srv/melissi

2. Fetch the source code

   ::

   ~$ git clone git://github.com/melissiproject/server.git


Installing Melissi
------------------

Move to the directory you cloned melissi server and run the
melissi-installer. Melissi installer will download from `pypi
<http://pypi.python.org>`_ all the needed python packages to run
melissi.

::

~$ cd /srv/melissi/server
~$ ./scripts/melissi-installer.py --install

 .. note::

    It is recomended that you use melissi with a good database
    backend like MySQL or PostgreSQL. Do install the needed support
    you can should use the --mysql and / or --postgresql flags among
    the --install flag.

    ::

    ~$ ./scripts/melissi-install.py --install --mysql

    If no flags are used then your hive will be able to run only
    using *sqlite*.

    .. warning::

       To install the mysql or postesql backends you need to execute
       the steps in section extra-packages_


Configuring Your Hive
---------------------

Before running your hive you need to configure at least the database
settings and the storage path. All configuration options are located
in file local_settings.py.

1. **Copy settings template**

  ::

  ~$ cp local_settings.py.example local_settings.py

2. **Edit using you favorite editor local_settings.py**

   - **Set DATABASES**

     This is the database to be used for melisi. You can refer to
     `Django's documentation on Databases
     <https://docs.djangoproject.com/en/dev/ref/settings/#databases>`_
     if you need more help.

   - **Set SECRET_KEY**

     A random secret key used as a seed in secret-key hashing
     algorithms. For more see `Django's documentation on SECRET_KEY
     <https://docs.djangoproject.com/en/dev/ref/settings/#secret-key>`_


   - **Set MELISSI_STORE_LOCATION**

     Point to a directory to store uploaded data to.

     .. note::

     	Since this directory is going to store the data from all user
     	of your hive make sure that you save enough storage for
     	everything.

   - **Set MELISSI_REGISTRATIONS_OPEN** (Default: False)

     Set either to *True* or *False* if you want or not other to be
     able to create accounts on your hive.

3. **Setup the database**

   ::

   ~$ source env/bin/activate

   ::

   (env)~$ python manage.py syncdb
   (env)~$ python manage.py migrate mlscommon


   .. warning::

      When executing *syncdb* answer **no** to the question whether to
      create a superuser or not, or the setup will fail.

4. **Setup a superuser**

   ::

   (env)~$ python manage.py createsuperuser

Running Your Hive
-----------------

Test Setup: Using internal webserver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can run your hive in *test* mode using django's internal webserver.

   ::

   (env)~$ python manage.py runserver

   .. note::

      Your hive listens by default on *localhost:8000*. To listen to
      another port or interface you can execute *runserver* command
      with extra parameters

      ::

         (env)~$ python manage.py runserver 0.0.0.0:8000

      bind to *all* available interfaces on port 8000


   .. warning::

      The communication between your hive and clients will not be
      encrypted.

   Now you can visit your administration interface at
   http://localhost:8000/admin/ and login using your superuser
   account.


Real Setup: Nginx and Gunicorn
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

   This section is incomplete

1. **gunicorn**

   ::

   ~$ cd /path/you/installed/melissi
   ~$ pip -E env install gunicorn

2. **nginx**

   1. **install**
   2. **setup**
   3. **ssl** (optional but recommended)


3. **Install supervisor**


Updating Your Hive
------------------

.. - updates using the installer
.. - database updates

1. Update the source

   ::

   ~$ cd /path/you/installed/melissi
   ~$ ./scripts/melissi-installer.py --upgrade

2. If first step completes without errors, when run the install
   script, to download  new packages

   ::

   ~$ ./scripts/melissi-install.py --install

3. Synchronize and migrate database

   ::

   ~$ source env/bin/activate

   ::

   (env)~$ cd melisi
   (env)~$ python manage.py syncdb
   (env)~$ python manage.py migrate mlscommon

4. Restart your server

Hive Administration
===================

Things To Know
--------------

Adding and Removing Users
--------------------------

You can use `Django's Admin <http://localhost:8000/admin>`_ with you
superuser account to add and remove users.


.. Indices and tables
.. ==================

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

