"""Run Atrium's Python source checks using the isolated ZipRunner Python."""
from __future__ import annotations

from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
COMMANDS = [
    ['tools/validate_atriumd.py', 'examples/life.atriumd.yaml', '--component', 'the-life-loop'],
    ['tools/build_registry_spec.py', '--check'],
    ['tools/build_registration_spec.py', '--check'],
    ['tools/build_spec.py', '--check'],
    ['tools/check_specs.py'],
    ['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
]


def main() -> None:
    if not PYTHON.is_file():
        raise SystemExit('Missing isolated .venv: run python tools/setup_build_env.py first')
    for argv in COMMANDS:
        cmd = [str(PYTHON), *argv]
        print(f'[atrium-python] {" ".join(cmd)}', flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
    print('[atrium-python] All Python source checks passed', flush=True)


if __name__ == '__main__':
    main()
