# Historical cleanup assessment — 2026-09-06

## Disposition

Retain historical entrypoints at their existing paths. This round adds a broader
reference snapshot and records the evidence needed to retire candidates. It does
not establish that any historical script is safe to delete or relocate.

The source snapshot is packaging head `15a0938215be59143753e572bac26818155cc887`.
The earlier `SCRIPT_INVENTORY.md` remains a historical extraction-stage snapshot;
use [the dated inventory](HISTORICAL_SCRIPT_INVENTORY_20260906.md) for this round.
Its old generator scans only selected folders and `.py`, `.sh`, `.md` files, misses
CI workflows/configuration, and counts bare stem substrings. This snapshot scans
tracked files at a fixed revision, matches filenames or qualified module names,
and separates engineering mentions from other references. Neither method proves
absence of external callers or constitutes a complete call graph.

## Evidence and decisions

| Group | Repository evidence inspected | Decision |
| --- | --- | --- |
| Funding collector and cron wrapper | `scripts/log_cde_live_funding_rate_cron.sh`; `docs/ITERA_CAMPAIGN_BOARD.md`, 2026-08-24 scheduling correction | Retain both paths. Wrapper documents `/root/ID_test` and hourly minute 5; historical operator record says collection actually started August 24. |
| Basis collector and cron wrapper | `scripts/log_cde_basis_ladder_cron.sh`; campaign board, 2026-08-25 update; Campaign 53 planning charter | Retain both paths. Wrapper documents hourly minute 10; campaign record ties collection to forward evidence. |
| Core v1 paper runner and dashboard | `ops/decisions.md`, 2026-08-28 deployment entry; `docs/engineering/CORE_V1_DASHBOARD_REDESIGN.md` | Retain entrypoints and helpers. Record names `/opt/itera/app` and paper/dashboard systemd services. This is historical evidence, not a fresh deployed-revision check. |
| CI commands and verification scripts | `.github/workflows/ci.yml`; CI reference locations in the dated inventory | Retain. Their absence from the old inventory's scan could hide actual callers. |
| Research runners and legacy aliases | Source/test/documentation references in the dated inventory; packaging alias contracts | Retain original commands and module identities for reproducibility. A superseding runner does not prove the historical command is disposable. |
| Files with no non-engineering literal references | Explicit candidate list in the dated inventory | Retain pending external caller and provenance review. Inventory or migration-manifest references alone do not establish use. |

No checked-in systemd unit definitions were found in the snapshot. The two checked-in
cron shells are instructions/wrappers, not an export of the installed crontab.
No deployed host, scheduler, service configuration, live state, private artifact
store or operator shell history was accessed. A scratch environment's crontab
would not establish anything about the deployed hosts.

## Evidence required before deletion or relocation

For each proposed candidate, attach dated, host-identified exports of relevant
user/root crontabs, systemd units and timers (including drop-ins), and any other
process manager or external scheduled workflow. Inspect the command, working
directory, interpreter and wrapper chain. Include operator-maintained runbooks
and confirmation of ad hoc recovery/replay commands. Redact credentials; only
caller configuration is needed.

Then check the candidate against historical experiment/campaign provenance and
recorded artifact reproduction commands. Record a per-file retirement decision,
its evidence locations, replacement command if applicable, and compatibility
requirements. Only a supported retirement should become a separate small code
commit with import/CLI and relevant parity verification. Zero literal references,
an old modification date, or a closed campaign is insufficient by itself.

These exports are the remaining input for a deletion stage; they were not
available in this checkout. Deployment-gate implementation remains separate,
and neither this inventory nor a green CI run authorizes merge or deployment.

## Verification and scope

The snapshot is regenerated from committed Git objects, so untracked/private
files and later edits cannot silently alter its inputs. Re-running the embedded
script must reproduce the dated Markdown file byte-for-byte. Counts denote
matching files, not occurrence counts; comments and examples count. Data/artifact
contents are deliberately excluded. Suffix coverage is explicit below; extensionless
launchers and dynamically constructed names are not covered. Engineering mentions
are reported separately, not discarded from the evidence.

This round changes documentation only: no source, packaging, lockfile, workflow,
ops record, research definition or artifact changes; no deletions or relocations.
Verification is snapshot reproducibility, inventory completeness against the
pinned Git tree, and an exact changed-path check. A new full runtime suite is not
claimed for this documentation-only assessment.

## Reproduce the snapshot

From the repository root, run this standard-library Python script. It reads only
committed objects at the pinned SHA and writes only the dated inventory Markdown.
It does not run any inventoried entrypoint or fetch market inputs.

```python
import collections
import pathlib
import re
import subprocess

BASE = '15a0938215be59143753e572bac26818155cc887'
OUTPUT = pathlib.Path('docs/engineering/HISTORICAL_SCRIPT_INVENTORY_20260906.md')
def git(*args):
    return subprocess.check_output(['git', *args])
paths = git('ls-tree', '-r', '--name-only', BASE).decode().splitlines()
scripts = [p for p in paths if p.startswith('scripts/') and p.count('/') == 1 and pathlib.Path(p).suffix in {'.py', '.sh'}]
suffixes = {'.py', '.sh', '.md', '.yml', '.yaml', '.toml', '.cfg', '.ini', '.json', '.service', '.timer'}
texts = {}
for p in paths:
    if pathlib.Path(p).suffix not in suffixes or p.startswith(('artifacts/', 'data/')):
        continue
    try:
        texts[p] = git('show', f'{BASE}:{p}').decode('utf-8')
    except UnicodeDecodeError:
        pass

def category(path):
    if path.startswith('.github/workflows/'): return 'CI'
    if path.startswith('tests/'): return 'Tests'
    if path.startswith('docs/engineering/'): return 'Engineering'
    if path.startswith('ops/') or path in {'README.md', 'docs/ITERA_CAMPAIGN_BOARD.md'}: return 'Operator'
    if path.startswith('docs/'): return 'Documentation'
    return 'Code/config'

categories = ['Code/config', 'Tests', 'CI', 'Operator', 'Documentation', 'Engineering']
rows = []
for script in sorted(scripts):
    stem = pathlib.Path(script).stem
    # Exact filename or qualified module; do not match bare stem substrings.
    pattern = re.compile(r'(?<![\w])(?:' + re.escape(pathlib.Path(script).name) + r'|scripts\.' + re.escape(stem) + r')(?![\w.])')
    hits = {k: [] for k in categories}
    for path, value in texts.items():
        if path != script and pattern.search(value):
            hits[category(path)].append(path)
    rows.append((script, hits))

lines = ['# Historical script reference snapshot — 2026-09-06', '', f'Source revision: `{BASE}`. Scanned {len(texts)} tracked UTF-8 text files and {len(scripts)} top-level Python/shell files in `scripts/`.', '',
'Counts are distinct matching files, including comments and examples; they are not runtime usage counts. Engineering mentions are separated because inventories and migration manifests do not establish a caller. No-reference candidates require external caller checks before removal. Package support files are included, so this is not an executable-command count.', '',
'Artifacts and data are excluded to avoid treating evidence contents as callers. Supported source/configuration suffixes and the exact matching rule are recorded in the companion cleanup report. Bare names, dynamic imports and external commands can be missed.', '',
'| Script | Code/config | Tests | CI | Operator | Documentation | Engineering |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
for p, hits in rows:
    lines.append('| `' + p + '` | ' + ' | '.join(str(len(hits[k])) for k in categories) + ' |')
lines += ['', '## CI and operator reference locations', '', 'These are repository evidence, not confirmation of what is currently deployed.', '']
for p, hits in rows:
    evidence = hits['CI'] + hits['Operator']
    if evidence:
        lines.append('- `' + p + '`: ' + ', '.join('`' + x + '`' for x in sorted(evidence)))
zero = [p for p, hits in rows if not any(hits[k] for k in categories if k != 'Engineering')]
lines += ['', '## No non-engineering literal references', '', f'{len(zero)} files have no matches outside engineering documentation under this scan. Retain pending caller and provenance review; this is not a deletion list.', '']
lines += ['- `' + p + '`' for p in zero]
OUTPUT.write_text('\n'.join(lines) + '\n')
print({'scripts': len(scripts), 'scanned_files': len(texts), 'no_nonengineering_references': len(zero), 'CI_referenced_scripts': sum(bool(h['CI']) for _, h in rows), 'operator_referenced_scripts': sum(bool(h['Operator']) for _, h in rows)})
```
