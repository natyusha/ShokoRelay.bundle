import os, sys, json, urllib, inspect, urllib2, logging, logging.handlers
import Media, Stack, VideoFiles, ConfigParser

# Load Shoko's credentials and the SingleSeasonOrdering preference from the external configuration file
cfg = ConfigParser.RawConfigParser()
cfg.read(os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), '.', 'Shoko Relay Scanner.cfg')))

API_KEY = '' # Leave this blank

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
    LOG_ROOT = os.path.expandvars(path_location[Platform.OS.lower()] if Platform.OS.lower() in path_location else '~') # Platform.OS: Windows, MacOS, or Linux

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
            'user'   : cfg.get('Prefs', 'Username'),
            'pass'   : cfg.get('Prefs', 'Password') if cfg.get('Prefs', 'Password') != None else '',
            'device' : 'Shoko Relay for Plex'
        })
        API_KEY = HttpPost('api/auth', data)['apikey']
        # Log.debug('Got API Key:              %s' % API_KEY) # Not needed
    return API_KEY

def HttpPost(url, postdata):
    myheaders = {'Content-Type': 'application/json'}
    req = urllib2.Request('http://%s:%s/%s' % (cfg.get('Prefs', 'Hostname'), cfg.get('Prefs', 'Port'), url), headers=myheaders)
    return json.load(urllib2.urlopen(req, postdata))

def HttpReq(url, retry=True):
    global API_KEY
    Log.info(' Requesting:               %s' % url)
    myheaders = {'Accept': 'application/json', 'apikey': GetApiKey()}
    try:
        req = urllib2.Request('http://%s:%s/%s' % (cfg.get('Prefs', 'Hostname'), cfg.get('Prefs', 'Port'), url), headers=myheaders)
        return json.load(urllib2.urlopen(req))
    except Exception as e:
        if not retry: raise e
        API_KEY = ''
        return HttpReq(url, False)

def Scan(path, files, mediaList, subdirs, language=None, root=None):
    if path  : Log.debug('[Path]                    %s' % path)
    if files : Log.debug('[Files]                   %s' % ', '.join(files))

    for subdir in subdirs: Log.debug('[Folder]                  %s' % os.path.relpath(subdir, root))
    ordering = ' Single Season' if cfg.getboolean('Prefs', 'SingleSeasonOrdering') else ' Multi Seasons'
    Log.info('===========================[Shoko Relay Scanner v1.2.26%s]%s' % (ordering, '=' * 230))

    if files:
        # Scan for video files
        VideoFiles.Scan(path, files, mediaList, subdirs, root)
        prev_series_id = None

        for idx, file in enumerate(files):
            try:
                Log.info(' File:                     %s' % file)

                # Get file data using the filename
                filename  = os.path.join(os.path.split(os.path.dirname(file))[-1], os.path.basename(file)) # Parent folder + file name
                file_data = HttpReq('api/v3/File/PathEndsWith/%s' % (urllib.quote(filename))) # http://127.0.0.1:8111/api/v3/File/PathEndsWith/Kowarekake%20no%20Orgel%5CKowarekake%20no%20Orgel%20-%2001.mkv

                # Take the first file from the search - Searching with both parent folder and filename should only return a single result
                if len(file_data) == 1:
                    file_data = file_data[0]
                elif len(file_data) > 1: # This will usually trigger for edge cases where the user only uses season subfolders coupled with file names that only use episode and season numbers
                    Log.error('Multiple Files:           File Search Returned More Than One Result - Skipping!')
                    Log.info('-' * 300)
                    continue
                else: # This will usually trigger if files are scanned by Plex before they are hashed in Shoko
                    Log.error('Missing File:             File Search Returned No Results - Skipping!')
                    Log.info('-' * 300)
                    continue

                # Take the first series id from the file - Make sure a series id exists
                if try_get(file_data['SeriesIDs'], 0, None):
                    series_id = file_data['SeriesIDs'][0]['SeriesID']['ID']  # Take the first matching anime in case of crossover episodes
                    ep_multi  = len(file_data['SeriesIDs'][0]['EpisodeIDs']) # Account for multi episode files
                else:
                    Log.error('Missing ID:               Unrecognized or Ignored File Detected - Skipping!')
                    Log.info('-' * 300)
                    continue

                # Get series data using the series id if it wasn't already retrieved in the previous loop
                if prev_series_id != series_id: series_data = HttpReq('api/v3/Series/%s?includeDataFrom=AniDB,TMDB' % series_id) # http://127.0.0.1:8111/api/v3/Series/24?includeDataFrom=AniDB,TMDB
                prev_series_id = series_id

                # Get the preferred/overridden title (preferred title follows Shoko's language settings)
                title = series_data['Name'].encode('utf-8') # Requires utf-8
                Log.info(' Title [ShokoID]:          %s [%s]' % (title, series_id))

                # Determine the TMDB type
                tmdb_type, tmdb_type_log, tmdb_title = None, '', ''
                if   try_get(series_data['TMDB']['Shows'], 0, None)  : tmdb_type, tmdb_type_log = 'Shows'  , 'tv/'
                elif try_get(series_data['TMDB']['Movies'], 0, None) : tmdb_type, tmdb_type_log = 'Movies' , 'movie/'
                if tmdb_type: # If TMDB type is populated add the title as a comparison to the regular one to help spot mismatches
                    tmdb_title, tmdb_id = try_get(series_data['TMDB'][tmdb_type][0], 'Title', None), try_get(series_data['TMDB'][tmdb_type][0], 'ID', None)
                    tmdb_title_log = 'N/A (CRITICAL: Removed from TMDB or Missing Data) - Falling Back to AniDB Ordering!' if not tmdb_title else tmdb_title # Account for rare cases where Shoko has a TMDB ID that returns no data
                    Log.info(' TMDB Check (Title [ID]):  %s [%s%s]' % (tmdb_title_log, tmdb_type_log, tmdb_id))

                prev_season, prev_episode, ep_part = None, None, 0
                for ep in range(ep_multi):
                    # Get episode data
                    ep_id         = file_data['SeriesIDs'][0]['EpisodeIDs'][ep]['ID']
                    ep_data       = HttpReq('api/v3/Episode/%s?includeDataFrom=AniDB,TMDB' % ep_id) # http://127.0.0.1:8111/api/v3/Episode/212?includeDataFrom=AniDB,TMDB
                    tmdb_ep_group = len(ep_data['IDs']['TMDB']['Episode']) or 1 if not cfg.getboolean('Prefs', 'SingleSeasonOrdering') else 1 # Account for TMDB episode groups if SingleSeasonOrdering isn't disabled

                    if ep_data['IsHidden']:
                        Log.info(' Skipping Ignored Ep [ID]: An episode that is marked as hidden in Shoko was detected! [%s]' % ep_data['IDs']['ID'])
                        Log.info('-' * 300)
                        continue

                    for group in range(tmdb_ep_group):
                        ep_type, tmdb_ep_data = ep_data['AniDB']['Type'], try_get(ep_data['TMDB']['Episodes'], group, None) if tmdb_title else None

                        # Ignore multi episode files of differing types (AniDB episode relations) if they are not ThemeSongs
                        if ep > 0 and ep_type != prev_ep_type and ep_type != 'ThemeSong' != prev_ep_type:
                            Log.info(' Skipping Multi Ep File:   An AniDB episode relation of a differing type was detected! [%s -> %s]' % (prev_ep_type, ep_type))
                            continue
                        prev_ep_type, ep_multi_log = ep_type, ' (Multi Episode File Detected!)' if ep_multi > 1 else ''

                        # Get season and episode numbers
                        ep_source, season, episode = '(AniDB):         ', 0, ep_data['AniDB']['EpisodeNumber']
                        if   ep_type == 'Normal'    : season =  1
                        elif ep_type == 'Special'   : season =  0
                        elif ep_type == 'ThemeSong' : season = -1
                        elif ep_type == 'Trailer'   : season = -2
                        elif ep_type == 'Parody'    : season = -3
                        elif ep_type == 'Other'     : season = -4
                        if not cfg.getboolean('Prefs', 'SingleSeasonOrdering') and tmdb_ep_data: ep_source, season, episode = '(TMDB Ep Group): ' if tmdb_ep_group > 1 else '(TMDB):          ', tmdb_ep_data['SeasonNumber'], tmdb_ep_data['EpisodeNumber'] # Grab TMDB info when possible and SingleSeasonOrdering is disabled

                        # Ignore the current file if it has already been added with the same season and episode number
                        if prev_season == season and prev_episode == episode:
                            Log.info(' Skipping Multi Ep File:   A duplicate season and episode number was detected! [S%sE%s]' % (season, episode))
                            continue
                        prev_season, prev_episode = season, episode

                        Log.info(' Season  %s %s%s' % (ep_source, season , ep_multi_log))
                        Log.info(' Episode %s %s%s' % (ep_source, episode, ep_multi_log))

                        ep_parts_total, ep_final = ep_multi * tmdb_ep_group, Media.Episode(title, season, episode)
                        # The display offset is equal to the part count's percentage of the total parts (required for multi episode files and/or TMDB episode groups)
                        if ep_parts_total > 1: ep_final.display_offset, ep_part = (ep_part * 100) / ep_parts_total, ep_part + 1
                        Log.info(' Mapping:                  %s' % ep_final)
                        ep_final.parts.append(file)
                        mediaList.append(ep_final)
                    Log.info('-' * 300)
            except Exception as e:
                Log.error('Error in Scan:            (%s)' % e)
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
