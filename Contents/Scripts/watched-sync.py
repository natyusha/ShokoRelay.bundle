#!/usr/bin/env python
from plexapi.myplex import MyPlexAccount
import os, re, sys, urllib, requests
import config as cfg

r"""
Description:
  - This script uses the Python-PlexAPI and Shoko Server to sync watched states from Plex to Shoko or Shoko to Plex.
  - If something is marked as watched in Plex it will also be marked as watched in Shoko and AniDB.
  - This was created due to various issues with Plex and Shoko's built in watched status syncing.
      i. The webhook for syncing requires Plex Pass and does not account for things manually marked as watched.
     ii. Shoko's "Sync Plex Watch Status" command doesn't work with cross platform setups.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, ShokoRelay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex and Shoko Server credentials into config.py.
  - If your anime is split across multiple libraries they can all be added in a python list under Plex "LibraryNames".
      - It must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies']"
  - If you want to track watched states from managed/home accounts on your Plex server you can add them to Plex "ExtraUsers" following the same list format as above.
      - Leave it as "None" otherwise.
Usage:
  - Run in a terminal (watched-sync.py) to sync watched states from Plex to Shoko.
  - Append a relative date suffix as an argument to narrow down the time frame and speed up the process:
      - (watched-sync.py 2w) would return results from the last 2 weeks
      - (watched-sync.py 3d) would return results from the last 3 days
  - The full list of suffixes (from 1-999) are: m=minutes, h=hours, d=days, w=weeks, mon=months, y=years
  - Append the argument "import" (watched-sync.py import) if you want to sync watched states from Shoko to Plex instead.
      - The script will ask for (Y/N) confirmation for each Plex user that has been configured.
Behaviour:
  - Due to the potential for losing a huge amount of data removing watch states has been omitted from this script.
"""

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# check the arguments if the user is looking to use a relative date or not
relative_date = '999y' # set the relative date to 999 years by default
shoko_import = False
if len(sys.argv) == 2:
    if re.match('^(?:[1-9]|[1-9][0-9]|[1-9][0-9][0-9])(?:m|h|d|w|mon|y)$', sys.argv[1]): # if the argument is a valid relative date
        relative_date = sys.argv[1]
    elif sys.argv[1].lower() == 'import': # switch to shoko import mode
        shoko_import = True
    else:
        print(f'{error_prefix}Failed: Invalid Argument')
        exit(1)

# authenticate and connect to the Plex server/library specified
try:
    if cfg.Plex['X-Plex-Token']:
        admin = MyPlexAccount(token=cfg.Plex['X-Plex-Token'])
    else:
        admin = MyPlexAccount(cfg.Plex['Username'], cfg.Plex['Password'])
except Exception:
    print(f'{error_prefix}Failed: Plex Credentials Invalid or Server Offline')
    exit(1)

# add the admin account to a list then append any other users to it
accounts = [admin]
if cfg.Plex['ExtraUsers']:
    try:
        extra_users = [admin.user(username) for username in cfg.Plex['ExtraUsers']]
        data = [admin.query(f'https://plex.tv/api/home/users/{user.id}/switch', method=admin._session.post) for user in extra_users]
        for userID in data: accounts.append(MyPlexAccount(token=userID.attrib.get('authenticationToken')))
    except Exception as error: # if the extra users can't be found show an error and continue
        print(f'{error_prefix}Failed:', error)

# grab a shoko api key using the credentials from the prefs
try:
    auth = requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/auth', json={'user': cfg.Shoko['Username'], 'pass': cfg.Shoko['Password'], 'device': 'ShokoRelay Scripts for Plex'}).json()
except Exception:
    print(f'{error_prefix}Failed: Unable to Connect to Shoko Server')
    exit(1)
if 'status' in auth and auth['status'] in (400, 401):
    print(f'{error_prefix}Failed: Shoko Credentials Invalid')
    exit(1)

# loop through all of the accounts listed and sync watched states
print_f('\n┌ShokoRelay Watched Sync')
# if importing grab the filenames for all the watched episodes in shoko and add them to a list
if shoko_import == True:
    print_f(f'├─Generating: Shoko Watched Episode List...')
    watched_episodes = []
    shoko_watched = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode?pageSize=0&page=1&includeWatched=only&includeFiles=true&apikey={auth["apikey"]}').json()
    for file in shoko_watched['List']:
        watched_episodes.append(os.path.basename(file['Files'][0]['Locations'][0]['RelativePath']))

for account in accounts:
    # if importing ask the user to confirm syncing for each username
    if shoko_import == True:
        class SkipUser(Exception): pass # label for skipping users via input
        try:
            while True:
                import_confirmation = input(f'├──Would you like to import Shoko watched states to: {account} (Y/N) ')
                if import_confirmation.lower() ==   'y': break
                elif import_confirmation.lower() == 'n': raise SkipUser()
                else: print(f'{error_prefix}───Please enter "Y" or "N"')
        except SkipUser: continue

    try:
        plex = account.resource(cfg.Plex['ServerName']).connect()
    except Exception:
        print(f'└{error_prefix}Failed: Server Name Not Found')
        exit(1)

    # loop through the configured libraries
    for library in cfg.Plex['LibraryNames']:
        print_f(f'├┬Querying: {account} @ {cfg.Plex["ServerName"]}/{library}')
        try:
            anime = plex.library.section(library)
        except Exception as error:
            print(f'│{error_prefix}─Failed', error)
            continue

        # if importing loop through all the unwatched episodes in the plex library
        if shoko_import == True:
            for episode in anime.searchEpisodes(unwatched=True):
                for episode_path in episode.iterParts():
                    filepath = os.path.basename(episode_path.file)
                    if filepath in watched_episodes: # if an unwatched episode's filename in plex is found in shoko's watched episodes list mark it as played
                        episode.markPlayed()
                        print_f(f'│├─Importing: {filepath}')
        else:
            # loop through all the watched episodes in the plex library within the time frame of the relative date
            for episode in anime.searchEpisodes(unwatched=False, filters={'lastViewedAt>>': relative_date}):
                for episode_path in episode.iterParts():
                    filepath = os.path.sep + os.path.basename(episode_path.file) # add a path separator to the filename to avoid duplicate matches
                    path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={auth["apikey"]}').json()
                    try:
                        if path_ends_with[0]['Watched'] == None:
                            print_f(f'│├─Relaying: {filepath} → {episode.title}')
                            for EpisodeID in path_ends_with[0]['SeriesIDs'][0]['EpisodeIDs']:
                                requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode/{EpisodeID["ID"]}/Watched/true?apikey={auth["apikey"]}')
                    except Exception:
                        print(f'│├{error_prefix}─Failed: Make sure that "{filepath}" is matched by Shoko')
        print_f('│└─Finished!')
print('└Watched Sync Complete')
