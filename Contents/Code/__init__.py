import os, re, json, urllib
from datetime import datetime

API_KEY = ''

def ValidatePrefs():
    pass

def Start():
    Log('Shoko Relay Agent Started')
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
        Log.Debug('Got API KEY: %s' % resp)
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

        # Hardcode search replacement for "86" since it currently doesn't work as a search term with /api/v3/Series/Search
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

            score = 100 if series_data['Name'] == name else 100 - index - int(series_data['Distance'] * 100)

            meta = MetadataSearchResult(str(series_id), series_data['Name'], year, score, lang)
            results.Append(meta)

    def Update(self, metadata, media, lang, force):
        aid = metadata.id

        # Get series data
        Log('################## ShokoRelay for Series ID: %-*s ##################' % (7, aid))
        series_data = HttpReq('api/v3/Series/%s?includeDataFrom=AniDB' % aid) # http://127.0.0.1:8111/api/v3/Series/24?includeDataFrom=AniDB

        # Make a dict of language -> title for all series titles in anidb data
        series_titles = {}
        for item in series_data['AniDB']['Titles']:
            if item['Type'] != 'Short': # Exclude all short titles
                series_titles[item['Language']] = item['Name']
        series_titles['shoko'] = series_data['Name']

        # Get Title according to the preference
        title = None
        for lang in Prefs['SeriesTitleLanguagePreference'].split(','):
            lang = lang.strip()
            title = try_get(series_titles, lang.lower(), None)
            if title: break
        if title is None: title = series_titles['shoko'] # If not found, fallback to preferred title in Shoko

        metadata.title = title
        Log('Title:                         %s' % title)

        # Get alternate Title according to the preference
        alt_title = None
        for lang in Prefs['SeriesAltTitleLanguagePreference'].split(','):
            lang = lang.strip()
            alt_title = try_get(series_titles, lang.lower(), None)
            if alt_title: break


        # Append the alternate title to the Sort Title to make it searchable
        if alt_title is not None and alt_title != metadata.title:
            metadata.title_sort = title + ' [' + alt_title + ']'
            Log('Alternate Title:               %s' % alt_title)
        else:
            metadata.title_sort = title
            Log('Alternate Title:               Alternate Title Matches the Title - Skipping!')

        # Get Original Title (enable if Plex fixes blocking issue)
        # original_title = None
        # for item in series_data['AniDB']['Titles']:
        #     if item['Type'] == 'Main':
        #         original_title = item['Name']
        #         break
        # metadata.original_title = original_title

        # Get Originally Available
        airdate = try_get(series_data['AniDB'], 'AirDate', None)
        if airdate:
            metadata.originally_available_at = datetime.strptime(airdate, '%Y-%m-%d').date()
            Log('Originally Available:          %s' % metadata.originally_available_at)
        else:
            Log('Originally Available:          %s' % None)

        # Get Content Rating (missing metadata source)
        # metadata.content_rating =

        # Get Rating
        metadata.rating = float(series_data['AniDB']['Rating']['Value']/100)
        Log('Rating:                        %s' % metadata.rating)

        # Get Studio
        studio = HttpReq('api/v3/Series/%s/Cast?roleType=Studio' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Cast?roleType=Studio
        studio = try_get(studio, 0, None)
        if not studio: # If no studio use Animation Work listing
            studio = HttpReq('api/v3/Series/%s/Cast?roleType=Staff&roleDetails=Work' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Cast?roleType=Staff&roleDetails=Work
            studio = try_get(studio, 0, None)
        if studio:
            metadata.studio = studio['Staff']['Name']
            Log('Studio:                        %s' % studio['Staff']['Name'])
        else:
            Log('Studio:                        %s' % None)

        # Get Tagline (missing metadata source)
        # metadata.tagline =

        # Get Summary
        if try_get(series_data['AniDB'], 'Description', None):
            metadata.summary = summary_sanitizer(try_get(series_data['AniDB'], 'Description'))
            Log('Summary:                       %s' % metadata.summary)
        else:
            Log('Summary:                       %s' % None)

        # Get Genres
        ## filter=1 removes TagBlacklistAniDBHelpers as defined here: https://github.com/ShokoAnime/ShokoServer/blob/d7c7f6ecdd883c714b15dbef385e19428c8d29cf/Shoko.Server/Utilities/TagFilter.cs#L37C44-L37C68
        series_tags = HttpReq('api/v3/Series/%s/Tags?filter=1&excludeDescriptions=true&orderByName=false&onlyVerified=true' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Tags?filter=1&excludeDescriptions=true&orderByName=false&onlyVerified=true
        metadata.genres.clear()
        
        ## Filter out weighted tags by the configured tag weight but leave ones weighted 0 as that means that they are unweighted tags
        tags, tags_list = [], None
        for tag in series_tags:
            if tag['Weight'] == 0 or tag['Weight'] >= int(Prefs['minimumTagWeight']):
                tags.append(tag['Name'])
        metadata.genres = tags
        if tags:
            tags_list = ', '.join(tags)
            Log('Genres:                        %s' % tags_list)
        else:
            Log('Genres:                        %s' % None)

        # Get Collections
        metadata.collections.clear()
        groupinfo = HttpReq('api/v3/Series/%s/Group' % aid)
        if groupinfo['Size'] > 1:
            metadata.collections = [groupinfo['Name']]
            Log('Collection:                    %s' % groupinfo['Name'])
        else:
            Log('Collection:                    %s' % None)

        # Get Labels (likely never to be supported)
        # metadata.labels.clear()
        # if try_get(series_data['AniDB'], 'Type', None):
        #     metadata.labels = [try_get(series_data['AniDB'], 'Type')]
        #     Log('Labels:                        %s' % metadata.labels)
        # else: 
        #     Log('Labels:                        %s' % None)

        # Get Content Rating (assumed from Genres)
        ## A rough approximation of: http://www.tvguidelines.org/resources/TheRatings.pdf
        ## Uses the target audience tags on AniDB: https://anidb.net/tag/2606/animetb
        if Prefs['contentRatings']:
            rating = None
            tags_lower = [tag.lower() for tag in tags] # Account for inconsistent capitalization of tags
            if 'kodomo' in tags_lower: rating = 'TV-Y'
            if 'mina' in tags_lower: rating = 'TV-G'
            if ('shoujo' or 'shounen') in tags_lower: rating = 'TV-14'
            if ('josei' or 'seinen' or 'tv censoring') in tags_lower: rating = 'TV-MA'
            if ('borderline porn') in tags_lower: rating = 'TV-MA-S'
            if '18 restricted' in tags_lower: rating = 'X'

            metadata.content_rating = rating
            Log('Content Rating (Assumed):      %s' % metadata.content_rating)

        # Get Posters & Backgrounds
        images = try_get(series_data, 'Images', {})
        self.metadata_add(metadata.posters, try_get(images, 'Posters', []))
        self.metadata_add(metadata.banners, try_get(images, 'Banners', []))
        self.metadata_add(metadata.art, try_get(images, 'Fanarts', []))

        # Get Cast & Crew
        cast_crew = HttpReq('api/v3/Series/%s/Cast' % aid) # http://127.0.0.1:8111/api/v3/Series/24/Cast
        Log('-----------------------------------------------------------------------')
        Log('Character                      Seiyuu')
        Log('-----------------------------------------------------------------------')
        metadata.roles.clear()
        for role in cast_crew:
            role_name = role['RoleName']
            if role_name != 'Seiyuu': continue # Skip if not seiyuu
            meta_role = metadata.roles.new()
            meta_role.name = role['Staff']['Name']
            meta_role.role = role['Character']['Name']

            Log('%-30s %s' % (meta_role.role, meta_role.name))
            image = role['Staff']['Image']
            if image:
                meta_role.photo = 'http://{host}:{port}/api/v3/Image/{source}/{type}/{id}'.format(host=Prefs['Hostname'], port=Prefs['Port'], source=image['Source'], type=image['Type'], id=image['ID'])
    
        director_name, writer_name = [], []
        if Prefs['crewListings']:
            Log('-----------------------------------------------------------------------')
            Log('Role                           Staff Name')
            Log('-----------------------------------------------------------------------')
            for role in cast_crew: # Second loop for cast so that seiyuu appear first in the list
                role_name = role['RoleName']
                if role_name in ('Seiyuu', 'Staff'): continue # Skip if not part of the main staff or a seiyuu
                meta_role = metadata.roles.new()
                meta_role.name = role['Staff']['Name']
                if role_name == 'Director': # Initialize Director outside of the episodes loop to avoid repeated requests per episode
                    meta_role.role = 'Director'
                    director_name.append(meta_role.name)
                elif role_name == 'SourceWork': # Initialize Writer outside of the episodes loop to avoid repeated requests per episode
                    meta_role.role = 'Writer (Original Work)'
                    writer_name.append(meta_role.name)
                elif role_name == 'CharacterDesign': meta_role.role = role['RoleDetails']
                elif role_name == 'SeriesComposer': meta_role.role = 'Chief Scriptwriter'
                elif role_name == 'Producer': meta_role.role = role['RoleDetails']
                elif role_name == 'Music': meta_role.role = 'Composer'
                else: meta_role.role = role_name

                Log('%-30s %s' % (meta_role.role, meta_role.name))
                image = role['Staff']['Image']
                if image:
                    meta_role.photo = 'http://{host}:{port}/api/v3/Image/{source}/{type}/{id}'.format(host=Prefs['Hostname'], port=Prefs['Port'], source=image['Source'], type=image['Type'], id=image['ID'])

        # Get episode list using series ID
        episodes = HttpReq('api/v3/Series/%s/Episode?pageSize=0' % aid) # http://127.0.0.1:8111/api/v3/Series/212/Episode?pageSize=0

        for episode in episodes['List']:
            # Get episode data
            episode_id = episode['IDs']['ID']
            episode_data = HttpReq('api/v3/Episode/%s?includeDataFrom=AniDB,TvDB' % episode_id) # http://127.0.0.1:8111/api/v3/Episode/212?includeDataFrom=AniDB,TvDB

            # Get episode type
            episode_type = episode_data['AniDB']['Type']

            # Get season number
            season = 0
            episode_source = '(AniDB):'
            if episode_type == 'Normal': season = 1
            elif episode_type == 'Special': season = 0
            elif episode_type == 'ThemeSong': season = -1
            elif episode_type == 'Trailer': season = -2
            elif episode_type == 'Parody': season = -3
            elif episode_type == 'Other': season = -4
            if not Prefs['SingleSeasonOrdering']: episode_data['TvDB'] = try_get(episode_data['TvDB'], 0, None) # Grab TvDB info when SingleSeasonOrdering isn't enabled

            if not Prefs['SingleSeasonOrdering'] and episode_data['TvDB']:
                season = episode_data['TvDB']['Season']
                episode_number = episode_data['TvDB']['Number']
                episode_source = '(TvDB): '
            else: episode_number = episode_data['AniDB']['EpisodeNumber']

            Log('Season %s                %s' % (episode_source, season))
            Log('Episode %s               %s' % (episode_source, episode_number))

            episode_obj = metadata.seasons[season].episodes[episode_number]

            # Make a dict of language -> title for all episode titles in anidb data
            episode_titles = {}
            for item in episode_data['AniDB']['Titles']: episode_titles[item['Language']] = item['Name']

            # Get episode Title according to the preference
            title = None
            title_source = '(AniDB):       '
            for lang in Prefs['EpisodeTitleLanguagePreference'].split(','):
                lang = lang.strip()
                title = try_get(episode_titles, lang.lower(), None)
                if title: break
            if title is None: title = episode_titles['en'] # If not found, fallback to EN title

            # Replace Ambiguous Title with series Title
            SingleEntryTitles = ['Complete Movie', 'Music Video', 'OAD', 'OVA', 'Short Movie', 'TV Special', 'Web'] # AniDB titles used for single entries which are ambiguous
            if title in SingleEntryTitles:
                # Get series title according to the preference
                single_title = title
                for lang in Prefs['EpisodeTitleLanguagePreference'].split(','):
                    lang = lang.strip()                                   
                    title = try_get(series_titles, lang.lower(), title)
                    title_source = '(AniDB Series):'
                    if title is not single_title: break
                if title is single_title: # If not found, fallback to EN series title
                    title = try_get(series_titles, 'en', title)
                if title is single_title: # Fallback to TvDB title as a last resort
                    if try_get(episode_data['TvDB'], 'Title', None):
                        title = try_get(episode_data['TvDB'], 'Title')
                        title_source = '(TvDB):        '
                # Append Ambiguous Title to series Title if a replacement title was found and it doesn't contain it
                if single_title != title and single_title not in title: title = title + ' — ' + single_title

            # TvDB episode title fallback
            if title.startswith('Episode ') and try_get(episode_data['TvDB'], 'Title', None):
                title = try_get(episode_data['TvDB'], 'Title')
                title_source = '(TvDB):        '

            episode_obj.title = title
            Log('Title %s          %s' % (title_source, episode_obj.title))

            # Get Originally Available
            airdate = try_get(episode_data['AniDB'], 'AirDate', None)
            if airdate:
                episode_obj.originally_available_at = datetime.strptime(airdate, '%Y-%m-%d').date()
                Log('Originally Available:          %s' % episode_obj.originally_available_at)

            # Get Content Ratings (from series)
            episode_obj.content_rating = metadata.content_rating
            Log('Content Rating (Assumed):      %s' % episode_obj.content_rating)

            # Get Rating
            episode_obj.rating = episode_data['AniDB']['Rating']['Value']
            Log('Rating:                        %s' % float(episode_obj.rating))
            
            # Get Summary
            if try_get(episode_data['AniDB'], 'Description', None):
                episode_obj.summary = summary_sanitizer(try_get(episode_data['AniDB'], 'Description', None))
                Log('Summary (AniDB):               %s' % episode_obj.summary)
            elif episode_data['TvDB'] and try_get(episode_data['TvDB'], 'Description', None): 
                episode_obj.summary = summary_sanitizer(try_get(episode_data['TvDB'], 'Description', None))
                Log('Summary (TvDB):                %s' % episode_obj.summary)
            else:
                Log('Summary:                       %s' % None)

            # Get Writer (Original Work) (if there is only one)
            episode_obj.writers.clear()
            if len(writer_name) == 1:
                writer = episode_obj.writers.new()
                writer.name = writer_name[0]
                Log('Writer (Original Work):        %s', writer_name[0])
            elif len(writer_name) > 1:
                Log('Writer (Original Work):        Multiple Writers Detected - Skipping!')
            else:
                Log('Writer (Original Work):        %s' % None)

            # Get Director (if there is only one)
            episode_obj.directors.clear()
            if len(director_name) == 1:
                director = episode_obj.directors.new()
                director.name = director_name[0]
                Log('Director:                      %s' % director_name[0])
            elif len(director_name) > 1:
                Log('Director:                      Multiple Directors Detected - Skipping!')
            else:
                Log('Director:                      %s' % None)

            # Get Episode Poster (Thumbnail)
            if Prefs['customThumbs']:
                self.metadata_add(episode_obj.thumbs, [try_get(try_get(episode_data['TvDB'], 0, {}), 'Thumbnail', {})])

        # Set custom negative season names (enable if Plex fixes blocking issue)
        # for season_num in metadata.seasons:
        #     season_title = None
        #     if season_num == '-1': season_title = 'Credits'
        #     elif season_num == '-2': season_title = 'Trailers'
        #     elif season_num == '-3': season_title = 'Parodies'
        #     elif season_num == '-4': season_title = 'Other'
        #     if int(season_num) < 0 and season_title is not None:
        #         Log('Renaming season: %s to %s' % (season_num, season_title))
        #         metadata.seasons[season_num].title = season_title

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
    if Prefs['synposisCleanLinks']:
        summary = re.sub(r'https?:\/\/\w+.\w+(?:\/?\w+)? \[([^\]]+)\]', r'\1', summary) # Replace links
    if Prefs['synposisCleanMiscLines']:
        summary = re.sub(r'^(\*|--|~) .*', '', summary, flags=re.MULTILINE)             # Remove the line if it starts with ('* ' / '-- ' / '~ ')
    if Prefs['synposisRemoveSummary']:
        summary = re.sub(r'\n(Source|Note|Summary):.*', '', summary, flags=re.DOTALL)   # Remove all lines after this is seen
    if Prefs['synposisCleanMultiEmptyLines']:
        summary = re.sub(r'\n\n+', r'\n\n', summary, flags=re.DOTALL)                   # Condense multiple empty lines
    return summary.strip(' \n')

def try_get(arr, idx, default=''):
    try:
        return arr[idx]
    except:
        return default

# Agent Declaration
class ShokoRelayAgent(Agent.TV_Shows, ShokoRelayAgent):
    name, primary_provider, fallback_agent = 'ShokoRelay', True, False
    contributes_to = ['com.plexapp.agents.none', 'com.plexapp.agents.hama']
    accepts_from = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.lambda']
    languages = [Locale.Language.English, 'fr', 'zh', 'sv', 'no', 'da', 'fi', 'nl', 'de', 'it', 'es', 'pl', 'hu', 'el', 'tr', 'ru', 'he', 'ja', 'pt', 'cs', 'ko', 'sl', 'hr']
    def search(self, results, media, lang, manual): self.Search(results, media, lang, manual)
    def update(self, metadata, media, lang, force): self.Update(metadata, media, lang, force)
