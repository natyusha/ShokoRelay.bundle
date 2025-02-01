#!/usr/bin/env python3
from argparse import RawTextHelpFormatter
from plexapi.myplex import MyPlexAccount
import os, re, sys, argparse, requests
import config as cfg

r"""
Description:
  - This is mostly used for quickly adding currently airing series to Plex that were unrecognized when initially imported into Shoko.
  - Once the files are recognized running this script will trigger a rescan in Plex for any series that they are attached to.
  - This requires Plex's partial scanning (or an alternative) to be enabled.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Requests Library (pip install requests), Plex, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Shoko Server credentials into config.py.
  - The Path Remapping section can be configured when running the scripts from a location where the paths differ from Shoko's.
Usage:
  - Run in a terminal (rescan-recent.py) to trigger a Plex rescan of the 5 most recently added series in Shoko.
  - Change the number of recently added series (from 1-99) to rescan with an argument when 5 isn't enough:
      - (rescan-recent.py 20) would rescan the 20 most recently added series
- Append the argument "import" (rescan-recent.py import) if you want to force Shoko to import unrecognized files.
- Append the argument "remove" (rescan-recent.py remove) if you want to force Shoko to remove missing files incl. MyList.
"""

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# recent series regex definition and import check for argument type
def arg_parse(arg):
    arg = arg.lower()
    if not re.match('^(?:(?:[1-9]|[1-9][0-9])|(?:import|remove))$', arg):
        raise argparse.ArgumentTypeError('invalid range or import/remove')
    return arg

# check the arguments for how many recent series to rescan
parser = argparse.ArgumentParser(description='Trigger a Plex rescan of the 5 most recently added series in Shoko.', formatter_class=RawTextHelpFormatter)
parser.add_argument('recent_series', metavar='range', nargs='?', type=arg_parse, default='5', help='range:  Change the number of recently added series (from 1-99) to rescan.\n        *must be the sole argument and is entered as an Integer\n\n')
parser.add_argument('rescan_remove', metavar='import | remove', nargs='?', type=arg_parse, help='import: If you want to force Shoko to import unrecognized files.\n        *must be the sole argument and is entered as "import"\n\nremove: If you want to force Shoko to remove missing files incl. MyList.\n        *must be the sole argument and is entered as "remove"')
arg_value, shoko_import, shoko_remove = parser.parse_args().recent_series, False, False
if    arg_value == 'import': shoko_import = True
elif  arg_value == 'remove': shoko_remove = True

# grab a Shoko API key using the credentials from the prefs
try:
    auth = requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/auth', json={'user': cfg.Shoko['Username'], 'pass': cfg.Shoko['Password'], 'device': 'Shoko Relay Scripts for Plex'}).json()
except Exception:
    print(f'{error_prefix}Failed: Unable to Connect to Shoko Server')
    exit(1)
if 'status' in auth and auth['status'] in (400, 401):
    print(f'{error_prefix}Failed: Shoko Credentials Invalid')
    exit(1)

print_f('\n╭Shoko Relay Rescan Recent')
if shoko_import:
    # If importing run an api command to get the drop folder ids then another one to scan them
    print_f(f'├┬Scanning Shoko\'s Import Folders...')
    try:
        import_folders = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/ImportFolder?apikey={auth["apikey"]}').json()
        for folder in import_folders:
            if folder['DropFolderType'] == 1:
                requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/ImportFolder/{folder["ID"]}/Scan?apikey={auth["apikey"]}')
                print_f(f'│├─Scanning: {folder['Name']}')
    except Exception as error:
        print(f'│{error_prefix}─Failed:', error)
elif shoko_remove:
    # If removing run an api command to remove missing files
    print_f(f'├┬Removing Missing Files From Shoko...')
    try:
        requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Action/RemoveMissingFiles/true?apikey={auth["apikey"]}')
    except Exception as error:
        print(f'│{error_prefix}─Failed:', error)
else:
    # grab a list of Shoko's most recently added series
    print_f(f'├┬Checking Shoko\'s ({arg_value}) most recently added series...')
    recently_added = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Dashboard/RecentlyAddedSeries?pageSize={arg_value}&page=1&includeRestricted=true&apikey={auth["apikey"]}').json()

    # loop through recently added series and add the series ids to a list
    recently_added_ids = []
    for series in recently_added['List']: recently_added_ids.append(series['IDs']['ID'])

    # loop through the series ids and grab filepaths for each
    for ids in recently_added_ids:
        recent_episodes = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Series/{ids}/Episode?pageSize=1&page=1&includeFiles=true&includeMediaInfo=false&includeAbsolutePaths=true&fuzzy=true&apikey={auth["apikey"]}').json()
        path = os.path.dirname(recent_episodes['List'][0]['Files'][0]['Locations'][0]['AbsolutePath'])
        # use regex substitution to remap paths to those used locally
        for key, value in cfg.PathRemapping.items(): path = re.sub(key, re.escape(value), path)
        # create an empty file in the location to trigger autoscan and then immediately delete it
        try:
            with open(os.path.join(path, 'plex.autoscan'), 'w'): pass
            os.remove(os.path.join(path, 'plex.autoscan'))
            print_f(f'│├─Rescanning: {path}')
        except Exception as error:
            print(f'│{error_prefix}─Failed:', error)
print_f('│╰─Finished!')
print_f('╰Task Complete')
