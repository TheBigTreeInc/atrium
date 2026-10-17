"""Validate portable atriumd/v1 sidecar metadata without registering a game."""
import argparse
from pathlib import Path

# Direct execution (`python tools/name.py`) must resolve project-local packages.
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from src.atriumd_contract import SidecarError, validate_document


def validate_file(path, *, component, max_bytes=65_536):
    data = Path(path).read_bytes()
    if not 0 < len(data) <= max_bytes: raise SidecarError('invalid sidecar size')
    try: doc = yaml.safe_load(data.decode('utf-8'))
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise SidecarError('invalid YAML or encoding') from error
    return validate_document(doc, component=component)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sidecar', type=Path)
    parser.add_argument('--component', required=True)
    args = parser.parse_args()
    validate_file(args.sidecar, component=args.component)
    print('Validated portable atriumd/v1 sidecar; no registration performed')


if __name__ == '__main__': main()
