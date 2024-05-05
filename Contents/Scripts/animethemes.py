#!/usr/bin/env python3
import os, re, sys, time, urllib, requests, subprocess
import config as cfg

r"""
Description:
  - This script uses the Shoko and AnimeThemes APIs to find the OP/ED for a series and convert it into a Theme.mp3 file which will play when viewing the series in Plex.
  - The default themes grabbed by Plex are limited to 30 seconds long and are completely missing for a massive amount of anime making this a great upgrade to local metadata.
Author:
  - natyusha
Requirements:
  - Python 3.7+, Requests Library (pip install requests), FFmpeg, Shoko Server
Preferences:
  - Before doing anything with this script you must enter your Shoko credentials into config.py.
  - To allow Theme.mp3 files to be used by Plex you must also enable "Local Media Assets" for the libraries that have your Anime in it.
      - The "Play Theme Music" option also has to be enabled in the settings for the Plex client.
Usage:
  - Run in a terminal (animethemes.py) with the working directory set to a folder containing an anime series.
  - If the anime has been matched by Shoko Server it will grab the anidbID and use that to match with an AnimeThemes anime entry.
Behaviour:
  - By default this script will download the first OP (or ED if there is none) for the given series.
  - If "FFplay_Enabled" is set to True in config.py the song will begin playing in the background which helps with picking the correct theme.
  - FFmpeg will then encode it as a 320kbps mp3 and save it as Theme.mp3 in the anime folder.
  - FFmpeg will also apply the following metadata:
      - Title (with TV Size or not)
      - Artist (if available)
      - Album (as source anime)
      - Subtitle (as OP/ED number + the version if there are multiple)
  - If you want a different OP/ED than the default simply supply the AnimeThemes slug as an argument.
  - For the rare cases where there are multiple anime mapped to the same anidbID on AnimeThemes you can add an offset as an argument to select the next matched entry.
  - When running this on multiple folders at once adding the "batch" argument is recommended. This disables audio playback and skips folders already containing a Theme.mp3 file.
      - If "BatchOverwrite" is set to true in config.py the batch argument will instead overwrite any existing Theme.mp3 files.
Arguments:
  - animethemes.py slug offset OR animethemes.py slug offset play OR animethemes.py batch
  - slug: must be the first argument and is formatted as "op", "ed", "op2", "ed2" and so on
  - offset: an optional single digit number which must be the second argument if the slug is provided
  - play: for force enabling FFplay and disabling Theme.mp3 generation, must be the last or sole argument and is simply entered as "play"
  - batch: must be the sole argument and is simply entered as "batch"
Examples Commands:
  - Using bash / cmd respectively and assuming that both the script and FFmpeg can be called directly from the PATH.
  - Library Batch Processing
      for d in "/PathToAnime/"*/; do cd "$d" && animethemes.py batch; done
      for /d %d in ("X:\PathToAnime\*") do cd /d %d && animethemes.py batch
  - Fix "Mushoku Tensei II: Isekai Ittara Honki Dasu" Matching to Episode 0 (offset to the next animethemes match)
      cd "/PathToMushokuTenseiII"; animethemes.py 1
      cd /d "X:\PathToMushokuTenseiII" && animethemes.py 1
  - Same as above but download the second ending instead of the default OP
      cd "/PathToMushokuTenseiII"; animethemes.py ed2 1
      cd /d "X:\PathToMushokuTenseiII" && animethemes.py ed2 1
  - Download the 9th Opening of Bleach
      cd "/PathToBleach"; animethemes.py op9
      cd /d "X:\PathToBleach" && animethemes.py op9
  - Preview the 9th Opening of Bleach
      cd "/PathToBleach"; animethemes.py op9 play
      cd /d "X:\PathToBleach" && animethemes.py op9 play
"""

# file formats that will work with the script (uses shoko's defaults)
file_formats = ('.mkv', '.avi', '.mp4', '.mov', '.ogm', '.wmv', '.mpg', '.mpeg', '.mk3d', '.m4v')

# regex substitution pairs for additional slug formatting (executed top to bottom)
slug_formatting = {
    'OP':        'Opening ',
    'ED':        'Ending ',
    '-BD':       ' (Blu-ray Version)',
    '-Original': ' (Original Version)',
    '-TV':       ' (Broadcast Version)',
    '-Web':      ' (Web Version)',
    '  ':        ' ', # check for double spaces after other substitutions
    ' $':        '' # check for trailing spaces after other substitutions
}

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
error_prefix = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# check if subprocess is running
def is_running(pid):
    try: os.kill(pid, -9)
    except OSError: return False
    return True

## check the arguments if the user is looking for a specific op/ed, a series match offset or to batch
theme_slug = None
offset = 0
play = batch = False
FFplay = cfg.AnimeThemes['FFplay_Enabled']
# if one argument supplied check if it is a theme slug, offset, play or batch
if len(sys.argv) == 2:
    if re.match('^\\d$', sys.argv[1]): # if the first argument is a single digit set it as the offset
        offset = int(sys.argv[1])
    elif re.match('^(?:op|ed)(?!0)[0-9]{0,2}$', sys.argv[1], re.I): # otherwise check if it is a viable slug
        theme_slug = sys.argv[1].upper()
    elif sys.argv[1].lower() == 'play': # enable ffplay and disable conversion when running in play mode
        FFplay = play = True
    elif sys.argv[1].lower() == 'batch': # disable ffplay when running in batch mode and pad the console output
        FFplay = False
        batch = True
        print('')
    else:
        print(f'{error_prefix}Failed: Invalid Argument')
        exit(1)
# if two arguments supplied make sure they follow the same rules as above but without batch
elif len(sys.argv) == 3:
    if re.match('^(?:op|ed)(?!0)[0-9]{0,2}$', sys.argv[1], re.I) and re.match('^\\d$', sys.argv[2]):
        theme_slug = sys.argv[1].upper()
        offset = int(sys.argv[2])
    elif re.match('^\\d$', sys.argv[1]) and sys.argv[2].lower() == 'play':
        offset = int(sys.argv[1])
        FFplay = play = True
    elif re.match('^(?:op|ed)(?!0)[0-9]{0,2}$', sys.argv[1], re.I) and sys.argv[2].lower() == 'play':
        theme_slug = sys.argv[1].upper()
        FFplay = play = True
    else:
        print(f'{error_prefix}Failed: Invalid Arguments')
        exit(1)
# if three arguments supplied it must be slug, offset and play
elif len(sys.argv) == 4:
    if (re.match('^(?:op|ed)(?!0)[0-9]{0,2}$', sys.argv[1], re.I) and re.match('^\\d$', sys.argv[2]) and sys.argv[3].lower() == 'play'):
        theme_slug = sys.argv[1].upper()
        offset = int(sys.argv[2])
        FFplay = play = True
    else:
        print(f'{error_prefix}Failed: Invalid Arguments')
        exit(1)
elif len(sys.argv) > 4:
    print(f'{error_prefix}Failed: Too Many Arguments')
    exit(1)

# if the theme slug is set to the first op/ed entry search for it with and without a 1 appended
# this is done due to the first op/ed slugs not having a 1 appended unless there are multiple op/ed respectively
if theme_slug is not None:
    if re.match('^(?:OP1|ED1)$', theme_slug): theme_slug = theme_slug.replace('1','')
    if re.match('^(?:OP|ED)$', theme_slug): theme_slug += f',{theme_slug}1'

# grab a shoko api key using the credentials from the prefs
try:
    auth = requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/auth', json={'user': cfg.Shoko['Username'], 'pass': cfg.Shoko['Password'], 'device': 'ShokoRelay Scripts for Plex'}).json()
except Exception:
    print(f'{error_prefix}Failed: Unable to Connect to Shoko Server')
    exit(1)
if 'status' in auth and auth['status'] in (400, 401):
    print(f'{error_prefix}Failed: Shoko Credentials Invalid')
    exit(1)

## grab the anidb id using shoko api and a video file path
print_f('┌Plex Theme.mp3 Generator')
folder = os.path.sep + os.path.basename(os.getcwd()) + os.path.sep
files = []
for file in os.listdir('.'):
    if batch == True and file.lower() == 'theme.mp3' and not cfg.AnimeThemes['BatchOverwrite']: # if batching with overwrite disabled skip when a Theme.mp3 file is present
        print(f'{error_prefix}─Skipped: Theme.mp3 already exists in {folder}')
        exit(1)
    if file.lower().endswith(file_formats): files.append(file) # check for video files regardless of case
try:
    filepath = folder + files[0] # add the base folder name to the filename in case of duplicate filenames
except Exception:
    print(f'{error_prefix}─Failed: Make sure that the working directory contains video files matched by Shoko\n')
    exit(1)
print_f('├┬Shoko')
print_f(f'│├─File: {filepath}')
# get the anidbid of a series by using the first filename present in its folder
path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={auth["apikey"]}').json()
try:
    anidbID = path_ends_with[0]['SeriesIDs'][0]['SeriesID']['AniDB']
except Exception as error:
    print(f'{error_prefix}└─Failed: Make sure that the video file listed above is matched by Shoko\n', error)
    exit(1)
print_f(f'│└─URL: https://anidb.net/anime/{str(anidbID)}')

## get the first op/ed from a series with a known anidb id (Kage no Jitsuryokusha ni Naritakute! op as an example)
## https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniDB&filter[external_id]=16073&include=animethemes&filter[animetheme][type]=OP,ED
## https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniDB&filter[external_id]=16073&include=animethemes&filter[animetheme][slug]=OP,OP1
if anidbID is not None:
    print_f('├┬AnimeThemes')
    if theme_slug is not None:
        theme_type = f'&filter[animetheme][slug]={theme_slug}'
    else: # default to the first opening if the slug isn't specified in the argument
        theme_type = '&filter[animetheme][type]=OP,ED'
    anime = requests.get(f'https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniDB&filter[external_id]={anidbID}&include=animethemes{theme_type}').json()
    try:
        anime_name = anime['anime'][offset]['name']
        anime_slug = anime['anime'][offset]['slug']
    except Exception as error:
        print(f'{error_prefix}└─Failed: The current anime isn\'t present on AnimeThemes\n', error)
        exit(1)
    print_f(f'│├─Title: {anime_name}')
    print_f(f'│└─URL: https://animethemes.moe/anime/{anime_slug}')
    try:
        animethemeID = anime['anime'][offset]['animethemes'][0]['id']
        slug = anime['anime'][offset]['animethemes'][0]['slug']
    except Exception as error:
        print(f'{error_prefix}──Failed: Enter a valid argument\n', error)
        exit(1)

## grab first video id from anime theme id above (also make it easy to retrofit this script into a video downloader)
## https://api.animethemes.moe/animetheme/11808?include=animethemeentries.videos,song.artists
if animethemeID is not None:
    animetheme = requests.get(f'https://api.animethemes.moe/animetheme/{animethemeID}?include=animethemeentries.videos,song.artists').json()
    try:    song_title = animetheme['animetheme']['song']['title']
    except: song_title = ''
    try:    artist_name = animetheme['animetheme']['song']['artists'][0]['name']
    except: artist_name = ''
    try:
        videoID = animetheme['animetheme']['animethemeentries'][0]['videos'][0]['id']
    except Exception as error:
        print(f'{error_prefix}──Failed: The AnimeThemes entry is awaiting file upload\n', error)
        exit(1)    
    if artist_name != '': # set the artist info to an empty sting if animethemes doesn't have it
        artist_display = f'{artist_name} - '
    else:
        artist_display = ''

## grab first audio link from video id above
## https://api.animethemes.moe/video?filter[video][id]=16031&include=audio
if videoID is not None:
    video = requests.get(f'https://api.animethemes.moe/video?filter[video][id]={videoID}&include=audio').json()
    try:
        audioURL = video['videos'][0]['audio']['link']
    except Exception as error:
        print(f'{error_prefix}──Failed: Audio URL not found\n', error)
        exit(1)
print_f('├┬Downloading...')

# replace shorthand in slug with full text
for key, value in slug_formatting.items():
    slug = re.sub(key, value, slug)
print_f(f'│├─{slug}: {artist_display}{song_title}')

# download .ogg file from animethemes
def progress(count, block_size, total_size): # track the progress with a simple reporthook
    percent = int(count*block_size*100/total_size)
    print(f'│└─URL: {audioURL} [{str(percent).zfill(3)}%]', flush=True, end='\r')
try:
    urllib.request.urlretrieve(audioURL, 'temp', reporthook=progress)
except Exception as error:
    print(f'{error_prefix}──Failed: Download Incomplete\n', error)
    exit(1)
print_f('')

# label for cleaning up files and skipping other commands if ffprobe fails
class clean(Exception): pass

try:
    # grab the duration to allow a time remaining display when playing back and for determining if a song is tv size or not
    try:
        duration = int(float(subprocess.check_output('ffprobe -i temp -show_entries format=duration -v quiet -of csv="p=0"', shell=True).decode('ascii').strip())) # find the duration of the song
        if duration < 100: song_title += ' (TV Size)' # add "(TV Size)" to the end of the title if the song is less than 1:40 long
    except Exception as error:
        print(f'{error_prefix}──FFProbe Failed\n  ', error)
        raise clean()

    # if ffplay is enabled playback the originally downloaded file with ffplay for an easy way to see if it is the correct song
    if FFplay:
        try:
            ffplay = subprocess.Popen(f'ffplay -v quiet -autoexit -nodisp -volume {cfg.AnimeThemes["FFplay_Volume"]} temp', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True) # playback the theme until the script is closed
        except Exception as error: # continue to run even if ffplay fails as it is not necessary for the script to complete
            print(f'{error_prefix}──FFPlay Failed\n │', error)

    # escape double quotes for titles/artists/albums which contain them
    def escape_quotes(s): return s.replace('\\','\\\\').replace('"',r'\"')

    # ffmpeg metadata for easily checking what a Theme.mp3 file contains
    metadata = {
        'title':    f' -metadata title="{escape_quotes(song_title)}"',
        'subtitle': f' -metadata TIT3="{slug}"',
        'artist':   f' -metadata artist="{escape_quotes(artist_name)}"',
        'album':    f' -metadata album="{escape_quotes(anime_name)}"'
    }

    ## if not just playing convert the temp .ogg file to .mp3 with ffmpeg and add title + artist metadata
    if not play:
        try:
            print_f('└┬Converting...')
            subprocess.run(f'ffmpeg -i temp -v quiet -y -ab 320k{metadata["title"]}{metadata["subtitle"]}{metadata["artist"]}{metadata["album"]} Theme.mp3', shell=True, check=True)
            status = ' └─Finished! '
        except Exception as error:
            print(f' {error_prefix}─FFmpeg Failed\n  ', error)
            status = ' Failed! '
    else:
        print_f('└┬Playing...')
        status = ' └─'

    ## kill ffplay and end the operation after pressing ctrl-c if not running as a batch or with ffplay disabled
    if FFplay:
        try:
            for t in range(duration):
                print(f'{status}Press Ctrl-C to continue... [{str(duration - t - 1).zfill(len(str(duration)))}s]', flush=True, end='\r') # show time remaining with padded zeros
                time.sleep(1)
            print_f('')
        except KeyboardInterrupt:
            pass
        while is_running(ffplay.pid): time.sleep(.25) # wait for ffplay to be killed before deleting the temp file
    else:
        print_f(f'{status}')
except clean:
    pass
os.remove('temp') # delete the original file
