"""Source-only daily-market lineage gate for the RRE experiment."""
from __future__ import annotations

if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError:
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)

import argparse, csv, hashlib, json, math
from pathlib import Path
import pandas as pd

EXPECTED_COLUMNS=("timestamp","open","high","low","close","volume")
SPECS={
 "SPY":{"rows":2010,"first":"2018-01-02","last":"2025-12-30"},
 "QQQ":{"rows":2010,"first":"2018-01-02","last":"2025-12-30"},
 "GLD":{"rows":2010,"first":"2018-01-02","last":"2025-12-30"},
 "BIL":{"rows":1714,"first":"2019-03-08","last":"2025-12-30"},
}
class GateError(RuntimeError): pass

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""): h.update(c)
    return h.hexdigest()

def load(path):
    path=Path(path)
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f)
        if tuple(r.fieldnames or ())!=EXPECTED_COLUMNS: raise GateError(f"SCHEMA:{path}")
        rows=list(r)
    df=pd.DataFrame(rows)
    ts=pd.to_datetime(df["timestamp"],utc=True,errors="raise").dt.tz_convert(None)
    if ts.duplicated().any(): raise GateError(f"DUPLICATE:{path}")
    if not ts.is_monotonic_increasing: raise GateError(f"ORDER:{path}")
    for c in ("open","high","low","close","volume"):
        df[c]=pd.to_numeric(df[c],errors="raise")
        if not df[c].map(math.isfinite).all(): raise GateError(f"NONFINITE_{c}:{path}")
    if (df[["open","high","low","close"]]<=0).any().any(): raise GateError(f"PRICE:{path}")
    if (df["volume"]<0).any(): raise GateError(f"VOLUME:{path}")
    if (df["low"]>df[["open","close"]].min(axis=1)).any(): raise GateError(f"LOW:{path}")
    if (df["high"]<df[["open","close"]].max(axis=1)).any(): raise GateError(f"HIGH:{path}")
    df.index=pd.DatetimeIndex(ts,name="timestamp")
    return df.drop(columns=["timestamp"])

def extract(asset,path,outdir):
    spec=SPECS[asset]; df=load(path)
    first,last=pd.Timestamp(spec["first"]),pd.Timestamp(spec["last"])
    cut=df.loc[first:last].copy()
    if len(cut)!=spec["rows"]: raise GateError(f"{asset}_ROW_COUNT:{len(cut)}")
    if cut.index[0]!=first or cut.index[-1]!=last: raise GateError(f"{asset}_BOUNDARY")
    op=Path(outdir)/f"{asset}_1D_RRE_AMENDED.csv"; op.parent.mkdir(parents=True,exist_ok=True)
    x=cut.reset_index(); x["timestamp"]=x["timestamp"].dt.strftime("%Y-%m-%d")
    x.to_csv(op,index=False,lineterminator="\n")
    return cut,{"asset":asset,"source_path":str(path),"source_sha256":sha(path),"source_bytes":Path(path).stat().st_size,
                "source_rows":len(df),"source_first":df.index[0].date().isoformat(),"source_last":df.index[-1].date().isoformat(),
                "extract_path":str(op),"extract_sha256":sha(op),"extract_rows":len(cut),"extract_first":cut.index[0].date().isoformat(),
                "extract_last":cut.index[-1].date().isoformat()}

def main():
    p=argparse.ArgumentParser()
    for a in ("spy","qqq","bil","gld"): p.add_argument(f"--{a}-data",required=True)
    p.add_argument("--out-dir",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    frames={}; records={}
    for asset in ("SPY","QQQ","BIL","GLD"):
        frames[asset],records[asset]=extract(asset,getattr(a,f"{asset.lower()}_data"),a.out_dir)
    if not frames["SPY"].index.equals(frames["QQQ"].index) or not frames["SPY"].index.equals(frames["GLD"].index):
        raise GateError("EQUITY_CALENDAR_MISMATCH")
    result={"status":"PASS","gate_type":"rre_daily_source_lineage_source_only","assets":records,
            "prices_compared_to_historical_missing_sources":False,"signals_generated":False,"rre_scores_generated":False,
            "trades_generated":False,"returns_generated":False,"nav_generated":False,"performance_metrics_calculated":False,
            "runtime_modified":False,"strategy_modified":False,"allocation_modified":False}
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__": main()
