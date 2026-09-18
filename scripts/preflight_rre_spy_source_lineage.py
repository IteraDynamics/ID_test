"""Source-only gate for the RRE experiment's amended SPY source.

No strategy, signal, RRE feature, return, position, trade, NAV, or performance
calculation is performed here.
"""
from __future__ import annotations

if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError:
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

EXPECTED_COLUMNS=("timestamp","open","high","low","close","volume")
FROZEN_SPY_SHA="85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86"
FROZEN_QQQ_SHA="34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b"
FROZEN_ROWS=2010
FROZEN_FIRST=pd.Timestamp("2018-01-02")
FROZEN_LAST=pd.Timestamp("2025-12-30")


class SourceGateError(RuntimeError):
    pass


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def load_validate(path:Path)->pd.DataFrame:
    if not path.exists(): raise SourceGateError(f"SOURCE_NOT_FOUND:{path}")
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or ())!=EXPECTED_COLUMNS: raise SourceGateError(f"SCHEMA_MISMATCH:{path}")
        rows=list(reader)
    if not rows: raise SourceGateError(f"EMPTY_SOURCE:{path}")
    df=pd.DataFrame(rows)
    ts=pd.to_datetime(df["timestamp"],utc=True,errors="raise").dt.tz_convert(None)
    if ts.duplicated().any(): raise SourceGateError(f"DUPLICATE_TIMESTAMP:{path}")
    if not ts.is_monotonic_increasing: raise SourceGateError(f"NONINCREASING_TIMESTAMP:{path}")
    for c in ("open","high","low","close","volume"):
        df[c]=pd.to_numeric(df[c],errors="raise")
        if not df[c].map(math.isfinite).all(): raise SourceGateError(f"NONFINITE_{c.upper()}:{path}")
    if (df[["open","high","low","close"]]<=0).any().any(): raise SourceGateError(f"NONPOSITIVE_PRICE:{path}")
    if (df["volume"]<0).any(): raise SourceGateError(f"NEGATIVE_VOLUME:{path}")
    tol=1e-12
    lo=df[["open","close"]].min(axis=1)
    hi=df[["open","close"]].max(axis=1)
    if (df["low"]>lo+tol*np.maximum(1.0,lo.abs())).any(): raise SourceGateError(f"INVALID_LOW:{path}")
    if (df["high"]<hi-tol*np.maximum(1.0,hi.abs())).any(): raise SourceGateError(f"INVALID_HIGH:{path}")
    df.index=pd.DatetimeIndex(ts,name="timestamp")
    return df.drop(columns=["timestamp"])


def build(spy_path:Path,qqq_path:Path,normalized_path:Path)->dict:
    qhash=sha(qqq_path)
    if qhash!=FROZEN_QQQ_SHA: raise SourceGateError(f"QQQ_HASH_MISMATCH:{qhash}")
    spy=load_validate(spy_path);qqq=load_validate(qqq_path)
    calendar=qqq.index[(qqq.index>=FROZEN_FIRST)&(qqq.index<=FROZEN_LAST)]
    if len(calendar)!=FROZEN_ROWS: raise SourceGateError(f"FROZEN_CALENDAR_ROW_COUNT:{len(calendar)}")
    if calendar[0]!=FROZEN_FIRST or calendar[-1]!=FROZEN_LAST: raise SourceGateError("FROZEN_CALENDAR_BOUNDARY")
    missing=calendar.difference(spy.index)
    if len(missing): raise SourceGateError("MISSING_FROZEN_SPY_SESSIONS:"+",".join(x.isoformat() for x in missing[:20]))
    matched=spy.loc[calendar].copy()
    if len(matched)!=FROZEN_ROWS: raise SourceGateError(f"MATCHED_ROW_COUNT:{len(matched)}")
    normalized_path.parent.mkdir(parents=True,exist_ok=True)
    out=matched.reset_index()
    out["timestamp"]=out["timestamp"].dt.strftime("%Y-%m-%d")
    out.to_csv(normalized_path,index=False,lineterminator="\n")
    extras=spy.index.difference(calendar)
    return {
        "status":"PASS",
        "gate_type":"rre_spy_source_lineage_source_only",
        "historical_spy_sha256":FROZEN_SPY_SHA,
        "candidate_spy_path":str(spy_path),
        "candidate_spy_sha256":sha(spy_path),
        "candidate_spy_bytes":spy_path.stat().st_size,
        "candidate_full_row_count":len(spy),
        "candidate_first_session":spy.index[0].date().isoformat(),
        "candidate_last_session":spy.index[-1].date().isoformat(),
        "frozen_calendar_source":"QQQ_1D.csv",
        "frozen_qqq_sha256":qhash,
        "matched_row_count":len(matched),
        "matched_first_session":matched.index[0].date().isoformat(),
        "matched_last_session":matched.index[-1].date().isoformat(),
        "extra_session_count":len(extras),
        "normalized_spy_path":str(normalized_path),
        "normalized_spy_sha256":sha(normalized_path),
        "prices_compared_to_missing_historical_spy":False,
        "prices_parsed":True,
        "signals_generated":False,
        "rre_scores_generated":False,
        "positions_generated":False,
        "trades_generated":False,
        "returns_generated":False,
        "nav_generated":False,
        "performance_metrics_calculated":False,
        "runtime_modified":False,
        "strategy_modified":False,
        "allocation_modified":False,
    }


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--spy-data",required=True);p.add_argument("--qqq-data",required=True)
    p.add_argument("--normalized-spy",required=True);p.add_argument("--output",required=True)
    return p.parse_args()


def main():
    a=parse_args();result=build(Path(a.spy_data),Path(a.qqq_data),Path(a.normalized_spy))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__": main()
