#!/usr/bin/env python3
"""Install or remove Vale hooks for a project or the current user."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'plugins/vale'
MARKER = '# vale-hook'
OWNERSHIP = '.vale-install.json'
PROJECT_COMMAND = "python3 -c 'from pathlib import Path; import subprocess, sys; p=Path.cwd().resolve(); f=next(r/\".codex/vale/scripts/prose_lint.py\" for r in (p,*p.parents) if (r/\".codex/vale/scripts/prose_lint.py\").is_file()); sys.exit(subprocess.call([sys.executable,str(f),*sys.argv[1:]]))' # vale-hook"
USER_COMMAND = 'python3 "${CODEX_HOME:-$HOME/.codex}/vale/scripts/prose_lint.py" # vale-hook'


def owned(group):
    handlers = group.get('hooks', [])
    return len(handlers) == 1 and handlers[0].get('command', '').endswith(MARKER)


def atomic_json(path, data):
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.vale-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def install(config, user, uninstall, host="codex", feedback_scope=None):
    destination = config / 'vale'
    hooks_file = config / ('settings.json' if host == 'claude' else 'hooks.json')
    if config.is_symlink() or destination.is_symlink() or hooks_file.is_symlink():
        raise ValueError('Refusing to replace a symlink in the installation paths.')
    data = json.loads(hooks_file.read_text()) if hooks_file.exists() else {'hooks': {}}
    if not isinstance(data, dict) or not isinstance(data.get('hooks', {}), dict):
        raise ValueError('hooks.json must contain a hooks object.')
    hooks = data.setdefault('hooks', {})
    for groups in hooks.values():
        if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
            raise ValueError('Each hook event must contain a list of matcher groups.')
    if destination.exists() and not (destination / OWNERSHIP).is_file():
        raise ValueError(f'Refusing to overwrite an unowned directory: {destination}')
    config.mkdir(parents=True, exist_ok=True)
    if hooks_file.exists():
        # A unique backup preserves every pre-install state, including local changes.
        fd, backup = tempfile.mkstemp(prefix=hooks_file.name + '.vale-backup-', dir=config)
        os.close(fd)
        shutil.copy2(hooks_file, backup)
    for event in list(hooks):
        hooks[event] = [group for group in hooks[event] if not owned(group)]
        if not hooks[event]:
            del hooks[event]
    if not uninstall:
        staging = Path(tempfile.mkdtemp(prefix='.vale-install-', dir=config))
        try:
            shutil.copytree(SOURCE, staging, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            (staging / OWNERSHIP).write_text(json.dumps({'package': 'vale', 'version': '0.7.0'}) + '\n')
            # Remove only files from our previous installed package; backups remain.
            if destination.exists():
                shutil.rmtree(destination)
            staging.rename(destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        command = USER_COMMAND if user else PROJECT_COMMAND
        if host == "claude":
            command = ('python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/vale/scripts/prose_lint.py" # vale-hook'
                       if user else PROJECT_COMMAND.replace(".codex/vale", ".claude/vale"))
        if feedback_scope is not None:
            command = command.removesuffix(MARKER) + f'--scope {feedback_scope} ' + MARKER
        for event in ('PreToolUse', 'PostToolUse', 'Stop'):
            hooks.setdefault(event, []).append({'hooks': [{'type': 'command', 'command': command,
                                                         'timeout': 60, 'statusMessage': 'Checking documentation style'}]})
        # Project hook discovery follows config layers. Preserve existing settings.
        config_file = config / 'config.toml'
        if host == 'codex' and not config_file.exists():
            config_file.write_text('# Vale hook configuration layer.\n[features]\nhooks = true\n')
    atomic_json(hooks_file, data)
    if uninstall and destination.exists():
        shutil.rmtree(destination)
    print(f'{"Removed" if uninstall else "Installed"} Vale hooks: {hooks_file}')
    if not uninstall:
        print(f'Restart {host}, trust the project if needed, then review Vale in /hooks.')
        if host == 'codex':
            print('If hooks are disabled in config.toml, enable them with: codex --enable hooks')
        if not shutil.which('vale'):
            print('Vale is missing. Install Vale 3.23 or later before using the hook.')
        if not user and (config.parent / '.vale.ini').exists():
            print('The project .vale.ini takes precedence. Run vale sync if its packages are missing.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--project', type=Path, metavar='DIRECTORY')
    scope.add_argument('--user', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--host', choices=('codex', 'claude'), default='codex')
    parser.add_argument('--feedback-scope', choices=('changed-files', 'new-findings'),
                        help='Select hook feedback. Reapply this option when updating an opt-in installation.')
    args = parser.parse_args()
    directory = '.claude' if args.host == 'claude' else '.codex'
    home_variable = 'CLAUDE_CONFIG_DIR' if args.host == 'claude' else 'CODEX_HOME'
    config = (Path(os.environ.get(home_variable, str(Path.home() / directory))).expanduser()
              if args.user else args.project.expanduser().resolve() / directory)
    try:
        install(config, args.user, args.uninstall, args.host, args.feedback_scope)
    except (OSError, ValueError, TypeError) as error:
        print(f'Vale installation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
