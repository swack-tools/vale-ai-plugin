#!/usr/bin/env python3
"""Install the optional /prompts:vale compatibility command for Codex."""
import argparse
import os
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'plugins/vale/prompts/vale.md'
MARKER = '<!-- vale-plugin-command -->'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser()
    directory = home / 'prompts'
    target = directory / 'vale.md'
    try:
        if home.is_symlink() or directory.is_symlink() or target.is_symlink():
            raise ValueError('Refusing a symlink in the command installation paths.')
        if target.exists() and MARKER not in target.read_text():
            raise ValueError(f'Refusing to replace an existing command: {target}')
        if args.uninstall:
            target.unlink(missing_ok=True)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            target.write_text(SOURCE.read_text())
        print(f'{"Removed" if args.uninstall else "Installed"}: {target}')
        if not args.uninstall:
            print('Requires the Vale plugin. Start a new Codex chat and use /prompts:vale.')
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
