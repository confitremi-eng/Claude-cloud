"""Remi Superb v2, bar by bar as the indicator runs it (NQ 2 minutes, the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/v2_port.py

A Python copy of remi_superb_v2.pine's state machine on the research data: trend signals (the filtered alerts with
the indicator's trend-minute count, 0-180 minutes by default), MIX-box breakouts (mix_breakout.py boxes), and the one-at-a-time
virtual position (stop first, target, 60 bars, the 17:00 ET halt bar, data holes). Trade results use the same
prices the indicator records: stop, target, or the close on a time exit; 1 point cost per trade.
Prints the trades with the 0-180 (default) and 30-120 minute limits and without one, so they can be compared with the research numbers
(rbs/one_minute.py, trend_mix_matrix.py) and with the indicator's marks on TradingView.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp
import mix_range as mr
import mix_breakout as mb

TH, ST, TGT, HOLD, COST = 10.0, 35.0, 3.0, 60, 1.0


def run(age_only, tgt=TGT, lo=0, hi=180, mix_on=True):
    df = rbs.prepared('NQ', 2)
    h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
    n = len(c)
    d = df.tj_diff.values
    dirI = np.where(np.isnan(d), 0, np.where(d > ST, 2, np.where(d > TH, 1, np.where(d < -ST, -2, np.where(d < -TH, -1, 0)))))
    tdir = np.sign(dirI)
    tb = np.zeros(n, int)
    for j in range(n):
        tb[j] = (tb[j - 1] + 1) if (j and tdir[j] != 0 and tdir[j] == tdir[j - 1]) else (1 if tdir[j] != 0 else 0)
    tmin = tb * 2
    # trend signals: the filtered alerts
    tw.TF = 2; tw.CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl')
    s = tw.build(); s = pd.concat([s, mp.features(s, df)], axis=1)
    f = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.tjSlow < 3) & (s.spread > TH)]
    trend = {int(i): int(k) for i, k in zip(f.i.values, f.side.values)}
    # MIX breakouts: bar, side, entry, middle
    mr.TH = TH
    B = mr.load()
    mix = {}
    hb, lb, ob, hole, evt = B['h'], B['l'], B['o'], B['hole'], B['evt']
    for s0, fm, top, bot in mb.causal_boxes(B, 30, grace=2):
        H = top - bot
        if H <= 0: continue
        bu, bd, mid = top + 0.1 * H, bot - 0.1 * H, (top + bot) / 2
        for j in range(fm + 1, min(fm + mb.AGE, n - 1) + 1):
            if hole[j]: break
            up, dn = hb[j] >= bu, lb[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            k = 1 if up else -1
            mix[j] = (k, max(ob[j], bu) if k == 1 else min(ob[j], bd), mid)
            break
    et = (df.datetime + pd.Timedelta(minutes=2)).dt.tz_convert(ss.NY)
    halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    date = df.datetime.dt.tz_convert(ss.NY).dt.date.astype(str).values
    trad = df.tradable.values

    trades = []; pos = 0
    for j in range(n):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= HOLD or halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                trades.append(dict(kind=kind, side=pos, entry=ve, exit=px, risk=abs(ve - vs), date=d0, bars=j - vb)); pos = 0
        if not trad[j]: continue
        if mix_on and pos == 0 and j in mix and not halt[j]:
            k, px, mid = mix[j]
            pos, ve, vs, vt, vb, kind, d0 = k, px, mid, px + tgt * (px - mid), j, 'MIX', date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                trades.append(dict(kind=kind, side=pos, entry=ve, exit=vs, risk=abs(ve - vs), date=d0, bars=0)); pos = 0
        if pos == 0 and j in trend and not halt[j] and (not age_only or lo <= tmin[j] < hi):
            k = trend[j]
            stop = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, kind, d0 = k, c[j], stop, c[j] + tgt * (c[j] - stop), j, '趨勢', date[j]
    t = pd.DataFrame(trades)
    run.last_signals = (f, tmin)
    t['R'] = (t.exit - t.entry) * t.side / t.risk
    t['net'] = t.R - COST / t.risk
    return t


def show(t, nm):
    a = t.date.values < ss.SPLIT; n = t.net.values
    eq = np.cumsum(n); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = pd.Series(n).groupby(t.date.str[:7].values).sum()
    print(f'  {nm:<28} {len(t):4d} 筆  勝率 {100 * (t.R > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R（前 {n[a].mean():+.3f} 後 {n[~a].mean():+.3f}）'
          f'  一年 {n.sum():+6.1f}R  回撤 {dd:5.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}'
          f'  | 趨勢 {(t.kind == "趨勢").sum()} 筆 {t.net[t.kind == "趨勢"].mean():+.3f}R  MIX {(t.kind == "MIX").sum()} 筆 {t.net[t.kind == "MIX"].mean():+.3f}R')


WINDOWS = [('0–30 分', 0, 30), ('30–120 分', 30, 120), ('120–180 分', 120, 180), ('0–180 分（v2 預設）', 0, 180),
           ('180 分以上（到趨勢結束）', 180, 10 ** 9), ('不限', 0, 10 ** 9)]


def windows():
    print('\n######## 趨勢時間範圍（趨勢已持續 = 指標的分鐘數，MIX 或轉向歸零）')
    run(False)
    f, tmin = run.last_signals
    f = f.assign(tm=tmin[f.i.values])
    a = f.date.values < ss.SPLIT
    print('\n  ## 趨勢訊號各自獨立（勝率 % / 每筆淨 R（前 / 後））')
    for nm, lo, hi in WINDOWS:
        m = ((f.tm >= lo) & (f.tm < hi)).values
        cells = []
        for R in (1.0, 2.0, 3.0):
            nn = f[f'r{R:g}'].values[m] - COST / f.risk.values[m]
            cells.append(f'{R:g}R {100 * (f[f"r{R:g}"].values[m] > 0).mean():4.1f}% {nn.mean():+.3f}（{nn[a[m]].mean():+.2f}/{nn[~a[m]].mean():+.2f}）')
        print(f'   {nm:<22} {m.sum():4d} 筆  ' + '  '.join(cells))
    for mix_on, title in ((False, '只做趨勢訊號'), (True, '趨勢訊號 + MIX 突破（v2 的做法）')):
        print(f'\n  ## {title}，一次一筆')
        for R in (2.0, 3.0):
            for nm, lo, hi in WINDOWS:
                show(run(True, R, lo, hi, mix_on), f'{R:g}R {nm}')


if __name__ == '__main__':
    if '--windows' in sys.argv:
        windows(); sys.exit()
    print('######## Remi Superb v2 逐根重算（一次一筆、3R、每筆扣 1 點）')
    show(run(True), '預設（趨勢只做 0–180 分）')
    show(run(True, lo=30, hi=120), '趨勢只做 30–120 分')
    show(run(False), '趨勢不限時間')
    show(run(True, 2.0), '預設，目標 2R')
