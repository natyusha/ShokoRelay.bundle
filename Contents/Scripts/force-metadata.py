#!/usr/bin/env python
from plexapi.myplex import MyPlexAccount
import config as cfg
import sys

r"""
Description:
  - This script uses the Python-PlexAPI to force all metadata in your anime library to update to Shoko's bypassing Plex's caching or other issues.
  - Any unused posters or empty collections will be removed from your library automatically while also updating negative season names and collection sort titles.
  - After making sweeping changes to the metadata in Shoko (like collections or title languages) this is a great way to ensure everything updates correctly in Plex.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Plex, ShokoRelay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex credentials into config.py.
  - If your anime is split across multiple libraries they can all be added in a python list under Plex "LibraryNames".
      - It must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies']"
Usage:
  - Run in a terminal (force-metadata.py) to remove empty collections, rename negative seasons and normalise sort titles.
  - Append the argument "full" (force-metadata.py full) if you want to do the time consuming full metadata clean up.
  - Important: In "full" mode you must wait until the Plex activity queue is fully completed before advancing to the next step (with the enter key) or this will not function correctly.
      - You can tell if Plex is done by looking at the library in the desktop/web client or checking the logs in your "PMS Plugin Logs" folder for activity.
      - This may take a significant amount of time to complete with a large library so it is recommended to run the first step overnight.
Behaviour:
  - This script will ignore locked fields/posters assuming that the user wants to keep them intact.
  - Manually merged series will not be split apart and may need to be handled manually to correctly refresh their metadata.
  - If the main title of an anime was changed on AniDB or overridden in Shoko after it was first scanned into Plex it might fail to match using this method.
      - In these cases the original title will be output to the console for the user to fix with a Plex dance or manual match.
  - Video preview thumbnails and watched states are maintained with this script (unless an anime encounters the above naming issue).
  - Negative seasons like "Season -1" which contain Credits, Trailers, Parodies etc. will have their names updated to reflect their contents.
  - The "Sort Title" for all collections will be set to match the current title to avoid Plex's custom sorting rules e.g. ignoring "The" or "A"
  - All Smart Collection are ignored as they are not managed by Shoko Relay
"""

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# check the arguments if the user is looking to run a full clean or not
full_clean = False
if len(sys.argv) == 2:
    if sys.argv[1].lower() == 'full': # if the first argument is 'full'
        full_clean = True
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

try:
    plex = admin.resource(cfg.Plex['ServerName']).connect()
except Exception:
    print(f'{error_prefix}Failed: Server Name Not Found')
    exit(1)

# loop through the configured libraries
print_f('\n┌ShokoRelay: Force Plex Metadata')
for library in cfg.Plex['LibraryNames']:
    try:
        anime = plex.library.section(library)
    except Exception as error:
        print(f'├{error_prefix}Failed', error)
        continue

    ## if running a full scan execute the next 3 steps
    if full_clean:
        """ not fully compatible with files that were added through shoko relay scanner's subfolder scanner queue
        # split apart any merged series to allow each part to receive updated metadata
        print_f(f'├┬Queueing Splits @ {cfg.Plex["ServerName"]}/{library}')
        for series in anime.search(title=''):
            print_f(f'│├─Splitting: {series.title}')
            series.split()
        input('│└─Splitting Queued: Press Enter to continue once Plex is finished...')
        """

        # unmatch all anime to clear out bad metadata
        print_f(f'├┬Queueing Unmatches @ {cfg.Plex["ServerName"]}/{library}')
        for series in anime.search(title=''):
            print_f(f'│├─Unmatch: {series.title}')
            series.unmatch()
        input('│└─Unmatching Queued: Press Enter to continue once Plex is finished...')

        # clean bundles of things unmatched
        print_f('├┬Cleaning Bundles...')
        plex.library.cleanBundles()
        input('│└─Clean Bundles Queued: Press Enter to continue once Plex is finished...')

        # fix match for all anime and grab fresh metadata
        print_f(f'├┬Queueing Matches @ {cfg.Plex["ServerName"]}/{library}')
        for series in anime.search(title=''):
            print_f(f'│├─Match: {series.title}')
            relay = series.matches(agent='shokorelay', title=series.title, year='')
            try:
                failed_list = []
                series.fixMatch(auto=False, agent='shokorelay', searchResult=relay[0])
            except IndexError:
                print_f(f'│├{error_prefix}Failed: {series.title}') # print titles of things which failed to match
                failed_list.append(series.title)
        input('│└─Matching Queued: Press Enter to continue once Plex is finished...')

    # rename negative seasons to their correct names
    print_f(f'├┬Renaming Negative Seasons @ {cfg.Plex["ServerName"]}/{library}')
    for season in anime.searchSeasons(title=''):
        if   season.title in ('Season -1', '[Unknown Season]'): season.editTitle('Credits')
        elif season.title == 'Season -2': season.editTitle('Trailers')
        elif season.title == 'Season -3': season.editTitle('Parodies')
        elif season.title == 'Season -4': season.editTitle('Other')
    print_f('│└─Finished Renaming Seasons!')

    # clear any empty collections that are left over and set the sort title to match the title
    print_f(f'├┬Checking Collections @ {cfg.Plex["ServerName"]}/{library}')
    for collection in anime.collections():
        if not collection.smart: # ignore any smart collections as they are not managed by Shoko Relay
            if collection.childCount != 0:
                if collection.title != collection.titleSort:
                    collection.editSortTitle(collection.title, locked=True)
                    print_f(f'│├─Correcting Sort Title: {collection.title}')
                continue
            else:
                collection.delete()
                print_f(f'│├─Deleting Empty Entry: {collection.title}')
    print_f('│└─Finished!')
print_f('└Force Metadata Task Complete')

# if there were failed matches list them so the user doesn't have to scroll up
if full_clean and failed_list:
    print_f('\nThe following series failed to match:')
    for failed in failed_list: print_f(f'{failed}')
