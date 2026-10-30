#!/usr/bin/env python3
"""Install this local skill, verifying any backup before replacement."""
import argparse
import hashlib
import shutil
from datetime import datetime
from pathlib import Path


def manifest(root):
    values = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('Symlink encountered; inspect manually before installation: ' + str(path))
        if path.is_file():
            values[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude'], default='codex')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / 'mv-script'
    if not (source / 'SKILL.md').is_file():
        parser.error('mv-script/SKILL.md is missing beside the installer')
    home_root = Path.home() / ('.agents' if args.host == 'codex' else '.claude') / 'skills'
    destination = home_root / 'mv-script'
    if destination.is_symlink():
        parser.error('existing skill is a symlink; inspect before replacing')
    expected = manifest(source)
    home_root.mkdir(parents=True, exist_ok=True)
    # Stage and verify before touching an existing installation.
    stamp = datetime.now().strftime('%Y%m%dT%H%M%S%f')
    staging = home_root / ('.mv-script-staging-' + stamp)
    shutil.copytree(source, staging)
    if manifest(staging) != expected:
        raise RuntimeError('Staged copy did not match source; original skill retained')
    backup = None
    if destination.exists():
        if not destination.is_dir():
            raise RuntimeError('Existing destination is not a skill directory')
        previous = manifest(destination)
        # Keep backups outside the discovery root to avoid duplicate skills.
        backup = home_root.parent / 'skill-backups' / ('mv-script-' + stamp)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(destination, backup)
        if manifest(backup) != previous:
            raise RuntimeError('Backup verification failed; original skill retained')
        if manifest(destination) != previous:
            raise RuntimeError('Existing skill changed during backup; replacement stopped')
        print('Inspected existing skill: %s files' % len(previous))
        print('Verified backup: ' + str(backup))
        shutil.rmtree(destination)
    try:
        staging.rename(destination)
    except OSError:
        if backup is not None and not destination.exists():
            shutil.copytree(backup, destination)
        raise
    if manifest(destination) != expected:
        raise RuntimeError('Installed copy differs from source; verified backup retained')
    print('Installed and SHA256 verified: ' + str(destination))


if __name__ == '__main__':
    main()
