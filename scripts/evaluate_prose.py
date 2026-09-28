#!/usr/bin/env python3
"""Validate paired writing trials without contacting a model or reading credentials."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = 'plugins/vale/skills/google-prose/SKILL.md'
CHECKS = ('meaning', 'quantities', 'negation', 'modality', 'prerequisites', 'order',
          'quoted_code', 'rule_references', 'unnecessary_changes')
PREFLIGHT = ('fresh_session', 'isolated_home', 'isolated_workspace', 'target_skill',
             'automatic_hooks', 'other_prose_tools')
TRIAL_FIELDS = {'case_id', 'arm', 'host', 'client_version', 'model', 'timestamp', 'session_id',
                'home', 'workspace', 'settings', 'prompt_file', 'prompt_sha256', 'skill_file',
                'skill_sha256', 'output_file', 'reviewer', 'semantic_verdict', 'notes',
                'review_checks', 'preflight', 'reviewed_output_sha256'}
LIMIT = 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(root, name):
    if (not isinstance(name, str) or not name or '\\' in name or
            PurePosixPath(name).is_absolute() or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('Evidence paths must be relative without dot or empty components.')
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Evidence path leaves its directory.')
    if any(part.is_symlink() for part in [path, *path.parents] if part != root and part.is_relative_to(root)):
        raise ValueError('Evidence paths must not contain symbolic links.')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            raise ValueError('Evidence must be a regular file of at most 1 MiB.')
        data = source.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('Evidence exceeds 1 MiB.')
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(root, name):
    return json.loads(read_file(root, name), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON number: ' + value)))


def catalog():
    return {case['case_id']: case for case in read_json(ROOT, 'evals/cases.json')}


def prepare(directory):
    """Create an unrun template; never overwrite existing evidence."""
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'prompts').mkdir()
    (directory / 'outputs').mkdir()
    (directory / 'skills').mkdir()
    skill = read_file(ROOT, SKILL)
    (directory / 'skills/google-prose.md').write_bytes(skill)
    trials = []
    for case in catalog().values():
        prompt = read_file(ROOT, case['prompt_file'])
        prompt_file = 'prompts/' + case['case_id'] + '.txt'
        (directory / prompt_file).write_bytes(prompt)
        for arm in ('baseline', 'skill'):
            trials.append(dict(case_id=case['case_id'], arm=arm, host='', client_version='', model='',
                               timestamp='', session_id='', home='', workspace='', settings={},
                               prompt_file=prompt_file, prompt_sha256=digest(prompt),
                               skill_file='skills/google-prose.md' if arm == 'skill' else None,
                               skill_sha256=digest(skill) if arm == 'skill' else None,
                               output_file=f"outputs/{case['case_id']}-{arm}.{case['format']}",
                               reviewer=None, semantic_verdict='unreviewed', reviewed_output_sha256=None, notes='',
                               review_checks=dict.fromkeys(CHECKS, 'unreviewed'),
                               preflight={key: key == 'target_skill' and arm == 'skill' for key in PREFLIGHT}))
    (directory / 'trials.json').write_text(json.dumps(trials, indent=2) + '\n')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def inspect_trial(directory, trial, case):
    if set(trial) != TRIAL_FIELDS:
        raise ValueError('Trial fields differ from the prepared schema: ' + ', '.join(sorted(set(trial) ^ TRIAL_FIELDS)))
    for key in ('host', 'client_version', 'model', 'timestamp', 'session_id', 'home', 'workspace'):
        if not nonempty(trial.get(key)):
            raise ValueError('Missing nonempty ' + key)
    stamp = datetime.fromisoformat(trial['timestamp'].replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timestamp needs a timezone.')
    if trial['host'] not in ('codex', 'claude'):
        raise ValueError('host must identify codex or claude.')
    settings = trial.get('settings')
    if not isinstance(settings, dict) or not settings or not all(nonempty(k) and type(v) in (str, int, float, bool) for k, v in settings.items()):
        raise ValueError('settings must record nonempty model settings with scalar values.')
    preflight = trial.get('preflight')
    expected = dict(fresh_session=True, isolated_home=True, isolated_workspace=True,
                    target_skill=trial['arm'] == 'skill', automatic_hooks=False, other_prose_tools=False)
    if (not isinstance(preflight, dict) or set(preflight) != set(expected) or
            any(type(preflight[k]) is not bool or preflight[k] != v for k, v in expected.items())):
        raise ValueError('Preflight does not attest to fresh, isolated, uncontaminated skill-only trials.')
    prompt = read_file(directory, trial.get('prompt_file'))
    if digest(prompt) != trial.get('prompt_sha256') or prompt != read_file(ROOT, case['prompt_file']):
        raise ValueError('Prompt hash/content does not match the synthetic case.')
    if trial['arm'] == 'skill':
        skill = read_file(directory, trial.get('skill_file'))
        if digest(skill) != trial.get('skill_sha256') or skill != read_file(ROOT, SKILL):
            raise ValueError('Skill hash/content does not match this checkout.')
    elif trial.get('skill_file') is not None or trial.get('skill_sha256') is not None:
        raise ValueError('Baseline must not load the target skill.')
    output = read_file(directory, trial.get('output_file')).decode('utf-8')
    if not output.strip():
        raise ValueError('Output is empty.')
    checks = trial.get('review_checks')
    if not isinstance(checks, dict) or set(checks) != set(CHECKS) or any(v not in ('pass', 'fail', 'unreviewed') for v in checks.values()):
        raise ValueError('Record every semantic review dimension as pass, fail, or unreviewed.')
    verdict = 'unreviewed' if 'unreviewed' in checks.values() else 'fail' if 'fail' in checks.values() else 'pass'
    if trial.get('semantic_verdict') != verdict:
        raise ValueError('semantic_verdict contradicts the review dimensions.')
    reviewer = trial.get('reviewer')
    if verdict != 'unreviewed':
        if trial.get('reviewed_output_sha256') != digest(output.encode('utf-8')):
            raise ValueError('Output changed or its review hash is missing; review this exact output.')
        if (not isinstance(reviewer, dict) or reviewer.get('kind') not in ('human', 'agent') or
                not nonempty(reviewer.get('id')) or not nonempty(trial.get('notes'))):
            raise ValueError('Reviewed evidence needs an identified human/agent and review notes.')
    source = read_file(ROOT, case['input_file']).decode('utf-8')
    mismatches = [dict(literal=literal, expected=source.count(literal), actual=output.count(literal))
                  for literal in case['protected_literals'] if output.count(literal) != source.count(literal)]
    return dict(case_id=trial['case_id'], arm=trial['arm'], literal_status='fail' if mismatches else 'pass',
                literal_mismatches=mismatches, semantic_verdict=verdict, reviewer=reviewer,
                review_checks=checks, notes=trial.get('notes'), output_sha256=digest(output.encode('utf-8')),
                lint={'status': 'not_run'})


def evaluate(directory):
    report = dict(schema_version=1, status='incomplete', exit_code=2, errors=[], trials=[], pairs=[],
                  lint={'status': 'not_run', 'note': 'No lint or model calls are made by the offline validator.'},
                  note='A pass means complete reviewed evidence, not measured editorial improvement or certified compliance.')
    errors = report['errors']
    try:
        cases = catalog()
        trials = read_json(directory, 'trials.json')
        if not isinstance(trials, list) or len(trials) > 12:
            raise ValueError('trials.json must contain at most 12 records for the six paired cases.')
    except (OSError, ValueError, TypeError) as exc:
        errors.append(str(exc))
        return report
    grouped = {}
    unique = {key: set() for key in ('session_id', 'home', 'workspace', 'output_file')}
    for index, trial in enumerate(trials):
        try:
            if not isinstance(trial, dict) or trial.get('case_id') not in cases or trial.get('arm') not in ('baseline', 'skill'):
                raise ValueError('Unknown case or arm.')
            key = (trial['case_id'], trial['arm'])
            if key in grouped:
                raise ValueError('Duplicate case/arm.')
            grouped[key] = trial
            result = inspect_trial(directory, trial, cases[trial['case_id']])
            for field, seen in unique.items():
                value = trial[field]
                if value in seen:
                    errors.append(f'Reused {field} in {key}.')
                seen.add(value)
            report['trials'].append(result)
            if result['semantic_verdict'] == 'unreviewed':
                errors.append(f'{key}: semantic review is incomplete.')
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(f'Trial {index}: {exc}')
    for case_id in cases:
        baseline, skill = (grouped.get((case_id, arm)) for arm in ('baseline', 'skill'))
        if baseline is None or skill is None:
            errors.append(f'{case_id}: missing baseline or skill arm.')
            continue
        mismatches = [field for field in ('host', 'client_version', 'model', 'settings', 'prompt_sha256')
                      if baseline.get(field) != skill.get(field)]
        if mismatches:
            errors.append(f'{case_id}: mismatched pair metadata: ' + ', '.join(mismatches))
        report['pairs'].append(dict(case_id=case_id, metadata_match=not mismatches))
    failures = sum(t['literal_status'] == 'fail' or t['semantic_verdict'] == 'fail' for t in report['trials'])
    report['exit_code'] = 2 if errors else 1 if failures else 0
    report['status'] = {0: 'reviewed', 1: 'failed', 2: 'incomplete'}[report['exit_code']]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--results', type=Path, help='Directory containing trials.json and evidence files.')
    mode.add_argument('--prepare', type=Path, help='Create a new, unrun six-pair template.')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    args = parser.parse_args()
    if args.prepare:
        try:
            prepare(args.prepare)
        except (OSError, ValueError) as exc:
            print('Cannot prepare evaluation: ' + str(exc), file=sys.stderr)
            return 2
        print('Created unrun evaluation template at ' + str(args.prepare))
        return 0
    report = evaluate(args.results.resolve())
    if args.format == 'json':
        print(json.dumps(report, indent=2))
    else:
        print('Evaluation: ' + report['status'])
        print(report['note'])
        for trial in report['trials']:
            print(f"{trial['case_id']} {trial['arm']}: literals={trial['literal_status']}, semantic={trial['semantic_verdict']}")
            for mismatch in trial['literal_mismatches']:
                print(f"  Protected literal {mismatch['literal']!r}: expected {mismatch['expected']}, observed {mismatch['actual']}")
        for error in report['errors']:
            print('Incomplete: ' + error)
        print('Lint: not run; run the package checker separately.')
    return report['exit_code']


if __name__ == '__main__':
    sys.exit(main())
