#!/usr/bin/env python3
from plexapi.myplex import MyPlexAccount
import os, re, sys, urllib, requests
import config as cfg

r"""
Description:
  - This script uses the Python-PlexAPI and Shoko Server to apply posters to the collections in Plex.
  - It will look for posters in a user defined folder and if none are found take the default poster from the corresponding Shoko group.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, ShokoRelay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex and Shoko Server credentials into config.py.
  - If your anime is split across multiple libraries they can all be added in a python list under "LibraryNames".
      - It must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies']"
  - The Plex "PostersFolder" and "DataFolder" settings require double backslashes on windows e.g. "'PostersFolder': 'M:\\Anime\\Posters',".
      - The "DataFolder" setting is the base Plex Media Server Data Directory (where the Metadata folder is located).
      - The "PostersFolder" setting is the folder containing any custom collection posters.
Usage:
  - Run in a terminal (collection-posters.py) to set Plex collection posters to the user provided ones or Shoko's.
      - Any Posters in the "PostersFolder" must have the same name as their respective collection in Plex.
      - The following characters must be stripped from the filenames: \ / : * ? " < > |
      - The accepted file extension are: jpg / jpeg / png / tbn
  - Append the argument 'clean' (collection-posters.py clean) if you want to remove old collection posters instead.
      - This works by deleting everything but the newest custom poster for all collections.
"""

# file formats that will work with plex
file_formats = ('.jpg', '.jpeg', '.png', '.tbn')

# characters to replace in the collection name when comparing it to the filename using regex substitution
file_formatting = ('\\\\', '\\/', ':', '\\*', '\\?', '"', '<', ">", '\\|')

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# check the arguments if the user is looking to clean posters or not
clean_posters = False
if len(sys.argv) == 2:
    if sys.argv[1].lower() == 'clean': # if the first argument is 'clean'
        clean_posters = True
    else:
        print(f'{error_prefix}Failed: Invalid Argument')
        exit(1)
elif len(sys.argv) > 2:
    print(f'{error_prefix}Failed: Too Many Arguments')
    exit(1)

# authenticate and connect to the plex server/library specified
try:
    if cfg.Plex['X-Plex-Token']:
        admin = MyPlexAccount(token=cfg.Plex['X-Plex-Token'])
    else:
        admin = MyPlexAccount(cfg.Plex['Username'], cfg.Plex['Password'])
except Exception:
    print(f'{error_prefix}Failed: Plex Credentials Invalid or Server Offline')
    exit(1)

try:
    plex = admin.resource(cfg.Plex['ServerName']).connect()
except Exception:
    print(f'{error_prefix}Failed: Server Name Not Found')
    exit(1)

# loop through the configured libraries
print_f('\n┌ShokoRelay: Collection Posters')
for library in cfg.Plex['LibraryNames']:
    try:
        anime = plex.library.section(library)
    except Exception as error:
        print(f'├{error_prefix}Failed', error)
        continue

    # if the user is looking to clean posters
    if clean_posters:
        print_f(f'├┬Removing Posters @ {cfg.Plex["ServerName"]}/{library}')
        try:
            for collection in anime.collections():
                # check for multiple custom posters and delete the oldest ones
                if len(collection.posters()) > 2:
                    posters_path = cfg.Plex['DataFolder'] + os.path.sep + collection.metadataDirectory + os.path.sep + 'Uploads' + os.path.sep + 'posters'
                    for poster in sorted(os.listdir(posters_path))[:-1]: # list all but the newest poster
                        print_f(f'│├─Removing: {collection.title} → {poster}')
                        os.remove(os.path.join(posters_path,poster))
            print_f('│└─Finished!')
        except Exception as error:
            print(f'│├{error_prefix}Failed', error)
    else:
        # grab a shoko api key using the credentials from the prefs
        try:
            auth = requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/auth', json={'user': cfg.Shoko['Username'], 'pass': cfg.Shoko['Password'], 'device': 'ShokoRelay Scripts for Plex'}).json()
        except Exception:
            print(f'└{error_prefix}Failed: Unable to Connect to Shoko Server')
            exit(1)
        if 'status' in auth and auth['status'] in (400, 401):
            print(f'└{error_prefix}Failed: Shoko Credentials Invalid')
            exit(1)

        # make a list of all the user defined collection posters (if any)
        if cfg.Plex['PostersFolder']:
            user_posters = []
            try:
                for file in os.listdir(cfg.Plex['PostersFolder']):
                    if file.lower().endswith(file_formats): user_posters.append(file) # check image files regardless of case
            except Exception as error:
                print(f'└{error_prefix}Failed', error)
                exit(1)

        print_f(f'├┬Applying Posters @ {cfg.Plex["ServerName"]}/{library}')
        # loop through plex collections grabbing their names to compare to shoko's group names and user defined poster names
        for collection in anime.collections():
            # check for user defined posters first
            fallback = True
            if cfg.Plex['PostersFolder']:
                try:
                    for user_poster in user_posters:
                        tile_formatted = collection.title
                        for key in file_formatting:
                            tile_formatted = re.sub(key, '', tile_formatted)
                        if os.path.splitext(user_poster)[0] == tile_formatted:
                            print_f(f'│├─Relaying: {user_poster} → {collection.title}')
                            collection.uploadPoster(filepath=cfg.Plex['PostersFolder'] + os.path.sep + user_poster)
                            fallback = False # don't fallback to the shoko group if user poster found
                            continue
                except Exception as error:
                    print(f'│├{error_prefix}──Failed', error)

            # fallback to shoko group posters if no user defined psoter
            if fallback:
                try:
                    group_search = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Group?pageSize=1&page=1&includeEmpty=false&randomImages=false&topLevelOnly=true&startsWith={urllib.parse.quote(collection.title)}&apikey={auth["apikey"]}').json()
                    shoko_poster = group_search['List'][0]['Images']['Posters'][0]
                    poster_url = f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Image/' + shoko_poster['Source'] + '/Poster/' + shoko_poster['ID']
                    print_f(f'│├─Relaying: Shoko/{shoko_poster["Source"]}/{shoko_poster["ID"]} → {collection.title}')
                    collection.uploadPoster(url=poster_url)
                except:
                    print(f'│├{error_prefix}──Failed: No Shoko Group → {collection.title}')
        print_f('│└─Finished!')
print_f('└Posters Task Complete')
