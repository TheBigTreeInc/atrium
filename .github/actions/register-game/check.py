"""Game-side preflight only. The Atrium receiver validates everything again."""
from pathlib import Path
import argparse, json, os, sys
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
from tools.github_game_registry import locally_compatible, parse_yaml

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--source-sha',required=True)
    args=parser.parse_args()
    from tools.github_game_registry import SHA
    if not SHA.fullmatch(args.source_sha): raise ValueError('Immutable 40-character commit SHA required')
    sidecar=parse_yaml((args.root/'atriumd.yaml').read_bytes())
    looprd=parse_yaml((args.root/'looprd.yaml').read_bytes())
    data=locally_compatible(sidecar,looprd)
    outputs={'game_id':data['gameId'],'component':data['component'],'source_sha':args.source_sha}
    print('Atrium static web compatibility passed:',json.dumps(data))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write(f"### Atrium game compatibility: {data['title']}\nSource validation passed. **This does not prove deployed multiplayer readiness or publication approval.**\n")
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
            for key,val in outputs.items(): f.write(f'{key}={val}\n')
if __name__=='__main__': main()
