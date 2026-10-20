"""Candle charts of the days v3 (NQ 2m) lost most in the earlier years, with its trades: writes ../v3_kline.html.

  cd indicators/backtest
  python3 -I rbs/v3_kline.py

v3 frozen, one at a time, 3R. Days: the 3 worst days of each out-of-sample year and the 3 best days of the v3 year.
Each chart: 2-minute candles of that New York day, 5 s EMA1130 (fast, magenta) and 15 s EMA1130 (slow, blue), entries,
exits, stop and target lines. Times are Taipei time like Remi's charts.
"""
import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def trades(C, trend, mix, R=3.0):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                risk = abs(ve - vs)
                out.append(dict(i=vb, x=j, side=pos, kind=kind, entry=ve, stop=vs, tgt=vt, exit_px=px, date=d0,
                                exit='停損' if hs else '目標' if ht else '時間', net=(px - ve) * pos / risk - oc.COST / risk))
                pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, kind, d0 = k, px, st, px + R * (px - st), j, 'MIX', C.date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append(dict(i=j, x=j, side=pos, kind=kind, entry=ve, stop=vs, tgt=vt, exit_px=vs, date=d0, exit='停損',
                                net=-1.0 - oc.COST / abs(ve - vs))); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, kind, d0 = k, c[j], st, c[j] + R * (c[j] - st), j, '趨勢', C.date[j]
    return pd.DataFrame(out)


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df
    T = oc.trend_set(df, M.H, 2, 20, df.thr.values, 3.0, 0, 180)
    t = trades(C, T, oc.mix_list(C))
    lm = pd.DatetimeIndex(df.last_min)
    fast = M.tdm['emaF'].reindex(lm).values; slow = M.tdm['emaS'].reindex(lm).values
    tw = (df.datetime + pd.Timedelta(minutes=2)).dt.tz_convert('Asia/Taipei')
    ts = ((tw.dt.tz_localize(None) - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s')).values     # Taipei clock as fake UTC
    nyday = df.datetime.dt.tz_convert(ss.NY).dt.date.astype(str).values
    pick = []
    for nm, a, b in oc.YEARS:
        y = t[(t.date >= a) & (t.date <= b)]
        day = y.groupby('date').net.sum()
        sel = day.nsmallest(3) if not nm.startswith('IS') else day.nlargest(3)
        for d, v in sel.items():
            pick.append((nm, d, v))
    days = []
    for nm, d, v in pick:
        idx = np.where(nyday == d)[0]
        bars = [[int(ts[j]), float(df.open.values[j]), float(df.high.values[j]), float(df.low.values[j]), float(df.close.values[j]),
                 None if np.isnan(fast[j]) else round(float(fast[j]), 2), None if np.isnan(slow[j]) else round(float(slow[j]), 2)] for j in idx]
        tt = t[t.date == d]
        trs = [dict(t0=int(ts[r.i]), t1=int(ts[r.x]), side=int(r.side), kind=r.kind, entry=float(r.entry), stop=float(r.stop),
                    tgt=float(r.tgt), exit_px=float(r.exit_px), exit=r.exit, net=round(float(r.net), 2)) for r in tt.itertuples()]
        tj = df.tj_dir.values[idx]
        days.append(dict(label=f'{nm[:2]}｜{d}｜{v:+.1f}R（{len(trs)} 筆）', year=nm, date=d, net=round(float(v), 1), bars=bars, trades=trs,
                         trend=round(100 * float((tj != 0).mean()), 0), move=round(float(df.close.values[idx[-1]] - df.open.values[idx[0]]), 1)))
    page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v3_kline_template.html'), encoding='utf-8').read()
    out = os.path.join(HERE, 'v3_kline.html')
    open(out, 'w', encoding='utf-8').write(page.replace('/*DATA*/null', json.dumps(days, ensure_ascii=False)))
    print('寫好', out)
    for x in days:
        print(f'   {x["label"]}  當天 {x["move"]:+.0f} 點、Trend Judge 有趨勢 {x["trend"]:.0f}%  出場 ' + ' '.join(f'{r["kind"]}{"買" if r["side"] == 1 else "賣"}{r["exit"]}' for r in x['trades']))


if __name__ == '__main__':
    main()
