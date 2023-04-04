ShokoMetadata.bundle
====================
This is a Plex library metadata agent/scanner written to work with anything listed on AniDB. All you need to get started is [Shoko](https://shokoanime.com/) and Plex Media Server.

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
	- Seasons: `Hide for single-season seasons`
- In Plex Settings: `Settings > Agents > Shows > ShokoTV` move the following entry to the top of the list and enable it:
	- [x] Local Media Assets (TV)

### Notes
#### Automatic Season Naming Limitations
Due to custom agent limitations certain season names which contain special files will not name themselves correctly. These can be renamed manually or with a script that accesses the Plex API. The affected season names and their intended names are listed below:
- Season -1 = Themes
- Season -2 = Trailers
- Season -3 = Parodies
- Season -4 = Other

#### Combining Series
If you have TheTVDB matching enabled in Shoko the agent will prioritise episode numbering from it by default. This allows shows which are separated on AniDB to be combined into a single entry inside Plex. To Achieve this simply multi-select the series in your Plex library which you know are part of a single TheTVDB entry then select `Merge`.

Using Fairy Tail as an example all of the following series can be safely merged into a single entry in Plex if they are correctly matched to TheTVDB in Shoko:
- Fairy Tail
- Fairy Tail (2011)
- Fairy Tail (2014)
- Fairy Tail (2018)