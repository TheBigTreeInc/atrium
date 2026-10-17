"""Test-only compatibility with already-registered legacy ZipRunner commands.

The registered command `python -m unittest discover -s tests -v` may ignore
project.zr. Allow that interpreter to consume dependencies from an existing
project .venv ONLY when the Python major/minor ABI matches. This is not a
production import hook, a substitute for bootstrap, or permission to install
packages globally. Missing dependencies fail loudly; tests are never skipped.
"""
from __future__ import annotations

import importlib
import re
import subprocess
import site
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('sqlalchemy', 'starlette')


def site_packages(root: Path | None = None, *, platform: str | None = None) -> Path:
    """Return ABI-compatible venv packages or fail without altering sys.path."""
    root = ROOT if root is None else root
    venv = root / '.venv'
    config = venv / 'pyvenv.cfg'
    if not config.is_file():
        raise RuntimeError('Atrium .venv is absent: run python tools/setup_build_env.py')
    text = config.read_text(encoding='utf-8')
    found = re.search(r'(?im)^version\s*=\s*(\d+)\.(\d+)(?:\.|$)', text)
    if not found or tuple(map(int, found.groups())) != sys.version_info[:2]:
        raise RuntimeError('Atrium .venv Python version differs from the ZipRunner test interpreter; '
                           'run tests via python tools/run_python_checks.py')
    if (platform or sys.platform).startswith('win'):
        path = venv / 'Lib' / 'site-packages'
    else:
        path = venv / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    if not path.is_dir():
        raise RuntimeError('Atrium .venv packages are missing: run python tools/setup_build_env.py')
    return path


def _bootstrap_environment() -> None:
    """Initialize only the project-local venv using the audited setup tool."""
    cmd = [sys.executable, str(ROOT / 'tools' / 'setup_build_env.py')]
    print('[atrium-tests] Legacy recipe detected; bootstrapping isolated .venv',
          file=sys.stderr, flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def require_test_dependencies() -> None:
    """Keep legacy direct unittest discovery running the complete real suite."""
    try:
        for name in REQUIRED:
            importlib.import_module(name)
        return
    except ModuleNotFoundError:
        pass
    try:
        path = site_packages()
    except RuntimeError as error:
        if 'differs from' in str(error):
            raise  # Never attach binary packages from a different Python ABI.
        _bootstrap_environment()
        path = site_packages()
    site.addsitedir(str(path))
    importlib.invalidate_caches()
    try:
        for name in REQUIRED:
            importlib.import_module(name)
    except ModuleNotFoundError:
        # The existing environment may have an old/incomplete installation.
        _bootstrap_environment()
        site.addsitedir(str(site_packages()))
        importlib.invalidate_caches()
        for name in REQUIRED:
            importlib.import_module(name)  # Do not skip or conceal any failure.
    print('[atrium-tests] Legacy ZipRunner Python: using ABI-matched project .venv dependencies',
          file=sys.stderr, flush=True)
