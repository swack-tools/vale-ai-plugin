"""Match occurrences only when their complete local context stays unchanged."""
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from difflib import SequenceMatcher

# These bundled rules inspect words or punctuation in local prose. Other rules
# may depend on headings, definitions, or document-wide state and stay actionable.
LOCAL_RULES = frozenset({'Google.Latin', 'Google.We', 'Google.FirstPerson', 'Google.Will',
                         'Google.WordList', 'Google.WordListCase'})


@dataclass
class DiffResult:
    new: list[int]
    existing: list[int]
    resolved: list[int]
    uncertain: bool = False
    reason: str | None = None


def paragraphs(lines):
    ranges, by_line = [], {}
    start = None
    for index in range(len(lines) + 1):
        if index < len(lines) and lines[index].strip():
            if start is None:
                start = index
        elif start is not None:
            item = (start, index, tuple(lines[start:index]))
            ranges.append(item)
            for line in range(start, index):
                by_line[line] = item
            start = None
    return ranges, by_line


def identity(finding, line):
    return (line, finding.column, finding.end_column, finding.rule,
            finding.severity, finding.message, finding.match)


def classify_findings(before_text, after_text, before, after):
    """Return after indexes for new/existing and before indexes for resolved."""
    all_findings = [*before, *after]
    if any(f.line is None or f.column is None or f.end_column is None for f in all_findings):
        return DiffResult(list(range(len(after))), [], [], True,
                          'A finding is missing source location details.')
    old, new = before_text.splitlines(), after_text.splitlines()
    if max(len(old), len(new)) > 5000 or len(old) * len(new) > 1_000_000:
        return DiffResult(list(range(len(after))), [], [], True, 'Alignment budget exceeded.')
    old_paras, old_lines = paragraphs(old)
    new_paras, new_lines = paragraphs(new)
    old_counts, new_counts = Counter(p[2] for p in old_paras), Counter(p[2] for p in new_paras)
    unique = {p for p in old_counts if old_counts[p] == new_counts[p] == 1}
    if [p[2] for p in old_paras if p[2] in unique] != [p[2] for p in new_paras if p[2] in unique]:
        return DiffResult(list(range(len(after))), [], [], True, 'Paragraph order changed; matching is ambiguous.')
    mapping = {}
    for block in SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks():
        mapping.update((block.b + offset, block.a + offset) for offset in range(block.size))
    occurrences = defaultdict(deque)
    for index, finding in enumerate(before):
        occurrences[identity(finding, finding.line)].append(index)
    existing, actionable, matched = [], [], set()
    for index, finding in enumerate(after):
        line = finding.line - 1
        paragraph = new_lines.get(line)
        mapped = mapping.get(line)
        old_paragraph = old_lines.get(mapped)
        safe = (paragraph is not None and old_paragraph is not None and
                paragraph[2] == old_paragraph[2] and
                all(mapping.get(paragraph[0] + offset) == old_paragraph[0] + offset
                    for offset in range(paragraph[1] - paragraph[0])))
        if safe and (finding.rule in LOCAL_RULES or before_text == after_text):
            candidates = occurrences[identity(finding, mapped + 1)]
            if candidates:
                matched.add(candidates.popleft())
                existing.append(index)
                continue
        actionable.append(index)
    return DiffResult(actionable, existing, [i for i in range(len(before)) if i not in matched])
