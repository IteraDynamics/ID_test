"""Dated raw-source acquisition probe. Cached files retained; failed URLs recorded."""
import json,urllib.request,hashlib,concurrent.futures
from pathlib import Path
p=Path('artifacts/ml_crop_feasibility_20260910');(p/'xml').mkdir(exist_ok=True);rs=json.loads((p/'all_formats_index.json').read_text())
def get(r):
 fs=[f for f in r['files'] if f['format']=='xml']
 if not fs:return None
 u=fs[0]['url']; fn=r['release_date']+'_'+hashlib.sha256(u.encode()).hexdigest()[:10]+'.xml';f=p/'xml'/fn
 try:
  if not f.exists():f.write_bytes(urllib.request.urlopen(u,timeout=20).read())
  b=f.read_bytes();return dict(release_date=r['release_date'],url=u,file=fn,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
 except Exception as e:return dict(release_date=r['release_date'],url=u,error=str(e))
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 for r in ex.map(get,rs):
  if r:rows.append(r)
(p/'xml_manifest.json').write_text(json.dumps(rows,indent=2));print('downloaded',sum('error' not in r for r in rows),'errors',[r for r in rows if 'error'in r])
