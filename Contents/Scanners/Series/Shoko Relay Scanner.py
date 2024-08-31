import os, sys, json, urllib, inspect, urllib2, logging, logging.handlers
import Media, Stack, VideoFiles

Prefs = {
    'Hostname': '127.0.0.1',
    'Port': 8111,
    'Username': 'Default',
    'Password': '',
    # SingleSeasonOrdering set to "True" to ignore TMDB season ordering (must be Changed in Agent settings too)
    'SingleSeasonOrdering': False
}

API_KEY = ''

# Setup the logger
Log = logging.getLogger('main')
Log.setLevel(logging.DEBUG)

# Define the path the logs should save to
LOG_ROOT = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), '..', '..', 'Logs'))
if not os.path.isdir(LOG_ROOT):
    path_location = {
        'Windows' : '%LOCALAPPDATA%\\Plex Media Server',
        'MacOSX'  : '$HOME/Library/Application Support/Plex Media Server',
        'Linux'   : '$PLEX_HOME/Library/Application Support/Plex Media Server',
        'Android' : '/storage/emulated/0/Plex Media Server'
    }
    LOG_ROOT = os.path.expandvars(path_location[Platform.OS.lower()] if Platform.OS.lower() in path_location else '~') # Platform.OS:  Windows, MacOSX, or Linux

# Define logger parameters with a max size of 12MiB and five backups for file rotation
def set_logging(foldername='', filename='', format=''):
    foldername = os.path.join(LOG_ROOT, '')
    filename   = 'Shoko Relay Scanner.log'
    format     = '%(asctime)s : %(levelname)s - %(message)s'
    handler = logging.handlers.RotatingFileHandler(os.path.join(foldername, filename), maxBytes=12*1024*1024, backupCount=5)
    handler.setFormatter(logging.Formatter(format))
    handler.setLevel(logging.DEBUG)
    Log.addHandler(handler)

set_logging() # Start logger

def GetApiKey():
    global API_KEY
    if not API_KEY:
        data = json.dumps({
            'user'   : Prefs['Username'],
            'pass'   : Prefs['Password'] if Prefs['Password'] != None else '',
            'device' : 'Shoko Relay for Plex'
        })
        resp = HttpPost('api/auth', data)['apikey']
        # Log.debug('Got API Key:              %s' % resp) # Not needed
        API_KEY = resp
        return resp
    return API_KEY

def HttpPost(url, postdata):
    myheaders = {'Content-Type': 'application/json'}
    req = urllib2.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders)
    return json.load(urllib2.urlopen(req, postdata))

def HttpReq(url, retry=True):
    global API_KEY
    Log.info(' Requesting:               %s' % url)
    myheaders = {'Accept': 'application/json', 'apikey': GetApiKey()}
    try:
        req = urllib2.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders)
        return json.load(urllib2.urlopen(req))
    except Exception as e:
        if not retry: raise e
        API_KEY = ''
        return HttpReq(url, False)

def Scan(path, files, mediaList, subdirs, language=None, root=None):
    if path  : Log.debug('[Path]                    %s' % path)
    if files : Log.debug('[Files]                   %s' % ', '.join(files))

    for subdir in subdirs: Log.debug('[Folder]                  %s' % os.path.relpath(subdir, root))
    Log.info('===========================[Shoko Relay Scanner v1.2.6]' + '=' * 245)

    if files:
        # Scan for video files
        VideoFiles.Scan(path, files, mediaList, subdirs, root)

        for idx, file in enumerate(files):
            try:
                Log.info(' File:                     %s' % file)

                # Get file data using the filename
                filename = os.path.join(os.path.split(os.path.dirname(file))[-1], os.path.basename(file)) # Parent folder + file name
                file_data = HttpReq('api/v3/File/PathEndsWith/%s' % (urllib.quote(filename))) # http://127.0.0.1:8111/api/v3/File/PathEndsWith/Kowarekake%20no%20Orgel%5CKowarekake%20no%20Orgel%20-%2001.mkv

                # Take the first file from the search - Searching with both parent folder and filename should only return a single result
                if len(file_data) == 1:
                    file_data = file_data[0]
                elif len(file_data) > 1: # This will usually trigger for edge cases where the user only uses season subfolders coupled with file name that only use episode and season numbers
                    Log.error('Multiple Files:           File Search Returned More Than One Result - Skipping!')
                    continue
                else: # This will usually trigger if files are scanned by Plex before they are hashed in Shoko
                    Log.error('Missing File:             File Search Returned No Results - Skipping!')
                    continue

                # Take the first series id from the file - Make sure a series id exists
                if try_get(file_data['SeriesIDs'], 0, None):
                    series_id = file_data['SeriesIDs'][0]['SeriesID']['ID'] # Take the first matching anime in case of crossover episodes
                else:
                    Log.error('Missing ID:               Unrecognized or Ignored File Detected - Skipping!')
                    continue

                # Get series data using the series id
                series_data = HttpReq('api/v3/Series/%s?includeDataFrom=AniDB,TMDB' % series_id) # http://127.0.0.1:8111/api/v3/Series/24?includeDataFrom=AniDB,TMDB

                # Get the preferred/overridden title (preferred title follows Shoko's language settings)
                show_title = series_data['Name'].encode('utf-8') # Requires utf-8
                Log.info(' Title [ShokoID]:          %s [%s]' % (show_title, series_id))

                # If SingleSeasonOrdering isn't enabled determine the TMDB type
                tmdb_type, tmdb_title = None, ''
                if not Prefs['SingleSeasonOrdering']:
                    if   try_get(series_data['TMDB']['Shows'], 0, None)  : tmdb_type = 'Shows'
                    elif try_get(series_data['TMDB']['Movies'], 0, None) : tmdb_type = 'Movies'
                    if tmdb_type: # If TMDB type is populated add the title as a comparison to the regular one to help spot mismatches
                        tmdb_title, tmdb_id = try_get(series_data['TMDB'][tmdb_type][0], 'Title', None), try_get(series_data['TMDB'][tmdb_type][0], 'ID', None)
                        if not tmdb_title: tmdb_title = 'N/A (CRITICAL: Removed from TMDB or Missing Data) - Falling Back to AniDB Ordering!' # Account for rare cases where Shoko has a TMDB ID that returns no data
                        Log.info(' TMDB Check (Title [ID]):  %s [%s]' % (tmdb_title, tmdb_id))

                # Get episode data
                episode_multi = len(file_data['SeriesIDs'][0]['EpisodeIDs']) # Account for multi episode files
                for episode in range(episode_multi):
                    episode_id   = file_data['SeriesIDs'][0]['EpisodeIDs'][episode]['ID']
                    episode_data = HttpReq('api/v3/Episode/%s?includeDataFrom=AniDB,TMDB' % episode_id) # http://127.0.0.1:8111/api/v3/Episode/212?includeDataFrom=AniDB,TMDB
                    tmdb_ep_data = try_get(episode_data['TMDB']['Episodes'], 0, None)

                    # Ignore multi episode files of differing types (AniDB episode relations)
                    if episode > 0 and episode_type != episode_data['AniDB']['Type']: continue

                    # Get episode type
                    episode_type = episode_data['AniDB']['Type']

                    # Get season and episode numbers
                    episode_source, season = '(AniDB):', 0
                    if   episode_type == 'Normal'    : season =  1
                    elif episode_type == 'Special'   : season =  0
                    elif episode_type == 'ThemeSong' : season = -1
                    elif episode_type == 'Trailer'   : season = -2
                    elif episode_type == 'Parody'    : season = -3
                    elif episode_type == 'Other'     : season = -4
                    if tmdb_title and tmdb_ep_data: # Grab TMDB info when SingleSeasonOrdering isn't enabled and there is a populated TMDB Episodes match
                        episode_source, season, episode_number = '(TMDB): ', tmdb_ep_data['SeasonNumber'], tmdb_ep_data['EpisodeNumber']
                    else: episode_number = episode_data['AniDB']['EpisodeNumber'] # Fallback to AniDB info

                    Log.info(' Season %s           %s' % (episode_source, season))
                    Log.info(' Episode %s          %s' % (episode_source, episode_number))

                    vid = Media.Episode(show_title, season, episode_number)
                    if episode_multi > 1: vid.display_offset = (episode * 100) / episode_multi # Required for multi episode files
                    Log.info(' Mapping:                  %s' % vid)
                    Log.info('-' * 300)
                    vid.parts.append(file)
                    mediaList.append(vid)
            except Exception as e:
                Log.error('Error in Scan:             "%s"' % e)
                continue

        Stack.Scan(path, files, mediaList, subdirs)

    if not path: # If current folder is root folder
        Log.info(' Initiating Global Subfolder Scan & Plex Grouping Removal') # Log once during the root scan
        Log.info('=' * 300)
        subfolders = subdirs[:]

        while subfolders: # Subfolder scanning queue
            full_path = subfolders.pop(0)
            path = os.path.relpath(full_path, root)
            Log.info(' Subfolder Scan:           %s' % full_path)

            subdir_dirs, subdir_files = [], []
            for file in os.listdir(full_path):
                path_item = os.path.join(full_path, file)
                if os.path.isdir(path_item): subdir_dirs.append(path_item)
                else: subdir_files.append(path_item)

            if subdir_dirs: Log.info(' Subdirectories:           %s' % ', '.join(subdir_dirs))

            for dir in subdir_dirs:
                subfolders.append(dir)
                Log.info(' Added to Scan:            %s' % dir) # Add the subfolder to subfolder scanning queue

            grouping_dir = full_path.rsplit(os.sep, full_path.count(os.sep)-1-root.count(os.sep))[0]
            if subdir_files and (len(list(reversed(path.split(os.sep))))>1 or subdir_dirs):
                Log.info(' Files Detected:           Subfolder Scan & Plex Grouping Removal Initiated in Current Folder')
                if grouping_dir in subdirs: subdirs.remove(grouping_dir) # Prevent group folders from being called by Plex normal call to Scan()
                Log.info('-' * 300)
                # Relative path for dir or it will group multiple series into one as before and no empty subdirs array because they will be scanned afterwards
                Scan(path, sorted(subdir_files), mediaList, [], language, root)

def try_get(arr, idx, default=''):
    try:    return arr[idx]
    except: return default
