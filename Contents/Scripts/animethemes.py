#!/usr/bin/env python3
import os, re, sys, json, time, urllib, argparse, requests, subprocess
import config as cfg; import common as cmn

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
  - Append the arguments "slug" / "offset" (animethemes.py slug offset) in order to specify which opening or ending to download.
      - slug: an optional identifier which must be the first argument and is formatted as "op", "ed", "op2", "ed2", "op1-tv" and so on
      - offset: an optional single digit number which must be the second argument if the slug is provided
  - Append the argument "play" to the commands above to run in "Preview" mode.
      - play: for force enabling FFplay and disabling Theme.mp3 generation, must be the last or sole argument and is simply entered as "play"
  - Append the argument "batch" (animethemes.py batch) when running the script on multiple folders at a time.
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

# file formats that will work with the script (uses Shoko's defaults)
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

# check if subprocess is running
def is_running(pid):
    try: os.kill(pid, -9)
    except OSError: return False
    return True

# initialise default values for the arguments and their regex
theme_slug, offset, idx = None, 0, 0
play = local = batch = False
FFplay = cfg.AnimeThemes['FFplay_Enabled'] # from config instead of argument
slug_regex, offset_regex = '^(?:op|ed)(?!0)[0-9]{0,2}(?:-(?:bd|web|tv|original))?$', '^\\d$'

# define functions for if there are 1, 2 or 3 arguments supplied
def arg_parse_1(arg1):
    arg1 = arg1.lower()
    global slug_regex, offset_regex, theme_slug, offset, play, local, batch, FFplay
    if re.match(slug_regex, arg1): # check if the argument is a slug via regex
        theme_slug = arg1.upper()
    elif re.match(offset_regex, arg1): # else check if it is a single digit offset via regex
        offset = int(arg1)
    elif arg1 == 'play': # else check if the user wants to run in preview mode
        play = local = True
    elif arg1 == 'batch': # else check if the user want to run in batch mode
        batch, FFplay = True, False
    else:
        raise argparse.ArgumentTypeError('invalid (slug, offset, play or batch)')
    return arg1
def arg_parse_2(arg2): # use a combination of the single argument logic for the second argument (excluding batch)
    arg1, arg2 = sys.argv[1], arg2.lower()
    global slug_regex, offset_regex, theme_slug, offset, play
    if re.match(slug_regex, arg1) and re.match(offset_regex, arg2):
        theme_slug, offset = arg1.upper(), int(arg2)
    elif re.match(offset_regex, arg1) and arg2 == 'play':
        offset, play = int(arg1), True
    elif re.match(slug_regex, arg1) and arg2 == 'play':
        theme_slug, play = arg1.upper(), True
    else:
        raise argparse.ArgumentTypeError('invalid (slug + offset), (slug + play) or (offset + play)')
    return arg2
def arg_parse_3(arg3): # there is only a single possible format if there are three arguments at once
    arg1, arg2, arg3 = sys.argv[1], sys.argv[2], arg3.lower()
    global slug_regex, offset_regex, offset, theme_slug, play
    if (re.match(slug_regex, arg1.lower()) and re.match(offset_regex, arg2) and arg3 == 'play'):
        theme_slug, offset, play = arg1.upper(), int(arg2), True
    else:
        raise argparse.ArgumentTypeError('invalid (slug + offset + play)')
    return arg3

# check the arguments if the user is looking for a specific op/ed, a series match offset, to preview or to batch
parser = argparse.ArgumentParser(description='Download the first OP (or ED if there is none) for the given series.', epilog='Batch Processing Example Commands:\n  bash:         for d in "/PathToAnime/"*/; do cd "$d" && animethemes.py batch; done\n  cmd:          for /d %d in ("X:\\PathToAnime\\*") do cd /d %d && animethemes.py batch', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('arg1', metavar='slug',         nargs='?', type=arg_parse_1, help='An optional identifier which must be the first argument.\n*formatted as "op", "ed", "op2", "ed2", "op1-tv" and so on\n\n')
parser.add_argument('arg2', metavar='offset',       nargs='?', type=arg_parse_2, help='An optional single digit number.\n*must be the second argument if the slug is provided\n\n')
parser.add_argument('arg3', metavar='play | batch', nargs='?', type=arg_parse_3, help='play: To run in "Preview" mode.\n*must be the last or sole argument and is simply entered as "play"\n*without other arguments local "Theme.mp3" files will be prioritised\n\nbatch: When running the script on multiple folders at a time.\n*must be the sole argument and is simply entered as "batch"')
args = parser.parse_args()
args.arg1, args.arg2, args.arg3 # grab the arguments if available
if play: FFplay = True # force enable FFplay if the play argument was supplied

print('╭Plex Theme.mp3 Generator')
# enter local playback mode if play is the solo argument and a Theme.mp3 file is present
media = 'Theme.tmp'
if local == True and os.path.isfile('Theme.mp3'):
    media, song_title = 'Theme.mp3', 'local'
    print('├┬Local Theme Detected')
    try:
        local_metadata = json.loads(subprocess.run(f'ffprobe -i Theme.mp3 -show_entries format_tags -v quiet -of json', capture_output=True, universal_newlines=True, encoding='utf-8').stdout)['format']['tags']
    except Exception as error:
        print(f'{cmn.err}──FFProbe Failed\n  ', error)
    print(f'│├─{local_metadata.get('TIT3', '???')}: {local_metadata.get('title', '???')} by {local_metadata.get('artist', '???')}')
    print(f'│╰─Source: {local_metadata.get('album', '???')}')
else:
    # if the theme slug is set to the first op/ed entry search for it with and without a 1 appended
    # this is done due to the first op/ed slugs not having a 1 appended unless there are multiple op/ed respectively
    if theme_slug is not None:
        if re.match('^(?:OP1|ED1)$', theme_slug): theme_slug = theme_slug.replace('1','')
        if re.match('^(?:OP|ED)$', theme_slug): theme_slug += f',{theme_slug}1'

    shoko_key = cmn.shoko_auth() # grab a Shoko API key using the credentials from the prefs and the common auth function

    ## grab the anidb id using Shoko API and a video file path
    folder, files = os.path.sep + os.path.basename(os.getcwd()) + os.path.sep, []
    for file in os.listdir('.'):
        if batch == True and file.lower() == 'theme.mp3' and not cfg.AnimeThemes['BatchOverwrite']: # if batching with overwrite disabled skip when a Theme.mp3 file is present
            print(f'{cmn.err}─Skipped: Theme.mp3 already exists in {folder}')
            exit(1)
        if file.lower().endswith(file_formats): files.append(file) # check for video files regardless of case
    try:
        filepath = folder + files[0] # add the base folder name to the filename in case of duplicate filenames
    except Exception:
        print(f'{cmn.err}─Failed: Make sure that the working directory contains video files matched by Shoko\n')
        exit(1)
    print('├┬Shoko')
    print(f'│├─File: {filepath}')
    # get the anidbid of a series by using the first filename present in its folder
    path_ends_with = requests.get(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/v3/File/PathEndsWith?path={urllib.parse.quote(filepath)}&limit=0&apikey={shoko_key}').json()
    try:
        anidbID = path_ends_with[0]['SeriesIDs'][0]['SeriesID']['AniDB']
    except Exception as error:
        print(f'{cmn.err}╰─Failed: Make sure that the video file listed above is matched by Shoko\n', error)
        exit(1)
    print(f'│╰─URL: https://anidb.net/anime/{str(anidbID)}')

    ## get the first op/ed from a series with a known anidb id (Kage no Jitsuryokusha ni Naritakute! op as an example)
    ## https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniDB&filter[external_id]=16073&include=animethemes&filter[animetheme][type]=OP,ED
    ## https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniDB&filter[external_id]=16073&include=animethemes&filter[animetheme][slug]=OP,OP1
    if anidbID is not None:
        print('├┬AnimeThemes')
        theme_type = f'&filter[animetheme][slug]={theme_slug}' if theme_slug is not None else '&filter[animetheme][type]=OP,ED' # default to the first op/ed if the slug isn't specified in the argument
        anime = requests.get(f'https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniDB&filter[external_id]={anidbID}&include=animethemes{theme_type}').json()
        try:
            anime_name = anime['anime'][offset]['name']
            anime_slug = anime['anime'][offset]['slug']
        except Exception as error:
            print(f'{cmn.err}╰─Failed: The current anime isn\'t present on AnimeThemes\n', error)
            exit(1)
        print(f'│├─Title: {anime_name}')
        print(f'│╰─URL: https://animethemes.moe/anime/{anime_slug}')
        try:
            if not theme_slug and anime['anime'][offset]['animethemes'][1]['slug'] == 'OP1': idx = 1 # account for cases where the first op comes after the first ed
        except:
            pass
        try:
            animethemeID = anime['anime'][offset]['animethemes'][idx]['id']
            slug = anime['anime'][offset]['animethemes'][idx]['slug']
        except Exception as error:
            print(f'{cmn.err}──Failed: Enter a valid argument\n', error)
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
            print(f'{cmn.err}──Failed: The AnimeThemes entry is awaiting file upload\n', error)
            exit(1)
        artist_display = f' by {artist_name}' if artist_name != '' else '' # set the artist info to an empty sting if animethemes doesn't have it

    ## grab first audio link from video id above
    ## https://api.animethemes.moe/video?filter[video][id]=16031&include=audio
    if videoID is not None:
        video = requests.get(f'https://api.animethemes.moe/video?filter[video][id]={videoID}&include=audio').json()
        try:
            audioURL = video['videos'][0]['audio']['link']
        except Exception as error:
            print(f'{cmn.err}──Failed: Audio URL not found\n', error)
            exit(1)
    print('├┬Downloading...')

    # replace shorthand in slug with full text
    for key, value in slug_formatting.items(): slug = re.sub(key, value, slug)
    print(f'│├─{slug}: {song_title}{artist_display}')

    # download .ogg file from animethemes
    def progress(count, block_size, total_size): # track the progress with a simple reporthook
        percent = int(count*block_size*100/total_size)
        print(f'│╰─URL: {audioURL} [{str(percent).zfill(3)}%]', flush=True, end='\r')
    try:
        urllib.request.urlretrieve(audioURL, 'Theme.tmp', reporthook=progress)
    except Exception as error:
        print(f'{cmn.err}──Failed: Download Incomplete\n', error)
        exit(1)
    print('')

# label for cleaning up files and skipping other commands if ffprobe fails
class clean(Exception): pass

try:
    # grab the duration to allow a time remaining display when playing back and for determining if a song is tv size or not
    try:
        duration = int(float(subprocess.run(f'ffprobe -i {media} -show_entries format=duration -v quiet -of csv="p=0"', capture_output=True).stdout)) # find the duration of the song
        if duration < 100: song_title += ' (TV Size)' # add "(TV Size)" to the end of the title if the song is less than 1:40 long
    except Exception as error:
        print(f'{cmn.err}──FFProbe Failed\n  ', error)
        raise clean()

    # if ffplay is enabled playback the originally downloaded file with ffplay for an easy way to see if it is the correct song
    if FFplay:
        try:
            ffplay = subprocess.Popen(f'ffplay -v quiet -autoexit -nodisp -volume {cfg.AnimeThemes["FFplay_Volume"]} {media}', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True) # playback the theme until the script is closed
        except Exception as error: # continue to run even if ffplay fails as it is not necessary for the script to complete
            print(f'{cmn.err}──FFPlay Failed\n │', error)

    # escape double quotes for titles/artists/albums which contain them
    def escape_quotes(s): return s.replace('\\','\\\\').replace('"',r'\"')

    ## if not just playing convert the temp .ogg file to .mp3 with ffmpeg and add title + artist metadata
    if not play:
        # ffmpeg metadata for easily checking what a Theme.mp3 file contains
        metadata = {
            'title':    f' -metadata title="{escape_quotes(song_title)}"',
            'subtitle': f' -metadata TIT3="{slug}"',
            'artist':   f' -metadata artist="{escape_quotes(artist_name)}"',
            'album':    f' -metadata album="{escape_quotes(anime_name)}"'
        }

        try:
            print('╰┬Converting...')
            subprocess.run(f'ffmpeg -i {media} -v quiet -y -ab 320k{metadata["title"]}{metadata["subtitle"]}{metadata["artist"]}{metadata["album"]} Theme.mp3', shell=True, check=True)
            status = ' ╰─Finished! '
        except Exception as error:
            print(f' {cmn.err}─FFmpeg Failed\n  ', error)
            status = ' Failed! '
    else:
        print('╰┬Playing...')
        status = ' ╰─'

    ## kill ffplay and end the operation after pressing ctrl-c if not running as a batch or with ffplay disabled
    if FFplay:
        try:
            for t in range(duration):
                print(f'{status}Press Ctrl-C to continue... [{str(duration - t - 1).zfill(len(str(duration)))}s]', flush=True, end='\r') # show time remaining with padded zeros
                time.sleep(1)
            print('')
            time.sleep(1.5) # account for ending the countdown 1 second early to avoid file locks
        except KeyboardInterrupt:
            print('')
            pass
        while is_running(ffplay.pid): time.sleep(.25) # wait for ffplay to be killed before deleting the temp file
    else:
        print(f'{status}')
except clean:
    pass
if os.path.isfile('Theme.tmp'): os.remove('Theme.tmp') # delete the temp file if it exists
