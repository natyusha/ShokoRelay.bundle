#!/usr/bin/env python3
import argparse
import config as cfg; import common as cmn

r"""
Description:
  - This script uses the Python-PlexAPI to force all metadata in your anime library to update to Shoko's bypassing Plex's caching or other issues.
  - Any unused posters or empty collections will be removed from your library automatically while also updating negative season names, collection sort titles and original titles.
  - After making sweeping changes to the metadata in Shoko (like collections or title languages) this is a great way to ensure everything updates correctly in Plex.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Plex, Shoko Relay, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Plex credentials into config.py.
  - If your anime is split across multiple libraries they can all be added in a python list under Plex "LibraryNames".
      - It must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies']"
Usage:
  - Run in a terminal (force-metadata.py) to remove empty collections, normalise collection sort titles, rename negative seasons and add original titles in Plex.
  - Append the "dance" flag (-d or --dance) if you want to do a time consuming full metadata clean up (Plex dance).
      - This will ask for (Y/N) confirmation for each configured library.
  - Important: In "dance" mode you must wait until the Plex activity queue is fully completed before advancing to the next step (with the enter key) or this will not function correctly.
      - You can tell if Plex is done by looking at the library in the desktop/web client or checking the logs in your "PMS Plugin Logs" folder for activity.
      - This may take a significant amount of time to complete with a large library so it is recommended to run the first step overnight.
   - All operations including a dance can be limited to select titles with the "-t" flag (force-metadata.py -t "TITLE")
   - Confirmation prompts can be bypassed by adding the "force" flag (-f or --force).
Behaviour:
  - This script will ignore locked fields/posters assuming that the user wants to keep them intact.
  - Manually merged series will not be split apart and may need to be handled manually to correctly refresh their metadata.
  - If the main title of an anime was changed on AniDB or overridden in Shoko after it was first scanned into Plex it might fail to match using this method.
      - In these cases the original title will be output to the console for the user to fix with a Plex dance or manual match.
  - Video preview thumbnails and watched states are maintained with this script (unless an anime encounters the above naming issue).
  - The "Original Title" for all series will be set using info Shoko Relay added to the "Sort Title" (if available).
  - Negative seasons like "Season -1" which contain Credits, Trailers, Parodies etc. will have their names updated to reflect their contents.
  - The "Sort Title" for all collections will be set to match the current title to avoid Plex's custom sorting rules e.g. ignoring "The" or "A"
  - All Smart Collections are ignored as they are not managed by Shoko Relay
"""

# check the arguments if the user is looking to run a full clean or not
note   = 'IMPORTANT: In "dance" mode you must wait until the Plex activity queue is fully completed before advancing to the next step (with the enter key) or this script will not function correctly. By limiting the operation with the "-t" flag you can do a full cleanup on filtered series only.'
parser = argparse.ArgumentParser(description='Remove empty collections, normalise collection sort titles, rename negative seasons and add original titles in Plex.', epilog=note, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-d', '--dance', action='store_true', help='If you want to do a time consuming full metadata clean up (Plex dance)')
parser.add_argument('-f', '--force', action='store_true', help='ignore user confirmation prompts when running a dance')
parser.add_argument('-t', '--target', type=str, metavar='STR', default='', help='limit operations to series titles matching the entered string "STR"')
args, failed_list, collection_count = parser.parse_args(), [], {}

plex = cmn.plex_auth() # authenticate and connect to the Plex server/library specified using the credentials from the prefs and the common auth function

# loop through the configured libraries
print('\n╭Shoko Relay: Force Plex Metadata')
if args.target: print(f'├─Operations limited to the following title filter: "{args.target}"')
for library in cfg.Plex['LibraryNames']:
    try:
        section = plex.library.section(library)
    except Exception as error:
        print(f'├{cmn.err}Failed', error)
        continue

    ## if running a full scan execute the next 3 steps
    if args.dance and section.search(title=args.target):
        if cmn.confirmation(f'├─Initiate a potentially time consuming Plex Dance™ for {cfg.Plex["ServerName"]}/{library}: (Y/N) ', args.force):
            """ not fully compatible with files that were added through Shoko Relay scanner's subfolder scanner queue
            # split apart any merged series to allow each part to receive updated metadata
            print(f'├┬Queueing Splits @ {cfg.Plex["ServerName"]}/{library}')
            for series in section.search(title=args.target):
                print(f'│├─Splitting: {series.title}')
                series.split()
            input('│╰─Splitting Queued: Press Enter to continue once Plex is finished...')
            """

            # unmatch all/filtered anime to clear out bad metadata
            print(f'├┬Queueing Unmatches @ {cfg.Plex["ServerName"]}/{library}')
            for series in section.search(title=args.target):
                try:
                    series.unmatch()
                    print(f'│├─Unmatch: {series.title}')
                except Exception:
                    print(f'│{cmn.err}─Failed Unmatch: {series.title}') # print titles of things which failed to unmatch
                    failed_list.append(f'Unmatch: {series.title}')
            input('│╰─Unmatching Queued: Press Enter to continue once Plex is finished...')

            # clean bundles for unmatched series
            print('├┬Cleaning Bundles...')
            plex.library.cleanBundles()
            input('│╰─Clean Bundles Queued: Press Enter to continue once Plex is finished...')

            # fix match for unmatched series and grab fresh metadata
            print(f'├┬Queueing Matches @ {cfg.Plex["ServerName"]}/{library}')
            for series in section.search(title=args.target):
                relay = series.matches(agent='shokorelay', title=cmn.revert_title(series.title), year='') # revert any common title prefix modifications for the match
                try:
                    series.fixMatch(auto=False, agent='shokorelay', searchResult=relay[0])
                    print(f'│├─Match: {series.title}')
                except IndexError:
                    print(f'│{cmn.err}─Failed Match: {series.title}') # print titles of things which failed to match
                    failed_list.append(f'Match: {series.title}')
            input('│╰─Matching Queued: Press Enter to continue once Plex is finished...')
        else: print(f'{cmn.err}──Operation Aborted!')

    # rename negative seasons to their correct names
    print(f'├┬Renaming Negative Seasons @ {cfg.Plex["ServerName"]}/{library}')
    for season in section.searchSeasons(title=args.target):
        if   season.title in ('Season -1', '[Unknown Season]'): season.editTitle('Credits')
        elif season.title == 'Season -2': season.editTitle('Trailers')
        elif season.title == 'Season -3': season.editTitle('Parodies')
        elif season.title == 'Season -4': season.editTitle('Other')
    print('│╰─Finished Renaming Seasons!')

    # add original titles if there are sort title additions from Shoko Relay
    print(f'├┬Adding Original Titles @ {cfg.Plex["ServerName"]}/{library}')
    for series in section.search(title=args.target):
        if series.title != series.titleSort: series.editOriginalTitle(series.titleSort.replace(series.title + ' [', '')[:-1], locked=False)
    print('│╰─Finished Adding Original Titles!')

    # clear any empty collections that are left over and set the sort title to match the title
    print(f'├┬Checking Collections @ {cfg.Plex["ServerName"]}/{library}')
    for collection in section.collections():
        if collection.smart: continue # ignore any smart collections as they are not managed by Shoko Relay
        if collection.title not in collection_count: collection_count[collection.title] = 0
        collection_count[collection.title] += collection.childCount # tabulate the item count for all collections by title
        if collection.childCount != 0:
            if collection.title != collection.titleSort:
                collection.editSortTitle(collection.title, locked=True)
                print(f'│├─Correcting Sort Title: {collection.title}')
            continue
        else:
            collection.delete()
            print(f'│├─Deleting Empty Entry: {collection.title}')
    print('│╰─Finished!')
print('╰Force Metadata Task Complete')

# if there are collections with only a single item in them across the configured libraries list them
single_series_collections = [(title, count) for title, count in collection_count.items() if count == 1]
if single_series_collections:
    print('\nThe following collections only have a single series present:')
    for title, _ in single_series_collections: print(f'{title}')

# if there were failed matches list them so the user doesn't have to scroll up
if args.dance and failed_list:
    print('\nThe following series failed to match:')
    for failed in failed_list: print(f'{failed}')
