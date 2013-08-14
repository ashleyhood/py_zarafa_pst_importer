#!/usr/bin/python

import os
import sys
import argparse
import subprocess
import re
import fnmatch
import datetime
import getpass
import requests

from icalendar import Calendar, Event, Timezone

VERSION = "1.0"
DEBUG = False
DRYRUN = False
EMAILS = True
CALENDARS = True
CONTACTS = True
OUR_TIMEZONE = 'Europe/London'

working_dir = os.path.dirname(os.path.abspath(__file__))
import_dir = os.path.join(working_dir, "pst")
converted_dir = os.path.join(working_dir, "converted")

def get_files(backup_dirs, include_files=[]):
        import_files = []
        include_files = r'|'.join([fnmatch.translate(x) for x in include_files]) or r'$.'

        for backup_dir in backup_dirs:
            for root, dirs, files in os.walk(backup_dir):
                for fname in files:
                    # include files
                    if re.search(include_files, fname):
                        fname = os.path.join(root, fname)
                        if not os.path.islink(fname):
                            import_files.append(fname)
        return import_files

def import_emails(user_dir, username):
    folder_display = None
    emails = get_files([user_dir], ['.eml'])
    #print "Importing emails"
    for email in emails:
        folder = os.path.relpath(email, user_dir)
        folder = folder.split('/')
        folder.pop(0)
        folder = os.path.normpath('/'.join(folder))
        folder = os.path.split(folder)[0]
        
        zarafadagent = ["zarafa-dagent", "-p", "/", "-C", "-F", folder, "-f", email, username]
        if not DRYRUN:
            try:
                email_output = subprocess.check_output(zarafadagent)
            except subprocess.CalledProcessError as e:
                print email_output
                print "Failed to import {}".format(email)
        if folder_display != folder:
            print "Imported {}".format(folder)
            folder_display = folder

def import_calendars(user_dir, username, zadmin, zadmin_password):
    IGNORE_DUPLICATE = True
    
    url = "https://127.0.0.1:8443/ical/"+username
    merged_ical = os.path.join(user_dir, 'merged.ics')
    now = datetime.datetime.now()
    icals = get_files([user_dir], ['.ics'])
    
    # do nothing if no ics files found
    if not icals:
        return
    
    # this set will be used fo find duplicate events
    eventSet = set()
    if DEBUG:
        if IGNORE_DUPLICATE:
            print 'ignore duplicated events'
    
    # Open the new calendarfile and adding the information about this script to it
    newcal = Calendar()
    newcal.add('prodid', '-//opensaucesystems.com//')
    newcal.add('version', '2.0')
    newcal.add('x-wr-calname', 'Default')
    if DEBUG:
        print 'new calendar ' + merged_ical + ' started'
    
    # we need to add a timezone, because some clients want it (e.g. sunbird 0.5)
    newtimezone = Timezone()
    newtimezone.add('tzid', OUR_TIMEZONE)
    newcal.add_component(newtimezone)
    
    # Looping through the existing calendarfiles
    for ical in icals:
        try:
            # open the file and read it
            with open(ical,'rb') as calfile:
                cal = Calendar.from_ical(calfile.read())
                if DEBUG:
                    print 'reading file ' + ical
                # every part of the file...
                for component in cal.subcomponents:
                    # ...which name is VEVENT will be added to the new file
                    if component.name == 'VEVENT':
                        try:
                            if IGNORE_DUPLICATE:
                                eventId = str(component['dtstart']) + ' | ' + str(component['dtend']) + ' | ' + str(component['summary'])
                                if eventId not in eventSet:
                                    eventSet.add(eventId)
                                else:
                                    if DEBUG:
                                        print 'skipped duplicated event: ' + eventId
                                    continue
                        except:
                            # ignore events with missing dtstart, dtend or summary
                            if DEBUG:
                                print '! skipped an event with missing dtstart, dtend or summary. likely historic or duplicated event.'
                            continue
                        newcal.add_component(component)
        except:
            # if the file was not readable, we need a errormessage ;)
            print 'Merge iCals: Error: reading file:', sys.exc_info()[1]
            print ical
    
    # After the loop, we have all of our data and can write the file now
    try:
        with open(merged_ical, 'wb') as f:
            f.write(newcal.to_ical())
        if DEBUG:
            print 'new calendar written'
    except:
        print 'Merge iCals: Error: ', sys.exc_info()[1]
    
    s = requests.Session()
    s.auth = (zadmin, zadmin_password)
    
    try:
        #print "Importing Calendar"
        with open(merged_ical, 'rb') as f:
            r = s.put(url, verify=False, data=f)
        
        if r.status_code == 200:
            print "Successfully imported calendar"
        else:
            print "Failed to import calendar"
    except:
        print "Failed to connect with server"

def import_contacts():
    print "No contacts will be imported. Need to code this"

def start_import_pst():
    # Get Zarafa admin username and password
    zadmin = raw_input('Enter Zarafa admin username: ')
    zadmin_password = getpass.getpass()
    
    try:
        os.mkdir(converted_dir)
        if DEBUG:
            print "Created directory: ", converted_dir
    except:
        if DEBUG:
            print "The directory already exists: ", converted_dir

    files = [f for f in os.listdir(import_dir) if os.path.isfile(os.path.join(import_dir, f)) and f.endswith(".pst")]

    for f in files:
        try:
            username = os.path.splitext(f)[0]
            user_dir = os.path.join(converted_dir, username)
            os.makedirs(user_dir)
            if DEBUG:
                print "Created directory: " + user_dir

            readpst = ["readpst", "-e", "-o", user_dir, os.path.join(import_dir, f)]
            try:
                print "Converting PST for user: " + username
                readpst_output = subprocess.check_output(readpst)
                if DEBUG:
                    print "Converted: ", f
            except subprocess.CalledProcessError as e:
                print readpst_output
                print "Failed to convert PST: ", f
                #sys.exit(1)
        except OSError:
            if not os.path.isdir(user_dir):
                print "Unable to create directory: ", user_dir
                sys.exit(1)
            else:
                if DEBUG:
                    print "User directory for {} already exists: {}".format(username, user_dir)
        
        if EMAILS:
            print "Importing emails for user: " + username
            import_emails(user_dir, username)
        if CALENDARS:
            print "Importing calendar for user: " + username
            import_calendars(user_dir, username, zadmin, zadmin_password)
        if CONTACTS:
            print "Importing contacts for user: " + username
            import_contacts()

def main():
    '''Import PST files into Zarafa'''
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
    description = 'Import PST files into Zarafa',
    epilog = """
    This program will import emails, calendars and contacts from and Outlook PST file into a Zarafa server
    
    You will need to create a directory called 'pst' in the same directory as this script.
    In this directory place any PST file you want to import.
    The name of the PST file must match the Zarafa username you want it imported into.
    
    i.e.
        Zarafa username:    joeblog
        PST name:           joeblog.pst
    """
    )
    parser.add_argument('-V', '--version', 
        action='version', 
        version = '%(prog)s version: ' + VERSION)
    parser.add_argument('--noemails', action = 'store_true', default = False,
        help = "Don't import emails")
    parser.add_argument('--nocalendars', action = 'store_true', default = False,
        help = "Don't import calendars")
    parser.add_argument('--nocontacts', action = 'store_true', default = False,
        help = "Don't import contacts")
    parser.add_argument('--debug', action = 'store_true', default = False,
        help = "Print a bunch of debug info.")
    parser.add_argument('--dryrun', action = 'store_true', default = False,
        help = "Dry Run, do not actually import.")
    args = parser.parse_args()
    
    if args.debug:
        global DEBUG
        DEBUG = True
        print 'Turning debug on'
    
    if args.dryrun:
        global DRYRUN
        DRYRUN = True
        print "Dry-run: sync or snapshot won't run"
    
    if args.noemails:
        global EMAILS
        EMAILS = False
        print "Not importing emails"
    
    if args.nocalendars:
        global CALENDARS
        CALENDARS = False
        print "Not importing calendars"
    
    if args.nocontacts:
        global CONTACTS
        CONTACTS = False
        print "Not importing contacts"

    if EMAILS or CALENDARS or CONTACTS:
        start_import_pst()
    else:
        print "You can't import nothing!!! Remove at least one of --noemails --nocalendars or --nocontacts"

if __name__ == '__main__':
    main()
