import os, sys, json, urllib, inspect, urllib2, logging, logging.handlers
import Media, Stack, VideoFiles

Prefs = {
    'Hostname': '127.0.0.1',
    'Port': 8111,
    'Username': 'Default',
    'Password': '',
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
        'Windows': '%LOCALAPPDATA%\\Plex Media Server',
        'MacOSX':  '$HOME/Library/Application Support/Plex Media Server',
        'Linux':   '$PLEX_HOME/Library/Application Support/Plex Media Server',
        'Android': '/storage/emulated/0/Plex Media Server'
    }
    LOG_ROOT = os.path.expandvars(path_location[Platform.OS.lower()] if Platform.OS.lower() in path_location else '~') # Platform.OS:  Windows, MacOSX, or Linux

# Define logger parameters with a max size of 12MiB and five backups for file rotation
def set_logging(foldername='', filename='', format=''):
    foldername = os.path.join(LOG_ROOT, '')
    filename = 'Shoko Relay Scanner.log'
    format = '%(asctime)s %(message)s'
    handler = logging.handlers.RotatingFileHandler(os.path.join(foldername, filename), maxBytes=12*1024*1024, backupCount=5)
    handler.setFormatter(logging.Formatter(format))
    handler.setLevel(logging.DEBUG)
    Log.addHandler(handler)

set_logging() # Start logger

def GetApiKey():
    global API_KEY
    if not API_KEY:
        data = json.dumps({
            'user': Prefs['Username'],
            'pass': Prefs['Password'] if Prefs['Password'] != None else '',
            'device': 'Shoko Relay for Plex'
        })
        resp = HttpPost('api/auth', data)['apikey']
        # Log.debug('Got API Key:     %s' % resp) # Not needed
        API_KEY = resp
        return resp
    return API_KEY

def HttpPost(url, postdata):
    myheaders = {'Content-Type': 'application/json'}
    req = urllib2.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders)
    return json.load(urllib2.urlopen(req, postdata))

def HttpReq(url, retry=True):
    global API_KEY
    Log.info('Requesting:      %s' % url)
    myheaders = {'Accept': 'application/json', 'apikey': GetApiKey()}
    try:
        req = urllib2.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders)
        return json.load(urllib2.urlopen(req))
    except Exception, e:
        if not retry:
            raise e
        API_KEY = ''
        return HttpReq(url, False)

def Scan(path, files, mediaList, subdirs, language=None, root=None):
    Log.debug('[Path]           %s', path)
    Log.debug('[Files]          %s', files)

    for subdir in subdirs: Log.debug('[Folder]         %s' % os.path.relpath(subdir, root))
    Log.info('=' * 400)

    if files:
        # Scan for video files
        VideoFiles.Scan(path, files, mediaList, subdirs, root)

        for idx, file in enumerate(files):
            try:
                Log.info('File:            %s' % file)

                # Get file data using the filename
                filename = os.path.join(os.path.split(os.path.dirname(file))[-1], os.path.basename(file)) # Parent folder + file name
                file_data = HttpReq('api/v3/File/PathEndsWith/%s' % (urllib.quote(filename))) # http://127.0.0.1:8111/api/v3/File/PathEndsWith/Kowarekake%20no%20Orgel%5CKowarekake%20no%20Orgel%20-%2001.mkv
                if len(file_data) == 0: continue # Skip if file data is not found

                # Take the first file - Searching with both parent folder and filename should only return a single result
                if len(file_data) > 1:
                    Log.info('Multiple Files:  File Search Detected More Than One Result - Skipping!')
                    continue

                file_data = file_data[0]

                # Ignore unrecognized files
                if 'SeriesIDs' not in file_data or file_data['SeriesIDs'] is None:
                    Log.info('Missing ID:      Unrecognized or Ignored File Detected - Skipping!')
                    continue

                # Get series data
                series_ids = try_get(file_data['SeriesIDs'], 0, None)

                if series_ids is None:
                    Log.info('Missing ID:      Unrecognized or Ignored File Detected - Skipping!')
                    continue

                series_id = series_ids['SeriesID']['ID'] # Take the first matching anime in case of crossover episodes
                series_data = HttpReq('api/v3/Series/%s?includeDataFrom=AniDB' % series_id) # http://127.0.0.1:8111/api/v3/Series/24?includeDataFrom=AniDB

                # Get the preferred/overridden title (preferred title follows shoko's language settings)
                show_title = series_data['Name'].encode('utf-8') # Requires utf-8
                Log.info('Title:           %s' % show_title)

                # Get episode data
                episode_multi = len(file_data['SeriesIDs'][0]['EpisodeIDs']) # Account for multi episode files
                for episode in range(episode_multi):
                    episode_id = file_data['SeriesIDs'][0]['EpisodeIDs'][episode]['ID']
                    episode_data = HttpReq('api/v3/Episode/%s?includeDataFrom=AniDB,TvDB' % episode_id) # http://127.0.0.1:8111/api/v3/Episode/212?includeDataFrom=AniDB,TvDB

                    # Ignore multi episode files of differing types (anidb episode relations)
                    if episode > 0 and episode_type != episode_data['AniDB']['Type']: continue

                    # Get episode type
                    episode_type = episode_data['AniDB']['Type']

                    # Get season and episode numbers
                    episode_source, season = '(AniDB):', 0
                    if episode_type   == 'Normal'    : season =  1
                    elif episode_type == 'Special'   : season =  0
                    elif episode_type == 'ThemeSong' : season = -1
                    elif episode_type == 'Trailer'   : season = -2
                    elif episode_type == 'Parody'    : season = -3
                    elif episode_type == 'Other'     : season = -4
                    if not Prefs['SingleSeasonOrdering'] and try_get(episode_data['TvDB'], 0, None): # Grab TvDB info when SingleSeasonOrdering isn't enabled
                        episode_data['TvDB'] = try_get(episode_data['TvDB'], 0, None)
                        season               = episode_data['TvDB']['Season']
                        episode_number       = episode_data['TvDB']['Number']
                        episode_source       = '(TvDB): '
                    else: episode_number     = episode_data['AniDB']['EpisodeNumber'] # Fallback to AniDB info

                    Log.info('Season %s  %s' % (episode_source, season))
                    Log.info('Episode %s %s' % (episode_source, episode_number))

                    vid = Media.Episode(show_title, season, episode_number)
                    if episode_multi > 1: vid.display_offset = (episode * 100) / episode_multi # Required for multi episode files
                    Log.info('Mapping:         %s' % vid)
                    Log.info('-' * 400)
                    vid.parts.append(file)
                    mediaList.append(vid)
            except Exception as e:
                Log.error('Error in Scan:   "%s"' % e)
                continue

        Stack.Scan(path, files, mediaList, subdirs)

    if not path: # If current folder is root folder
        Log.info('Initiating Global Subfolder Scan & Plex Grouping Removal') # Log once during the root scan
        Log.info('=' * 400)
        subfolders = subdirs[:]

        while subfolders: # Subfolder scanning queue
            full_path = subfolders.pop(0)
            path = os.path.relpath(full_path, root)
            Log.info('Subfolder Scan:  %s' % full_path)

            subdir_dirs, subdir_files = [], []
            for file in os.listdir(full_path):
                path_item = os.path.join(full_path, file)
                if os.path.isdir(path_item): subdir_dirs.append(path_item)
                else: subdir_files.append(path_item)

            if subdir_dirs: Log.info('Subdirectories:  %s' % subdir_dirs)

            for dir in subdir_dirs:
                subfolders.append(dir)
                Log.info('Added to Scan:   %s' % dir) # Add the subfolder to subfolder scanning queue

            grouping_dir = full_path.rsplit(os.sep, full_path.count(os.sep)-1-root.count(os.sep))[0]
            if subdir_files and (len(list(reversed(path.split(os.sep))))>1 or subdir_dirs):
                Log.info('Files Detected:  Subfolder Scan & Plex Grouping Removal Initiated in Current Folder')
                if grouping_dir in subdirs: subdirs.remove(grouping_dir) # Prevent group folders from being called by Plex normal call to Scan()
                Log.info('-' * 400)
                # Relative path for dir or it will group multiple series into one as before and no empty subdirs array because they will be scanned afterwards
                Scan(path, sorted(subdir_files), mediaList, [], language, root)

def try_get(arr, idx, default=''):
    try:    return arr[idx]
    except: return default
