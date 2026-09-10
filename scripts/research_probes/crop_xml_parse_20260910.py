"""Dated extraction probe; run from repository root. Not a production feature builder."""
import xml.etree.ElementTree as E,json,re
from pathlib import Path
p=Path('artifacts/ml_crop_feasibility_20260910');out=[];issues=[]
spec=[('WEAT','U.S. Wheat Supply and Use','matrix1'),('CORN','U.S. Feed Grain and Corn Supply and Use','matrix2'),('SOYB','U.S. Soybeans and Products Supply and Use (Domestic Measure)','matrix1')]
for f in sorted((p/'xml').glob('*.xml')):
 try:
  root=E.parse(f).getroot(); local=[]
  for element in root.iter():
   if element.tag.startswith('{wasde}'):element.tag=element.tag[len('{wasde}'):]
   elif element.tag.startswith('{'):raise ValueError('Unrecognized XML namespace')
  for asset,title,mat in spec:
   reports=[x for x in root.iter('Report') if x.get('sub_report_title','').startswith(title)]
   if len(reports)!=1:raise ValueError(f'{asset}: expected unique report, got {len(reports)}')
   report=reports[0];m=report.find(mat)
   if m is None:raise ValueError(f'{asset}: missing {mat}')
   if not any('million bushels' in v.lower() for x in m.iter() for v in x.attrib.values()):raise ValueError(f'{asset}: missing bushel unit marker')
   seen=set()
   for node in m.iter():
    labels=[v.strip().lower() for k,v in node.attrib.items() if k.startswith('attribute')]
    if not labels or labels[0] not in ['use, total','ending stocks','supply, total']:continue
    field=labels[0]
    for y in node.iter():
     year=next((v for k,v in y.attrib.items() if k.startswith('market_year')),None)
     if year is None:continue
     for mo in y.iter():
      month=next((v for k,v in mo.attrib.items() if k.startswith('forecast_month')),None)
      if month is None:continue
      vals=[v for cell in mo.iter() for k,v in cell.attrib.items() if k.startswith('cell_value')]
      if len(vals)!=1:raise ValueError(f'{asset}: ambiguous/missing numeric cell')
      val=None if vals[0].strip().upper() in {'NA','N/A','--',''} else float(vals[0].replace(',',''));key=(field,year.strip(),month.strip())
      if key in seen:raise ValueError(f'{asset}: duplicate semantic key {key}')
      seen.add(key);local.append(dict(source_file=f.name,asset=asset,report_month=report.get('Report_Month'),crop_year=year.strip(),forecast_month=month.strip(),field=field,value=val,unit='million_bushels'))
   if not any(x['asset']==asset and x['field']=='use, total' for x in local):raise ValueError(f'{asset}: no use rows')
  out.extend(local)
 except Exception as e:issues.append(dict(file=f.name,error=str(e)))
(p/'parsed_cells.json').write_text(json.dumps(out,indent=2));(p/'parse_issues.json').write_text(json.dumps(issues,indent=2));print('files',len(list((p/'xml').glob('*.xml'))),'cells',len(out),'failed',len(issues));print(issues[:5])
