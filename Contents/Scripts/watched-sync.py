#!/usr/bin/env python3
from plexapi.myplex import MyPlexAccount
import re, urllib, argparse, requests
import config as cfg; import common as cmn

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
  - Append the "votes" flag (-v or --votes) to add user ratings/votes to all operations.
  - There are two alternate modes for this script which will ask for (Y/N) confirmation for each configured Plex user.
      - Append the argument "import" (watched-sync.py import) if you want to sync watched states (and votes if enabled) from Shoko to Plex.
      - Append the argument "purge" (watched-sync.py purge) if you want to remove all watched states (and votes if enabled) from the configured Plex libraries.
      - Confirmation prompts can be bypassed by adding the "force" flag (-f or --force).
Behaviour:
  - Due to the potential for losing a huge amount of data, removing watch states or ratings from Plex has been omitted from this script unless "purge" mode is used.
"""

# relative date regex definition and import/purge check for argument type
def arg_parse(arg):
    arg = arg.lower()
    if not re.match('^(?:[1-9]|[1-9][0-9]|[1-9][0-9][0-9])(?:m|h|d|w|mon|y)$', arg) and not re.match('^(?:import|purge)$', arg):
        raise argparse.ArgumentTypeError('invalid range, import or purge')
    return arg


# check the arguments if the user is looking to use a relative date or not
parser = argparse.ArgumentParser(description='Sync watched states from Plex to Shoko.', epilog='NOTE: "import" and "purge" mode will ask for (Y/N) confirmation for each configured Plex user.', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('relative_date', metavar='range | import | purge', nargs='?', type=arg_parse, default='999y', help='range:  Limit the time range (from 1-999) for syncing watched states.\n        *must be the sole argument and is entered as Integer+Suffix\n'
                    '        *the full list of suffixes are:\n         m=minutes\n         h=hours\n         d=days\n         w=weeks\n         mon=months\n         y=years\n\nimport: If you want to sync watched states from Shoko to Plex instead.\n'
                    '        *must be the sole argument and is simply entered as "import"\n\npurge:  If you want to clear all watched states from Plex.\n        *must be the sole argument and is simply entered as "purge"')
parser.add_argument('-v', '--votes', action='store_true', help='include user votes/ratings when syncing, importing or purging')
parser.add_argument('-f', '--force', action='store_true', help='ignore user confirmation prompts when importing or purging')
args, shoko_import, plex_purge = parser.parse_args(), False, False
if   args.relative_date == 'import': shoko_import = True
elif args.relative_date == 'purge':  plex_purge   = True

admin = cmn.plex_auth(connect=False) # authenticate to the Plex server/library specified using the credentials from the prefs and the common auth function

# add the admin account to a list (if it is enabled) then append any other users to it
accounts = [admin] if cfg.Plex['SyncAdmin'] else []
if cfg.Plex['ExtraUsers']:
    try:
        extra_users = [admin.user(username) for username in cfg.Plex['ExtraUsers']]
        data = [admin.query(f'https://plex.tv/api/home/users/{user.id}/switch', method=admin._session.post) for user in extra_users]
        for userID in data: accounts.append(MyPlexAccount(token=userID.attrib.get('authenticationToken')))
    except Exception as error: # if the extra users can't be found show an error and continue
        print(f'{cmn.err}Failed:', error)

if not plex_purge: shoko_key = cmn.shoko_auth() # grab a Shoko API key using the credentials from the prefs and the common auth function (when not purging)

# loop through all of the accounts listed and sync watched states
print('\n╭Shoko Relay Watched Sync')
if shoko_import: # if importing grab the filenames for all the watched episodes in Shoko and add them to a list
    print('├─Generating: Shoko Episode List (Watched)...')
    watched_eps = []
    episodes = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode?pageSize=0&page=1&includeWatched=Only&includeFiles=true&apikey={shoko_key}').json()
    for episode in episodes['List']:
        if episode['Watched']: watched_eps.append(cmn.basename_sep(episode['Files'][0]['Locations'][0]['RelativePath']))
    if args.votes: # if including votes grab the filenames/series names for all the voted episodes/series in Shoko and add them to a list
        print('├─Generating: Shoko Series List (Voted)...')
        series, voted_series = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Series?pageSize=0&page=1&apikey={shoko_key}').json(), {}
        for series in series['List']:
            if series['UserRating']:
                series_eps = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Series/{series["IDs"]["ID"]}/Episode?pageSize=0&page=1&includeFiles=true&apikey={shoko_key}').json()
                voted_series[cmn.basename_sep(series_eps['List'][0]['Files'][0]['Locations'][0]['RelativePath'])] = series['UserRating']['Value']
        print('├─Generating: Shoko Episode List (Voted)...')
        episodes, voted_eps = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode?pageSize=0&page=1&includeVoted=Only&includeFiles=true&apikey={shoko_key}').json(), {}
        for episode in episodes['List']:
            if episode['UserRating']: voted_eps[cmn.basename_sep(episode['Files'][0]['Locations'][0]['RelativePath'])] = episode['UserRating']['Value']

for account in accounts:
    # if importing/purging ask the user to confirm for each username
    query = 'import Shoko watched states and votes to' if args.votes else 'import Shoko watched states to' if shoko_import else 'clear all watched states from'
    if (shoko_import or plex_purge) and cmn.confirmation(f'├──Would you like to {query}: {account} (Y/N) ', args.force, 3): pass
    elif not (shoko_import or plex_purge): pass
    else: continue

    try:
        plex = account.resource(cfg.Plex['ServerName']).connect()
    except Exception as error:
        print(f'╰{cmn.err}Failed:', error)
        exit(1)

    # loop through the configured libraries
    for library in cfg.Plex['LibraryNames']:
        print(f'├┬Querying: {account} @ {cfg.Plex["ServerName"]}/{library}')
        try:
            section = plex.library.section(library)
        except Exception as error:
            print(f'│{cmn.err}─Failed', error)
            continue

        # if importing loop through all the episodes in the Plex library
        if shoko_import: # if an unwatched episode's filename in Plex is found in Shoko's watched episodes list mark it as played
            for episode in section.searchEpisodes(unwatched=True):
                for episode_path in episode.iterParts():
                    filepath = cmn.basename_sep(episode_path.file)
                    if filepath in watched_eps:
                        episode.markPlayed()
                        print(f'│├─Importing: {filepath}')
            if args.votes: # if a rated episode's filename in Plex is found in Shoko's voted episodes or series list update the rating accordingly
                for episode in section.searchEpisodes():
                    for episode_path in episode.iterParts():
                        try:
                            filepath = cmn.basename_sep(episode_path.file)
                            if filepath in voted_series:
                                vote, title = voted_series[filepath], cmn.revert_title(episode.show().title)
                                episode.show().rate(vote)
                                print(f'│├─Rating Series [{vote:04.1f}]: {title}')
                            if filepath in voted_eps:
                                vote = voted_eps[filepath]
                                episode.rate(vote)
                                print(f'│├─Rating Episode [{vote:04.1f}]: {filepath}')
                        except Exception:
                            print(f'│├{cmn.err}─Failed: Make sure that "{filepath}" is matched by Shoko')
        elif plex_purge:
            print('│├─Clearing watched states...')
            for episode in section.searchEpisodes(unwatched=False): episode.markUnplayed()
            if args.votes:
                print('│├─Clearing ratings...')
                for episode in section.searchEpisodes(filters={'userRating>>': 0}): episode.rate(None)
                for series in section.search(filters={'userRating>>': 0}): series.rate(None)
        else:
            # loop through all the watched episodes in the Plex library within the time frame of the relative date
            for episode in section.searchEpisodes(unwatched=False, filters={'lastViewedAt>>': args.relative_date}):
                for episode_path in episode.iterParts():
                    filepath = cmn.basename_sep(episode_path.file) # add a path separator to the filename to avoid duplicate matches
                    path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={shoko_key}').json()
                    try:
                        if path_ends_with[0]['Watched'] is None:
                            print(f'│├─Relaying: {filepath} → {episode.title}')
                            for EpisodeID in path_ends_with[0]['SeriesIDs'][0]['EpisodeIDs']:
                                requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode/{EpisodeID["ID"]}/Watched/true?apikey={shoko_key}')
                    except Exception:
                        print(f'│├{cmn.err}─Failed: Make sure that "{filepath}" is matched by Shoko')
            if args.votes:
                for episode in section.searchEpisodes(filters={'userRating>>': 0}): # loop through all the rated episodes in the Plex library if votes are enabled
                    for episode_path in episode.iterParts():
                        filepath, rating = cmn.basename_sep(episode_path.file), episode.userRating # add a path separator to the filename to avoid duplicate matches
                        path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={shoko_key}').json()
                        try:
                            print(f'│├─Voting Episode [{rating:04.1f}]: {filepath} → {episode.title}')
                            for EpisodeID in path_ends_with[0]['SeriesIDs'][0]['EpisodeIDs']:
                                requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Episode/{EpisodeID["ID"]}/Vote?apikey={shoko_key}', json={'Value': rating})
                        except Exception:
                            print(f'│├{cmn.err}─Failed: Make sure that "{filepath}" is matched by Shoko')
                for series in section.search(filters={'userRating>>': 0}): # sync series level ratings
                    rating, title = series.userRating, cmn.revert_title(series.title) # revert any common title prefix modifications for the match
                    try:
                        filepath = cmn.basename_sep(series.episodes()[0].media[0].parts[0].file) # grab the filepath with path separator for the first episode asociated with the series so it can be used to find the shokoid
                        path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={shoko_key}').json()
                        print(f'│├─Voting Series [{rating:04.1f}]: {filepath} → {title}')
                        requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/Series/{path_ends_with[0]["SeriesIDs"][0]["SeriesID"]["ID"]}/Vote?apikey={shoko_key}', json={'Value': rating})
                    except Exception:
                        print(f'│├{cmn.err}─Failed: Make sure that "{filepath}" is matched by Shoko')
        print('│╰─Finished!')
print('╰Watched Sync Complete')
