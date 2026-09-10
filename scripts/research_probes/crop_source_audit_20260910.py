"""Audit extracted cells without joining fundamentals to future returns."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

p = Path('artifacts/ml_crop_feasibility_20260910')
rows = json.loads((p / 'parsed_cells.json').read_text())
manifest = json.loads((p / 'xml_manifest.json').read_text())
groups = collections.defaultdict(dict)
files = collections.defaultdict(list)
issues = []
for row in rows:
    groups[(row['source_file'], row['asset'], row['crop_year'], row['forecast_month'])][row['field']] = row['value']
    files[row['source_file']].append(row)
    expected = dt.datetime.strptime(row['source_file'][:10], '%Y-%m-%d').strftime('%B %Y')
    if row['report_month'] != expected:
        issues.append({'kind': 'report_month_mismatch', 'file': row['source_file'], 'actual': row['report_month']})
checks = 0
missing = 0
for key, values in groups.items():
    if set(values) != {'supply, total', 'use, total', 'ending stocks'}:
        issues.append({'kind': 'missing_field', 'key': key})
        continue
    if any(v is None for v in values.values()):
        missing += 1
        continue
    checks += 1
    residual = values['supply, total'] - values['use, total'] - values['ending stocks']
    if abs(residual) > 2 or values['use, total'] <= 0 or values['ending stocks'] < 0:
        issues.append({'kind': 'balance_or_denominator', 'key': key, 'residual': residual})
versions = collections.defaultdict(list)
for name, cells in files.items():
    canonical = sorted((r['asset'], r['crop_year'], r['forecast_month'], r['field'], r['value']) for r in cells)
    digest = hashlib.sha256(json.dumps(canonical).encode()).hexdigest()
    versions[name[:7]].append({'file': name, 'selected_cells_sha256': digest, 'cells': len(cells)})
duplicates = {month: v for month, v in versions.items() if len(v) > 1}
report = {
    'status': 'SOURCE_EXTRACTION_AUDIT_NOT_PREDICTIVE_RESEARCH',
    'indexed_xml_entries': len(manifest),
    'downloaded': sum('error' not in r for r in manifest),
    'download_errors': [r for r in manifest if 'error' in r],
    'parsed_files': len(files), 'parsed_cells': len(rows),
    'parse_issues': json.loads((p / 'parse_issues.json').read_text()),
    'first_parsed_file': min(files) if files else None,
    'last_parsed_file': max(files) if files else None,
    'balance_checks': checks, 'balance_tolerance_million_bushels': 2,
    'groups_with_missing_values': missing,
    'issues': issues, 'multiple_versions_by_month': duplicates,
    'limitations': [
        'Selected U.S. table fields only; unit-marker validation is not a complete table schema audit.',
        'Matching selected cells does not prove entire reports or their publication times are identical.',
        'Archive-date metadata is not independently verified intraday availability.',
        'No historical source is overwritten; announcements and supplements remain in the index.',
        'No predictor/return association or fitted model evaluated.'
    ]
}
(p / 'source_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in {'multiple_versions_by_month', 'download_errors', 'limitations'}}, indent=2))
