#!/usr/bin/env python

## Plex Server Configuration
Plex = {
    'Username': 'Default',
    'Password': '',
    'ServerName': 'Media',
    # LibraryNames must be a list to work e.g. "'LibraryNames': ['Anime Shows', 'Anime Movies'],"
    'LibraryNames': ['Anime'],
    # ExtraUsers must be a list to work e.g. "'ExtraUsers': ['Family'],"
    'ExtraUsers': None,
    # DataFolder requires double backslashes on windows e.g. "'DataFolder': '%LOCALAPPDATA%\\Plex Media Server',".
    'DataFolder': None,
    # PostersFolder requires double backslashes on windows e.g. "'PostersFolder': 'M:\\Anime\\Posters'".
    'PostersFolder': None
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
