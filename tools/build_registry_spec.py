"""Generate reviewed inline DAPI registry handlers from canonical Python sources."""
from pathlib import Path
import argparse
import yaml

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'modules/registry/looprd.base.yaml'
OUTPUT=ROOT/'modules/registry/looprd.yaml'
ENDPOINTS=[
 ('/registry/publishers','POST','apps:approve','register_publisher'),
 ('/registry/publishers/status','POST','apps:approve','change_publisher_status'),
 ('/registry/publishers/proofs','POST','apps:approve','issue_publisher_proof'),
 ('/registry/publishers/proofs/verify','POST','apps:approve','verify_publisher_proof'),
 ('/registry/publishers/proofs','GET','apps:approve','list_publisher_proofs'),
 ('/registry/submissions','POST','apps:approve','submit'),
 ('/registry/reviews','POST','apps:approve','review'),
 ('/registry/disable','POST','apps:approve','disable'),
 ('/registry/catalog','GET','apps:read','catalog'),
 ('/registry/submissions','GET','apps:approve','submissions'),
 ('/registry/discovery/candidates','POST','apps:approve','record_discovery'),
 ('/registry/discovery/candidates','GET','apps:approve','list_discoveries'),
 ('/registry/discovery/manage','POST','apps:approve','manage_discovery'),
 ('/registry/discovery/observations','POST','apps:discover','receive_discovery_observation'),
 ('/registry/discovery/v2/capabilities','GET','apps:discover','trusted_discovery_capabilities'),
 ('/registry/discovery/v2/observations','POST','apps:discover','trusted_discovery_observation'),
 ('/registry/discovery/v2/manage','POST','apps:approve','manage_trusted_deployments'),
 ('/registry/discovery/v2/catalog','GET','apps:read','trusted_discovery_catalog'),
 ('/catalog/hosted-games','GET',None,'hosted_games_from_looprd'),
]

class Literal(str): pass

def render():
    spec=yaml.safe_load(BASE.read_text(encoding='utf-8'))
    library='\n'.join((ROOT/x).read_text(encoding='utf-8') for x in ('src/catalog.py','src/atriumd_contract.py','src/registry_runtime.py','src/discovery_runtime.py','src/discovery_delivery.py','src/publisher_proof.py'))
    v2_library='\n'.join((ROOT/x).read_text(encoding='utf-8') for x in ('src/atriumd_contract.py','src/discovery_v2.py'))
    hosted_library='\n'.join((ROOT/x).read_text(encoding='utf-8') for x in ('src/hosted_catalog_projection.py','src/hosted_catalog_looprd.py'))
    for path,method,scope,fn in ENDPOINTS:
        code = hosted_library if path == '/catalog/hosted-games' else (v2_library if '/discovery/v2/' in path else library)
        source=code+f'\n\nasync def handle(ctx):\n    return await {fn}(ctx)\n'
        entry = {'path':path,'method':method,'kind':'python','source':Literal(source)}
        if path == '/catalog/hosted-games':
            # Looprd 0.5.0 opt-in: exact anonymous GET, no scopes or service contract.
            entry['access'] = 'anonymous'
        else:
            entry['scopes'] = [scope]
        spec['handlers'].append(entry)
    dumper_class=type('LiteralDumper',(yaml.SafeDumper,),{})
    dumper_class.add_representer(Literal,lambda dumper,data:dumper.represent_scalar('tag:yaml.org,2002:str',str(data),style='|'))
    return yaml.dump(spec,Dumper=dumper_class,sort_keys=False,allow_unicode=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    expected=render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding='utf-8')!=expected:
            raise SystemExit('registry fragment stale; run python tools/build_registry_spec.py')
        print('Registry fragment matches canonical Python source')
    else:
        OUTPUT.write_text(expected,encoding='utf-8')
        print('generated modules/registry/looprd.yaml')

if __name__=='__main__': main()
