# Evaluate writing quality

Use these tools from a source checkout to test rule behavior and review actual
writing changes. They don't run automatically when you install the plugin.
The tools answer different questions:

| Evidence | What it establishes | What it doesn't establish |
| --- | --- | --- |
| Native client fixtures | Hooks and skill feedback reach the client | A model improves writing |
| Labeled prose corpus | Selected rules produce expected findings at expected lines | General accuracy or complete style compliance |
| Offline trial validator | Paired records are complete and protected literals remain | An independent judgment of meaning |
| Reviewed model trials | Observed outcomes for the recorded cases, model, and reviewer | Results for other models or documents |

## Run the corpus

```sh
python3 -m unittest discover -s tests -p test_corpus.py -v
```

The corpus contains twelve synthetic Markdown and Python fixtures: positive and
negative cases for installation, troubleshooting, runbooks, API reference,
source comments, and already-correct prose. The positive control for correct
prose introduces one intentional error. These examples cover four selected rules:
`Google.We`, `Google.Will`, `Google.Latin`, and `Google.WordList`.

The manifest in `tests/fixtures/prose/manifest.json` records each case's identifier,
category, format, input path, expected findings, forbidden findings, and protected
literals. Findings identify a rule and a source line. Duplicate records express
multiplicity: the API example expects two Latin-abbreviation findings on one
line. Negative assertions protect code strings and quoted error literals.
Tests compare the exact counts for selected rules. Other rule findings aren't
labels for this corpus and don't contribute to an accuracy claim. Both
troubleshooting fixtures also produce a `Google.Contractions` suggestion for
the preserved prohibition. This observation remains separate from their
selected `Google.Will` labels.

The tests invoke real Vale with the bundled configuration at suggestion level.
They need no model account or network request. A missing Vale installation skips
the local integration cases with a reason. In CI, or with
`VALE_REQUIRE_PARSERS=1`, it fails the required suite. These fixtures need no
optional markup parser. Keep observed misses and false positives visible when
updating labels. Don't change labels merely to match the engine.

## Prepare paired trials

```sh
python3 scripts/evaluate_prose.py --prepare evals/results/pilot
```

Preparation creates a new directory containing `trials.json`, six prompt files,
a snapshot of `google-prose`, and an empty `outputs` directory. It refuses an
existing destination. It makes no model calls and reads no credentials.
Use a new directory for every experiment. Keep synthetic inputs in Git and raw
outputs under ignored `evals/results/`. Don't add user documents, credentials,
or account transcripts to the corpus or evidence.

Each case has two arms: `baseline` and `skill`. Both receive exactly the same
prompt from `evals/cases.json`. The skill arm enables only `google-prose`.
Automatic prose hooks stay off in both arms. This isolates the writing
skill's effect. Testing the combined skill and hooks needs a separate experiment.

Complete this preflight for every arm:

1. Create a fresh client session, home, and temporary workspace. Use unique
   identifiers for all twelve runs.
2. Verify the same host, client version, model, and model settings in each pair.
   Use those same values for all six pairs in a pilot. Record settings such as
   reasoning effort and temperature when supported.
3. Check that no inherited instructions, plugins, prose hooks, or writing skills
   affect the baseline. Confirm that both arms have the same other context.
4. Enable the target skill only in the skill arm. Keep automatic hooks and other
   prose tools off. Make the package checker available at the path the
   skill expects, with Vale on `PATH` and no project style overrides.
5. Verify authorized model access in the isolated environment. If it isn't
   available, leave the pilot unrun. Don't copy credentials into the evidence.
6. Send the saved prompt without changing it. Save the returned document exactly,
   then record the actual session metadata. Keep any extra run logs private.

These checks are operator attestations. The validator checks their structure
and consistency. It can't prove session isolation or that a
recorded model produced a file. Retain enough private run evidence for review.
The existing smoke scripts use scripted responses and can't substitute for this
pilot.

## Complete the records

Edit the generated records after the runs. Each record has these fields:

| Fields | Required content |
| --- | --- |
| `case_id`, `arm` | One known case and either `baseline` or `skill`. Exactly one of each per case |
| `host`, `client_version`, `model` | A host name of `codex` or `claude`, an actual client version, and a model identifier |
| `timestamp` | A timestamp with a timezone, such as `2026-09-28T12:00:00Z` |
| `session_id`, `home`, `workspace` | Distinct identifiers for each isolated run |
| `settings` | A nonempty object of model settings with string, number, or boolean values |
| `prompt_file`, `prompt_sha256` | A relative prompt path and its `SHA-256` digest |
| `skill_file`, `skill_sha256` | The target skill snapshot and digest for the skill arm. Both `null` for baseline |
| `output_file` | The relative path to the raw returned document |
| `reviewer` | An object with `kind` equal to `human` or `agent`, and a nonempty `id`. Use `null` while unreviewed |
| `review_checks` | A verdict for every dimension listed in the next section |
| `semantic_verdict` | `pass`, `fail`, or `unreviewed`, consistent with the dimension verdicts |
| `reviewed_output_sha256` | The `SHA-256` digest of the exact output that the reviewer assessed |
| `notes` | Nonempty review evidence for reviewed records |
| `preflight` | The six boolean attestations described below |

In `preflight`, set `fresh_session`, `isolated_home`, and `isolated_workspace` to
`true` only after checking them. Set `target_skill` to `false` for baseline and
`true` for the skill arm. Set `automatic_hooks` and `other_prose_tools` to `false`.

The validator rejects unknown record fields, duplicate JSON keys, reused run
identifiers, mismatched pair metadata, missing pairs, and unreviewed evidence.
Evidence files must be regular files of at most 1 MiB within the results
directory. The validator rejects absolute paths, path traversal, and symbolic links.

The validator checks prompt and skill digests against actual file bytes and the
current checkout. Preserve the checkout revision with your results. Revalidate
old experiments from that revision if prompts or skills have changed.
Don't change snapshots to make old evidence pass a new revision.

After reviewing an output, compute its digest:

```sh
python3 -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path("evals/results/pilot/outputs/installation-skill.md").read_bytes()).hexdigest())'
```

Copy the result into `reviewed_output_sha256`. An output edit invalidates its
review digest. Review the new output before recording a replacement digest.

## Review meaning separately

For each dimension, record `pass`, `fail`, or `unreviewed`:

| Dimension | Review question |
| --- | --- |
| `meaning` | Does the revision preserve the technical claim? |
| `quantities` | Are numbers, units, limits, and conditions unchanged? |
| `negation` | Are negative conditions and prohibitions preserved? |
| `modality` | Are requirements, recommendations, and permissions equally strong? |
| `prerequisites` | Are all prerequisites still present? |
| `order` | Does the required command and step order remain intact? |
| `quoted_code` | Are commands, paths, identifiers, quoted errors, and code unchanged? |
| `rule_references` | Are any cited rule names supported by actual checker output? |
| `unnecessary_changes` | Does already-correct prose remain useful without gratuitous rewriting? |

Use the original synthetic input alongside the output. Explain failures and
non-obvious judgments in `notes`. Identify agent review as agent review. Don't
label it human review. A dimension with no applicable content can pass with an
explanation in the notes. Any unreviewed dimension makes the overall verdict
`unreviewed`. Otherwise any failure makes it `fail`.

Protected-literal checks compare exact occurrence counts against the original
input and flag missing or added occurrences. Labels inside inline code protect
the complete code span. Labels that occupy a whole source line protect that
line. Other word and identifier labels use word boundaries, so an extended
identifier or a changed command argument can't pass as an unchanged prefix.
This conservative check also flags code-format changes that remove the
original delimiters or line layout. Keep that formatting intact during a trial.

These checks can detect a changed command even
when a reviewer marks the prose as a pass. Literal presence doesn't prove
correct meaning: an output could keep a command in the wrong context. The
semantic review remains necessary.

Run Vale separately on outputs to collect lint evidence:

```sh
python3 plugins/vale/scripts/prose_lint.py --check evals/results/pilot/outputs/installation-skill.md --format json
```

This explicit file check can inspect an ignored output. Automatic scans skip
ignored evaluation results. Record the configuration and raw findings with the
experiment. The offline validator reports lint as `not_run`. It doesn't infer
style quality from a semantic verdict or fewer words.

## Validate and interpret results

```sh
python3 scripts/evaluate_prose.py --results evals/results/pilot
python3 scripts/evaluate_prose.py --results evals/results/pilot --format json
```

| Exit | Meaning |
| --- | --- |
| `0` | All six pairs have matching metadata, complete reviews, and no literal or semantic failures |
| `1` | Complete reviewed evidence contains a literal or semantic failure |
| `2` | Evidence is invalid, incomplete, missing, or unreviewed |

Invalid or incomplete evidence takes precedence over reviewed failures. JSON
output retains per-arm literal and semantic results, reviewer identity, output
digests, pair consistency, and errors. A successful validation doesn't mean the
skill improved the baseline. Compare both arms' actual outcomes and report
regressions as well as improvements. Don't calculate general model accuracy or
Simplified Technical English (STE) compliance from these six cases or from a model's self-assessment.

## Current evidence

The twelve corpus fixtures pass their selected rule and location assertions
with Vale 3.23.0. Validator regressions demonstrate that changed commands,
incomplete pairs, contaminated baselines, mismatched models, stale output
reviews, and missing review dimensions can't pass.

The real-model pilot remains unrun. The current isolated client environments
have no authorized model session. A normal signed-in client doesn't establish
an uncontaminated paired experiment. Editorial improvement and semantic
preservation by the writing skill remain unverified. The harness is ready for
six matched pairs when isolated authorized model access is available.
