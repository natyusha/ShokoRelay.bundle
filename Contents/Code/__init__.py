import os, re, json, urllib, datetime

API_KEY = ''

def ValidatePrefs():
    pass

def Start():
    Log('======================[Shoko Relay Agent v1.2.15]======================')
    HTTP.Headers['Accept'] = 'application/json'
    HTTP.ClearCache()    # Clear the cache possibly removing stuck metadata
    HTTP.CacheTime = 0.1 # Reduce the cache time as much as possible since Shoko has all the metadata
    ValidatePrefs()

def GetApiKey():
    global API_KEY
    if not API_KEY:
        data = json.dumps({
            'user'   : Prefs['Username'],
            'pass'   : Prefs['Password'] if Prefs['Password'] != None else '',
            'device' : 'Shoko Relay for Plex'
        })
        API_KEY = HttpPost('api/auth', data)['apikey']
        # Log.debug('Got API KEY:                   %s' % API_KEY) # Not needed
    return API_KEY

def HttpPost(url, postdata):
    myheaders = {'Content-Type': 'application/json'}
    return JSON.ObjectFromString(HTTP.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders, data=postdata).content)

def HttpReq(url, retry=True):
    global API_KEY
    # Log('Requesting:                    %s' % url) # Not needed since debug logging shows these requests anyway
    myheaders = {'apikey': GetApiKey()}
    try:
        return JSON.ObjectFromString(HTTP.Request('http://%s:%s/%s' % (Prefs['Hostname'], Prefs['Port'], url), headers=myheaders).content)
    except Exception as e:
        if not retry: raise e
        API_KEY = ''
        return HttpReq(url, False)

class ShokoRelayAgent:
    def Search(self, results, media, lang, manual):
        # Search for the series using the name from the scanner
        name = media.show
        prelimresults = HttpReq('api/v3/Series/Search?query=%s&fuzzy=false&limit=10' % (urllib.quote_plus(name.encode('utf8')))) # http://127.0.0.1:8111/api/v3/Series/Search?query=Kowarekake%20no%20Orgel&fuzzy=false&limit=10
        for idx, series_data in enumerate(prelimresults):
            series_id = series_data['IDs']['ID']                                                              # Get series series id from series data
            airdate   = try_get(HttpReq('api/v3/Series/%s/AniDB' % series_id), 'AirDate', None)               # Get airdate from series id
            year      = airdate.split('-')[0] if airdate else None                                            # Get year from air date
            score     = 100 if series_data['Name'] == name else 99 - idx - int(series_data['Distance'] * 100) # Get score from name vs distance
            results.Append(MetadataSearchResult(str(series_id), series_data['Name'], year, score, lang))      # Tabulate the results

    def Update(self, metadata, media, lang, force):
        series_id = metadata.id

        # Get series data
        Log('==================[Shoko Relay for Series ID: %s]==================' % series_id.zfill(6))
        series_data = HttpReq('api/v3/Series/%s?includeDataFrom=AniDB,TMDB' % series_id) # http://127.0.0.1:8111/api/v3/Series/24?includeDataFrom=AniDB,TMDB

        # Make a dict of language -> title for all series titles in the AniDB series data (one pair per language)
        title_mod, series_titles = '[LANG]:               ', {}
        for item in [i for i in sorted(series_data['AniDB']['Titles'], key=lambda i: i['Type'], reverse=True) if i['Type'] != 'Short']: series_titles[item['Language']] = item['Name'] # Sort by reversed Type (Synonym -> Short (Excluded) -> Official -> Main) so that the dict prioritises official titles over synonyms
        series_titles['shoko'] = series_data['Name'] # Add Shoko's preferred series title to the dict

        # Get Title according to the language preference
        for lang in [l.strip().lower() for l in Prefs['SeriesTitleLanguage'].split(',')]:
            title = try_get(series_titles, lang, None)
            if title: break
        if not title: title, lang = series_titles['shoko'], 'shoko (fallback)' # If not found, fallback to Shoko's preferred series title

        # Move common title prefixes to the end of the title (pad with a space)
        if Prefs['moveCommonTitlePrefixes']:
            if title.startswith(('Gekijouban ', 'Eiga ', 'OVA ')): title_mod, title = '(Prefix Moved) [LANG]:', (lambda t: t[1] + ' — ' + t[0])(title.split(' ', 1))

        # Determine the TMDB type
        tmdb_type, tmdb_type_log, tmdb_title, tmdb_group, tmdb_group_log = None, '', '', False, ''
        if   try_get(series_data['TMDB']['Shows'], 0, None)  : tmdb_type, tmdb_type_log = 'Shows'  , 'tv/'
        elif try_get(series_data['TMDB']['Movies'], 0, None) : tmdb_type, tmdb_type_log = 'Movies' , 'movie/'
        if tmdb_type: # If TMDB type is populated add the title as a comparison to the regular one to help spot mismatches
            tmdb_title, tmdb_id = try_get(series_data['TMDB'][tmdb_type][0], 'Title', None), try_get(series_data['TMDB'][tmdb_type][0], 'ID', None)
            tmdb_title_log = 'N/A (CRITICAL: Removed from TMDB or Missing Data) - Falling Back to AniDB Ordering!' if not tmdb_title else tmdb_title # Account for rare cases where Shoko has a TMDB ID that returns no data
            Log('TMDB Check (Title [ID]):       %s [%s%s]' % (tmdb_title_log, tmdb_type_log, tmdb_id))

        # Get TMDB group information if SingleSeasonOrdering isn't enabled
        tmdb_ep_groups = HttpReq('api/v3/Series/%s/TMDB/Show/CrossReferences/EpisodeGroups?tmdbShowID=%s&pageSize=0' % (series_id, tmdb_id)) if not Prefs['SingleSeasonOrdering'] and tmdb_type == 'Shows' else None # http://127.0.0.1:8111/api/v3/Series/24/TMDB/Show/CrossReferences/EpisodeGroups?tmdbShowID=1873&pageSize=0

        metadata.title = title
        Log('Title %s   %s [%s]' % (title_mod, title, lang.upper()))

        # Get Alternate Title according to the language preference
        for lang in [l.strip().lower() for l in Prefs['SeriesAltTitleLanguage'].split(',')]:
            alt_title = try_get(series_titles, lang, None)
            if alt_title: break

        # Append the Alternate title to the Sort Title to make it searchable
        if alt_title and alt_title != metadata.title: metadata.title_sort = title + ' [' + alt_title + ']'
        else: alt_title, metadata.title_sort = 'Alternate Title Matches the Title - Skipping!', title
        Log('Alt Title (AddToSort) [LANG]:  %s [%s]' % (alt_title, lang.upper()))

        """ Enable if Plex fixes blocking legacy agent issue
        # Get Original Title
        if alt_title and alt_title != metadata.title: metadata.original_title = alt_title
        else: metadata.original_title = None
        Log('Original Title:                %s' % metadata.original_title)
        """

        # Get Originally Available
        metadata.originally_available_at = datetime.datetime.strptime(series_data['AniDB']['AirDate'], '%Y-%m-%d').date() if try_get(series_data['AniDB'], 'AirDate', None) else None
        Log('Originally Available:          %s' % metadata.originally_available_at)

        # Get Content Rating (missing metadata source)
        # metadata.content_rating =

        # Get Rating
        metadata.rating = float(series_data['AniDB']['Rating']['Value']/100)
        Log('Rating (Critic):               %s' % metadata.rating)

        # Get Studio as Animation Work (アニメーション制作)
        studio = HttpReq('api/v3/Series/%s/Cast?roleType=Studio' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Cast?roleType=Studio
        studio_source, studio = '(Animation Work):', try_get(studio, 0, None)
        if not studio: # If no Studio fallback and override with Work (制作) listing
            studio = HttpReq('api/v3/Series/%s/Cast?roleType=Staff&roleDetails=Work' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Cast?roleType=Staff&roleDetails=Work
            studio_source, studio = '(Work):          ', try_get(studio, 0, None)
        metadata.studio = studio['Staff']['Name'] if studio else None
        Log('Studio %s       %s' % (studio_source, metadata.studio))

        # Get Tagline (missing metadata source)
        # metadata.tagline =

        # Get Summary
        summary_source, metadata.summary = '(Preferred):    ', summary_sanitizer(try_get(series_data, 'Description', None))
        if not metadata.summary and tmdb_type: summary_source, metadata.summary = '(TMDB Fallback):', summary_sanitizer(try_get(series_data['TMDB'][tmdb_type][0], 'Overview', None)) # Fallback to the TMDB series summary if the default one is empty after being sanitized
        Log('Summary %s       %s' % (summary_source, metadata.summary))

        # Get Genres
        ## filter=1 removes TagBlacklistAniDBHelpers as defined here: https://github.com/ShokoAnime/ShokoServer/blob/d7c7f6ecdd883c714b15dbef385e19428c8d29cf/Shoko.Server/Utilities/TagFilter.cs#L37C44-L37C68
        series_tags = HttpReq('api/v3/Series/%s/Tags?filter=1&excludeDescriptions=true&orderByName=false&onlyVerified=true' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Tags?filter=1&excludeDescriptions=true&orderByName=false&onlyVerified=true
        metadata.genres.clear()

        ## Filter out weighted tags by the configured tag weight but leave ones weighted 0 as that means that they are unweighted (high priority) tags
        tags, c_rating, descriptor, descriptor_d, descriptor_s, descriptor_v = [], None, '', '', '', ''
        for tag in series_tags:
            if (tag['Weight'] == 0 or tag['Weight'] >= int(Prefs['minimumTagWeight'])): tags.append(title_case(tag['Name'])) # Convert tags to title case and add them to the list
            ## Prep weight based content ratings (if enabled) using the content indicators described here: https://wiki.anidb.net/Categories:Content_Indicators
            if Prefs['contentRatings']:
                indicator, weight = tag['Name'].lower(), tag['Weight']
                if indicator == 'nudity' or indicator == 'violence':             # Raise ratings for the "Nudity" and "Violence" tags to TV-14 and then TV-MA if the weight exceeds 400 and 500 respectively
                    if indicator == 'nudity': descriptor_s = 'S'                 # Apply the "Sexual Situations" descriptor for the "Nudity" tag
                    if indicator == 'violence': descriptor_v = 'V'               # Apply the "Violence" descriptor for the "Violence" tag
                    if weight >= 400 and c_rating != 'TV-MA': c_rating = 'TV-14' # Weight:400 = Full frontal nudity with nipples and/or visible genitals OR Any violence causing death and/or serious physical dismemberment (e.g. a limb is cut off)
                    if weight >= 500: c_rating = 'TV-MA'                         # Weight:500 = Most borderline porn / hentai OR Added gore, repetitive killing/mutilation of more than 1 individual
                if indicator == 'sex':                                           # Raise ratings for the "Sex" tag to TV-14 and then TV-MA if the weight exceeds 300 and 400 respectively
                    descriptor_s = 'S'                                           # Apply the "Sexual Situations" descriptor for the "Sex" tag
                    if weight >= 300 and c_rating != 'TV-MA': c_rating = 'TV-14' # Weight:300 = Sexual activity that is "on camera", but most of the action is not even indirectly visible
                    if weight >= 400: c_rating = 'TV-MA'                         # Weight:400 = Sexual activity that is "on camera", but most of the action is indirectly visible (99% TV-MA material)
                if indicator == 'sexual humour': descriptor_d = 'D'              # Apply the "Suggestive Dialogue" descriptor as a special case for the "Sexual Humour" tag
        if descriptor_d or descriptor_s or descriptor_v: descriptor = '-' + descriptor_d + descriptor_s + descriptor_v

        metadata.genres = tags
        Log('Genres:                        %s' % ', '.join(tags))

        # Get Collections
        groupinfo = HttpReq('api/v3/Series/%s/Group' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Group
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
        if Prefs['contentRatings']:
            if not c_rating: # If the rating wasn't already determined using the content indicators above take the lowest target audience rating
                if   'Kodomo' in tags                      : c_rating = 'TV-Y'
                elif 'Mina'   in tags                      : c_rating = 'TV-G'
                elif 'Shoujo' in tags or 'Shounen' in tags : c_rating = 'TV-PG'
                elif 'Josei'  in tags or 'Seinen'  in tags : c_rating = 'TV-14'
            if 'Borderline Porn' in tags: c_rating = 'TV-MA' # Override any previous rating for borderline porn content
            if c_rating: c_rating += descriptor              # Append the content descriptor using the content indicators above
            if '18 Restricted'   in tags: c_rating = 'X'     # Override any previous rating and remove content indicators for 18 restricted content

            metadata.content_rating = c_rating
            Log('Content Rating (Assumed):      %s' % metadata.content_rating)

        # Get Posters & Backgrounds
        if Prefs['addEveryImage']:
            series_images = HttpReq('api/v3/Series/%s/Images?includeDisabled=false' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Images?includeDisabled=false
            self.image_add(metadata.posters, sorted(try_get(series_images, 'Posters', []),   key=lambda p: not p['Preferred']), '(Poster):       ') # Move preferred poster to the top of the list
            self.image_add(metadata.art,     sorted(try_get(series_images, 'Backdrops', []), key=lambda b: not b['Preferred']), '(Background):   ') # Move preferred backdrop to the top of the list
        else: # Series data only contains the preferred image for each type
            self.image_add(metadata.posters, try_get(series_data['Images'], 'Posters', []),   '(Poster):       ')
            self.image_add(metadata.art,     try_get(series_data['Images'], 'Backdrops', []), '(Background):   ')

        # Get Cast & Crew
        cast_crew = HttpReq('api/v3/Series/%s/Cast' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Cast
        metadata.roles.clear()
        cv_check, image_base = False, 'http://%s:%s/api/v3/Image/' % (Prefs['Hostname'], Prefs['Port'])
        Log('-----------------------------------------------------------------------')
        Log('Character                      Seiyuu (CV)                    Image')
        Log('-----------------------------------------------------------------------')
        for role in [r for r in cast_crew if r['RoleName'] == 'Seiyuu']: # Filter cast to Seiyuu Only
            cv_check, meta_role, image, meta_role.name, meta_role.role = True, metadata.roles.new(), role['Staff']['Image'], role['Staff']['Name'], try_get(role.get('Character', None), 'Name', 'Unnamed (AniDB)')
            if image: meta_role.photo = image_base + '%s/%s/%s' % (image['Source'], image['Type'], image['ID'])
            Log('%-30s %-30s %s' % (meta_role.role, meta_role.name, try_get(image, 'ID', None)))
        if not cv_check: Log('N/A')

        director_name, writer_name, staff_check = [], [], False
        if Prefs['crewListings']:
            Log('-----------------------------------------------------------------------')
            Log('Role                           Staff Name                     Image')
            Log('-----------------------------------------------------------------------')
            for role in [r for r in cast_crew if r['RoleName'] != 'Seiyuu']: # Second loop filtered for staff only so that Seiyuu appear first in the list
                staff_check, meta_role, image, meta_role.name, role_type = True, metadata.roles.new(), role['Staff']['Image'], role['Staff']['Name'], role['RoleName']
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
                if image: meta_role.photo = image_base + '%s/%s/%s' % (image['Source'], image['Type'], image['ID'])
                Log('%-30s %-30s %s' % (meta_role.role, meta_role.name, try_get(image, 'ID', None)))
            if not staff_check: Log('N/A')

        # Get episode list using series ID
        episodes = HttpReq('api/v3/Series/%s/Episode?pageSize=0' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/Episode?pageSize=0

        for episode in episodes['List']:
            # Get episode data
            episode_id   = episode['IDs']['ID']
            episode_data = HttpReq('api/v3/Episode/%s?includeDataFrom=AniDB,TMDB' % episode_id) # http://127.0.0.1:8111/api/v3/Episode/212?includeDataFrom=AniDB,TMDB
            tmdb_ep_data = try_get(episode_data['TMDB']['Episodes'], 0, None) if tmdb_title else None
            episode_type = episode_data['AniDB']['Type'] # Get episode type

            # Ignore TMDB numbering for episodes split across multiple files (prevent file stacking in Plex)
            if tmdb_ep_data and tmdb_ep_groups:
                for xref in [group for groups in [grp for grp in tmdb_ep_groups['List'] if len(grp) > 1] for group in groups]:
                    if tmdb_group: continue
                    if xref['AnidbEpisodeID'] == episode_data['AniDB']['ID']: tmdb_group, tmdb_group_log = True, ' (TMDB Episode Grouping Detected!)'

            # Get season and episode numbers
            episode_source, season = '(AniDB):', 0
            if   episode_type == 'Normal'    : season =  1
            elif episode_type == 'Special'   : season =  0
            elif episode_type == 'ThemeSong' : season = -1
            elif episode_type == 'Trailer'   : season = -2
            elif episode_type == 'Parody'    : season = -3
            elif episode_type == 'Other'     : season = -4
            if not Prefs['SingleSeasonOrdering'] and tmdb_ep_data and not tmdb_group: episode_source, season, episode_number = '(TMDB): ', tmdb_ep_data['SeasonNumber'], tmdb_ep_data['EpisodeNumber'] # Grab TMDB info when possible and SingleSeasonOrdering is disabled
            else: episode_number = episode_data['AniDB']['EpisodeNumber'] # Fallback to AniDB info

            Log('Season %s                %s%s' % (episode_source, season, tmdb_group_log))
            Log('Episode %s               %s%s' % (episode_source, episode_number, tmdb_group_log))

            episode_obj = metadata.seasons[season].episodes[episode_number]

            # Make a dict of language -> title for all episode titles in the AniDB episode data
            episode_titles = {}
            for item in episode_data['AniDB']['Titles']: episode_titles[item['Language']] = item['Name']
            episode_titles['shoko'] = episode_data['Name'] # Add Shoko's preferred episode title to the dict

            # Get episode title according to the language preference
            ep_title_mod, tmdb_ep_title = '[LANG]:                 ', try_get(tmdb_ep_data, 'Title', None)
            for lang in [l.strip().lower() for l in Prefs['EpisodeTitleLanguage'].split(',')]:
                episode_title = try_get(episode_titles, lang, None)
                if episode_title: break
            if not episode_title: episode_title, lang = episode_titles['shoko'], 'shoko (fallback)' # If not found, fallback to Shoko's preferred episode title

            # Replace ambiguous title with series title
            if episode_title in ('Complete Movie', 'Music Video', 'OAD', 'OVA', 'Short Movie', 'Special', 'TV Special', 'Web'):
                # Get series title according to the language preference
                ep_title_mod, original_title = '(FromSeries) [LANG]:    ', episode_title
                for lang in [l.strip().lower() for l in Prefs['EpisodeTitleLanguage'].split(',')]:
                    if lang != 'shoko': episode_title = try_get(series_titles, lang, episode_title) # Exclude "shoko" as it will return the preferred language for series and not episodes
                    if episode_title != original_title: break
                if episode_title == original_title and tmdb_ep_title: ep_title_mod, episode_title = '(TMDB) [LANG]:          ', tmdb_ep_title # Fallback to the TMDB title if there is a TMDB Episodes match
                if episode_title == original_title: episode_title, lang = try_get(series_titles, 'en', episode_title), 'en (fallback)'        # If not found, fallback to EN series title as a last resort
                if original_title != episode_title and original_title not in episode_title: # Append ambiguous title to series title if a replacement title was found and it doesn't contain it
                    if original_title == 'Complete Movie': episode_title = re.sub(r'(:? The)?( Movie| Motion Picture)', '', episode_title) # Reduce redundant movie descriptors
                    episode_title += ' — ' + original_title

            # TMDB episode title override (if the episode title is Episode/Volume [S]# on AniDB excluding Episode/Volume 0) and there is a TMDB match
            default_titles = r'^(Episode|Volume) S?[1-9][0-9]*$' # Regex pattern for default episode titles
            if tmdb_ep_title and re.match(default_titles, episode_title) and not re.match(default_titles, tmdb_ep_title): ep_title_mod, episode_title, lang = '(TMDB Override) [LANG]: ', tmdb_ep_title, 'shoko'

            episode_obj.title = episode_title
            Log('Title %s %s [%s]' % (ep_title_mod, episode_obj.title, lang.upper()))

            # Get Originally Available
            airdate_log = episode_obj.originally_available_at = datetime.datetime.strptime(episode_data['AniDB']['AirDate'], '%Y-%m-%d').date() if try_get(episode_data['AniDB'], 'AirDate', None) else None
            # Remove the air dates for negative seasons according to the preference
            if season == -4 and Prefs['disableNegativeSeasonAirdates'] == 'Exclude Other': pass
            elif season < 0 and Prefs['disableNegativeSeasonAirdates'] != 'Disabled':
                airdate_log, episode_obj.originally_available_at = 'Disabled in Agent Settings - Skipping!', None
            Log('Originally Available:          %s' % airdate_log)

            # Get Content Ratings (from series)
            episode_obj.content_rating = metadata.content_rating
            Log('Content Rating (Assumed):      %s' % episode_obj.content_rating)

            # Get Rating
            episode_obj.rating = episode_data['AniDB']['Rating']['Value']
            Log('Rating:                        %s' % float(episode_obj.rating))

            # Get Summary
            episode_obj.summary = summary_sanitizer(try_get(episode_data, 'Description', None))
            Log('Summary (Preferred):           %s' % episode_obj.summary)

            # Get Writer as Original Work (原作) [if there is only one]
            episode_obj.writers.clear()
            writer_log = None
            if   len(writer_name) == 1 : writer_log = episode_obj.writers.new().name = writer_name[0]
            elif len(writer_name)  > 1 : writer_log = 'Multiple Writers Detected - Skipping!'
            Log('Writer (Original Work):        %s' % writer_log)

            # Get Director as Direction (監督) [if there is only one]
            episode_obj.directors.clear()
            director_log = None
            if   len(director_name) == 1 : director_log = episode_obj.directors.new().name = director_name[0]
            elif len(director_name)  > 1 : director_log = 'Multiple Directors Detected - Skipping!'
            Log('Director:                      %s' % director_log)

            # Get Episode Poster (Grabs all episode thumbnails by default since there is no way to set a preferred one in Shoko's UI)
            if Prefs['tmdbThumbnails']: self.image_add(episode_obj.thumbs, try_get(try_get(episode_data, 'Images', {}), 'Thumbnails', []), '(Thumbnail):    ')

        # Get Season Posters (Grabs all season posters by default since there is no way to set a preferred one in Shoko's UI)
        if Prefs['tmdbSeasonPosters'] and tmdb_type == 'Shows' and len(metadata.seasons) > 1: # Skip if there is only a single season in Plex since those should be set to hidden
            seasons = HttpReq('api/v3/Series/%s/TMDB/Season?include=Images' % series_id) # http://127.0.0.1:8111/api/v3/Series/24/TMDB/Season?include=Images
            for season_num in [s for s in metadata.seasons if s >= 0]: # Skip negative seasons as they will never have TMDB posters
                for season in [s for s in seasons if int(season_num) == s['SeasonNumber']]: self.image_add(metadata.seasons[season_num].posters, try_get(season['Images'], 'Posters', []), '(Season Poster):')

        """ Enable if Plex fixes blocking legacy agent issue
        # Set custom negative season names
        for season_num in metadata.seasons:
            season_title = None
            if   season_num == '-1' : season_title = 'Credits'
            elif season_num == '-2' : season_title = 'Trailers'
            elif season_num == '-3' : season_title = 'Parodies'
            elif season_num == '-4' : season_title = 'Other'
            if int(season_num) < 0 and season_title:
                Log('Renaming Season:               %s to %s' % (season_num, season_title))
                metadata.seasons[season_num].title = season_title
        """

        # Get Plex theme music using a TvDB ID cross referenced from TMDB
        if Prefs['themeMusic']:
            if tmdb_type and try_get(series_data['TMDB'][tmdb_type][0], 'TvdbID', None):
                theme_url = 'http://tvthemes.plexapp.com/%s.mp3' % series_data['TMDB'][tmdb_type][0]['TvdbID']
                if theme_url not in metadata.themes:
                    try:
                        metadata.themes[theme_url] = Proxy.Media(HTTP.Request(theme_url))
                        Log('Adding Theme Music:            %s' % theme_url % tid)
                    except:
                        Log('Error Adding Theme Music:      %s (Not Found)' % theme_url)

    def image_add(self, meta, images, log):
        valid, url = list(), ''
        for image in images:
            try:
                url = 'http://%s:%s/api/v3/Image/%s/%s/%s' % (Prefs['Hostname'], Prefs['Port'], image['Source'], image['Type'], image['ID'])
                meta[url] = Proxy.Media(HTTP.Request(url).content, try_get(image, 'index', 0))
                valid.append(url)
                Log('Image Add %s     %s' % (log, url))
            except:
                Log('Image Add Err %s %s (Not Found)' % (log, url))

        meta.validate_keys(valid)
        for key in [k for k in meta.keys() if k not in valid]: del meta[key]

def summary_sanitizer(summary):
    if summary:
        if Prefs['sanitizeSummary'] != 'Allow Both Types':
            if Prefs['sanitizeSummary'] != 'Allow Info Lines'  : summary = re.sub(r'\(?\b((Modified )?Sour?ce|Note( [1-9])?|Summ?ary|From|See Also):(?!$| a daikon)([^\r\n]+|$)', '', summary, flags=re.I|re.M)   # Remove the line if it starts with ("Source: ", "Note: ", "Summary: ")
            if Prefs['sanitizeSummary'] != 'Allow Misc. Lines' : summary = re.sub(ur'^(\*|[\u2014~-] (adapted|source|description|summary|translated|written):?) ([^\r\n]+|$)', '', summary, flags=re.I|re.M|re.U) # Remove the line if it starts with ("* ", "— ", "- ", "~ ")
        summary = re.sub(r'(?:http:\/\/anidb\.net\/(?:ch|co|cr|[feast]|(?:character|creator|file|episode|anime|tag)\/)(?:\d+)) \[([^\]]+)]', r'\1', summary) # Replace AniDB links with text
        summary = re.sub(r'\[i\](?!"The Sasami|"Stellar|In the distant| occurred in)(.*?)\[\/i\]', '', summary, flags=re.I|re.S) # Remove BBCode [i][/i] tags and their contents (AniDB API Bug)
        summary = re.sub(r'\[\/?i\]', '', summary)             # Remove solitary leftover BBCode [i] or [/i] tags (AniDB API Bug)
        summary = re.sub(r'\n{2,}', r'\n', summary)            # Condense stacked empty lines
        summary = re.sub(r'\s{2,}', ' ', summary).strip(' \n') # Remove double spaces and strip spaces and newlines
    if not summary: summary = None # For logging purposes
    return summary

def title_case(text):
    # Words to force lowercase in tags to follow AniDB capitalisation rules: https://wiki.anidb.net/Capitalisation (some romaji tag endings and separator words are also included)
    force_lower = ('a', 'an', 'the', 'and', 'but', 'or', 'nor', 'at', 'by', 'for', 'from', 'in', 'into', 'of', 'off', 'on', 'onto', 'out', 'over', 'per', 'to', 'up', 'with', 'as', '4-koma', '-hime', '-kei', '-kousai', '-sama', '-warashi', 'no', 'vs', 'x')
    # Abbreviations or acronyms that should be fully capitalised
    force_upper = ('3d', 'bdsm', 'cg', 'cgi', 'ed', 'fff', 'ffm', 'ii', 'milf', 'mmf', 'mmm', 'npc', 'op', 'rpg', 'tbs', 'tv')
    # Special cases where a specific capitalisation style is preferred
    force_special = {'comicfesta': 'ComicFesta', 'd\'etat': 'd\'Etat', 'noitamina': 'noitaminA'}
    text = re.sub(r'[\'\w\d]+\b', lambda t: t.group(0).capitalize(), text)                               # Capitalise all words accounting for apostrophes
    for key in force_lower: text = re.sub(r'\b' + key + r'\b', key.lower(), text, flags=re.I)            # Convert words from force_lower to lowercase
    for key in force_upper: text = re.sub(r'\b' + key + r'\b', key.upper(), text, flags=re.I)            # Convert words from force_upper to uppercase
    text = text[:1].upper() + text[1:]                                                                   # Force capitalise the first character no matter what
    if ' ' in text: text = (lambda t: t[0] + ' ' + t[1][:1].upper() + t[1][1:])(text.rsplit(' ', 1))     # Force capitalise the first character of the last word no matter what
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
