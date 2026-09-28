#!/usr/bin/env python3
"""Exercise Claude plugin discovery and hooks with a local model fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from smoke_support import temporary_workspace

REPO = Path(__file__).resolve().parents[1]
requests = []
project = None


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if not self.path.startswith('/v1/messages'):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{}')
            return
        requests.append(request)
        index = len(requests)
        is_tool = index in (1, 3)
        if is_tool:
            prose = 'We will use this, e.g. for testing.\n' if index == 1 else 'Use this file for testing.\n'
            block = {'type': 'tool_use', 'id': f'call_{index}', 'name': 'Write', 'input': {}}
            delta = {'type': 'input_json_delta', 'partial_json': json.dumps({'file_path': str(project / 'smoke.md'), 'content': prose})}
        else:
            block = {'type': 'text', 'text': ''}
            delta = {'type': 'text_delta', 'text': 'Fixture finished.'}
        message = {'id': f'msg_{index}', 'type': 'message', 'role': 'assistant',
                   'content': [], 'model': request.get('model'), 'stop_reason': None,
                   'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 1}}
        events = [('message_start', {'message': message}),
                  ('content_block_start', {'index': 0, 'content_block': block}),
                  ('content_block_delta', {'index': 0, 'delta': delta}),
                  ('content_block_stop', {'index': 0}),
                  ('message_delta', {'delta': {'stop_reason': 'tool_use' if is_tool else 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 1}}),
                  ('message_stop', {})]
        body = ''.join(f'event: {name}\ndata: {json.dumps(dict(type=name, **data))}\n\n' for name, data in events).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    global project
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=('user', 'project'), default='user')
    parser.add_argument('--feedback-scope', choices=('changed-files', 'new-findings'), default='changed-files')
    parser.add_argument('--skill', choices=('check-prose', 'procedural-prose'), default='check-prose')
    args = parser.parse_args()
    requests.clear()
    with temporary_workspace(prefix='vale-claude-smoke-') as tmp:
        base = Path(tmp).resolve()
        project = base / 'project'
        project.mkdir()
        subprocess.run(['git', 'init', '-q', str(project)], check=True)
        (project / '.vale-plugin.toml').write_text(
            f'scope = "{args.feedback_scope}"\ninclude = ["smoke.md"]\n')
        config = base / 'claude'
        config.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(('ANTHROPIC_', 'CLAUDE_')) and k != 'CLAUDECODE'}
        env.update(CLAUDE_CONFIG_DIR=str(config), ANTHROPIC_API_KEY='offline-fixture',
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', DISABLE_AUTOUPDATER='1')
        for command in (['claude', 'plugin', 'marketplace', 'add', str(REPO), '--scope', args.scope],
                        ['claude', 'plugin', 'install', 'vale@vale', '--scope', args.scope]):
            result = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
        server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env['ANTHROPIC_BASE_URL'] = f'http://127.0.0.1:{server.server_port}'
        try:
            result = subprocess.run(['claude', '-p', f'/vale:{args.skill} smoke.md', '--verbose',
                                     '--output-format', 'stream-json', '--dangerously-skip-permissions',
                                     '--max-turns', '8'], cwd=project, env=env,
                                    capture_output=True, text=True, timeout=90)
        finally:
            server.shutdown()
        evidence = REPO / '.research'
        evidence.mkdir(exist_ok=True)
        (evidence / 'claude-smoke.jsonl').write_text(result.stdout)
        (evidence / 'claude-smoke.stderr').write_text(result.stderr)
        (evidence / 'claude-smoke-requests.json').write_text(json.dumps(requests, indent=2))
        print(result.stdout[-5000:])
        print(result.stderr[-1500:])
        assert result.returncode == 0, result.returncode
        assert requests, 'Claude did not call the local fixture'
        heading = 'Revise procedures' if args.skill == 'procedural-prose' else 'Check technical prose'
        assert heading in json.dumps(requests[0]), 'Claude did not expand the selected command or skill'
        assert 'vale:procedural-prose' in json.dumps(requests[0]), 'Claude did not discover the procedural skill'
        assert any('Google.Latin' in json.dumps(r) for r in requests[1:]), 'Claude did not receive hook feedback'
        if args.feedback_scope == 'new-findings':
            received = json.dumps(requests[1:])
            assert 'new/actionable' in received, 'Client did not receive the project comparison scope'
            assert 'Comparison fallback' not in received, 'Comparison unexpectedly fell back'
        assert (project / 'smoke.md').read_text() == 'Use this file for testing.\n', 'Stop hook did not trigger correction'
        print(f'Real Claude plugin, command, and hook dispatch passed ({len(requests)} offline requests).')


if __name__ == '__main__':
    main()
