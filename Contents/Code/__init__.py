import os, re, json, urllib
from datetime import datetime

API_KEY = ''

def ValidatePrefs():
    pass

def Start():
    Log('Shoko Relay Agent Started [v1.1.9]')
    HTTP.Headers['Accept'] = 'application/json'
    HTTP.ClearCache() # Clear the cache possibly removing stuck metadata
    HTTP.CacheTime = 0.1 # Reduce the cache time as much as possible since Shoko has all the metadata
    ValidatePrefs()

def GetApiKey():
    global API_KEY
    if not API_KEY:
        data = json.dumps({
            'user': Prefs['Username'],
            'pass': Prefs['Password'] if Prefs['Password'] != None else '',
            'device': 'Shoko Relay for Plex'
        })
        resp = HttpPost('api/auth', data)['apikey']
        # Log.debug('Got API KEY:                   %s' % resp) # Not needed
        API_KEY = resp
        return resp
    return API_KEY

def HttpPost(url, postdata):
    myheaders = {'Content-Type': 'application/json'}
    return JSON.ObjectFromString(HTTP.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders, data=postdata).content)

def HttpReq(url, retry=True):
    global API_KEY
    # Log('Requesting:                    %s' % url) # Not needed since debug logging shows these requests anyways
    myheaders = {'apikey': GetApiKey()}

    try:
        return JSON.ObjectFromString(HTTP.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders).content)
    except Exception, e:
        if not retry:
            raise e

        API_KEY = ''
        return HttpReq(url, False)

class ShokoRelayAgent:
    def Search(self, results, media, lang, manual):
        name = media.show

        # Hardcode search replacement for "86" since it currently doesn't work as a search term with /api/v3/Series/Search (non negative integers are treated as anidb ids)
        ## https://github.com/ShokoAnime/ShokoServer/issues/1105
        if name == '86': name = 'Eighty-Six'

        # Search for the series using the name
        prelimresults = HttpReq('api/v3/Series/Search?query=%s&fuzzy=false&limit=10' % (urllib.quote_plus(name.encode('utf8')))) # http://127.0.0.1:8111/api/v3/Series/Search?query=Clannad&fuzzy=true&limit=10

        for index, series_data in enumerate(prelimresults):
            # Get series data
            series_id = series_data['IDs']['ID']
            anidb_series_data = HttpReq('api/v3/Series/%s/AniDB' % series_id)

            # Get year from air date
            airdate = try_get(anidb_series_data, 'AirDate', None)
            year = airdate.split('-')[0] if airdate else None

            score = 100 if series_data['Name'] == name else 99 - index - int(series_data['Distance'] * 100)

            meta = MetadataSearchResult(str(series_id), series_data['Name'], year, score, lang)
            results.Append(meta)

    def Update(self, metadata, media, lang, force):
        aid = metadata.id

        # Get series data
        Log('################## ShokoRelay for Series ID: %-*s ##################' % (7, aid))
        series_data = HttpReq('api/v3/Series/%s?includeDataFrom=AniDB' % aid) # http://127.0.0.1:8111/api/v3/Series/24?includeDataFrom=AniDB

        # Make a dict of language -> title for all series titles in the anidb series data (one pair per language)
        series_titles = {}
        for item in sorted(series_data['AniDB']['Titles'], key=lambda sort: sort['Type'], reverse=True): # Sort by reversed Type (Synonym -> Short -> Official -> Main) so that the dict prioritises official titles over synonyms
            if item['Type'] != 'Short': series_titles[item['Language']] = item['Name'] # Exclude all short titles
        series_titles['shoko'] = series_data['Name'] # Add shoko's preferred series title to the dict

        # Get Title according to the language preference
        for lang in Prefs['SeriesTitleLanguagePreference'].split(','):
            title = try_get(series_titles, lang.strip().lower(), None)
            if title: break
        if title is None: title = series_titles['shoko'] # If not found, fallback to shoko's preferred series title

        metadata.title = title
        Log('Title:                         %s' % title)

        # Get Alternate Title according to the language preference
        for lang in Prefs['SeriesAltTitleLanguagePreference'].split(','):
            alt_title = try_get(series_titles, lang.strip().lower(), None)
            if alt_title: break

        # Append the Alternate title to the Sort Title to make it searchable
        if alt_title is not None and alt_title != metadata.title: metadata.title_sort = title + ' [' + alt_title + ']'
        else: alt_title, metadata.title_sort = 'Alternate Title Matches the Title - Skipping!', title
        Log('Alternate Title (AddedToSort): %s' % alt_title)

        """ Enable if Plex Fixes Blocking Legacy Agent Issue
        # Get Original Title
        if alt_title is not None and alt_title != metadata.title: metadata.original_title = alt_title
        else: metadata.original_title = None
        Log('Original Title:                %s' % metadata.original_title)
        """

        # Get Originally Available
        airdate = try_get(series_data['AniDB'], 'AirDate', None)
        if airdate: metadata.originally_available_at = datetime.strptime(airdate, '%Y-%m-%d').date()
        else: metadata.originally_available_at = None
        Log('Originally Available:          %s' % metadata.originally_available_at)

        # Get Content Rating (missing metadata source)
        # metadata.content_rating =

        # Get Rating
        metadata.rating = float(series_data['AniDB']['Rating']['Value']/100)
        Log('Rating:                        %s' % metadata.rating)

        # Get Studio as Animation Work (アニメーション制作)
        studio = HttpReq('api/v3/Series/%s/Cast?roleType=Studio' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Cast?roleType=Studio
        studio_source, studio = '(Animation Work):', try_get(studio, 0, None)
        if not studio: # If no Studio fallback and override with Work (制作) listing
            studio = HttpReq('api/v3/Series/%s/Cast?roleType=Staff&roleDetails=Work' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Cast?roleType=Staff&roleDetails=Work
            studio_source, studio = '(Work):          ', try_get(studio, 0, None)
        if studio: metadata.studio = studio['Staff']['Name']
        else: metadata.studio = None
        Log('Studio %s       %s' % (studio_source, metadata.studio))

        # Get Tagline (missing metadata source)
        # metadata.tagline =

        # Get Summary
        summary = try_get(series_data['AniDB'], 'Description', None)
        if summary: metadata.summary = summary_sanitizer(summary)
        else: metadata.summary = None
        Log('Summary:                       %s' % metadata.summary)

        # Get Genres
        ## filter=1 removes TagBlacklistAniDBHelpers as defined here: https://github.com/ShokoAnime/ShokoServer/blob/d7c7f6ecdd883c714b15dbef385e19428c8d29cf/Shoko.Server/Utilities/TagFilter.cs#L37C44-L37C68
        series_tags = HttpReq('api/v3/Series/%s/Tags?filter=1&excludeDescriptions=true&orderByName=false&onlyVerified=true' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Tags?filter=1&excludeDescriptions=true&orderByName=false&onlyVerified=true
        metadata.genres.clear()

        ## Filter out weighted tags by the configured tag weight but leave ones weighted 0 as that means that they are unweighted tags
        tags, content_rating, content_descriptor, descriptor_s, descriptor_v = [], None, '', '', ''
        for tag in series_tags:
            if (tag['Weight'] == 0 or tag['Weight'] >= int(Prefs['minimumTagWeight'])):
                tags.append(title_case(tag['Name'])) # Convert tags to title case and add them to the list
            if Prefs['contentRatings']: # Prep weight based content ratings (if enabled) here: https://wiki.anidb.net/Categories:Content_Indicators
                # Raise ratings to TV-14 and then TV-MA if the weight exceeds 400 and 500 respectively
                if tag['Name'].lower() == 'nudity':
                    descriptor_s = 'S'
                    if tag['Weight'] >= 400 and content_rating != 'TV-MA': content_rating = 'TV-14' # Full frontal nudity with nipples and/or visible genitals
                    if tag['Weight'] >= 500: content_rating = 'TV-MA' # Most borderline porn / hentai
                if tag['Name'].lower() == 'sex':
                    descriptor_s = 'S' # 400 for sex is 99% TV-MA material
                    if tag['Weight'] >= 400: content_rating = 'TV-MA' # Sexual activity that is "on camera", but most of the action is indirectly visible
                if tag['Name'].lower() == 'violence':
                    descriptor_v = 'V'
                    if tag['Weight'] >= 400 and content_rating != 'TV-MA': content_rating = 'TV-14' # Any violence causing death and/or serious physical dismemberment (e.g. a limb is cut off)
                    if tag['Weight'] >= 500: content_rating = 'TV-MA' # Added gore, repetitive killing/mutilation of more than 1 individual
        if descriptor_s or descriptor_v: content_descriptor = '-' + descriptor_s + descriptor_v

        metadata.genres = tags
        Log('Genres:                        %s' % ', '.join(tags))

        # Get Collections
        groupinfo = HttpReq('api/v3/Series/%s/Group' % aid)
        metadata.collections.clear()
        if groupinfo['Size'] > 1: metadata.collections = [groupinfo['Name']]
        Log('Collection:                    %s' % metadata.collections[0])

        """ Labels are likely never to be supported for legacy agents
        # Get Labels
        metadata.labels.clear()
        metadata.labels = [try_get(series_data['AniDB'], 'Type', None)]
        Log('Labels:                        %s' % metadata.labels[0])
        """

        # Get Content Rating (assumed from Genres)
        ## A rough approximation of: http://www.tvguidelines.org/resources/TheRatings.pdf
        ## Uses the target audience tags on AniDB: https://anidb.net/tag/2606/animetb
        ## Uses the content indicator tags + weights on AniDB: https://anidb.net/tag/2604/animetb
        if Prefs['contentRatings']:
            if not content_rating: # If the rating wasn't already determined using the content indicators above take the lowest target audience rating
                if 'Kodomo' in tags:                        content_rating = 'TV-Y'
                elif 'Mina' in tags:                        content_rating = 'TV-G'
                elif 'Shoujo' in tags or 'Shounen' in tags: content_rating = 'TV-PG'
                elif 'Josei' in tags or 'Seinen' in tags:   content_rating = 'TV-14'
            if 'Borderline Porn' in tags:  content_rating = 'TV-MA' # Override any previous rating for borderline porn content
            if content_rating: content_rating += content_descriptor # Append the content descriptor using the content indicators above
            if '18 Restricted' in tags:    content_rating = 'X' # Override any previous rating and remove content indicators for 18 restricted content

            metadata.content_rating = content_rating
            Log('Content Rating (Assumed):      %s' % metadata.content_rating)

        # Get Posters & Backgrounds
        images = try_get(series_data, 'Images', {})
        self.metadata_add(metadata.posters, try_get(images, 'Posters', []))
        self.metadata_add(metadata.banners, try_get(images, 'Banners', []))
        self.metadata_add(metadata.art, try_get(images, 'Fanarts', []))

        # Get Cast & Crew
        cast_crew = HttpReq('api/v3/Series/%s/Cast' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Cast
        Log('-----------------------------------------------------------------------')
        Log('Character                      Seiyuu (CV)')
        Log('-----------------------------------------------------------------------')
        metadata.roles.clear()
        cv_check = False
        for role in cast_crew:
            role_type = role['RoleName']
            if role_type != 'Seiyuu': continue # Skip if not Seiyuu
            cv_check = True
            meta_role = metadata.roles.new()
            meta_role.name = role['Staff']['Name']
            meta_role.role = role['Character']['Name']
            Log('%-30s %s' % (meta_role.role, meta_role.name))
            # Grab staff image (if available)
            image = role['Staff']['Image']
            if image: meta_role.photo = 'http://{host}:{port}/api/v3/Image/{source}/{type}/{id}'.format(host=Prefs['Hostname'], port=Prefs['Port'], source=image['Source'], type=image['Type'], id=image['ID'])
        if not cv_check: Log('N/A')

        director_name, writer_name, staff_check = [], [], False
        if Prefs['crewListings']:
            Log('-----------------------------------------------------------------------')
            Log('Role                           Staff Name')
            Log('-----------------------------------------------------------------------')
            for role in cast_crew: # Second loop for cast so that seiyuu appear first in the list
                role_type = role['RoleName']
                if role_type == 'Seiyuu': continue # Skip if Seiyuu
                staff_check = True
                meta_role = metadata.roles.new()
                meta_role.name = role['Staff']['Name']
                if role_type == 'Director': # Initialize Director outside of the episodes loop to avoid repeated requests per episode
                    meta_role.role = 'Director' # Direction (監督)
                    director_name.append(meta_role.name)
                elif role_type == 'SourceWork': # Initialize Writer outside of the episodes loop to avoid repeated requests per episode
                    meta_role.role = 'Writer (Original Work)' # Original Work (原作)
                    writer_name.append(meta_role.name)
                elif role_type == 'CharacterDesign' : meta_role.role = 'Character Design'          # Character Design (キャラクターデザイン)
                elif role_type == 'SeriesComposer'  : meta_role.role = 'Chief Scriptwriter'        # Series Composition (シリーズ構成)
                elif role_type == 'Producer'        : meta_role.role = 'Chief Animation Direction' # Chief Animation Direction (総作画監督)
                elif role_type == 'Music'           : meta_role.role = 'Composer'                  # Music (音楽)
                elif role_type == 'Staff'           : meta_role.role = role['RoleDetails']         # Various Other Main Staff Entries
                else: meta_role.role = role_type
                Log('%-30s %s' % (meta_role.role, meta_role.name))
                # Grab staff image (if available)
                image = role['Staff']['Image']
                if image: meta_role.photo = 'http://{host}:{port}/api/v3/Image/{source}/{type}/{id}'.format(host=Prefs['Hostname'], port=Prefs['Port'], source=image['Source'], type=image['Type'], id=image['ID'])
            if not staff_check: Log('N/A')

        # Get episode list using series ID
        episodes = HttpReq('api/v3/Series/%s/Episode?pageSize=0' % aid) # http://127.0.0.1:8111/api/v3/Series/212/Episode?pageSize=0

        for episode in episodes['List']:
            # Get episode data
            episode_id   = episode['IDs']['ID']
            episode_data = HttpReq('api/v3/Episode/%s?includeDataFrom=AniDB,TvDB' % episode_id) # http://127.0.0.1:8111/api/v3/Episode/212?includeDataFrom=AniDB,TvDB
            episode_type = episode_data['AniDB']['Type'] # Get episode type

            # Get season and episode numbers
            episode_source, season = '(AniDB):', 0
            if   episode_type == 'Normal'    : season =  1
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

            Log('Season %s                %s' % (episode_source, season))
            Log('Episode %s               %s' % (episode_source, episode_number))

            episode_obj = metadata.seasons[season].episodes[episode_number]

            # Make a dict of language -> title for all episode titles in the anidb episode data
            episode_titles = {}
            for item in episode_data['AniDB']['Titles']: episode_titles[item['Language']] = item['Name']
            episode_titles['shoko'] = episode_data['Name'] # Add shoko's preferred episode title to the dict

            # Get episode Title according to the language preference
            title_source = '(AniDB):                '
            for lang in Prefs['EpisodeTitleLanguagePreference'].split(','):
                title = try_get(episode_titles, lang.strip().lower(), None)
                if title: break
            if not title: title = episode_titles['shoko'] # If not found, fallback to shoko's preferred episode title

            # Replace Ambiguous Title with series Title
            SingleEntryTitles = ('Complete Movie', 'Music Video', 'OAD', 'OVA', 'Short Movie', 'TV Special', 'Web') # AniDB titles used for single entries which are ambiguous
            if title in SingleEntryTitles:
                # Get series title according to the language preference
                title_source, original_title = '(ReplacementFromSeries):', title
                for lang in Prefs['EpisodeTitleLanguagePreference'].split(','):
                    lang = lang.strip().lower()
                    if lang != 'shoko': title = try_get(series_titles, lang, title) # Exclude "shoko" as it will return the preferred language for series and not episodes'
                    if title is not original_title: break
                if title is original_title: title = try_get(series_titles, 'en', title) # If not found, fallback to EN series title
                if title is original_title: # Fallback to TvDB title as a last resort
                    if try_get(episode_data['TvDB'], 'Title', None): title_source, title = '(TvDB):                 ', episode_data['TvDB']['Title']
                # Append Ambiguous Title to series Title if a replacement title was found and it doesn't contain it
                if original_title != title and original_title not in title: title += ' — ' + original_title

            # TvDB episode title override (if the episode title is Episode/Volume # on AniDB) excluding Episode/Volume 0
            if re.match(r'^(?:Episode|Volume) [1-9][0-9]*$', title) and try_get(episode_data['TvDB'], 'Title', None):
                title_source, title = '(TvDB Override):        ', episode_data['TvDB']['Title']

            episode_obj.title = title
            Log('Title %s %s' % (title_source, episode_obj.title))

            # Get Originally Available
            airdate_log, airdate = None, try_get(episode_data['AniDB'], 'AirDate', None)
            if airdate: airdate_log = episode_obj.originally_available_at = datetime.strptime(airdate, '%Y-%m-%d').date()
            else: episode_obj.originally_available_at = None
            # Remove the air dates for negative seasons according to the language preference
            if season == -4 and Prefs['disableNegativeSeasonAirdates'] == 'Exclude Other': pass
            elif season < 0 and Prefs['disableNegativeSeasonAirdates'] != 'None':
                airdate_log, episode_obj.originally_available_at = 'Disabled in Agent Settings - Skipping!', None
            Log('Originally Available:          %s' % airdate_log)

            # Get Content Ratings (from series)
            episode_obj.content_rating = metadata.content_rating
            Log('Content Rating (Assumed):      %s' % episode_obj.content_rating)

            # Get Rating
            episode_obj.rating = episode_data['AniDB']['Rating']['Value']
            Log('Rating:                        %s' % float(episode_obj.rating))

            # Get Summary
            summary_source, summary = '(AniDB):', try_get(episode_data['AniDB'], 'Description', None)
            if summary: episode_obj.summary = summary_sanitizer(summary)
            elif try_get(episode_data['TvDB'], 'Description', None):
                summary_source, summary = '(TvDB): ', episode_data['TvDB']['Description']
                episode_obj.summary = summary_sanitizer(summary)
            else: episode_obj.summary = None
            Log('Summary %s               %s' % (summary_source, episode_obj.summary))

            # Get Writer as Original Work (原作) [if there is only one]
            episode_obj.writers.clear()
            writer_log = None
            if len(writer_name) == 1:
                writer = episode_obj.writers.new()
                writer_log = writer.name = writer_name[0]
            elif len(writer_name) > 1: writer_log = 'Multiple Writers Detected - Skipping!'
            Log('Writer (Original Work):        %s' % writer_log)

            # Get Director as Direction (監督) [if there is only one]
            episode_obj.directors.clear()
            director_log = None
            if len(director_name) == 1:
                director = episode_obj.directors.new()
                director_log = director.name = director_name[0]
            elif len(director_name) > 1: director_log = 'Multiple Directors Detected - Skipping!'
            Log('Director:                      %s' % director_log)

            # Get Episode Poster (Thumbnail)
            if Prefs['customThumbs']: self.metadata_add(episode_obj.thumbs, [try_get(try_get(episode_data['TvDB'], 0, {}), 'Thumbnail', {})])

        """ Enable if Plex Fixes Blocking Legacy Agent Issue
        # Set custom negative season names
        for season_num in metadata.seasons:
            season_title = None
            if season_num == '-1': season_title = 'Credits'
            elif season_num == '-2': season_title = 'Trailers'
            elif season_num == '-3': season_title = 'Parodies'
            elif season_num == '-4': season_title = 'Other'
            if int(season_num) < 0 and season_title is not None:
                Log('Renaming Season:               %s to %s' % (season_num, season_title))
                metadata.seasons[season_num].title = season_title
        """

        # Adapted from: https://github.com/plexinc-agents/PlexThemeMusic.bundle/blob/master/Contents/Code/__init__.py
        if Prefs['themeMusic']:
            THEME_URL = 'http://tvthemes.plexapp.com/%s.mp3'
            for tid in try_get(series_data['IDs'],'TvDB', []):
                if THEME_URL % tid not in metadata.themes:
                    try:
                        metadata.themes[THEME_URL % tid] = Proxy.Media(HTTP.Request(THEME_URL % tid))
                        Log('Theme Music Added:             %s' % THEME_URL % tid)
                    except:
                        Log('Error Adding Theme Music:      (Probably Not Found)')

    def metadata_add(self, meta, images):
        valid = list()
        art_url = ''
        for art in images:
            try:
                art_url = '/api/v3/Image/{source}/{type}/{id}'.format(source=art['Source'], type=art['Type'], id=art['ID'])
                url = 'http://{host}:{port}{relativeURL}'.format(host=Prefs['Hostname'], port=Prefs['Port'], relativeURL=art_url)
                idx = try_get(art, 'index', 0)
                Log('Adding Metadata:               %s (index %d)' % (url, idx))
                meta[url] = Proxy.Media(HTTP.Request(url).content, idx)
                valid.append(url)
            except Exception as e:
                Log('Invalid URL Given:             (%s) - Skipping' % try_get(art, 'url', ''))
                Log(e)

        meta.validate_keys(valid)

        for key in meta.keys():
            if (key not in valid):
                del meta[key]

def summary_sanitizer(summary):
    if Prefs['synposisCleanLinks']:           summary = re.sub(r'https?:\/\/\w+.\w+(?:\/?\w+)? \[([^\]]+)\]', r'\1', summary) # Replace links
    if Prefs['synposisCleanMiscLines']:       summary = re.sub(r'^(\*|--|~) .*', '', summary, flags=re.M)                     # Remove the line if it starts with ('* ' / '-- ' / '~ ')
    if Prefs['synposisRemoveSummary']:        summary = re.sub(r'\n(Source|Note|Summary):.*', '', summary, flags=re.S)        # Remove all lines after this is seen
    if Prefs['synposisCleanMultiEmptyLines']: summary = re.sub(r'\n\n+', r'\n\n', summary, flags=re.S)                        # Condense multiple empty lines
    return summary.strip(' \n')

def title_case(text):
    # Words to force lowercase in tags to follow AniDB capitalisation rules: https://wiki.anidb.net/Capitalisation (some romaji tag endings and separator words are also included)
    force_lower = ('a', 'an', 'the', 'and', 'but', 'or', 'nor', 'at', 'by', 'for', 'from', 'in', 'into', 'of', 'off', 'on', 'onto', 'out', 'over', 'per', 'to', 'up', 'with', 'as', '4-koma', '-hime', '-kei', '-kousai', '-sama', '-warashi', 'no', 'vs', 'x')
    # Abbreviations or acronyms that should be fully capitalised
    force_upper = ('3d', 'bdsm', 'cg', 'cgi', 'ed', 'fff', 'ffm', 'ii', 'milf', 'mmf', 'mmm', 'npc', 'op', 'rpg', 'tbs', 'tv')
    # Special cases where a specific capitalisation style is preferred
    force_special = {'comicfesta': 'ComicFesta', 'D\'etat': 'd\'Etat', 'Noitamina': 'noitaminA'}
    text = re.sub(r'[\'\w\d]+\b', lambda m:m.group(0).capitalize(), text) # Capitalise all words accounting for apostrophes
    for key in force_lower: text = re.sub(r'\b' + key + r'\b', key.lower(), text, flags=re.I) # Convert words from force_lower to lowercase
    for key in force_upper: text = re.sub(r'\b' + key + r'\b', key.upper(), text, flags=re.I) # Convert words from force_upper to uppercase
    text = text[:1].upper() + text[1:] # Force capitalise the first character no matter what
    for key, value in force_special.items(): text = re.sub(r'\b' + key + r'\b', value, text, flags=re.I) # Apply special cases as a last step
    return text

def try_get(arr, idx, default=''):
    try:    return arr[idx]
    except: return default

# Agent Declaration
class ShokoRelayAgent(Agent.TV_Shows, ShokoRelayAgent):
    name, primary_provider, fallback_agent = 'ShokoRelay', True, False
    contributes_to = ['com.plexapp.agents.none', 'com.plexapp.agents.hama']
    accepts_from   = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.lambda']
    languages      = [Locale.Language.English, 'fr', 'zh', 'sv', 'no', 'da', 'fi', 'nl', 'de', 'it', 'es', 'pl', 'hu', 'el', 'tr', 'ru', 'he', 'ja', 'pt', 'cs', 'ko', 'sl', 'hr']
    def search(self, results, media, lang, manual): self.Search(results, media, lang, manual)
    def update(self, metadata, media, lang, force): self.Update(metadata, media, lang, force)
