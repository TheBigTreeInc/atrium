"""Git-backed Atrium game registry: static compatibility != review or permission.

The game-side action performs local source validation. This independent receiver
re-fetches source at the immutable commit, checks successful Pages deployment,
then uses *Atrium-owned* trust entries to generate a public reviewed snapshot.
It NEVER reads endpoints, URLs, approvals or publisher rights from the sender.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
import yaml
from src.atriumd_contract import validate_document

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'[a-f0-9]{40}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
ID = re.compile(r'[a-z][a-z0-9.-]{2,119}\Z')
DEPLOY = re.compile(r'[a-z][a-z0-9-]{2,95}\Z')

class RegistrationError(ValueError): pass

def https_url(value, *, trailing_slash=False):
    if not isinstance(value,str) or not 0 < len(value) <= 1800 or any(x in value for x in ['\\','%2f','%5c']):
        raise RegistrationError('Invalid approved HTTPS URL')
    p = urlsplit(value)
    if p.scheme!='https' or not p.hostname or '.' not in p.hostname or p.username or p.password or p.port or p.query or p.fragment or p.hostname.endswith(('.local','.localhost','.internal')) or re.fullmatch(r'[\d.]+', p.hostname):
        raise RegistrationError('Invalid approved HTTPS URL')
    if trailing_slash and not value.endswith('/'):
        raise RegistrationError('Approved Pages base must end in /')
    return value

def locally_compatible(sidecar: dict, looprd: dict) -> dict:
    component = looprd.get('component') if isinstance(looprd,dict) else None
    if not isinstance(component,str): raise RegistrationError('Missing LoopRD component')
    validate_document(sidecar,component=component)
    game = sidecar['game']
    if game['launch']['mode']!='hosted-web' or game['launch']['originRef']!='game-web':
        raise RegistrationError('Hosted-web game-web launch required in this action version')
    if not game['launch']['entrypoint'].endswith('.html'):
        raise RegistrationError('Web entrypoint must be a .html file')
    if 'web' not in {p['runtime'] for p in game['platforms']}:
        raise RegistrationError('No supported web runtime')
    return {'gameId':game['id'],'component':component,'publisherId':game['publisher'],
            'title':game['title'],'entrypoint':game['launch']['entrypoint']}

def parse_yaml(data: bytes):
    if not data or len(data)>65_536: raise RegistrationError('Invalid metadata size')
    return yaml.safe_load(data.decode('utf-8'))

def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward Atrium's own token to a redirect target.


def read_public(url: str, max_bytes=131_072):
    headers={'User-Agent':'Atrium-GitHub-Registration/1.0','Accept':'application/vnd.github+json'}
    # Token belongs to Atrium's OWN workflow; game repositories never receive it.
    if url.startswith('https://api.github.com/repos/') and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
    with build_opener(_NoRedirect()).open(Request(url,headers=headers),timeout=15) as res:
        data = res.read(max_bytes+1)
        if len(data)>max_bytes: raise RegistrationError('Remote source exceeds limit')
        return data

def pages_release(repo: str, sha: str, *, get=read_public):
    # Most recent GitHub Pages deploy must be the same revision, not merely a successful test run.
    url = f'https://api.github.com/repos/{repo}/actions/runs?per_page=30'
    rows = json.loads(get(url))['workflow_runs']
    pages = [r for r in rows if 'pages' in r.get('name','').lower() and 'deploy' in r.get('name','').lower()]
    if not pages or pages[0].get('head_sha')!=sha or pages[0].get('conclusion')!='success' or pages[0].get('status')!='completed':
        raise RegistrationError('Latest GitHub Pages deployment is not successful at submitted source SHA')
    return int(pages[0]['id'])

def approved_source(config: dict, repo: str, metadata: dict):
    if config.get('schema')!='atrium.trusted-game-sources/v1' or not isinstance(config.get('games'),list):
        raise RegistrationError('Invalid Atrium operator trust policy')
    matched = [x for x in config['games'] if x.get('repository')==repo]
    if len(matched)!=1: raise RegistrationError('Repository not operator-approved in Atrium; request onboarding review')
    a=matched[0]
    for key,value in [('gameId',metadata['gameId']),('publisherId',metadata['publisherId']),('component',metadata['component'])]:
        if a.get(key)!=value: raise RegistrationError('Game does not match operator trust binding: '+key)
    if a.get('status')!='active' or a.get('autoPublish') is not True:
        raise RegistrationError('Repository not enabled for automatic publishing')
    if not isinstance(a.get('deploymentId'),str) or not DEPLOY.fullmatch(a['deploymentId']):
        raise RegistrationError('Invalid trusted deployment identity')
    https_url(a.get('launchBase'),trailing_slash=True)
    https_url(a.get('apiBaseUrl'))
    if not a['apiBaseUrl'].startswith(urlsplit(a['apiBaseUrl']).scheme+'://'+urlsplit(a['apiBaseUrl']).netloc+'/looprd/'+a['component']+'/v'):
        raise RegistrationError('Unexpected game API route')
    return a

def candidate_entry(repo: str, sha: str, config: dict, *, get=read_public):
    if not REPO.fullmatch(repo) or not SHA.fullmatch(sha):
        raise RegistrationError('Expected exact owner/repository and 40-hex SHA')
    # Trust is checked BEFORE attempting outbound reads, avoiding untrusted URLs.
    matches = [x for x in config.get('games',[]) if x.get('repository')==repo]
    if len(matches)!=1: raise RegistrationError('Unapproved repository; request Atrium source review')
    sidecar = parse_yaml(get(f'https://raw.githubusercontent.com/{repo}/{sha}/atriumd.yaml'))
    looprd = parse_yaml(get(f'https://raw.githubusercontent.com/{repo}/{sha}/looprd.yaml'))
    meta=locally_compatible(sidecar,looprd)
    a=approved_source(config,repo,meta)
    pages_run_id=pages_release(repo,sha,get=get)
    launch_url=a['launchBase']+meta['entrypoint']
    https_url(launch_url)
    # The remote game's website is checked by the game deploy workflow. The
    # operator owns its base URL; the GitHub deployment SHA is checked here.
    return {'gameId':meta['gameId'],'title':meta['title'],'publisherId':meta['publisherId'],
            'deploymentId':a['deploymentId'],'component':meta['component'],
            'launchUrl':launch_url,'apiBaseUrl':a['apiBaseUrl'],
            'sourceRevision':sha,'approved':True,'status':'published','embedAllowed':False},pages_run_id

def snapshot(root: Path):
    games=[]
    for file in sorted((root/'registry/games').glob('*.json')):
        game=read_json(file)
        if file.stem != game['gameId'] or game.get('approved') is not True or game.get('status')!='published':
            raise RegistrationError('Invalid reviewed game record: '+file.name)
        games.append(game)
    if len(games)>100 or len({x['gameId'] for x in games})!=len(games):
        raise RegistrationError('Duplicate or excessive published games')
    return {'schema':'atrium.hosted-games/v1','games':games}

def update(root: Path, repo: str, sha: str, *, get=read_public):
    config=read_json(root/'registry/trusted-sources.json')
    entry,run_id=candidate_entry(repo,sha,config,get=get)
    path=root/'registry/games'/f"{entry['gameId']}.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(entry,indent=2)+'\n',encoding='utf-8')
    (root/'web/hosted-games.json').write_text(json.dumps(snapshot(root),indent=2)+'\n',encoding='utf-8')
    return entry,run_id

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repository',required=True)
    ap.add_argument('--sha',required=True)
    ap.add_argument('--root',type=Path,default=ROOT)
    args=ap.parse_args()
    entry,run=update(args.root,args.repository,args.sha)
    print(f"Published reviewed source {entry['gameId']} {entry['sourceRevision']} (Pages run {run}) to source-tree JSON")

if __name__=='__main__': main()
