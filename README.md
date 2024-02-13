ShokoRelay.bundle
====================
This is a Plex library metadata agent/scanner written to work with anything listed on AniDB. All you need to get started is [Shoko Server](https://shokoanime.com/) and [Plex Media Server](https://www.plex.tv/media-server-downloads/). Unlike the original metadata bundle for Shoko this one does not include a movie scanner and is intended to work with series of all types within a single "TV Shows" library.

### Installation
- Unzip [this repository](https://github.com/natyusha/ShokoRelay.bundle/archive/refs/heads/master.zip) into `\Plex Media Server\Plug-ins`
- Remove `-master` from the end of the resulting folder name (the folder name should be `ShokoRelay.bundle`)
- Move the `Scanners` folder located in `Contents` to `\Plex Media Server\`
- Navigate to `\Plex Media Server\Scanners\Series` and enter your Shoko credentials into `Shoko Relay Scanner.py` with a text editor:
	- Hostname
	- Port
	- Username
	- Password
- Add a `TV Shows` library in Plex and configure the following options under `Advanced`:
	- Scanner: `Shoko Relay Scanner`
	- Agent: `ShokoRelay`
	- The Shoko Server Username
	- The Shoko Server Password
	- The Shoko Server Hostname
	- The Shoko Server Port
	- Collections: `Hide items which are in collections`
	- Seasons: `Hide for single-season series`
- In Plex Settings: `Settings > Agents > Shows > ShokoRelay` move the following entry to the top of the list and enable it:
	- [x] Local Media Assets (TV)

### Changes from Shoko Metadata
- Uses Shoko's v3 API for fetching metadata
- Series and movies will list the studio
- Episodes and movies will list the writer and director
- Will apply content ratings like "TV-14", 'TV-Y' etc. (if the corresponding AniDB tags are present)
- Allows the user to configure the language for the series title (if they want a different language than in Shoko)
- Allows the user to configure an additional 'Alt Title' language for the series title (which will be searchable in Plex)
- Allows the user to configure what language they want for episode titles
- Will use TheTVDB descriptions and episode titles if AniDB is missing that information
- Will replace ambiguous AniDB episode titles with the series title plus a suffix for the type of episode
- Removes the original tag hiding options and replaces them with a tag weight system similar to what HAMA uses
- Automatically ignores all tags from Shoko's [TagBlacklistAniDBHelpers](https://github.com/ShokoAnime/ShokoServer/blob/d7c7f6ecdd883c714b15dbef385e19428c8d29cf/Shoko.Server/Utilities/TagFilter.cs#L37C44-L37C68) list
- Allows movies and series to be in the same library at once
- Allows multi season shows matched on TheTVDB to be merged into a single entry
- Support for Credits / Parodies / Trailers and Other types of special files
- Support for files which contain more than one episode

### Scripts
- The following scripts all require [Python 3](https://www.python.org/downloads/) to be installed.
- Some of them also require additional Python Packages which can installed using [pip](https://pypi.org/project/pip/):
	1. [Python-PlexAPI](https://pypi.org/project/PlexAPI/) `pip install plexapi`
	2. [Requests](https://pypi.org/project/requests/) `pip install requests`
- The animethemes script has the additional requirement of: [FFmpeg](https://ffmpeg.org/)

#### [animethemes.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/animethemes.py)
- This script uses the Shoko and AnimeThemes APIs to find the OP/ED for a series and convert it into a Theme.mp3 file which will play when viewing the series in Plex.
- The default themes grabbed by Plex are limited to 30 seconds long and are completely missing for a massive amount of anime making this a great upgrade to local metadata.

#### [collection-posters.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/collection-posters.py)
- This script uses the Python-PlexAPI and Shoko Server to apply posters to the collections in Plex.
- It will look for posters in a user defined folder and if none are found take the default poster from the corresponding Shoko group.

#### [force-metadata.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/force-metadata.py)
- This script uses the Python-PlexAPI to force all metadata in your anime library to update to Shoko's bypassing Plex's cacheing or other issues.
- Any unused posters or empty collections will be removed from your library automatically while also updating negative season names.
- After making sweeping changes to the metadata in Shoko (like collections or title languages) this is a great way to ensure everything updates correctly in Plex.

#### [watched-sync.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/watched-sync.py)
- This script uses the Python-PlexAPI and Shoko Server to sync watched states from Plex to AniDB.
- If something is marked as watched in Plex it will also be marked as watched on AniDB.
- This was created due to various issues with Plex and Shoko's built in watched status syncing.
  1. The webhook for syncing requires Plex Pass and does not account for things manually marked as watched.
  2. Shoko's "Sync Plex Watch Status" command doesn't work with cross platform setups.

### Notes
#### Handling "Stuck" Metadata
- In cases where metadata (generally posters) won't update there is a quick 3 step process to fix it:
  1. Navigate to the series > More "..." Button > Unmatch
  2. Settings > Manage > Troubleshooting > Clean Bundles
  3. Navigate back to the series > More "..." Button > Match > Select top result
- If this somehow still fails then a full [Plex Dance](https://forums.plex.tv/t/the-plex-dance/197064) is likely required.

#### Automatic Season Naming Limitations
Due to custom agent limitations certain season names which contain special files will not name themselves correctly. These can be renamed manually or with the included [force-metadata.py](#force-metadatapy) script that accesses the Plex API. The affected season names and their intended names are listed below:
- Season -1 → Credits
- Season -2 → Trailers
- Season -3 → Parodies
- Season -4 → Other

#### Ambiguous Title Replacement
In cases where AniDB uses ambiguous episode titles the series title will be used instead (with the original title appended to it as necessary). A list of the titles considered ambiguous by the agent are as follows: 
- Complete Movie
- Music Video
- OAD
- OVA
- Short Movie
- TV Special
- Web

#### Combining Series
If you have TheTVDB matching enabled in Shoko and `SingleSeasonOrdering` disabled the agent will prioritise episode numbering from it by default. This allows shows which are separated on AniDB to be combined into a single entry inside Plex. To Achieve this simply multi-select (with the primary series as the first selection) the series in your Plex library which you know are part of a single TheTVDB entry then select `Merge`.

Using Fairy Tail as an example all of the following series can be safely merged into a single entry in Plex if they are correctly matched to TheTVDB in Shoko:
- Fairy Tail
- Fairy Tail (2011)
- Fairy Tail (2014)
- Fairy Tail (2018)

**Note:** Only do this when you are happy with the metadata for the series to be merged as you will be unable to correctly refresh it without splitting the series apart first.

#### Assumed Content Ratings
If "assumed content ratings" are enabled in the agent settings the [target audience](https://anidb.net/tag/2606/animetb) tags from AniDB will be used to roughly match [TV Parental Guidlines](http://www.tvguidelines.org/resources/TheRatings.pdf).
The tags which will trigger a rating change are listed in the table below:
| Tag                         | Rating  |
| --------------------------- | ------- |
| kodomo                      | TV-Y    |
| mina                        | TV-G    |
| shoujo, shounen             | TV-14   |
| josei, seinen, TV censoring | TV-MA   |
| borderline porn             | TV-MA-S |
| 18 restricted               | X       |

**Note:** Many series are missing these tags on AniDB so adding them is encouraged to help improve everyone's metadata.

#### Minimum Tag Weight
Many tags on AniDB use a [3 Star Weight System](https://wiki.anidb.net/Tags#Star-rating_-_the_Weight_system) which represents a value from 0 (no stars) to 600 (3 stars) and determines how relevant the tag is to the series it is applied to. By setting this value you can filter out tags below a certain star threshold if desired.
