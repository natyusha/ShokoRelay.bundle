ShokoRelay.bundle
====================
This is a Plex library metadata agent/scanner written to work with anything listed on AniDB. All you need to get started is [Shoko](https://shokoanime.com/) and Plex Media Server. Unlike the original metadata bundle for Shoko this one does not include a movie scanner and is intended to work with series of all types within a single 'TV Shows' library.

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
	- The username to log into Shoko server
	- The password for above username
	- The host for Shoko
	- The port for Shoko
	- Collections: `Hide items which are in collections`
	- Seasons: `Hide for single-season series`
- In Plex Settings: `Settings > Agents > Shows > ShokoRelay` move the following entry to the top of the list and enable it:
	- [x] Local Media Assets (TV)

### Changes From the Official Shoko Scanner
- Uses Shoko's v3 API for fetching metadata
- Series and movies will list the studio
- Episodes and movies will list the writer and director
- Will apply ratings like 'TV-14' or 'TV-Y' to series, episode and movie entries (if the corresponding AniDB tags are present)
- Allows the user to configure the language for the series title (if they want a different language than in Shoko)
- Allows the user to configure an additional 'Alt Title' language for the series title (which will be searchable in Plex)
- Allows the user to configure what language they want for episode titles
- Will use TheTVDB descriptions and episode titles if AniDB is missing that information
- Will replace ambiguous AniDB episode titles with the series title
- Allows movies and series to be in the same library at once
- Allows multi season shows matched on TheTVDB to be merged into a single entry
- Support for files which contain more than one episode
- Includes a script for downloading the full OP/ED from AnimeThemes for local Plex metadata

### Notes
#### Handling 'Stuck' Metadata
- In cases where metadata (generally posters) won't update there is a 3 step process to fix it:
	1. Navigate to the series > More "..." Button > Unmatch
	2. Settings > Manage > Troubleshooting > Clean Bundles
	3. Navigate back to the series > More "..." Button > Match > Select top result

#### Automatic Season Naming Limitations
Due to custom agent limitations certain season names which contain special files will not name themselves correctly. These can be renamed manually or with a script that accesses the Plex API. The affected season names and their intended names are listed below:
- Season -1 → Themes
- Season -2 → Trailers
- Season -3 → Parodies
- Season -4 → Other

#### Ambiguous Title Replacement
In cases where AniDB uses ambiguous episode titles the series title will be used instead. A list of the titles considered ambiguous by the agent are as follows: 
- Complete Movie
- Music Video
- OAD
- OVA
- Short Movie
- TV Special
- Web

#### Combining Series
If you have TheTVDB matching enabled in Shoko the agent will prioritise episode numbering from it by default. This allows shows which are separated on AniDB to be combined into a single entry inside Plex. To Achieve this simply multi-select the series in your Plex library which you know are part of a single TheTVDB entry then select `Merge`.

Using Fairy Tail as an example all of the following series can be safely merged into a single entry in Plex if they are correctly matched to TheTVDB in Shoko:
- Fairy Tail
- Fairy Tail (2011)
- Fairy Tail (2014)
- Fairy Tail (2018)

#### Assumed Ratings
If assumed ratings are enabled in the agent settings the tags which will trigger a rating change are in the table below:
| Tag             | Rating |
| --------------- | ------ |
| kodomo          | TV-Y   |
| mina            | TV-G   |
| shoujo          | TV-14  |
| shounen         | TV-14  |
| josei           | TV-14  |
| seinen          | TV-MA  |
| borderline porn | TV-MA  |
| 18 restricted   | X 	   |
