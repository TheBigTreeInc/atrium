"""Generate checked-in nested DAPI checkers handler from canonical Python logic.

DAPI fetches only YAML fragments, not arbitrary sibling Python modules.
Never overwrite edited YAML silently; --check fails if generated content differs.
"""
import argparse
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'modules/games/checkers/looprd.base.yaml'
TARGET = ROOT / 'modules/games/checkers/looprd.yaml'
SOURCE = ROOT / 'src/checkers.py'

def render():
    spec = yaml.safe_load(BASE.read_text(encoding='utf-8'))
    code = SOURCE.read_text(encoding='utf-8').rstrip() + '\n'
    spec.setdefault('handlers', []).append({
        'path': '/games/checkers/evaluate',
        'method': 'POST',
        'kind': 'python',
        'scopes': ['checkers:play'],
        'source': code,
    })
    class Literal(str):pass
    def represent(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str',str(data),style='|')
    yaml.SafeDumper.add_representer(Literal,represent)
    spec['handlers'][-1]['source']=Literal(code)
    return yaml.safe_dump(spec,sort_keys=False,allow_unicode=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    expected=render()
    if args.check:
        if not TARGET.is_file() or TARGET.read_text(encoding='utf-8')!=expected:
            raise SystemExit('generated Checkers fragment stale: run python tools/build_spec.py')
        print('Checkers fragment matches canonical Python source')
    else:
        TARGET.write_text(expected,encoding='utf-8',newline='\n')
        print('updated nested Checkers fragment')

if __name__=='__main__':main()
