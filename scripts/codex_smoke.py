#!/usr/bin/env python3
"""Test real Codex hook dispatch with an offline, deterministic model fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[1]
requests = []


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(request)
        index = len(requests)
        tools = {t['name']: t for t in request.get('tools', []) if 'name' in t}
        if index in (1, 3):
            text = 'We will use this, e.g. for testing.' if index == 1 else 'Use this file for testing.'
            command = f"printf '%s\\n' '{text}' > smoke.md"
            if 'exec_command' in tools:
                name, args = 'exec_command', {'cmd': command, 'yield_time_ms': 1000}
            elif 'shell_command' in tools:
                name, args = 'shell_command', {'command': command}
            elif 'shell' in tools:
                name, args = 'shell', {'command': ['sh', '-c', command]}
            else:
                raise RuntimeError(f'Unknown shell tool names: {list(tools)}')
            output = {'type': 'function_call', 'id': f'fc_{index}', 'call_id': f'call_{index}', 'name': name, 'arguments': json.dumps(args)}
        else:
            output = {'type': 'message', 'id': f'msg_{index}', 'role': 'assistant', 'status': 'completed',
                      'content': [{'type': 'output_text', 'text': 'Fixture finished.', 'annotations': []}]}
        response = {'id': f'resp_{index}', 'object': 'response', 'created_at': 1, 'status': 'completed',
                    'model': 'gpt-5.4', 'output': [output], 'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}
        events = [
            ('response.created', {'response': dict(response, status='in_progress', output=[])}),
            ('response.output_item.added', {'output_index': 0, 'item': output}),
            ('response.output_item.done', {'output_index': 0, 'item': output}),
            ('response.completed', {'response': response})]
        body = ''.join('event: ' + name + '\ndata: ' + json.dumps(dict(type=name, **data)) + '\n\n' for name, data in events).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', action='store_true', help='Install the repository marketplace instead of project hooks.')
    args = parser.parse_args()
    requests.clear()
    with tempfile.TemporaryDirectory(prefix='vale-codex-smoke-') as tmp:
        base = Path(tmp).resolve()
        project = base / 'project'
        home = base / 'codex'
        project.mkdir(); home.mkdir()
        subprocess.run(['git', 'init', '-q', str(project)], check=True)
        env = dict(os.environ, CODEX_HOME=str(home))
        if not args.plugin:
            subprocess.run(['python3', str(REPO / 'scripts/install.py'), '--project', str(project)], check=True, capture_output=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = f'''model = "gpt-5.4"
model_provider = "fixture"
[model_providers.fixture]
name = "Offline hook test"
base_url = "http://127.0.0.1:{server.server_port}/v1"
wire_api = "responses"
requires_openai_auth = false
[features]
hooks = true
[projects.{json.dumps(str(project))}]
trust_level = "trusted"
'''
        (home / 'config.toml').write_text(config)
        if args.plugin:
            for command in (['codex', 'plugin', 'marketplace', 'add', str(REPO)],
                            ['codex', 'plugin', 'add', 'vale@vale']):
                install = subprocess.run(command, env=env, cwd=project, capture_output=True, text=True, timeout=60)
                assert install.returncode == 0, install.stdout + install.stderr
        try:
            result = subprocess.run(['codex', 'exec', '--ephemeral', '--dangerously-bypass-hook-trust',
                                     '-C', str(project), '-s', 'danger-full-access', '--json',
                                     ('$vale:check-prose smoke.md. Run the deterministic hook fixture.' if args.plugin else
                                      'Run the supplied deterministic hook fixture.')],
                                    env=env, capture_output=True, text=True, timeout=90)
        finally:
            server.shutdown()
        evidence = REPO / '.research'
        evidence.mkdir(exist_ok=True)
        (evidence / 'codex-smoke.jsonl').write_text(result.stdout)
        (evidence / 'codex-smoke.stderr').write_text(result.stderr)
        (evidence / 'codex-smoke-requests.json').write_text(json.dumps(requests, indent=2))
        print(result.stdout[-5000:])
        print(result.stderr[-1500:])
        assert result.returncode == 0, result.returncode
        if args.plugin:
            assert 'vale:check-prose' in json.dumps(requests[0]), 'Codex did not discover the checking skill'
            assert 'vale:google-prose' in json.dumps(requests[0]), 'Codex did not discover the writing skill'
        assert any('Google.Latin' in json.dumps(r) for r in requests[1:]), 'Codex did not receive Vale feedback'
        assert (project / 'smoke.md').read_text() == 'Use this file for testing.\n', 'Fixture did not correct the prose'
        print(f'Real Codex hook dispatch passed ({len(requests)} offline model requests).')


if __name__ == '__main__':
    main()
