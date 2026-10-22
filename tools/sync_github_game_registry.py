"""Atrium-side pull reconciler. No cross-repository secrets or game-origin requests.

Every run fetches latest Pages evidence from Atrium-approved PUBLIC GitHub repos.
Only exact immutable released revisions may become reviewed catalog entries.
Unreachable/failed source fetches do not grant approval or overwrite prior releases.
Revoked trust removes its corresponding Git-published entry on the next run.
"""
import json
import re
from pathlib import Path
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.github_game_registry import (ROOT, ID, REPO, SHA, RegistrationError,
                                         candidate_entry, read_json, read_public, snapshot)


def latest_successful_pages_sha(repo, *, get=read_public):
    if not REPO.fullmatch(repo):
        raise RegistrationError('Unsafe repository ID')
    payload=json.loads(get(f'https://api.github.com/repos/{repo}/actions/runs?per_page=30'))
    runs=payload.get('workflow_runs', [])
    if not isinstance(runs, list):
        raise RegistrationError('Invalid GitHub workflow API data')
    pages=[r for r in runs if isinstance(r, dict) and 'pages' in r.get('name','').lower()
           and 'deploy' in r.get('name','').lower()]
    if not pages:
        raise RegistrationError('No Pages deploy workflow found')
    release=pages[0]
    sha=release.get('head_sha')
    if release.get('status')!='completed' or release.get('conclusion')!='success' or not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise RegistrationError('Latest Pages deploy is not successful with immutable SHA')
    if release.get('head_branch') not in (None,'main'):
        raise RegistrationError('Latest Pages deploy is not from main')
    return sha


def reconcile(root: Path, *, get=read_public):
    root=Path(root)
    config=read_json(root/'registry/trusted-sources.json')
    if config.get('schema')!='atrium.trusted-game-sources/v1' or not isinstance(config.get('games'),list):
        raise RegistrationError('Invalid operator-owned trusted-source policy')
    published={}
    for file in sorted((root/'registry/games').glob('*.json')):
        if not ID.fullmatch(file.stem):
            raise RegistrationError('Unsafe game record name')
        published[file.stem]=read_json(file)
    allowed_ids=set()
    results=[]
    for source in config['games']:
        if not isinstance(source,dict):
            raise RegistrationError('Malformed trusted source policy')
        repo,game_id=source.get('repository'),source.get('gameId')
        if not isinstance(repo,str) or not REPO.fullmatch(repo) or not isinstance(game_id,str) or not ID.fullmatch(game_id):
            raise RegistrationError('Malformed trusted game binding')
        if source.get('status')!='active' or source.get('autoPublish') is not True:
            results.append((repo,'disabled'))
            continue
        if game_id in allowed_ids:
            raise RegistrationError('Duplicate trusted game ID')
        allowed_ids.add(game_id)
        try:
            sha=latest_successful_pages_sha(repo,get=get)
            entry,pages_run_id=candidate_entry(repo,sha,config,get=get)
        except (OSError,KeyError,TypeError,ValueError,json.JSONDecodeError) as error:
            results.append((repo,'unavailable: '+str(error)))
            continue  # Retain last approved release; never publish unverified bytes.
        published[game_id]=entry
        results.append((repo,'verified Pages run '+str(pages_run_id)+' at '+sha))
    # The Git registry contains only game entries from this approved-source policy.
    # Removal or disablement revokes public publication on the next sync.
    for game_id in list(published):
        if game_id not in allowed_ids:
            del published[game_id]
    directory=root/'registry/games'
    directory.mkdir(parents=True,exist_ok=True)
    for file in directory.glob('*.json'):
        if file.stem not in published:
            file.unlink()
    for game_id,entry in sorted(published.items()):
        dest=directory/(game_id+'.json')
        desired=json.dumps(entry,indent=2)+'\n'
        if not dest.exists() or dest.read_text(encoding='utf-8')!=desired:
            dest.write_text(desired,encoding='utf-8')
    final=json.dumps(snapshot(root),indent=2)+'\n'
    out=root/'web/hosted-games.json'
    if not out.exists() or out.read_text(encoding='utf-8')!=final:
        out.write_text(final,encoding='utf-8')
    return results


def main():
    results=reconcile(ROOT)
    for repository,result in results:
        print(f'{repository}: {result}')
    print('Atrium pull sync completed; no external repository writes or credentials')

if __name__=='__main__':
    main()
