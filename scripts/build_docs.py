#!/usr/bin/env python3
"""Build the static documentation site from local Markdown files."""
from html import escape
from pathlib import Path
import shutil
import markdown

ROOT = Path(__file__).resolve().parents[1]
PAGES = [('index', 'Overview'), ('installation', 'Installation'), ('usage', 'Commands and skills'), ('marketplaces', 'Marketplaces'), ('behavior', 'How it works'),
         ('configuration', 'Configuration'), ('troubleshooting', 'Troubleshooting'), ('development', 'Development')]


def main():
    output = ROOT / 'site'
    output.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'docs/assets', output / 'assets', dirs_exist_ok=True)
    for slug, label in PAGES:
        source = (ROOT / 'docs' / f'{slug}.md').read_text()
        content = markdown.markdown(source, extensions=['fenced_code', 'tables', 'toc'])
        nav = ''.join(f'<a href="{key}.html"' + (' aria-current="page"' if key == slug else '') + f'>{escape(title)}</a>' for key, title in PAGES)
        title = 'Vale for Claude Code and Codex' if slug == 'index' else f'{label} · Vale for Claude Code and Codex'
        page = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="Google documentation style checks for Claude Code and Codex, powered by Vale. Install for a project or your user.">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/style.css">
<link rel="canonical" href="https://vale.swacktech.com/{'' if slug == 'index' else slug + '.html'}"></head>
<body><a class="skip" href="#content">Skip to content</a>
<header><a class="brand" href="index.html"><span class="mark" aria-hidden="true">V.</span>Vale <span class="subtitle">for Claude Code and Codex</span></a><a class="source" href="https://github.com/swack-tools/vale-ai-plugin">Source on GitHub <span aria-hidden="true">↗</span></a></header>
<div class="layout"><aside><p class="eyebrow">DOCUMENTATION</p><nav aria-label="Documentation">{nav}</nav><div class="version">v0.2.0<br>Powered by Vale + Google rules</div></aside>
<main id="content"><p class="eyebrow">{'WRITE WITH CONFIDENCE' if slug == 'index' else 'VALE / ' + label.upper()}</p><article>{content}</article>
<footer><span>Swack Tools · MIT license</span><a href="https://github.com/swack-tools/vale-ai-plugin/blob/main/docs/{slug}.md">Edit this page</a></footer></main></div></body></html>'''
        (output / f'{slug}.html').write_text(page)
    (output / 'CNAME').write_text('vale.swacktech.com\n')
    (output / '.nojekyll').touch()
    (output / '404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Page not found</title><h1>Page not found</h1><a href="/">Return to Vale documentation</a></html>')
    print(f'Built {len(PAGES)} documentation pages in {output}')


if __name__ == '__main__':
    main()
