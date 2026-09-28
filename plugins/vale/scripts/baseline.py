"""Private initial documents and conservative, bounded comparison policy."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from deadline import DeadlineExceeded, run_process
from finding_diff import classify_findings
import vale_runner

MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_POLICY_FILES = 256
# Changing the bundled configuration or these rules requires reviewing locality.
TRUSTED_CONFIG = '16d6a15f80c63165715d3c5fa669ce9582a8ca611cf201d213880c900614d245'
TRUSTED_POLICY = 'dd65d5c0353e15692cea9bcd16171e46a46cb8f88bfb633ab47fdad5bc2897b7'
TRUSTED_RULES = {
    'Latin': 'fb453cb47632e8ab3687f4c6f1918b29f85ed653ed00c26d0497ad0c7c22b559',
    'We': '40887903a1ec910f1760dcfcca775d6731a07e157ab79d76db7ca8c0e9de69e4',
    'FirstPerson': '44e35192076ea0446acd977b45b86e5198e3d544331ce5657a375a7c42613f8b',
    'Will': 'a6960a331f30b6e4c0aea508722a3843eb31974261ca2981dcbea7793fba4f25',
    'WordList': 'a4823fd636cfdf015ac4a9602acae4fcbec492bcc3e997b2044d4555443bfd34',
    'WordListCase': '8bc410ad8956b0a1486a0cf389ea540a7ca9fc3ef3f6d8deff2e31ca40701520',
}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def safe_bytes(path, limit=vale_runner.MAX_BYTES):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Symbolic links are not used for comparison.')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Comparison input exceeds its size limit or is not a regular file.')
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError('Comparison input exceeds its size limit.')
    return content


def policy_identity(root, deadline):
    """Fingerprint only a sealed local configuration and bounded style tree."""
    if vale_runner.configuration(root) != vale_runner.PACKAGE / '.vale.ini':
        raise ValueError('Project policy dependencies are unverified; use a full-file check.')
    package = vale_runner.PACKAGE
    config = safe_bytes(package / '.vale.ini')
    if digest(config) != TRUSTED_CONFIG:
        raise ValueError('Bundled configuration changed; comparison locality needs review.')
    fingerprint = hashlib.sha256(config)
    count = total = 0
    verified_rules = set()

    def reject_walk_error(error):
        raise error

    for directory, dirs, files in os.walk(package / 'styles', followlinks=False, onerror=reject_walk_error):
        deadline.check()
        dirs.sort()
        if any((Path(directory) / d).is_symlink() for d in dirs):
            raise ValueError('Style directory contains a symbolic link.')
        count += len(dirs) + len(files)
        if count > MAX_POLICY_FILES:
            raise ValueError('Style fingerprint exceeds its traversal limit.')
        for name in sorted(files):
            deadline.check()
            path = Path(directory) / name
            content = safe_bytes(path)
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                raise ValueError('Style fingerprint exceeds its byte limit.')
            relative = str(path.relative_to(package))
            if relative.startswith('styles/Google/') and path.stem in TRUSTED_RULES:
                verified_rules.add(path.stem)
                if digest(content) != TRUSTED_RULES[path.stem]:
                    raise ValueError('A local rule changed; comparison locality needs review.')
            fingerprint.update(relative.encode() + b'\0' + content + b'\0')
    if verified_rules != TRUSTED_RULES.keys():
        raise ValueError('A required local rule was not read and verified.')
    if fingerprint.hexdigest() != TRUSTED_POLICY:
        raise ValueError('Bundled styles or vocabulary changed; comparison dependencies need review.')
    vale = shutil.which('vale')
    if not vale:
        raise ValueError('Vale is missing from PATH.')
    version = run_process([vale, '--version'], cwd=root, deadline=deadline, timeout=5)
    if version.returncode or version.stderr.strip():
        raise ValueError('Vale version could not be verified.')
    fingerprint.update(os.fsencode(str(Path(vale).resolve())) + b'\0' + version.stdout.encode())
    return fingerprint.hexdigest()


def atomic_json(path, data):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def session_directory(directory, session):
    return directory / (digest(session.encode()) + '.baseline')


def capture(directory, root, names, deadline):
    """Call once under the session lock, before the first editing tool runs."""
    if directory.exists() or directory.is_symlink():
        # Never replace a partial capture with bytes from a later editing step.
        return
    if any(p.is_symlink() for p in directory.parents):
        raise ValueError('Refusing a symbolic link in the baseline state path.')
    directory.mkdir(mode=0o700)
    manifest = {'schema_version': 1, 'complete': False, 'policy': None, 'files': {}}
    atomic_json(directory / 'manifest.json', manifest)
    try:
        manifest['policy'] = policy_identity(root, deadline)
    except (OSError, ValueError, RuntimeError) as exc:
        manifest['reason'] = str(exc)
        atomic_json(directory / 'manifest.json', manifest)
        return
    total = 0
    for name in sorted(names):
        deadline.check()
        try:
            content = safe_bytes(root / name)
            content.decode('utf-8')
            if total + len(content) > MAX_TOTAL_BYTES:
                raise ValueError('Session baseline exceeds the 16 MiB source-text limit.')
            filename = digest(os.fsencode(name))
            fd = os.open(directory / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as out:
                out.write(content)
            manifest['files'][name] = {'sha256': digest(content)}
            total += len(content)
        except (OSError, ValueError) as exc:
            manifest['files'][name] = {'reason': str(exc)}
    manifest['complete'] = True
    atomic_json(directory / 'manifest.json', manifest)


def session_reader(directory, policy):
    manifest = json.loads(safe_bytes(directory / 'manifest.json', MAX_TOTAL_BYTES))
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('Session baseline schema is invalid.')
    if manifest.get('complete') is not True:
        raise ValueError(manifest.get('reason') or 'Initial baseline capture is incomplete.')
    if manifest.get('policy') != policy:
        raise ValueError('Policy or Vale version changed since the initial snapshot.')
    files = manifest.get('files')
    if not isinstance(files, dict):
        raise ValueError('Session baseline manifest is invalid.')

    def read(name):
        if name not in files:
            return ''  # A file first created after the initial snapshot.
        entry = files[name]
        if not isinstance(entry, dict):
            raise ValueError('Session baseline entry is invalid.')
        if entry.get('reason'):
            raise ValueError(entry['reason'])
        content = safe_bytes(directory / digest(os.fsencode(name)))
        if digest(content) != entry.get('sha256'):
            raise ValueError('Stored baseline bytes changed.')
        return content.decode('utf-8')
    return read


def git_output(root, args, deadline, limit=8 * 1024 * 1024):
    proc = run_process(['git', '-C', str(root), '--literal-pathspecs', *args],
                       deadline=deadline, timeout=10, text=False, max_output=limit)
    if proc.returncode:
        raise ValueError(proc.stderr.decode('utf-8', errors='replace').strip() or 'Git baseline lookup failed.')
    return proc.stdout


def git_reader(root, revision, deadline):
    oid = git_output(root, ['rev-parse', '--verify', '--end-of-options', revision + '^{commit}'], deadline).decode().strip()

    def read(name):
        entry = git_output(root, ['ls-tree', '-z', oid, '--', name], deadline)
        if not entry:
            return ''
        metadata, path = entry.rstrip(b'\0').split(b'\t', 1)
        mode, kind, blob = metadata.split()
        if mode not in (b'100644', b'100755') or kind != b'blob' or os.fsdecode(path) != name:
            raise ValueError('Git baseline path is not a regular file.')
        content = git_output(root, ['cat-file', 'blob', blob.decode()], deadline, vale_runner.MAX_BYTES)
        return content.decode('utf-8')

    # An earlier project policy cannot be reconstructed through the bundled adapter.
    old_config = git_output(root, ['ls-tree', '-z', oid, '--', '.vale.ini'], deadline)
    reason = 'The base commit has a project policy with unverified dependencies.' if old_config else None
    package = vale_runner.PACKAGE
    if package.is_relative_to(root):
        tracked_policy = [str((package / item).relative_to(root)) for item in ('.vale.ini', 'styles')]
        # Omit --exclude-standard: ignored installed policies also lack Git history.
        if git_output(root, ['ls-files', '--others', '-z', '--', *tracked_policy], deadline):
            reason = 'Bundled policy has untracked or ignored inputs; historical equality is unverified.'
        elif git_output(root, ['diff', '--name-only', oid, '--', *tracked_policy], deadline):
            reason = 'Bundled policy differs from the base commit.'
    return oid, read, reason


def compare(root, result, documents, initial_policy, *, directory=None, revision=None, deadline):
    """Keep raw findings and select only conservatively actionable indexes."""
    comparison = dict(mode='new-findings', baseline_source='git' if revision is not None else 'session',
                      new=0, existing=0, resolved=0, fallback_reason=None, actionable_indexes=[])
    result.comparison = comparison
    reasons = []
    try:
        if revision is not None:
            try:
                oid, read, reason = git_reader(root, revision, deadline)
                comparison['baseline_source'] = 'git:' + oid
            except (OSError, ValueError, RuntimeError) as exc:
                result.errors.append(vale_runner.Issue('base_ref', 'Invalid Git baseline: ' + str(exc)))
                raise ValueError('Git baseline is unavailable.') from exc
            if reason:
                raise ValueError(reason)
        policy = policy_identity(root, deadline)
        if initial_policy != policy:
            raise ValueError('Policy was unverified or changed during the current check.')
        if revision is None:
            read = session_reader(directory, policy)
        for name in result.submitted_files:
            deadline.check()
            indexes = [i for i, f in enumerate(result.findings) if f.path == str(root / name)]
            try:
                if Path(name).suffix.lower() in ('.rst', '.adoc'):
                    raise ValueError('External parser dependencies are unverified.')
                before = read(name)
                after = documents[name]
                if after is None:
                    raise ValueError('Current comparison text exceeds the 16 MiB memory limit.')
                previous = vale_runner.check_document(root, before, name, deadline=deadline) if before else None
                if previous is not None and previous.errors:
                    raise ValueError('Baseline lint did not complete: ' + previous.errors[0].message)
                diff = classify_findings(before, after, previous.findings if previous else [], [result.findings[i] for i in indexes])
                deadline.check()
                if diff.uncertain:
                    raise ValueError(diff.reason)
                comparison['actionable_indexes'].extend(indexes[i] for i in diff.new)
                comparison['existing'] += len(diff.existing)
                comparison['resolved'] += len(diff.resolved)
            except DeadlineExceeded:
                raise
            except (OSError, ValueError, RuntimeError) as exc:
                reasons.append(name + ': ' + str(exc))
                comparison['actionable_indexes'].extend(indexes)
        if policy_identity(root, deadline) != policy:
            raise ValueError('Policy changed while comparison was running.')
        # Findings from partially failed batches are still actionable.
        submitted = {str(root / name) for name in result.submitted_files}
        comparison['actionable_indexes'].extend(i for i, f in enumerate(result.findings) if f.path not in submitted)
    except (OSError, ValueError, RuntimeError) as exc:
        reasons.append(str(exc))
        comparison['existing'] = comparison['resolved'] = 0
        comparison['actionable_indexes'] = list(range(len(result.findings)))
    comparison['actionable_indexes'].sort()
    comparison['new'] = len(comparison['actionable_indexes'])
    comparison['fallback_reason'] = '; '.join(reasons) or None
    return result.finish()
