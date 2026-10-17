"""Prepare an isolated, reusable Python build environment for ZipRunner.

Runs under the project-selected Python; does not mutate global site-packages.
A requirements/version fingerprint avoids needless network access on later builds.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / '.venv'
REQUIREMENTS = ROOT / 'requirements-dev.txt'
STAMP = ENV / '.atrium-build-env.json'
IMPORTS = ('yaml', 'sqlalchemy', 'starlette')


def venv_python() -> Path:
    return ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def fingerprint() -> str:
    payload = (REQUIREMENTS.read_bytes() + b'\0' + sys.version.encode() +
               b'\0' + sys.executable.encode() + b'\0' + sys.platform.encode())
    return hashlib.sha256(payload).hexdigest()


def run(args: list[str], *, stage: str) -> None:
    print(f'[{stage}] {" ".join(str(arg) for arg in args)}', flush=True)
    subprocess.run(args, check=True, cwd=ROOT)


def healthy(python: Path) -> bool:
    if not python.is_file():
        return False
    code = 'import ' + ', '.join(IMPORTS)
    return subprocess.run([str(python), '-c', code], cwd=ROOT, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, check=False).returncode == 0


def main() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit('Atrium requires Python 3.12 or later')
    key = fingerprint()
    python = venv_python()
    if python.is_file() and STAMP.is_file():
        try:
            if json.loads(STAMP.read_text(encoding='utf-8')) == {'fingerprint': key} and healthy(python):
                print('[build-env] Reusing verified isolated .venv', flush=True)
                return
        except (OSError, ValueError):
            pass
    if not python.is_file():
        print('[build-env] Creating .venv (no system-site-packages)', flush=True)
        run([sys.executable, '-m', 'venv', str(ENV)], stage='venv')
    # Invalidate the old successful stamp *before* changing dependencies.
    STAMP.unlink(missing_ok=True)
    try:
        run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--retries', '1', '--timeout', '10',
             '-r', str(REQUIREMENTS)], stage='dependencies')
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit('Could not install Atrium Python build dependencies in .venv. '
                         'Check pip availability/network access or configure an approved wheel index. '
                         'No global Python packages were changed.') from error
    if not healthy(python):
        raise SystemExit('Python build environment is missing yaml/sqlalchemy/starlette after installation')
    STAMP.write_text(json.dumps({'fingerprint': key}) + '\n', encoding='utf-8')
    print('[build-env] Ready: Python build dependencies verified', flush=True)


if __name__ == '__main__':
    main()
