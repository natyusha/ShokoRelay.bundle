ShokoMetadata.bundle
====================
This is a Plex library metadata agent/scanner written to work with anything listed on AniDB. All you need to get started is [Shoko](https://shokoanime.com/) and Plex Media Server. Unlike the official metadata bundle for Shoko this one does not include a movie scanner and is intended to work with series of all types within a single 'TV Shows' library.

### Installation
- Unzip [this repository](https://github.com/natyusha/ShokoMetadata.bundle/archive/refs/heads/master.zip) into `\Plex Media Server\Plug-ins`
- Move the `Scanners` folder located in `Contents` to `\Plex Media Server\`
- Navigate to `\Plex Media Server\Scanners\Series` and enter your Shoko credentials into `Shoko Series Scanner.py` with a text editor:
	- Hostname
	- Port
	- Username
	- Password
- Add a `TV Shows` library in Plex and configure the following options under `Advanced`:
	- Scanner: `Shoko Series Scanner`
	- Agent: `ShokoTV`
	- The username to log into shoko server
	- The password for above username
	- The host for Shoko
	- The port for Shoko
	- Collections: `Hide items which are in collections`
	- Seasons: `Hide for single-season series`
- In Plex Settings: `Settings > Agents > Shows > ShokoTV` move the following entry to the top of the list and enable it:
	- [x] Local Media Assets (TV)

### Changes From the Official Shoko Scanner
- Uses Shoko's v3 API for fetching metadata
- Series and movies will list the studio
- Episodes and movies will list the writer and director
- Will apply ratings like 'TV-14' or 'TV-Y' to series and movie entries (if the corresponding anidb tags are present)
- Allows the user to configure what language they want for episode titles
- Will use TheTVDB descriptions and episode titles if AniDB is missing that information
- Allows movies and series to be in the same library at once
- Allows multi season shows matched on TheTVDB to be merged into a single entry
- Support for files which contain more than one episode

### Notes
#### Automatic Season Naming Limitations
Due to custom agent limitations certain season names which contain special files will not name themselves correctly. These can be renamed manually or with a script that accesses the Plex API. The affected season names and their intended names are listed below:
- Season -1 → Themes
- Season -2 → Trailers
- Season -3 → Parodies
- Season -4 → Other

#### Combining Series
If you have TheTVDB matching enabled in Shoko the agent will prioritise episode numbering from it by default. This allows shows which are separated on AniDB to be combined into a single entry inside Plex. To Achieve this simply multi-select the series in your Plex library which you know are part of a single TheTVDB entry then select `Merge`.

Using Fairy Tail as an example all of the following series can be safely merged into a single entry in Plex if they are correctly matched to TheTVDB in Shoko:
- Fairy Tail
- Fairy Tail (2011)
- Fairy Tail (2014)
- Fairy Tail (2018)

#### Assumed Ratings
If assumed ratings are enabled in the agent settings the tags which will trigger a rating change are listed below:
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
