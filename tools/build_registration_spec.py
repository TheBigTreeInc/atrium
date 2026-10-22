"""Generate a separate PUBLIC LoopRD component, never widen Atrium admin auth."""
import argparse
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'modules/registration/looprd.yaml'
BASE=ROOT/'modules/registration/looprd.base.yaml'

class Literal(str): pass

def render():
    spec=yaml.safe_load(BASE.read_text(encoding='utf-8'))
    policy=json.loads((ROOT/'registry/trusted-sources.json').read_text(encoding='utf-8'))
    if policy.get('schema')!='atrium.trusted-game-sources/v1' or not isinstance(policy.get('games'),list):
        raise ValueError('Invalid trusted-source policy')
    # This is a deployment-time registration *allowlist*, NOT publication.
    approved=[]
    for game in policy['games']:
        if not isinstance(game,dict): raise ValueError('Invalid game policy entry')
        if game.get('status')=='active' and game.get('autoPublish') is True:
            repo=game.get('repository')
            from tools.github_game_registry import REPO
            if not isinstance(repo,str) or not REPO.fullmatch(repo): raise ValueError('Invalid approved repository')
            approved.append(repo)
    if len(approved)!=len(set(approved)) or len(approved)>100:
        raise ValueError('Duplicate or excessive approved registration repositories')
    library=(ROOT/'src/public_registration_ingress.py').read_text(encoding='utf-8')
    for method,fn in [('POST','register_notice'),('GET','list_notices')]:
        source=library+'\nTRUSTED_REPOSITORIES = frozenset('+repr(tuple(sorted(approved)))+')\n'+f'\nasync def handle(ctx):\n    return await {fn}(ctx)\n'
        spec['handlers'].append({'path':'/registrations','method':method,'kind':'python','scopes':[], 'source':Literal(source)})
    dump=type('LiteralDumper',(yaml.SafeDumper,),{})
    dump.add_representer(Literal,lambda d,s:d.represent_scalar('tag:yaml.org,2002:str',str(s),style='|'))
    return yaml.dump(spec,Dumper=dump,sort_keys=False,allow_unicode=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    expected=render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8')!=expected:
            raise SystemExit('Public registration spec stale: run python tools/build_registration_spec.py')
        print('Public LoopRD registration spec matches approved policy and source')
    else:
        TARGET.parent.mkdir(parents=True,exist_ok=True)
        TARGET.write_text(expected,encoding='utf-8')
        print('Generated bounded public registration component')
if __name__=='__main__':main()
