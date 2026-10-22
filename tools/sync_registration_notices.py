"""Atrium-owned audit of public LoopRD game notices; never trust a notice to publish.

The existing reconcile() independently fetches Pages evidence and signed-off
source policy, then writes registry/games and web/hosted-games.json. This pass
adds a bounded receipt history for reviewers, with verified source workflow IDs.
"""
import json
import os
from pathlib import Path
if __name__ == '__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from urllib.parse import urlsplit
from tools.github_game_registry import ROOT, SHA, REPO, read_json, read_public, candidate_entry
from tools.sync_github_game_registry import reconcile


def queue_url(value):
    if not isinstance(value,str) or not 0<len(value)<=1024: raise ValueError('Bad registration endpoint')
    url=urlsplit(value)
    if (url.scheme!='https' or not url.hostname or '.' not in url.hostname or url.username or url.password
        or url.port or url.hostname.endswith(('.local','.localhost','.internal')) or url.hostname.replace('.','').isdigit() or url.query or url.fragment or url.path!='/looprd/atrium-registration/v1/registrations'):
        raise ValueError('Public registration endpoint must be operator-configured LoopRD HTTPS route')
    return value


def get_notices(endpoint, get=read_public):
    body=json.loads(get(queue_url(endpoint)))
    if not isinstance(body,dict) or set(body)!={'schema','notices'} or body['schema']!='atrium.registration-queue/v1' or not isinstance(body['notices'],list) or len(body['notices'])>100:
        raise ValueError('Invalid LoopRD registration inbox')
    records=[]
    for item in body['notices']:
        if not isinstance(item,dict) or set(item)!={'repository','sha','runId','seenAt'}: raise ValueError('Malformed registration notice')
        repo,sha,run=item['repository'],item['sha'],item['runId']
        if not isinstance(repo,str) or not REPO.fullmatch(repo) or not isinstance(sha,str) or not SHA.fullmatch(sha) or type(run) is not int or not 0<run<2**63 or not isinstance(item['seenAt'],str) or len(item['seenAt'])>50:
            raise ValueError('Invalid registration notice')
        records.append(item)
    return records


def synchronize(root=ROOT, *, endpoint='', get=read_public):
    root=Path(root)
    # Never lose scheduled pull fallback: if ingress is unconfigured or down,
    # independently discover approved successful Pages deployments as before.
    results=reconcile(root,get=get)
    if not endpoint:
        return results,[]
    notices=get_notices(endpoint,get=get)
    policy=read_json(root/'registry/trusted-sources.json')
    approved={x.get('repository'):x for x in policy['games'] if x.get('status')=='active' and x.get('autoPublish') is True}
    receipts=[]
    for item in notices:
        repo,sha,run=item['repository'],item['sha'],item['runId']
        if repo not in approved:
            # A stale ingress allowlist never overrides current Atrium policy.
            continue
        status='rejected'
        try:
            entry,actual_run=candidate_entry(repo,sha,policy,get=get)
            game_path=root/'registry/games'/f"{entry['gameId']}.json"
            published=read_json(game_path) if game_path.exists() else None
            if actual_run==run and published==entry:
                status='published'
            elif actual_run==run:
                status='pending_sync'
        except (OSError,KeyError,TypeError,ValueError,json.JSONDecodeError):
            status='pending_verification'
        receipts.append({'repository':repo,'sha':sha,'runId':run,'status':status,'seenAt':item['seenAt']})
    receipts.sort(key=lambda r:r['repository'])
    history={'schema':'atrium.registration-history/v1','registrations':receipts}
    path=root/'registry/registration-history.json'
    desired=json.dumps(history,indent=2)+'\n'
    if not path.exists() or path.read_text(encoding='utf-8')!=desired:
        path.write_text(desired,encoding='utf-8')
    return results,receipts


def main():
    endpoint=os.environ.get('ATRIUM_PUBLIC_REGISTRATION_ENDPOINT','')
    try:
        results,receipts=synchronize(endpoint=endpoint)
    except (OSError,ValueError,json.JSONDecodeError) as err:
        # Network ingress outage must not fail the previously-working fallback;
        # report failure so operators can inspect service availability.
        if not endpoint: raise
        print('Public registration inbox unavailable; pull-sync fallback only:',type(err).__name__)
        results=reconcile(ROOT)
        receipts=[]
    for repository,result in results:
        print(f'{repository}: {result}')
    for item in receipts:
        print(f"Public notice {item['repository']} run {item['runId']}: {item['status']}")

if __name__=='__main__':main()
