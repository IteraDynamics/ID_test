"""Boundary checks for the dated extraction probe, not a general WASDE parser."""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/research_probes/crop_xml_parse_20260910.py'

def run_probe(tmp_path, *, duplicate=False, missing=False, namespace=None):
    folder = tmp_path / 'artifacts/ml_crop_feasibility_20260910/xml'
    folder.mkdir(parents=True)
    root = ET.Element('Report')
    for title, matrix in [
        ('U.S. Wheat Supply and Use', 'matrix1'),
        ('U.S. Feed Grain and Corn Supply and Use', 'matrix2'),
        ('U.S. Soybeans and Products Supply and Use (Domestic Measure)', 'matrix1'),
    ]:
        report = ET.SubElement(root, 'Report', sub_report_title=title, Report_Month='May 2012')
        table = ET.SubElement(report, matrix)
        ET.SubElement(table, 'Unit', description='Million Bushels')
        for field in ['Use, Total', 'Ending Stocks', 'Supply, Total']:
            node = ET.SubElement(table, 'Attribute', attribute1=field)
            for year in ['2011/12 Proj.', '2012/13 Proj.']:
                y = ET.SubElement(node, 'Year', market_year1=year)
                mo = ET.SubElement(y, 'Month', forecast_month1='May')
                ET.SubElement(mo, 'Cell', cell_value1='NA' if missing else '100')
                if duplicate:
                    mo = ET.SubElement(y, 'Month', forecast_month1='May')
                    ET.SubElement(mo, 'Cell', cell_value1='100')
    if namespace:
        for node in root.iter():
            node.tag = '{' + namespace + '}' + node.tag
    ET.ElementTree(root).write(folder / '2012-05-10_fixture.xml', encoding='utf-8')
    subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, check=True, capture_output=True)
    out = folder.parent
    return json.loads((out / 'parsed_cells.json').read_text()), json.loads((out / 'parse_issues.json').read_text())

def test_crop_years_remain_distinct(tmp_path):
    cells, issues = run_probe(tmp_path)
    assert not issues
    assert len(cells) == 18
    assert {x['crop_year'] for x in cells} == {'2011/12 Proj.', '2012/13 Proj.'}

def test_missing_projection_never_becomes_zero(tmp_path):
    cells, issues = run_probe(tmp_path, missing=True)
    assert not issues and cells
    assert all(x['value'] is None for x in cells)

def test_duplicate_semantic_cells_reject_release(tmp_path):
    cells, issues = run_probe(tmp_path, duplicate=True)
    assert cells == []
    assert len(issues) == 1 and 'duplicate' in issues[0]['error']


def test_known_namespace_preserves_cells(tmp_path):
    cells, issues = run_probe(tmp_path, namespace="wasde")
    assert not issues and len(cells) == 18

def test_unknown_namespace_rejects_release(tmp_path):
    cells, issues = run_probe(tmp_path, namespace="unexpected")
    assert not cells and "Unrecognized" in issues[0]["error"]
