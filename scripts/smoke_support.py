"""Temporary workspaces owned by the native client smoke fixtures."""
from contextlib import contextmanager
import errno
import tempfile
import time


@contextmanager
def temporary_workspace(*, prefix):
    directory = tempfile.TemporaryDirectory(prefix=prefix)
    try:
        yield directory.name
    finally:
        # A client can finish while a background Git clone is still exiting.
        # Retry only its transient directory race; never hide other failures.
        for attempt in range(6):
            try:
                directory.cleanup()
                break
            except OSError as exc:
                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST) or attempt == 5:
                    raise
                time.sleep(0.2 * (attempt + 1))


def isolated_environment(base, inherited=None):
    """Keep executable/parser lookup, but no ambient credentials or routing."""
    import os
    inherited = os.environ if inherited is None else inherited
    allowed = {'PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'TMP', 'TEMP',
               'SYSTEMROOT', 'GEM_HOME', 'GEM_PATH'}
    env = {key: value for key, value in inherited.items() if key in allowed}
    for key, name in (('HOME', 'home'), ('CODEX_HOME', 'codex'), ('CLAUDE_CONFIG_DIR', 'claude'),
                      ('XDG_CONFIG_HOME', 'xdg-config'), ('XDG_CACHE_HOME', 'xdg-cache')):
        directory = base / name
        directory.mkdir(parents=True, exist_ok=True)
        env[key] = str(directory)
    return env


def evidence_directory(requested, repository, host):
    """Allocate a fresh output directory, including for default invocations."""
    from pathlib import Path
    if requested is not None:
        path = Path(requested).resolve()
        path.mkdir(parents=True, exist_ok=False)
        return path
    parent = repository / '.research'
    parent.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=host + '-smoke-', dir=parent))


def fixture_repository(repository, base, trace):
    """Copy the package and trace its real hook, only inside the fixture workspace."""
    import shutil
    import subprocess
    destination = base / 'marketplace with spaces'
    destination.mkdir()
    for name in ('plugins', '.agents', '.claude-plugin'):
        shutil.copytree(repository / name, destination / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (destination / 'scripts').mkdir()
    shutil.copy2(repository / 'scripts/install.py', destination / 'scripts/install.py')
    hook = destination / 'plugins/vale/scripts/prose_lint.py'
    hook.rename(hook.with_name('prose_lint_runtime.py'))
    wrapper = '''import json, os, subprocess, sys
from pathlib import Path
payload = sys.stdin.read()
result = subprocess.run([sys.executable, str(Path(__file__).with_name('prose_lint_runtime.py')), *sys.argv[1:]], input=payload, capture_output=True, text=True, timeout=55)
try:
    incoming = json.loads(payload)
except ValueError:
    incoming = {}
try:
    outgoing = json.loads(result.stdout) if result.stdout.strip() else {}
except ValueError:
    outgoing = {'raw': result.stdout}
record = json.dumps({'input': incoming, 'output': outgoing, 'exit_code': result.returncode}) + '\\n'
fd = os.open(TRACE_PATH, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
try:
    os.write(fd, record.encode())
finally:
    os.close(fd)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
'''
    hook.write_text('TRACE_PATH = ' + repr(str(trace)) + '\n' + wrapper)
    env = isolated_environment(base)
    for command in (['git', 'init', '-q'], ['git', 'add', '.'],
                    ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture package']):
        subprocess.run(command, cwd=destination, env=env, check=True, capture_output=True, timeout=30)
    return destination


def assert_lifecycle(trace, requests, unresolved, stdout, *, host="codex"):
    """Keep emitted hook envelopes separate from client/model delivery evidence."""
    import json
    assert host in ('codex', 'claude'), 'Unknown native client'
    assert all(type(record.get('exit_code')) is int and record['exit_code'] == 0 for record in trace), 'Native hook invocation failed or lacks an exit code'
    events = [record['input'].get('hook_event_name') for record in trace]
    assert events == ['PreToolUse', 'PostToolUse', 'Stop'] * 2, 'Expected ordered Pre/Post/Stop events for both initial and correction writes'
    stops = [record for record in trace if record['input'].get('hook_event_name') == 'Stop']
    assert len(stops) == 2, 'Expected one initial Stop and one correction Stop'
    assert sum(record['output'].get('decision') == 'block' for record in stops) == 1, 'Expected exactly one blocking Stop'
    assert stops[-1]['input'].get('stop_hook_active') is True, 'Correction Stop was not marked active'
    assert stops[-1]['output'].get('decision') != 'block', 'Active Stop must not block again'
    assert len(requests) == 4, 'Fixture expected exactly one correction pass'
    assert 'Google.Latin' in json.dumps(requests[1]), 'Post feedback absent from model context'
    assert json.dumps(requests[2]).count('Google.Latin') > json.dumps(requests[1]).count('Google.Latin'), 'Stop feedback absent from model context'
    marker = 'Vale already requested a correction pass'
    if unresolved:
        assert marker in stops[-1]['output'].get('systemMessage', ''), 'Unresolved active Stop did not emit its report'
        assert marker not in json.dumps(requests), 'Active Stop unexpectedly reached model context; refresh the documented delivery contract'
        assert (marker in stdout) == (host == 'claude'), 'Active Stop stdout delivery changed; refresh the documented delivery contract'
    return {'events': events, 'blocking_stops': 1, 'model_requests': len(requests),
            'unresolved': unresolved,
            'active_stop_envelope_emitted': marker in json.dumps(stops[-1]['output']),
            'active_stop_model_visible': marker in json.dumps(requests),
            'active_stop_stdout_visible': marker in stdout}


UPGRADE_MARKER = 'Native fixture upgrade revision is present.'


def advance_fixture(repository, env):
    """Publish a new version only to the disposable local marketplace."""
    import json
    import subprocess
    for host in ('codex', 'claude'):
        manifest = repository / f'plugins/vale/.{host}-plugin/plugin.json'
        data = json.loads(manifest.read_text())
        data['version'] = data['version'].split('+', 1)[0] + '+fixture-upgrade'
        manifest.write_text(json.dumps(data, indent=2) + '\n')
    for skill in (repository / 'plugins/vale/skills').glob('*/SKILL.md'):
        skill.write_text(skill.read_text() + '\n' + UPGRADE_MARKER + '\n')
    for command in (['git', 'add', '.'], ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture upgrade']):
        subprocess.run(command, cwd=repository, env=env, check=True, capture_output=True, timeout=30)


def run_fixture_client(command, *, cwd, env, timeout, evidence, host, requests):
    """Retain captured client evidence on success, failure, and timeout."""
    import json
    import subprocess
    stdout, stderr = '', ''
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        stdout, stderr = result.stdout, result.stderr
        return result
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or '', exc.stderr or ''
        raise
    except OSError as exc:
        stderr = str(exc)
        raise
    finally:
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        (evidence / f'{host}-smoke.jsonl').write_text(stdout)
        (evidence / f'{host}-smoke.stderr').write_text(stderr)
        (evidence / f'{host}-smoke-requests.json').write_text(json.dumps(requests, indent=2))
