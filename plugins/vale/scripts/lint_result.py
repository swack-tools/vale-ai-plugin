"""Versioned results shared by the CLI and lifecycle adapters."""
from dataclasses import asdict, dataclass, field
import json


@dataclass
class Finding:
    path: str
    line: int
    column: int
    end_column: int | None
    rule: str
    severity: str
    message: str
    match: str
    link: str | None = None
    suggestions: list[str] = field(default_factory=list)
    action: dict | None = None


@dataclass
class Issue:
    code: str
    message: str
    path: str | None = None


@dataclass
class Coverage:
    source: str
    verification: str
    note: str


@dataclass
class CheckResult:
    schema_version: int
    status: str
    config_path: str
    requested_files: list[str]
    submitted_files: list[str]
    skipped_files: list[Issue]
    findings: list[Finding]
    errors: list[Issue]
    coverage: Coverage
    comparison: dict | None = None

    def finish(self):
        self.status = ('incomplete' if self.errors else 'findings' if self.actionable_findings else
                       'clean' if self.submitted_files else 'skipped')
        return self

    @property
    def actionable_findings(self):
        if self.comparison is None:
            return self.findings
        return [self.findings[i] for i in self.comparison['actionable_indexes']]

    @property
    def exit_code(self):
        return {'clean': 0, 'findings': 1, 'incomplete': 2, 'skipped': 2}[self.status]

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=True)


def one_line(value):
    """Prevent document text from injecting terminal lines or control sequences."""
    return ''.join(c if c.isprintable() else repr(c)[1:-1] for c in str(value))


def render_text(result, limit=None, *, prefix='', suffix='', report_path=None):
    """Render only whole entries; count metadata and adapter copy in the budget."""
    entries = [f'{one_line(f.path)}:{f.line}:{f.column}:{one_line(f.rule)}:{one_line(f.message)}'
               for f in result.actionable_findings]
    errors = [f'Vale could not complete the check: {one_line(e.message)}' for e in result.errors]
    if result.comparison is not None:
        c = result.comparison
        errors.append(f"Comparison: {c['new']} new/actionable, {c['existing']} existing, {c['resolved']} unmatched baseline findings.")
        if c['fallback_reason']:
            errors.append('Comparison fallback (full-file findings remain actionable): ' + one_line(c['fallback_reason']))
    skips = [f'Skipped {one_line(e.path)}: {one_line(e.message)}' for e in result.skipped_files]
    if limit is None:
        if not entries and not errors and not skips:
            return ('No findings under the selected configuration.' if result.status == 'clean'
                    else 'No applicable files were submitted.')
        return '\n'.join([*errors, *entries, *skips])
    # Reserve the largest possible summary before selecting entries.
    total = len(entries)
    report = f'Full report: {one_line(report_path)}' if report_path else ''
    summary_budget = len(f'{total} findings: {total} shown, {total} omitted.')
    fixed = '\n'.join(x for x in (prefix, report, suffix) if x)
    room = max(0, limit - len(fixed) - summary_budget - 16)
    selected = []
    omitted_errors = 0
    for error in errors + skips:
        if len(error) + 1 <= room:
            selected.append(error)
            room -= len(error) + 1
        else:
            omitted_errors += 1
    shown = 0
    for entry in entries:
        if len(entry) + 1 <= room:
            selected.append(entry)
            room -= len(entry) + 1
            shown += 1
    if omitted_errors:
        # A fixed short diagnostic, not a chopped error containing arbitrary content.
        selected.insert(0, 'Additional diagnostics omitted; inspect the full JSON result.')
    summary = f'{total} findings: {shown} shown, {total - shown} omitted.'
    parts = [prefix, *selected, summary, report, suffix]
    text = '\n'.join(x for x in parts if x)
    # Rare oversized metadata/error cases still preserve complete entries.
    while len(text) > limit and selected:
        removed = selected.pop()
        if removed in entries:
            shown -= 1
        summary = f'{total} findings: {shown} shown, {total - shown} omitted.'
        text = '\n'.join(x for x in (prefix, *selected, summary, report, suffix) if x)
    if len(text) > limit:
        text = '\n'.join(x for x in (prefix, summary, 'Full report location exceeds feedback budget.', suffix) if x)
    return text
