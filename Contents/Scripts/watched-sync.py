#!/usr/bin/env python3
from argparse import RawTextHelpFormatter
from common import print_f, plex_auth, shoko_auth
from plexapi.myplex import MyPlexAccount
import os, re, urllib, argparse, requests
import config as cfg
import common as cmn

r"""
Description:
  - This script uses the Python-PlexAPI and Shoko Server to sync watched states from Plex to Shoko or vice versa.
  - If something is marked as watched in Plex it will also be marked as watched in Shoko and AniDB.
  - This was created due to various issues with Plex and Shoko's built in watched status syncing.
      - Primarily, the webhook for syncing requires Plex Pass and does not account for things manually marked as watched.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, Shoko Relay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex and Shoko Server credentials into config.py.
  - If your anime is split across multiple libraries they can all be added in a python list under Plex "LibraryNames".
      - It must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies']"
  - If you want to track watched states from managed/home accounts on your Plex server you can add them to Plex "ExtraUsers" following the same list format as above.
      - Leave it as "None" otherwise.
  - If you don't want to track watched states from your Plex Server's Admin account set "SyncAdmin" to "False".
      - Leave it as "True" otherwise.
Usage:
  - Run in a terminal (watched-sync.py) to sync watched states from Plex to Shoko.
  - Append a relative date suffix as an argument to narrow down the time frame and speed up the process:
      - (watched-sync.py 2w) would return results from the last 2 weeks
      - (watched-sync.py 3d) would return results from the last 3 days
  - The full list of suffixes (from 1-999) are: m=minutes, h=hours, d=days, w=weeks, mon=months, y=years
  - There are two alternate modes for this script which will ask for (Y/N) confirmation for each configured Plex user.
      - Append the argument "import" (watched-sync.py import) if you want to sync watched states from Shoko to Plex.
      - Append the argument "purge" (watched-sync.py purge) if you want to remove all watched states from the configured Plex libraries.
      - The confirmation prompts can be bypassed by adding the "force" flag (-f or --force).
Behaviour:
  - Due to the potential for losing a huge amount of data, removing watch states from Plex has been omitted from this script unless "purge" mode is used.
"""

# relative date regex definition and import check for argument type
def arg_parse(arg):
    arg = arg.lower()
    if not re.match('^(?:[1-9]|[1-9][0-9]|[1-9][0-9][0-9])(?:m|h|d|w|mon|y)$', arg) and not re.match('(?:import|purge)', arg):
        raise argparse.ArgumentTypeError('invalid range, import or purge')
    return arg

# check the arguments if the user is looking to use a relative date or not
parser = argparse.ArgumentParser(description='Sync watched states from Plex to Shoko.', epilog='NOTE: "import" and "purge" mode will ask for (Y/N) confirmation for each configured Plex user.', formatter_class=RawTextHelpFormatter)
parser.add_argument('relative_date', metavar='range | import | purge', nargs='?', type=arg_parse, default='999y', help='range:  Limit the time range (from 1-999) for syncing watched states.\n        *must be the sole argument and is entered as Integer+Suffix\n        *the full list of suffixes are:\n        m=minutes\n        h=hours\n        d=days\n        w=weeks\n        mon=months\n        y=years\n\nimport: If you want to sync watched states from Shoko to Plex instead.\n        *must be the sole argument and is simply entered as "import"\n\npurge:  If you want to clear all watched states from Plex.\n        *must be the sole argument and is simply entered as "purge"')
parser.add_argument('-f', '--force', action='store_true', help='ignore user confirmation prompts when importing or purging')
relative_date, shoko_import, plex_purge, force = parser.parse_args().relative_date, False, False, parser.parse_args().force
if relative_date == 'import': relative_date, shoko_import = '999y', True
if relative_date == 'purge':  plex_purge = True

admin = plex_auth(connect=False) # authenticate to the Plex server/library specified using the credentials from the prefs and the common auth function

# add the admin account to a list (if it is enabled) then append any other users to it
accounts = [admin] if cfg.Plex['SyncAdmin'] else []
if cfg.Plex['ExtraUsers']:
    try:
        extra_users = [admin.user(username) for username in cfg.Plex['ExtraUsers']]
        data = [admin.query(f'https://plex.tv/api/home/users/{user.id}/switch', method=admin._session.post) for user in extra_users]
        for userID in data: accounts.append(MyPlexAccount(token=userID.attrib.get('authenticationToken')))
    except Exception as error: # if the extra users can't be found show an error and continue
        print(f'{cmn.error_prefix}Failed:', error)

if not plex_purge: shoko_key = shoko_auth() # grab a Shoko API key using the credentials from the prefs and the common auth function (when not purging)

# loop through all of the accounts listed and sync watched states
print_f('\n╭Shoko Relay Watched Sync')
# if importing grab the filenames for all the watched episodes in Shoko and add them to a list
if shoko_import:
    print_f(f'├─Generating: Shoko Watched Episode List...')
    watched_episodes = []
    shoko_watched = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode?pageSize=0&page=1&includeWatched=only&includeFiles=true&apikey={shoko_key}').json()
    for file in shoko_watched['List']:
        watched_episodes.append(os.path.basename(file['Files'][0]['Locations'][0]['RelativePath']))

for account in accounts:
    # if importing ask the user to confirm syncing for each username
    if (shoko_import or plex_purge) and force == False:
        class SkipUser(Exception): pass # label for skipping users via input
        try:
            while True:
                query = 'import Shoko watched states to' if shoko_import else 'clear all watched states from'
                confirmation = input(f'├──Would you like to {query}: {account} (Y/N) ')
                if   confirmation.lower() == 'y': break
                elif confirmation.lower() == 'n': raise SkipUser()
                else: print(f'{cmn.error_prefix}───Please enter "Y" or "N"')
        except SkipUser: continue

    try:
        plex = account.resource(cfg.Plex['ServerName']).connect()
    except Exception:
        print(f'╰{cmn.error_prefix}Failed: Server Name Not Found')
        exit(1)

    # loop through the configured libraries
    for library in cfg.Plex['LibraryNames']:
        print_f(f'├┬Querying: {account} @ {cfg.Plex["ServerName"]}/{library}')
        try:
            section = plex.library.section(library)
        except Exception as error:
            print(f'│{cmn.error_prefix}─Failed', error)
            continue

        # if importing loop through all the unwatched episodes in the Plex library
        if shoko_import:
            for episode in section.searchEpisodes(unwatched=True):
                for episode_path in episode.iterParts():
                    filepath = os.path.basename(episode_path.file)
                    if filepath in watched_episodes: # if an unwatched episode's filename in Plex is found in Shoko's watched episodes list mark it as played
                        episode.markPlayed()
                        print_f(f'│├─Importing: {filepath}')
        elif plex_purge:
            print_f(f'│├─Clearing watched states...')
            for episode in section.searchEpisodes(unwatched=False): episode.markUnplayed()
        else:
            # loop through all the watched episodes in the Plex library within the time frame of the relative date
            for episode in section.searchEpisodes(unwatched=False, filters={'lastViewedAt>>': relative_date}):
                for episode_path in episode.iterParts():
                    filepath = os.path.sep + os.path.basename(episode_path.file) # add a path separator to the filename to avoid duplicate matches
                    path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={shoko_key}').json()
                    try:
                        if path_ends_with[0]['Watched'] == None:
                            print_f(f'│├─Relaying: {filepath} → {episode.title}')
                            for EpisodeID in path_ends_with[0]['SeriesIDs'][0]['EpisodeIDs']:
                                requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode/{EpisodeID["ID"]}/Watched/true?apikey={shoko_key}')
                    except Exception:
                        print(f'│├{cmn.error_prefix}─Failed: Make sure that "{filepath}" is matched by Shoko')
        print_f('│╰─Finished!')
print('╰Watched Sync Complete')
