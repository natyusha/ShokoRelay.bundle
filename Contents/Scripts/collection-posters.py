#!/usr/bin/env python3
import os, re, urllib, argparse, requests
import config as cfg; import common as cmn

r"""
Description:
  - This script uses the Python-PlexAPI and Shoko Server to apply posters to the collections in Plex.
  - It will look for posters in a user defined folder and if none are found take the default poster from the corresponding Shoko group.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, Shoko Relay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex and Shoko Server credentials into config.py.
  - If your anime is split across multiple libraries they can all be added in a python list under "LibraryNames".
      - It must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies']"
  - The Plex "PostersFolder" and "DataFolder" settings require double backslashes on windows e.g. "'PostersFolder': 'M:\\Anime\\Posters',".
      - The "DataFolder" setting is the base Plex Media Server Data Directory (where the Metadata folder is located).
      - The "PostersFolder" setting is the folder containing any custom collection posters.
Usage:
  - Run in a terminal (collection-posters.py) to set Plex collection posters to user provided ones or Shoko's.
      - Any Posters in the "PostersFolder" must have the same name as their respective collection in Plex.
      - The following characters must be stripped from the filenames: \ / : * ? " < > |
      - The accepted file extensions are: bmp / gif / jpe / jpeg / jpg / png / tbn / tif / tiff / webp
  - Append the "clean" flag (-c or --clean) if you want to remove old collection posters too.
      - This works by deleting everything but the newest custom poster for all collections.
  - Append the "skip" flag (-s or --skip) if you want to skip poster application.
"""

# file formats that will work with Plex (several are not listed in Plex's documentation but still work)
file_formats = ('.bmp', '.gif', '.jpe', '.jpeg', '.jpg', '.png', '.tbn', '.tif', '.tiff', '.webp')

# characters to replace in the collection name when comparing it to the filename using regex substitution
file_formatting = ('\\\\', '\\/', ':', '\\*', '\\?', '"', '<', '>', '\\|')

# check the arguments if the user is looking to clean posters or not
parser = argparse.ArgumentParser(description="Set Plex collection posters to user provided ones or Shoko's.", formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-c', '--clean', action='store_true', help='if you want to remove old collection posters too')
parser.add_argument('-s', '--skip', action='store_true', help='if you want to skip poster application')
args = parser.parse_args()

plex = cmn.plex_auth() # authenticate and connect to the Plex server/library specified using the credentials from the prefs and the common auth function

# loop through the configured libraries
print('\n╭Shoko Relay: Collection Posters')
for library, section in cmn.plex_library_sections(plex):
    # if the user is looking to clean posters
    if args.clean:
        print(f"├┬Removing Posters @ {cfg.Plex['ServerName']}/{library}")
        try:
            for collection in section.collections():
                # check for multiple custom posters and delete the oldest ones
                if len(collection.posters()) > 2:
                    posters_path = os.path.join(cfg.Plex['DataFolder'], collection.metadataDirectory, 'Uploads', 'posters')
                    for poster in sorted(os.listdir(posters_path), key=lambda poster: os.path.getctime(os.path.join(posters_path, poster)))[:-1]: # list all but the newest poster
                        print(f'│├─Removing: {collection.title} → {poster}')
                        os.remove(os.path.join(posters_path, poster))
            print('│╰─Finished!')
        except Exception as error:
            print(f'│├{cmn.err}Failed', error)
    if not args.skip:
        shoko_key = cmn.shoko_auth() # grab a Shoko API key using the credentials from the prefs and the common auth function

        # make a list of all the user defined collection posters (if any)
        if cfg.Plex['PostersFolder']:
            user_posters = []
            try:
                for file in os.listdir(cfg.Plex['PostersFolder']):
                    if file.lower().endswith(file_formats): user_posters.append(file) # check image files regardless of case
            except Exception as error:
                print(f'╰{cmn.err}Failed', error)
                exit(1)

        print(f"├┬Applying Posters @ {cfg.Plex['ServerName']}/{library}")
        # loop through Plex collections grabbing their names to compare to Shoko's group names and user defined poster names
        for collection in section.collections():
            # check for user defined posters first
            fallback = True
            if cfg.Plex['PostersFolder']:
                try:
                    for user_poster in user_posters:
                        tile_formatted = collection.title
                        for key in file_formatting:
                            tile_formatted = re.sub(key, '', tile_formatted)
                        if os.path.splitext(user_poster)[0] == tile_formatted:
                            print(f'│├─Relaying: {user_poster} → {collection.title}')
                            collection.uploadPoster(filepath=os.path.join(cfg.Plex['PostersFolder'], user_poster))
                            fallback = False # don't fallback to the Shoko group if user poster found
                            continue
                except Exception as error:
                    print(f'│├{cmn.err}──Failed', error)

            # fallback to Shoko group posters if no user defined poster
            if fallback:
                try:
                    group_search = requests.get(f"http://{cfg.Shoko['Hostname']}:{cfg.Shoko['Port']}/api/v3/Group?pageSize=1&page=1&includeEmpty=false&randomImages=false&topLevelOnly=true&startsWith={urllib.parse.quote(collection.title)}&apikey={shoko_key}").json()
                    shoko_poster = group_search['List'][0]['Images']['Posters'][0]
                    poster_url = f"http://{cfg.Shoko['Hostname']}:{cfg.Shoko['Port']}/api/v3/Image/{shoko_poster['Source']}/Poster/{shoko_poster['ID']}"
                    print(f"│├─Relaying: Shoko/{shoko_poster['Source']}/{shoko_poster['ID']} → {collection.title}")
                    collection.uploadPoster(url=poster_url)
                except Exception:
                    print(f'│├{cmn.err}──Failed: No Shoko Group → {collection.title}')
        print('│╰─Finished!')
print('╰Posters Task Complete')
