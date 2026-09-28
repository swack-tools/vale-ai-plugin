# Evaluate prose changes

Use the labeled corpus and offline trial validator from a source checkout:

```sh
python3 -m unittest discover -s tests -p test_corpus.py -v
python3 scripts/evaluate_prose.py --prepare evals/results/pilot
python3 scripts/evaluate_prose.py --results evals/results/pilot --format json
```

The final command returns `2` until the trial records contain complete evidence.
Preparation creates prompts, a writing-skill snapshot, and twelve unrun records.
It never overwrites an existing directory or invokes a model. Raw outputs belong
in the ignored `evals/results/` directory.

The [evaluation guide](https://vale.swacktech.com/evaluation.html) documents the
record schema, isolated trial procedure, review rubric, exit codes, and limits.
The default test suite runs without model credentials. Synthetic validator tests
aren't observations of model writing quality. A real-model pilot remains unrun.
These checks don't verify editorial effectiveness.

For procedural writing, pass `--suite procedural-prose` to both preparation and
validation. This suite needs fourteen records for seven pairs and snapshots
`procedural-prose`. The default remains six Google pairs. See the
[profile guide](https://vale.swacktech.com/profiles.html) for cases and limits.
Both real-model pilots remain unrun.
