# Shoko Relay: Scripts Configuration

## Plex Server Configuration
Plex = {
    # If you use 2FA for Plex use the "X-Plex-Token" authentication method at the bottom of this section instead
    'Username': 'Default',
    'Password': '',
    'ServerName': 'Media',
    # LibraryNames must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies'],"
    'LibraryNames': ['Anime'],
    # ExtraUsers must be a list to work e.g. "'ExtraUsers': ['Family'],"
    'ExtraUsers': None,
    # DataFolder requires double backslashes on windows e.g. "'DataFolder': '%LOCALAPPDATA%\\Plex Media Server',"
    'DataFolder': None,
    # PostersFolder requires double backslashes on windows e.g. "'PostersFolder': 'M:\\Anime\\Posters',"
    'PostersFolder': None,
    # Alternate Plex authentication method (primarily for those using two-factor authentication)
    # https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
    'X-Plex-Token': ''
}

## Shoko Server Configuration
Shoko = {
    'Hostname': '127.0.0.1',
    'Port': 8111,
    'Username': 'Default',
    'Password': ''
}

## AnimeThemes Configuration
AnimeThemes = {
    'FFplay_Enabled': True,
    'FFplay_Volume': '10',
    'BatchOverwrite': False
}

## Path Remapping for Rescan-Recent
PathRemapping = {
    # This section is for remapping paths from Shoko's to the system where the scripts are running
    # It uses regex substitution pairs to achieve this in the following format: "'^/ShokoPath/': '/LocalPath/'"
    # Regex substitution pairs require double backslashes on windows e.g. "'^/anime/': 'M:\\Anime\\'"
    # As many pairs as required can be manually added below
}