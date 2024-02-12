#!/usr/bin/env python
from plexapi.myplex import MyPlexAccount
import os, requests, sys, urllib

r"""
Description:
  - This script uses the Python-PlexAPI and Shoko Server to sync watched states from Plex to AniDB.
  - If something is marked as watched in Plex it will also be marked as watched on AniDB.
  - This was created due to various issues with Plex and Shoko's built in watched status syncing.
      i. The webhook for syncing requires Plex Pass and does not account for things manually marked as watched.
     ii. Shoko's "Sync Plex Watch Status" command doesn't work with cross platform setups.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, ShokoRelay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex and Shoko Server information into the Prefs below.
  - If your anime is split across multiple libraries they can all be added in a python list under "Plex_LibraryNames".
      - It must be a list to work e.g. "'Plex_LibraryNames': ['Anime Shows', 'Anime Movies']"
  - If you want to track watched states from managed/home accounts on your Plex server you can add them to "Plex_ExtraUsers" following the same list format as above.
      - Leave it as "None" otherwise.
Usage:
  - Run in a terminal (watched-sync.py)
Behaviour:
  - Due to the potential for losing a huge amount of data removing watch states has been omitted from this script.
"""

# user preferences
Prefs = {
    'Plex_Username': 'Default',
    'Plex_Password': '',
    'Plex_ServerName': 'Media',
    'Plex_LibraryNames': ['Anime'],
    'Plex_ExtraUsers': None,
    'Shoko_Hostname': '127.0.0.1',
    'Shoko_Port': 8111,
    'Shoko_Username': 'Default',
    'Shoko_Password': ''
}

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# authenticate and connect to the Plex server/library specified
try:
    admin = MyPlexAccount(Prefs['Plex_Username'], Prefs['Plex_Password'])
except Exception:
    print(f'{error_prefix}Failed: Plex Credentials Invalid or Server Offline')
    exit(1)

# add the admin account to a list then append any other users to it
accounts = [admin]
if Prefs['Plex_ExtraUsers'] is not None:
    try:
        extra_users = [admin.user(username) for username in Prefs['Plex_ExtraUsers']]
        data = [admin.query(f'https://plex.tv/api/home/users/{user.id}/switch', method=admin._session.post) for user in extra_users]
        for userID in data: accounts.append(MyPlexAccount(token=userID.attrib.get('authenticationToken')))
    except Exception as error: # if the extra users can't be found show an error and continue
        print(f'{error_prefix}Failed:', error)

# grab a shoko api key using the credentials from the prefs
try:
    auth = requests.post(f'http://{Prefs['Shoko_Hostname']}:{Prefs['Shoko_Port']}/api/auth', json={'user': Prefs['Shoko_Username'], 'pass': Prefs['Shoko_Password'], 'device': 'ShokoRelay Scripts for Plex'}).json()
except Exception:
    print(f'{error_prefix}Failed: Unable to Connect to Shoko Server')
    exit(1)
if 'status' in auth and auth['status'] in (400, 401):
    print(f'{error_prefix}Failed: Shoko Credentials Invalid')
    exit(1)

# loop through all of the accounts listed and sync watched states
print_f('\n┌ShokoRelay Watched Sync')
for account in accounts:
    try:
        plex = account.resource(Prefs['Plex_ServerName']).connect()
    except Exception:
        print(f'└{error_prefix}Failed: Server Name Not Found')
        exit(1)

    # loop through the configured libraries
    for library in Prefs['Plex_LibraryNames']:
        print_f(f'├┬Querying: {account} @ {Prefs['Plex_ServerName']}/{library}')
        try:
            anime = plex.library.section(library)
        except Exception as error:
            print(f'│{error_prefix}Failed', error)
            continue

        # loop through all unwatched episodes in the plex library
        for episode in anime.searchEpisodes(unwatched=False):
            for episode_path in episode.iterParts():
                filepath = os.path.sep + os.path.basename(episode_path.file) # add a path separator to the filename to avoid duplicate matches
                path_ends_with = requests.get(f'http://{Prefs['Shoko_Hostname']}:{Prefs['Shoko_Port']}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={auth['apikey']}').json()
                if path_ends_with[0]['Watched'] == None: 
                    print_f(f'│├─Relaying: {filepath} → {episode.title}')
                    try:
                        for EpisodeID in path_ends_with[0]['SeriesIDs'][0]['EpisodeIDs']:
                            requests.post(f'http://{Prefs['Shoko_Hostname']}:{Prefs['Shoko_Port']}/api/v3/Episode/{EpisodeID['ID']}/Watched/true?apikey={auth['apikey']}')
                    except Exception as error:
                        print(f'││{error_prefix}─Failed: Make sure that the video file listed above is matched by Shoko\n', error)
        print_f(f'│└─Finished!')
print(f'└─Watched Sync Complete')
