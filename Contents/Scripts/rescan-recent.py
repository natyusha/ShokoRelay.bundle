#!/usr/bin/env python3
from plexapi.myplex import MyPlexAccount
import os, re, sys, requests
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
  - Append the number of recently added series (from 1-99) to rescan as an argument when 5 isn't enough:
      - (rescan-recent.py 20) would rescan the 20 most recently added series
"""

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# check the arguments for how many recent series to rescan
series_count = '5' # set the default series count to 5
if len(sys.argv) == 2:
    if re.match('^(?:[1-9]|[1-9][0-9])$', sys.argv[1]): # if the argument is a valid number from 1-99
        series_count = sys.argv[1]
    else:
        print(f'{error_prefix}Failed: Invalid Argument')
        exit(1)
elif len(sys.argv) > 2:
    print(f'{error_prefix}Failed: Too Many Arguments')
    exit(1)

# grab a shoko api key using the credentials from the prefs
try:
    auth = requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/auth', json={'user': cfg.Shoko['Username'], 'pass': cfg.Shoko['Password'], 'device': 'ShokoRelay Scripts for Plex'}).json()
except Exception:
    print(f'{error_prefix}Failed: Unable to Connect to Shoko Server')
    exit(1)
if 'status' in auth and auth['status'] in (400, 401):
    print(f'{error_prefix}Failed: Shoko Credentials Invalid')
    exit(1)

# grab a list of shoko's most recently added series
print_f('\n┌ShokoRelay Rescan Recent')
print_f(f'├┬Checking Shoko\'s ({series_count}) most recently added series...')
recently_added = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Dashboard/RecentlyAddedSeries?pageSize={series_count}&page=1&includeRestricted=true&apikey={auth["apikey"]}').json()

# loop through recently added series and add the series ids to a list
recently_added_ids = []
for series in recently_added: recently_added_ids.append(series['IDs']['ID'])

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
print_f('│└─Finished!')
print_f('└Rescan Task Complete')
