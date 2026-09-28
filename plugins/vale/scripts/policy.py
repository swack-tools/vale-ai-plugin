"""Resolve bounded project selection; Vale remains the authority for prose rules."""
import configparser
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
import os
from pathlib import Path, PureWindowsPath
import stat
import tomllib

EXTENSIONS = set('.md .mdx .txt .rst .adoc .html .rs .py .sh .pl .js .jsx .ts .tsx .go .c .h .cpp .hpp .java .css'.split())
HARD_EXCLUDED = {'.git', '.codex', '.claude', '.agents'}
SOFT_EXCLUDED = {'.venv', 'node_modules', 'target', 'dist', 'build', '.vale', 'vendor', '__pycache__'}
EXCLUDED = HARD_EXCLUDED | SOFT_EXCLUDED
MAX_POLICY_BYTES = 65536


@dataclass(frozen=True)
class EffectivePolicy:
    schema_version: int = 1
    scope: str = 'changed-files'
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    profile: str = 'auto'
    origins: dict[str, str] = field(default_factory=lambda: {k: 'default' for k in ('schema_version', 'scope', 'include', 'exclude', 'profile')})
    formats: dict[str, str] = field(default_factory=dict)

    def selected(self, name):
        path = Path(name)
        # Normalize ordinary traversal only after the caller validates symlinks.
        relative = os.path.normpath(name).replace(os.sep, '/')
        if set(Path(relative).parts) & HARD_EXCLUDED:
            return False
        if self.include:
            if not any(fnmatchcase(relative, pattern) for pattern in self.include):
                return False
        elif set(path.parts) & SOFT_EXCLUDED:
            return False
        return not any(fnmatchcase(relative, pattern) for pattern in self.exclude)

    def supports(self, name):
        suffix = Path(name).suffix
        return suffix.lower() in EXTENSIONS or (bool(self.include) and suffix[1:] in self.formats)


def policy_bytes(root):
    path = root / '.vale-plugin.toml'
    if not path.exists() and not path.is_symlink():
        return None
    return read_config(path)


def read_config(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError(f'Refusing a symbolic link for {path.name}.')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_POLICY_BYTES:
            raise ValueError(f'{path.name} must be a regular file of at most 64 KiB.')
        content = source.read(MAX_POLICY_BYTES + 1)
    if len(content) > MAX_POLICY_BYTES:
        raise ValueError(f'{path.name} exceeds 64 KiB.')
    return content


def validate(values):
    allowed = {'schema_version', 'scope', 'include', 'exclude', 'profile'}
    if unknown := values.keys() - allowed:
        raise ValueError('Unknown wrapper policy keys: ' + ', '.join(sorted(unknown)))
    for key, value in values.items():
        if key == 'schema_version':
            if type(value) is not int or value != 1:
                raise ValueError('schema_version must be the integer 1.')
        elif key in ('scope', 'profile'):
            choices = ('changed-files', 'new-findings') if key == 'scope' else ('auto', 'google')
            if not isinstance(value, str) or value not in choices:
                raise ValueError(f'{key} must be one of: ' + ', '.join(choices))
        else:
            if not isinstance(value, list) or len(value) > 64:
                raise ValueError(f'{key} must be a list of at most 64 patterns.')
            for pattern in value:
                if (not isinstance(pattern, str) or not pattern or len(pattern) > 512 or
                        '\\' in pattern or pattern.startswith('/') or PureWindowsPath(pattern).drive or
                        '..' in pattern.split('/') or any(ord(c) < 32 for c in pattern)):
                    raise ValueError(f'{key} requires nonempty root-relative POSIX patterns without traversal (512 characters maximum).')


def load_policy(root, cli_overrides=None):
    defaults = dict(schema_version=1, scope='changed-files', include=[], exclude=[], profile='auto')
    origins = {key: 'default' for key in defaults}
    content = policy_bytes(root)
    project = tomllib.loads(content.decode('utf-8')) if content is not None else {}
    explicit = {key: value for key, value in (cli_overrides or {}).items() if value is not None}
    for values, source in ((project, 'project'), (explicit, 'cli')):
        validate(values)
        defaults.update(values)
        origins.update({key: source for key in values})
    config = root / '.vale.ini'
    if defaults['profile'] == 'google' and (config.exists() or config.is_symlink()):
        raise ValueError('profile=google conflicts with the root .vale.ini; use profile=auto or remove the root configuration.')
    formats = {}
    if defaults['include'] and config.is_file():
        ini = configparser.ConfigParser(interpolation=None, strict=False)
        ini.optionxform = str
        try:
            ini.read_string('[DEFAULT]\n' + read_config(config).decode('utf-8'))
        except configparser.Error as exc:
            raise ValueError('Cannot read project format mappings: ' + str(exc)) from exc
        if ini.has_section('formats'):
            formats = {key: value for key, value in ini.items('formats')
                       if '.' + value in EXTENSIONS and key.lower() not in ('yaml', 'yml', 'json')}
    defaults['include'] = tuple(defaults['include'])
    defaults['exclude'] = tuple(defaults['exclude'])
    return EffectivePolicy(**defaults, origins=origins, formats=formats)
