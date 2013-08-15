py_zarafa_pst_importer
======================

Features
--------

* Import emails
* Import calendars

Requires
--------

Python Modules:

    pip install requests
    pip install icalendar
    pip install vobject

Other:

    apt-get install readpst

Setup
-----

1. Download import.pst.py
2. Create directory called: pst
3. Rename pst files the same as the Zarafa user
4. Copy pst files into directory "pst"

Options
-------

    --noemails  don't import emails
    --nocalendars  don't import calendars

Tested only with Outlook 2010 pst files and Zarafa 7.1.4
