try:    from plexapi.myplex import MyPlexAccount
except: pass

try:    import requests
except: pass

import sys
import config as cfg

sys.stdout.reconfigure(encoding='utf-8') # allow unicode characters in print
err = '\033[31m⨯\033[0m' # use the red terminal colour for ⨯

# unbuffered print command to allow the user to see progress immediately
def print_f(text): print(text, flush=True)

# grab a Shoko API key using the credentials from the prefs
def shoko_auth():
    try:
        auth = requests.post(f'http://{cfg.Shoko["Hostname"]}:{cfg.Shoko["Port"]}/api/auth', json={'user': cfg.Shoko['Username'], 'pass': cfg.Shoko['Password'], 'device': 'Shoko Relay Scripts for Plex'}).json()
    except Exception as error:
        print(f'{err}Failed:', error)
        exit(1)
    if 'status' in auth and auth['status'] in (400, 401):
        print(f'{err}Failed: Shoko Credentials Invalid')
        exit(1)
    return auth['apikey']

# authenticate and optionally connect to the Plex server/library specified using the credentials from the prefs
def plex_auth(connect=True):
    try:
        if cfg.Plex['X-Plex-Token']:
            admin = MyPlexAccount(token=cfg.Plex['X-Plex-Token'])
        else:
            admin = MyPlexAccount(cfg.Plex['Username'], cfg.Plex['Password'])
    except Exception as error:
        print(f'{err}Failed:', error)
        exit(1)
    if not connect: return admin # skip the connection when using partial auth (for scripts with more advanced user management)

    try:
        plex = admin.resource(cfg.Plex['ServerName']).connect()
    except Exception as error:
        print(f'{err}Failed:', error)
        exit(1)
    return plex