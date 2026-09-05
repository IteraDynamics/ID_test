"""Inventory explicit stdlib digest and JSON serialization sites without importing code."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
import warnings


def inventory(root: Path) -> str:
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    rows = []
    for folder in ('scripts', 'research', 'runtime'):
        for path in sorted((root / folder).rglob('*.py')):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse(path.read_text(encoding='utf-8'))
            names = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        names[alias.asname or alias.name] = alias.name
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        names[alias.asname or alias.name] = f'{node.module}.{alias.name}'
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = ast.unparse(node.func)
                first, *rest = name.split('.')
                name = '.'.join([names.get(first, first), *rest])
                if name not in ('hashlib.sha256', 'json.dumps', 'json.dump'):
                    continue
                options = ', '.join(f'{k.arg or "**"}={ast.unparse(k.value)}' for k in node.keywords)
                positional = ', '.join(ast.unparse(a) for a in node.args)
                rows.append((str(path.relative_to(root)), node.lineno, name, positional, options))
    lines = ['# Frozen digest and JSON inventory', '', f'Baseline: `{sha}`.', '',
             f'{len(rows)} explicit constructor/serialization call sites. This is a static inventory,',
             'not a count of independent formats or an assertion of runtime reachability.',
             'Aliases of stdlib imports are resolved; dynamic calls and external schedules are not.',
             'Caller-owned CSV options, file encodings, newline modes and publication order remain unchanged.', '',
             '| File | Line | Operation | Input expression | Explicit options |',
             '| --- | ---: | --- | --- | --- |']
    for row in sorted(rows):
        lines.append('| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', ' ') for v in row) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(inventory(args.root), encoding='utf-8')
