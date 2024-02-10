#!/usr/bin/env python
from plexapi.myplex import MyPlexAccount
import os, requests, sys, urllib

r"""
Description:
  - This script uses the Python-PlexAPI and Shoko Server to apply posters to the collections in Plex.
  - It will take the default poster from the corresponding Shoko group.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, ShokoRelay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex and Shoko Server information into the Prefs below.
Usage:
  - Run in a terminal (watched-sync.py) to set Plex collection posters to Shoko's.
  - Append the argument 'unlock' (force-metadata.py clean) if you want to unlock all collection posters instead.
  - To remove posters at a later date consider unlocking then using: Plex-Image-Cleanup
"""

# user preferences
Prefs = {
    'Plex_Username': 'Default',
    'Plex_Password': '',
    'Plex_ServerName': 'Media',
    'Plex_LibraryName': 'Anime',
    'Shoko_Hostname': '127.0.0.1',
    'Shoko_Port': 8111,
    'Shoko_Username': 'Default',
    'Shoko_Password': ''
}

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# check the arguments if the user is looking to run a full clean or not
unlock_posters = False
if len(sys.argv) == 2:
    if sys.argv[1].lower() == 'unlock': # if the first argument is 'full'
        unlock_posters = True
    else:
        print(f'{error_prefix}Failed: Invalid Argument')
        exit(1)

# authenticate and connect to the Plex server/library specified
try:
    admin = MyPlexAccount(Prefs['Plex_Username'], Prefs['Plex_Password'])
except Exception:
    print(f'{error_prefix}Failed: Plex Credentials Invalid or Server Offline')
    exit(1)

try:
    plex = admin.resource(Prefs['Plex_ServerName']).connect()
except Exception:
    print(f'└{error_prefix}Failed: Server Name Not Found')
    exit(1)

try:
    anime = plex.library.section(Prefs['Plex_LibraryName'])
except Exception:
    print(f'└{error_prefix}Failed: Library Name Not Found')
    exit(1)

# if running a clean remove all posters 
if unlock_posters:
    print_f('\n┌ShokoRelay: Unlocking Posters...')
    for collection in anime.collections():
        collection.unlockPoster()
else:
    # grab a shoko api key using the credentials from the prefs
    auth = requests.post(f'http://{Prefs['Shoko_Hostname']}:{Prefs['Shoko_Port']}/api/auth', json={'user': Prefs['Shoko_Username'], 'pass': Prefs['Shoko_Password'], 'device': 'Collection-Posters for Plex'}).json()

    print_f('\n┌ShokoRelay Collection Posters: Applying Shoko\'s Primary Group Images to Plex...')

    for collection in anime.collections():
        try:
            group_search = requests.get(f'http://{Prefs['Shoko_Hostname']}:{Prefs['Shoko_Port']}/api/v3/Group?pageSize=1&page=1&includeEmpty=false&randomImages=false&topLevelOnly=true&startsWith={urllib.parse.quote(collection.title)}&apikey={auth['apikey']}').json()
            poster = group_search['List'][0]['Images']['Posters'][0]
            poster_url = f'http://{Prefs['Shoko_Hostname']}:{Prefs['Shoko_Port']}/api/v3/Image/' + poster['Source'] + '/Poster/' + poster['ID']
            print_f(f'├─Relaying: {poster['ID']} → {collection.title}')
            collection.uploadPoster(url=poster_url)
        except Exception as error:
            print(f'│{error_prefix}─Failed: Collection Not Found in Shoko\n', error)
print_f(f'└Finished!')
