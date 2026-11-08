"""Local, offline TaviX -> Atrium presentation projection; no publication.

Usage: python tools/project_tavix_marketplace.py --index <TaviX-verified index>
       --approved-sha256 <operator-approved digest> --output <JSON>
       [--presentation <Atrium metadata JSON>]
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.tavix_marketplace_projection import project_tavix_games


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--approved-sha256', required=True)
    parser.add_argument('--presentation', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.index.read_bytes()
    presentation = json.loads(args.presentation.read_text(encoding='utf-8')) if args.presentation else None
    result = project_tavix_games(source, args.approved_sha256, presentation)
    if args.output.is_symlink() or not args.output.parent.is_dir():
        raise ValueError('output directory must exist; symlink outputs forbidden')
    data = (json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    # Do not replace a prior approved catalog until parsing/pinning succeeds.
    with tempfile.NamedTemporaryFile(prefix='.atrium-tavix-', suffix='.tmp', dir=args.output.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, args.output)
    print(f'projected {len(result["games"])} games from pinned TaviX snapshot (no publication/installation)')


if __name__ == '__main__':
    main()
