![Shoko Relay Logo](https://github.com/natyusha/ShokoRelay.bundle/assets/985941/23bfd7c2-eb89-46d5-a7cb-558c374393d6 "Shoko Relay")
=======================
This is a bundle containing a Plex metadata agent, scanner, and automation scripts written to work with anything listed on AniDB. All you need to get started is a populated [Shoko Server](https://shokoanime.com/) v5.0.0 or newer and [Plex Media Server](https://www.plex.tv/media-server-downloads/) (Not running on an Nvidia Shield). Unlike the original metadata bundle for Shoko this one does not include a movie scanner and is intended to work with series of all types within a single "TV Shows" library.

## Installation
- Extract [the latest release](https://github.com/natyusha/ShokoRelay.bundle/releases/latest/download/ShokoRelay.bundle.zip) into your [Plex Media Server Plug-ins Folder](https://support.plex.tv/articles/201106098-how-do-i-find-the-plug-ins-folder/) `\Plex Media Server\Plug-ins`
- Ensure that the resulting folder name is `ShokoRelay.bundle` and navigate to it
- Move the `Scanners` folder located in `Contents` to `\Plex Media Server\`
- Navigate to `\Plex Media Server\Scanners\Series` and enter your Shoko credentials into `Shoko Relay Scanner.py` with a text editor:
  - Hostname
  - Port
  - Username
  - Password
- Restart your Plex Media Server if it was running during the previous steps
- Add a `TV Shows` library in Plex and configure the following options under `Advanced`:
  - Scanner: `Shoko Relay Scanner`
  - Agent: `ShokoRelay`
  - The Shoko Server Username
  - The Shoko Server Password
  - The Shoko Server Hostname
  - The Shoko Server Port
  - Collections: `Hide items which are in collections`
  - Seasons: `Hide for single-season series`
- In Plex: `Settings > Agents (Legacy) > Shows > ShokoRelay` move the following entry to the top of the list and enable it:
  - [x] Local Media Assets (TV)

### Recommended Shoko Server Configuration
Enable the following options in Shoko to ensure that Plex has at least one source of metadata for everything:
- `Settings > AniDB > Download Options`
  - [x] Character Images
  - [x] Creator Images
- `Settings > Metadata Sites > TMDB Options`
  - [x] Auto Link
  - [x] Auto Link Restricted
- `Settings > Metadata Sites > TMDB Download Options`
  - [x] Download Alternate Ordering
  - [x] Download Backdrops
  - [x] Download Posters
- `Settings > Collection > Relation Options`
  - [x] Auto Group Series
  - [x] Determine Main Series Using Relation Weighing

## Changes from Shoko Metadata
- Uses Shoko's v3 API for fetching metadata and matching files while replacing any TVDB usage with TMDB
- Allows:
  - Movies and series to be in the same library at once
  - Multi "season" shows matched on TMDB to be merged into a single entry
- Allows the user to configure:
  - The language for the series or episode titles (to use a different language than Shoko's)
  - An "Alt Title" language for the series title (which will be searchable in Plex)
- Optionally:
  - Series and movies will list the Main Staff along with Seiyuu (CV) under "Cast & Crew"
    - **Note:** They will all appear as actors due to Crew not being accessible for custom agents
  - Individual episodes will list the Writer as Original Work (原作) and Director as Direction (監督)
    - **Note:** Only supported if there is a single entry for each credit to avoid incorrect metadata
  - Will apply content ratings like "TV-14", "TV-Y" etc. (if the corresponding AniDB tags are present)
  - Will move common series title prefixes like "Gekijouban", "Eiga" etc. to the end of the title
- Removes the original tag hiding options and replaces them with a tag weight system similar to what [HAMA](https://github.com/ZeroQI/Hama.bundle) uses
  - **Note:** Automatically ignores all tags from Shoko's [TagBlacklistAniDBHelpers](https://github.com/ShokoAnime/ShokoServer/blob/9c0ae9208479420dea3b766156435d364794e809/Shoko.Server/Utilities/TagFilter.cs#L37) list
- Series and movies will list the Studio as Animation Work (アニメーション制作) or Work (制作)
- Support for:
  - Files which contain more than one episode or episodes which span multiple files
  - Credits / Parodies / Trailers and Other types of special files
  - Individual episode ratings (from AniDB)
  - Automatic season posters
- Will replace:
  - Ambiguous AniDB episode titles with the series title plus a suffix for the type of episode
  - Inconsistently capitalised genre tags with ones using [AniDB Capitalisation Rules](https://wiki.anidb.net/Capitalisation)
- Will use TMDB episode descriptions and titles if configured in Shoko or AniDB is missing that information

## Utility Scripts
Shoko Relay includes several utility / automation scripts which can help to quickly add full length theme songs, automatic collection posters, correct negative season numbers, synced watched states, and more.

The scripts require basic knowledge of running Python and other simple commands in a terminal. They are located in the `.\Contents\Scripts` folder inside `ShokoRelay.bundle` and can be moved to whatever location is convenient for the user (as long as the `config.py` file is kept in the same folder).

For ease of use, adding the Scripts folder to the **[PATH](https://en.wikipedia.org/wiki/PATH_(variable))** is also recommended.

### Prerequisites
Before using any of the scripts you must have the requisite dependencies installed. For more information on using Python scripts in general check out the Python 3 docs for [linux](https://docs.python.org/3/using/unix.html#on-linux) or [windows](https://docs.python.org/3/using/windows.html).
| Dependency                                      | AnimeThemes  | Collection-Posters | Force-Metadata | Rescan-Recent | Watched-Sync |
| :---------------------------------------------- | :----------: | :----------------: | :------------: | :-----------: | :----------: |
| [Python 3](https://www.python.org/downloads/)   | ✔️           | ✔️                 | ✔️             | ✔️            | ✔️           |
| [PlexAPI](https://pypi.org/project/PlexAPI/)    | ❌           | ✔️                 | ✔️             | ❌            | ✔️           |
| [Requests](https://pypi.org/project/requests/)  | ✔️           | ✔️                 | ❌             | ✔️            | ✔️           |
| [FFmpeg](https://ffmpeg.org/download.html)      | ✔️           | ❌                 | ❌             | ❌            | ❌           |

> [!IMPORTANT]
> When installing FFmpeg on Windows make sure to add it to the **PATH** by editing [Windows environment variables](https://phoenixnap.com/kb/ffmpeg-windows#ftoc-heading-4) or using the following command: `setx /m PATH "PATHTOFFMPEG"`.

> [!TIP]
> When running Plex from a Docker container consider installing the additional packages via the [Universal Package Install](https://github.com/linuxserver/docker-mods/tree/universal-package-install) Docker mod. If this isn't feasible the entire Scripts folder can simply be moved outside of the container with full functionality intact.
```yaml
environment:
  - DOCKER_MODS=linuxserver/mods:universal-package-install
  - INSTALL_PIP_PACKAGES=plexapi|requests
  - INSTALL_PACKAGES=ffmpeg
```

### Configuration
After installing the dependencies you must use a text editor to enter your Shoko and Plex credentials (as well as several other options) into the included `config.py` file. The configuration file contains 4 sections which are fairly self explanatory.

> [!TIP]
> Append `-h` or `--help` as an argument when running the scripts to access their help pages and avoid having to consult the readme for all of the commands.

### [animethemes.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/animethemes.py)
- This script uses the Shoko and [AnimeThemes](https://animethemes.moe/) APIs to find the OP/ED for a series and convert it into a Theme.mp3 file which will play when viewing the series in Plex.
- The default themes grabbed by Plex are limited to 30 seconds long and are completely missing for a massive amount of anime making this a great upgrade to local metadata.
<details>
<summary><b>Additional Information</b></summary><br>

**Requirements:**
- Python 3.7+, Requests Library (pip install requests), FFmpeg, Shoko Server

**Preferences:**
- Before doing anything with this script you must enter your Shoko credentials into `config.py`.
- To allow Theme.mp3 files to be used by Plex you must also enable "Local Media Assets" for the libraries that have your Anime in it.
  - The "Play Theme Music" option also has to be enabled in the settings for the Plex client.

**Usage:**
- Run in a terminal `animethemes.py` with the working directory set to a folder containing an anime series.
- If the anime has been matched by Shoko Server it will grab the anidbID and use that to match with an AnimeThemes anime entry.

**Behaviour:**
- By default this script will download the first OP (or ED if there is none) for the given series.
- If "FFplay_Enabled" is set to True in `config.py` the song will begin playing in the background which helps with picking the correct theme.
- FFmpeg will then encode it as a 320kbps mp3 and save it as Theme.mp3 in the anime folder.
- FFmpeg will also apply the following metadata:
  - Title (with TV Size or not)
  - Artist (if available)
  - Album (as source anime)
  - Subtitle (as OP/ED number + the version if there are multiple)
- If you want a different OP/ED than the default simply supply the AnimeThemes slug as an argument.
- For the rare cases where there are multiple anime mapped to the same anidbID on AnimeThemes you can add an offset as an argument to select the next matched entry.
- When running this on multiple folders at once adding the "batch" argument is recommended. This disables audio playback and skips folders already containing a Theme.mp3 file.
    - If "BatchOverwrite" is set to true in `config.py` the batch argument will instead overwrite any existing Theme.mp3 files.

**Arguments:**
- Append the arguments "slug" / "offset" `animethemes.py slug offset` in order to specify which opening or ending to download.
  - slug: an optional identifier which must be the first argument and is formatted as "op", "ed", "op2", "ed2" and so on
  - offset: an optional single digit number which must be the second argument if the slug is provided
- Append the argument "play" to the commands above to run in "Preview" mode.
  - play: for force enabling FFplay and disabling Theme.mp3 generation, must be the last or sole argument and is simply entered as "play"
- Append the argument "batch" `animethemes.py batch` when running the script on multiple folders at a time.
  - batch: must be the sole argument and is simply entered as "batch"

**Example Commands:**
> :pencil2: **Note**  
> Using bash / cmd respectively and assuming that both the script and FFmpeg can be called directly from the PATH.
- Library Batch Processing
  - `for d in "/PathToAnime/"*/; do cd "$d" && animethemes.py batch; done`
  - `for /d %d in ("X:\PathToAnime\*") do cd /d %d && animethemes.py batch`
- Fix "Mushoku Tensei II: Isekai Ittara Honki Dasu" Matching to Episode 0 (offset to the next animethemes match)
  - `cd "/PathToMushokuTenseiII"; animethemes.py 1`
  - `cd /d "X:\PathToMushokuTenseiII" && animethemes.py 1`
- Same as above but download the second ending instead of the default OP
  - `cd "/PathToMushokuTenseiII"; animethemes.py ed2 1`
  - `cd /d "X:\PathToMushokuTenseiII" && animethemes.py ed2 1`
- Download the 9th Opening of Bleach
  - `cd "/PathToBleach"; animethemes.py op9`
  - `cd /d "X:\PathToBleach" && animethemes.py op9`
- Preview the 9th Opening of Bleach
  - `cd "/PathToBleach"; animethemes.py op9 play`
  - `cd /d "X:\PathToBleach" && animethemes.py op9 play`
</details>

### [collection-posters.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/collection-posters.py)
- This script uses the Python-PlexAPI and Shoko Server to apply posters to the collections in Plex.
- It will look for posters in a user defined folder and if none are found take the default poster from the corresponding Shoko group.

<details>
<summary><b>Additional Information</b></summary><br>

**Requirements:**
  - Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, Shoko Relay, Shoko Server

**Preferences:**
- Before doing anything with this script you must enter your Plex and Shoko Server credentials into `config.py`.
- If your anime is split across multiple libraries they can all be added in a python list under "LibraryNames".
  - It must be a list to work e.g. `'LibraryNames': ['Anime Shows', 'Anime Movies']`
- The Plex "PostersFolder" and "DataFolder" settings require double backslashes on windows e.g. `'PostersFolder': 'M:\\Anime\\Posters',`.
  - The "DataFolder" setting is the base [Plex Media Server Data Directory](https://support.plex.tv/articles/202915258-where-is-the-plex-media-server-data-directory-located/) (where the Metadata folder is located).
  - The "PostersFolder" setting is the folder containing any custom collection posters.

**Usage:**
- Run in a terminal `collection-posters.py` to set Plex collection posters to user provided ones or Shoko's.
  - Any Posters in the "PostersFolder" must have the same name as their respective collection in Plex.
  - The following characters must be stripped from the filenames: \ / : * ? " < > |
  - The accepted file extensions are: bmp / gif / jpe / jpeg / jpg / png / tbn / tif / tiff / webp
- Append the argument "clean" `collection-posters.py clean` if you want to remove old collection posters instead.
  - This works by deleting everything but the newest custom poster for all collections.
</details>

### [force-metadata.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/force-metadata.py)
- This script uses the Python-PlexAPI to force all metadata in your anime library to update to Shoko's bypassing Plex's caching or other issues.
- Any unused posters or empty collections will be removed from your library automatically while also updating negative season names, collection sort titles and original titles.
- After making sweeping changes to the metadata in Shoko (like collections or title languages) this is a great way to ensure everything updates correctly in Plex.

<details>
<summary><b>Additional Information</b></summary><br>

**Requirements:**
- Python 3.7+, Python-PlexAPI (pip install plexapi), Plex, Shoko Relay, Shoko Server

**Preferences:**
- Before doing anything with this script you must enter your Plex credentials into `config.py`.
- If your anime is split across multiple libraries they can all be added in a python list under Plex "LibraryNames".
  - It must be a list to work e.g. `'LibraryNames': ['Anime Shows', 'Anime Movies']`

**Usage:**
- Run in a terminal `force-metadata.py` to remove empty collections, normalise collection sort titles, rename negative seasons and add original titles in Plex.
- Append the argument "full" `force-metadata.py full` if you want to do a time consuming full metadata clean up.

> :warning: **Important**  
> In "full" mode you must wait until the Plex activity queue is fully completed before advancing to the next step (with the enter key) or this will not function correctly.
> - You can tell if Plex is done by looking at the library in the desktop/web client or checking the logs in your "PMS Plugin Logs" folder for activity.
> - This may take a significant amount of time to complete with a large library so it is recommended to run the first step overnight.

**Behaviour:**
- This script will ignore locked fields/posters assuming that the user wants to keep them intact.
- Manually merged series will not be split apart and may need to be handled manually to correctly refresh their metadata.
- If the main title of an anime was changed on AniDB or overridden in Shoko after it was first scanned into Plex it might fail to match using this method.
  - In these cases the original title will be output to the console for the user to fix with a Plex dance or manual match.
- Video preview thumbnails and watched states are maintained with this script (unless an anime encounters the above naming issue).
- The "Original Title" for all series will be set using info Shoko Relay added to the "Sort Title" (if available).
- Negative seasons like "Season -1" which contain Credits, Trailers, Parodies etc. will have their names updated to reflect their contents.
- The "Sort Title" for all collections will be set to match the current title to avoid Plex's custom sorting rules e.g. ignoring "The" or "A"
- All Smart Collections are ignored as they are not managed by Shoko Relay
</details>

### [rescan-recent.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/rescan-recent.py)
- This is mostly used for quickly adding currently airing series to Plex that were unrecognized when initially imported into Shoko.
- Once the files are recognized running this script will trigger a rescan in Plex for any series that they are attached to.
- This requires Plex's partial scanning (or an alternative) to be enabled.

<details>
<summary><b>Additional Information</b></summary><br>

**Requirements:**
- Python 3.7+, Requests Library (pip install requests), Plex, Shoko Server

**Preferences:**
- Before doing anything with this script you must enter your Shoko Server credentials into `config.py`.
- The Path Remapping section can be configured when running the scripts from a location where the paths differ from Shoko's.

**Usage:**
- Run in a terminal `rescan-recent.py` to trigger a Plex rescan of the 5 most recently added series in Shoko.
- Change the number of recently added series (from 1-99) to rescan with an argument when 5 isn't enough:
  - `rescan-recent.py 20` would rescan the 20 most recently added series
- Append the argument "import" `rescan-recent.py import` if you want to force shoko to import unrecognized files instead.
</details>

### [watched-sync.py](https://github.com/natyusha/ShokoRelay.bundle/blob/master/Contents/Scripts/watched-sync.py)
- This script uses the Python-PlexAPI and Shoko Server to sync watched states from Plex to Shoko or Shoko to Plex.
- If something is marked as watched in Plex it will also be marked as watched in Shoko and AniDB.
- This was created due to various issues with Plex and Shoko's built in watched status syncing.
  - Primarily, the webhook for syncing requires Plex Pass and does not account for things manually marked as watched.
<details>
<summary><b>Additional Information</b></summary><br>

**Requirements:**
- Python 3.7+, Python-PlexAPI (pip install plexapi), Requests Library (pip install requests), Plex, Shoko Relay, Shoko Server

**Preferences:**
- Before doing anything with this script you must enter your Plex and Shoko Server credentials into `config.py`.
- If your anime is split across multiple libraries they can all be added in a python list under Plex "LibraryNames".
  - It must be a list to work e.g. `'LibraryNames': ['Anime Shows', 'Anime Movies']`
- If you want to track watched states from managed/home accounts on your Plex server you can add them to Plex "ExtraUsers" following the same list format as above.
  - Leave it as "None" otherwise.
- If you don't want to track watched states from your Plex Server's Admin account set "SyncAdmin" to "False".
  - Leave it as "True" otherwise.

**Usage:**
- Run in a terminal `watched-sync.py` to sync watched states from Plex to Shoko.
- Append a relative date suffix as an argument to narrow down the time frame and speed up the process:
  - `watched-sync.py 2w` would return results from the last 2 weeks
  - `watched-sync.py 3d` would return results from the last 3 days
- The full list of suffixes (from 1-999) are: m=minutes, h=hours, d=days, w=weeks, mon=months, y=years
- Append the argument "import" `watched-sync.py import` if you want to sync watched states from Shoko to Plex instead.
  - By default the script will ask for (Y/N) confirmation for each configured Plex user.
  - This can be bypassed by adding the "force" flag (-f or --force).

**Behaviour:**
- Due to the potential for losing a huge amount of data removing watch states has been omitted from this script.
</details>

## Additional Information
### Troubleshooting
When encountering any issues with the scanner or agent, please note that there are detailed logs available in the [Plex Media Server Logs Folder](https://support.plex.tv/articles/200250417-plex-media-server-log-files/) which can help to pinpoint any issues:
- Agent Logs: `\Plex Media Server\Logs\PMS Plugin Logs\com.plexapp.agents.shokorelay.log`
- Scanner Logs: `\Plex Media Server\Logs\Shoko Relay Scanner.log`

> [!IMPORTANT]
> When encountering bad matches/metadata the first thing to check for is if TMDB matches/episode mappings are correct in Shoko for the series in question. Barring that, check AniDB's episode relations for the affected files.

> [!WARNING]
> Under extremely specific circumstances Plex will automatically group files together without user intervention. This occurs when storing files from multiple AniDB entries in a single folder (that has no other subfolders present inside of it) located in the root directory of a Plex library.
> 
> To resolve this there are several different approaches:
> 1. Nest the entire library within a new folder so folders affected by this are no longer in the root directory
> 2. Separate the files from each AniDB series into their own separate folders or subfolders
> 4. Create an empty subfolder in any directory affected by this

### Handling "Stuck" Metadata
In cases where metadata (generally posters) won't update there is a quick 3 step process to fix it:
1. Navigate to the series → More "..." Button → Unmatch
2. Settings → Manage → Troubleshooting → Clean Bundles + Optimize Database
3. Navigate back to the series → More "..." Button → Match → Select top result

If this somehow still fails then a full [Plex Dance](https://forums.plex.tv/t/the-plex-dance/197064) is likely required.

### Cast & Crew Limitations
If "staff listings" are enabled in the settings the following custom agent limitations apply:
- All Cast & Crew members are listed under the cast section only
- Directors, Producers and Writers will be empty when attempting to filter for them in Plex
- All Crew members are available for filtering under Actor only
- The links in the Cast & Crew section under individual episodes won't return any results

### Automatic Season Naming Limitations
Due to custom agent limitations certain season names which contain special files will not name themselves correctly. These can be renamed manually or with the included [force-metadata.py](#force-metadatapy) script that accesses the Plex API. The affected season names and their intended names are listed below:
- Season -1 → Credits **OR** [Unknown Season] → Credits
- Season -2 → Trailers
- Season -3 → Parodies
- Season -4 → Other

### Automatic Title Modification
**Common Prefixes for Series**  
When a series starts with a common title prefix it will optionally be moved to the end of the title (for improved alphabetical sorting). A list of the prefixes considered common by the agent are as follows:
- Gekijouban
- Eiga
- OVA

**Ambiguous Titles for Episodes**  
In cases where AniDB uses ambiguous episode titles the series title will be used instead (with the original title appended to it as necessary). A list of the titles considered ambiguous by the agent are as follows:
- Complete Movie
- Music Video
- OAD
- OVA
- Short Movie
- Special
- TV Special
- Web

> [!NOTE]
> The appended titles will appear after an em dash (**—**) making it easy to search for anything affected by this.

### TMDB Matching
If you have TMDB auto links enabled in Shoko you will have access to several features not available otherwise:
- Plex's default theme song support (using the TvDB ID)
- Season support for long running anime (including posters)
- Fallback for series/episode descriptions and titles (if AniDB is missing that information)

With `SingleSeasonOrdering` disabled in the Scanner and Agent the following will also be supported:
- Combining multiple Shoko series into a single Plex entry
- Alternate episode ordering for seasons

**Combining Series**  
This allows shows which are separated on AniDB to be combined into a single entry inside Plex. To Achieve this simply multi-select (with the primary series as the first selection) the series in your Plex library which you know are part of a single TMDB entry then select `Merge`.

Using Fairy Tail as an example all of the following series can be safely merged into a single entry in Plex if they are correctly matched to TMDB in Shoko:
- Fairy Tail
- Fairy Tail (2011)
- Fairy Tail (2014)
- Fairy Tail (2018)

> [!IMPORTANT]
> Only do this when you are happy with the metadata for the series to be merged as you will be unable to correctly refresh it without splitting the series apart first.

**Alternate Episode Ordering**  
It is quite common for anime to have multiple ways of grouping the episodes into seasons. This includes: DVD/BD ordering, stream site listings or even manga story arcs. If you used Shoko while it still had TvDB support you may find that series in your Plex library are grouping differently than they used to be. Using Bleach as an example you can see that [TMDB](https://www.themoviedb.org/tv/30984-bleach/seasons) doesn't split the original run into seasons while [TvDB](https://thetvdb.com/series/bleach#seasons) does. Fortunately, TMDB's [Episode Groups](https://www.themoviedb.org/tv/30984-bleach/episode_groups) page provides alternate ordering options (often including TvDB's) in case you would like to use one of them instead.

If you have "Download Alternate Ordering" enabled under Shoko's "TMDB Download Options" this can be achieved using Shoko's `/Tmdb/Show/{showID}/Ordering/SetPreferred` v3 API endpoint which is available via [/swagger/](https://docs.shokoanime.com/faq#general) (Shoko's public API).

Once you have authenticated with swagger, you can navigate to the previously mentioned endpoint. Using Bleach as an example once again, you would enter `30984` (Bleach's TMDB ID) into the `showID` box. Then you would the set the 16 character `AlternateOrderingID` in the request body to one of the ones available [here](https://www.themoviedb.org/tv/30984-bleach/episode_groups) (both IDs are available from the URL on TMDB). Lastly, click "Execute" and the order will be applied.

```json
{
  "AlternateOrderingID": "663fb548c10d4be3e80b2f6d"
}
```

> [!NOTE]
> If you select an alternate order for a series TMDB season posters will no longer be automatically added to Plex as those are only for the default seasons.

### Combining Episodes
Sometimes you may encounter a single episode which is split across multiple files. In order to ensure that all of the files are treated as a single entity you can follow Plex's [Naming Conventions](https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/#toc-6). For an ideal playback experience however, it is recommended to merge these types of files together.

### Minimum Tag Weights
Many tags on AniDB use a [3 Star Weight System](https://wiki.anidb.net/Tags#Star-rating_-_the_Weight_system) which represents a value from 0 (no stars) to 600 (3 stars) and determines how relevant the tag is to the series it is applied to. By setting this value in the Agent settings you can filter out tags below a certain star threshold.

### Assumed Content Ratings
If "assumed content ratings" are enabled in the agent settings the [target audience](https://anidb.net/tag/2606/animetb) and [content indicator](https://anidb.net/tag/2604/animetb) tags from AniDB will be used to roughly match the [TV Parental Guidelines](http://www.tvguidelines.org/resources/TheRatings.pdf) system. The target audience tags will conservatively set the initial rating anywhere from TV-Y to TV-14, then the content indicators will be appended. If the tag weights for the content indicators are high enough (> 400 or **\*\***) the rating will be raised to compensate. A general overview is listed in the table below:
| Tag                               | Rating  |
| :-------------------------------- | :------ |
| Kodomo                            | TV-Y    |
| Mina                              | TV-G    |
| Shoujo, Shounen                   | TV-PG   |
| Josei, Seinen                     | TV-14   |
| Sexual Humour                     | TV-\*-D |
| Nudity, Sex                       | TV-\*-S |
| **\*\*** Violence                 | TV-14-V |
| **\*\*** Nudity, **\*\+** Sex     | TV-14-S |
| Borderline Porn (override)        | TV-MA   |
| **\*\*\+** Nudity, **\*\*** Sex   | TV-MA-S |
| **\*\*\+** Violence               | TV-MA-V |
| 18 Restricted (override)          | X       |

> [!NOTE]
> Many series are missing these tags on AniDB so adding them is encouraged to help improve everyone's metadata.
