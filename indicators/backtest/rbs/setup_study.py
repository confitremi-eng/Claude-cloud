"""Remi's Buy/Sell trading setup study on the Databento year (NQ 1 / 2 / 3 / 5 minutes).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/setup_study.py

Builds every signal with its outcomes and context (cached in data/setup_signals.pkl), then prints
  1. each filter on its own (independent signals, 2R after a 1 point cost, both halves of the year)
  2. 1,152 setups (timeframe x trend filter x hours x cleaning x target), one position at a time,
     chosen on 2025-10-17 .. 2026-05-31 and checked on 2026-06-01 .. 2026-10-14
  3. the recommended rule (the filtered alerts in remis_buy_sell.pine) on 1 / 2 / 3 / 5 minutes
  4. stop placement on the recommended rule's 2-minute signals

Exits: entry at the signal close, stop at the extreme of the signal bar and the one before, fixed R target,
stop first when both are hit in one bar, 60-bar time exit, flat at the last bar before a hole longer than
30 minutes (daily halt, weekend). Trend Judge is estimated from 1-minute closes (rbs.py).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import itertools
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np
import pandas as pd
from rbs import prepared, load1, DATA_DIR
from remi_export import signals

NY = 'America/New_York'
SPLIT = '2026-06-01'
COST = 1.0
TARGETS = (1.0, 1.5, 2.0, 3.0)
HORIZON = 60
GAP_MIN = 30
FOMC = {'2025-10-29', '2025-12-10', '2026-01-28', '2026-03-18', '2026-04-29', '2026-06-17', '2026-07-29', '2026-09-16'}
CACHE = os.path.join(DATA_DIR, 'setup_signals.pkl')


def signals_ext(df, stage=20, ema_len=8):
    """remi_export.signals plus the lowest low (highest high) since the swing point, for the swing stop."""
    h, l, c = df.high.values, df.low.values, df.close.values
    ema = pd.Series(c).ewm(span=ema_len, adjust=False).mean().values
    lo = pd.Series(l).rolling(stage).min().shift().values
    hi = pd.Series(h).rolling(stage).max().shift().values
    n = len(c); B = np.zeros(n, int); S = np.zeros(n, int)
    swl = np.full(n, np.nan); swh = np.full(n, np.nan)
    armB = armS = False; refH = refL = lowS = highS = np.nan
    for i in range(stage, n):
        newLow, newHigh = l[i] < lo[i], h[i] > hi[i]
        if armB: lowS = min(lowS, l[i])
        if armS: highS = max(highS, h[i])
        trigB = armB and c[i] > refH
        trigS = armS and c[i] < refL
        B[i] = trigB and c[i] > ema[i]; S[i] = trigS and c[i] < ema[i]
        if trigB: swl[i] = lowS
        if trigS: swh[i] = highS
        if trigB: armB = False
        elif newLow: armB, refH, lowS = True, h[i], l[i]
        if trigS: armS = False
        elif newHigh: armS, refL, highS = True, l[i], h[i]
    return B, S, swl, swh


def bar_context(df, tf):
    h, l, c = df.high.values, df.low.values, df.close.values
    n = len(c)
    t0 = df.datetime
    gap_after = ((t0.shift(-1) - t0) > pd.Timedelta(minutes=tf + GAP_MIN)).values
    gap_after[-1] = True
    nxt = np.empty(n, int); last = n - 1
    for i in range(n - 1, -1, -1):
        if gap_after[i]: last = i
        nxt[i] = last
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[np.nan, c[:-1]]), np.abs(l - np.r_[np.nan, c[:-1]])))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    return nxt, atr


def outcome(h, l, c, i, k, stop, end):
    """R and exit bar for each target."""
    risk = (c[i] - stop) * k
    out = []
    for R in TARGETS:
        tgt = c[i] + k * R * risk; r = None; ex = end
        for j in range(i + 1, end + 1):
            if (l[j] <= stop) if k == 1 else (h[j] >= stop): r = -1.0; ex = j; break
            if (h[j] >= tgt) if k == 1 else (l[j] <= tgt): r = R; ex = j; break
        if r is None: r = (c[end] - c[i]) * k / risk
        out += [r, ex]
    return out


def hourly():
    one = load1('NQ')
    hc = one.close.resample('60min').last().dropna()
    he = hc.ewm(span=20, adjust=False).mean()
    # 1h close above / below EMA20 (the same as EMA20 rising / falling), usable once the hour is complete
    return pd.DataFrame({'t': hc.index + pd.Timedelta(minutes=60), 'h1': np.sign(hc - he).values}).dropna()


def add_context(s, df, tf, H):
    start = df.datetime.iloc[s.i].reset_index(drop=True)
    entry = start + pd.Timedelta(minutes=tf)                     # signal bar close = entry
    s['dir'] = df.tj_dir.values[s.i]
    s['h1'] = pd.merge_asof(pd.DataFrame({'t': entry}), H, on='t', direction='backward').h1.values
    es, ee = start.dt.tz_convert(NY), entry.dt.tz_convert(NY)
    ms, me = (es.dt.hour * 60 + es.dt.minute).values, (ee.dt.hour * 60 + ee.dt.minute).values
    s['rth'] = (ms >= 570) & (ms < 960)
    s['et_min'] = me
    s['date'] = es.dt.date.astype(str).values
    s['month'] = es.dt.strftime('%Y-%m').values
    fomc = np.isin(ee.dt.date.astype(str).values, list(FOMC)); wd = ee.dt.weekday.values
    s['ev_data'] = ((wd < 5) & (((me >= 508) & (me < 540)) | ((me >= 598) & (me < 615)))) | (fomc & (me >= 838) & (me < 900))
    s['ev_open'] = (me >= 570) & (me < 600)
    s['ev_close'] = (me >= 945) & (me < 975)
    s['ev_globex'] = ((me >= 1005) & (me < 1020)) | ((me >= 1080) & (me < 1110))
    s['asia'] = (me >= 1200) | (me < 180)
    return s


def build():
    H = hourly()
    out, days = [], {}
    for tf in (1, 2, 3, 5):
        df = prepared('NQ', tf)
        B, S = signals(df)
        h, l, c = df.high.values, df.low.values, df.close.values
        nxt, atr = bar_context(df, tf)
        rows = []
        for i in np.where((B == 1) | (S == 1))[0]:
            if i < 15 or not df.tradable.values[i]: continue
            end = min(i + HORIZON, nxt[i])
            if end <= i: continue
            k = 1 if B[i] else -1
            stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
            risk = (c[i] - stop) * k
            if not risk > 0: continue
            rows.append([tf, i, k, risk, (h[i] - l[i]) / atr[i - 1], risk / atr[i - 1]] + outcome(h, l, c, i, k, stop, end))
        cols = ['tf', 'i', 'side', 'risk', 'bar_atr', 'risk_atr']
        for R in TARGETS: cols += [f'r{R:g}', f'x{R:g}']
        out.append(add_context(pd.DataFrame(rows, columns=cols), df, tf, H))
        days[tf] = (df.datetime[df.tradable].dt.tz_convert(NY) + pd.Timedelta(hours=6)).dt.date.astype(str).nunique()
    s = pd.concat(out, ignore_index=True)
    s.attrs['days'] = days
    s.to_pickle(CACHE)
    return s


def seq(sub, R):
    """One position at a time: skip signals while the previous trade is open."""
    xs = sub[f'x{R:g}'].values; ii = sub.i.values; take = []; busy = -1
    for q in range(len(sub)):
        if ii[q] >= busy: take.append(q); busy = xs[q]
    return sub.iloc[take]


def stats(t, R, days):
    r = t[f'r{R:g}'].values; net = r - COST / t.risk.values
    eq = np.cumsum(net); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else np.nan
    a = t.date.values < SPLIT
    return dict(n=len(t), day=len(t) / days, win=(r > 0).mean() if len(r) else np.nan, net=net.mean() if len(net) else np.nan,
                A=net[a].mean() if a.any() else np.nan, B=net[~a].mean() if (~a).any() else np.nan, tot=net.sum(),
                pf=net[net > 0].sum() / -net[net < 0].sum() if (net < 0).any() else np.nan, dd=dd)


def fmt(m):
    return (f'{m["n"]:5d} 筆 {m["day"]:4.1f}/天  勝率 {100 * m["win"]:4.1f}%  淨 {m["net"]:+.3f}R（前 {m["A"]:+.3f} 後 {m["B"]:+.3f}）'
            f'  合計 {m["tot"]:+6.1f}R  PF {m["pf"]:.2f}  回撤 {m["dd"]:5.1f}R')


EVT = lambda x: x.ev_data | x.ev_open | x.ev_close | x.ev_globex
RULE = lambda x: (x.side * x.dir >= 1) & (x.side == x.h1) & ~EVT(x) & ~x.asia & (x.risk_atr >= 1.0)


def part1(s):
    print('\n######## 1. 每個條件單獨看（訊號各自獨立，2R，扣 1 點成本）')
    s = s.assign(net=s.r2 - COST / s.risk, a=s.date < SPLIT)
    groups = [('全部', lambda x: x.side != 0), ('數據時段', lambda x: x.ev_data), ('09:30-10:00', lambda x: x.ev_open),
              ('15:45-16:15', lambda x: x.ev_close), ('Globex 收/開', lambda x: x.ev_globex), ('大 K 棒 > 2 ATR', lambda x: x.bar_atr > 2),
              ('停損 < 1 ATR', lambda x: x.risk_atr < 1), ('亞洲盤 20-03', lambda x: x.asia), ('1h 順向', lambda x: x.side == x.h1),
              ('1h 逆向', lambda x: x.side == -x.h1), ('TJ 一般順勢', lambda x: x.side * x.dir == 1), ('TJ 強勢順勢', lambda x: x.side * x.dir == 2),
              ('TJ MIX', lambda x: x.dir == 0), ('TJ 逆勢', lambda x: x.side * x.dir < 0)]
    for tf in (1, 2, 3, 5):
        x = s[s.tf == tf]
        print(f'  {tf}m  停損中位數 {x.risk.median():.2f} 點')
        for name, f in groups:
            g = x[f(x)]
            print(f'    {name:<16} {len(g):5d}  1R勝 {100 * (g.r1 > 0).mean():4.1f}%  2R淨 {g.net.mean():+.3f}  前 {g.net[g.a].mean():+.3f}  後 {g.net[~g.a].mean():+.3f}')


def part2(s):
    print('\n######## 2. 1,152 組設定：前段挑、後段驗')
    days = s.attrs['days']
    TREND = {'不過濾': lambda x: x.side != 0, 'TJ一般': lambda x: x.side * x.dir == 1, 'TJ順勢': lambda x: x.side * x.dir >= 1,
             '1h順勢': lambda x: x.side == x.h1, 'TJ一般+1h': lambda x: (x.side * x.dir == 1) & (x.side == x.h1),
             'TJ順勢+1h': lambda x: (x.side * x.dir >= 1) & (x.side == x.h1)}
    SESS = {'全天': lambda x: x.side != 0, '現金盤': lambda x: x.rth, '排除亞洲盤': lambda x: ~x.asia}
    CLEAN = {'不清理': lambda x: x.side != 0, '你的清理': lambda x: ~(EVT(x) | (x.bar_atr > 2)),
             '停損>=1ATR': lambda x: x.risk_atr >= 1, '你的清理+停損': lambda x: ~(EVT(x) | (x.bar_atr > 2)) & (x.risk_atr >= 1)}
    rows = []
    for tf in (1, 2, 3, 5):
        x0 = s[s.tf == tf].sort_values('i')
        for (tn, tf_), (sn, sf), (cn, cf) in itertools.product(TREND.items(), SESS.items(), CLEAN.items()):
            sub = x0[tf_(x0) & sf(x0) & cf(x0)]
            for R in TARGETS:
                t = seq(sub, R); a, b = t[t.date < SPLIT], t[t.date >= SPLIT]
                ra, rb = a[f'r{R:g}'] - COST / a.risk, b[f'r{R:g}'] - COST / b.risk
                rows.append(dict(tf=tf, trend=tn, sess=sn, clean=cn, R=R, A_n=len(a), A=ra.mean(), B=rb.mean()))
    G = pd.DataFrame(rows); ok = G[G.A_n >= 120]
    print(f'  前段筆數 >= 120 的設定 {len(ok)} 組；前段 > 0 有 {(ok.A > 0).sum()}，後段 > 0 有 {(ok.B > 0).sum()}，兩段都 > 0 有 {((ok.A > 0) & (ok.B > 0)).sum()}'
          f'（前後段無關時預期 {(ok.A > 0).mean() * (ok.B > 0).mean() * len(ok):.0f}）')
    print(f'  前段排名 vs 後段排名 Spearman {ok.A.rank().corr(ok.B.rank()):+.3f}')
    print('  前段最好的 10 組 → 後段：')
    print(ok.sort_values('A', ascending=False).head(10)[['tf', 'trend', 'sess', 'clean', 'R', 'A_n', 'A', 'B']].round(3).to_string(index=False))
    for dim in ('tf', 'trend', 'sess', 'clean', 'R'):
        g = ok.groupby(dim)[['A', 'B']].mean()
        print(f'  依 {dim} 平均：' + '，'.join(f'{k} {v.A:+.3f}/{v.B:+.3f}' for k, v in g.iterrows()))


def part3(s):
    print('\n######## 3. 推薦規則（= remis_buy_sell.pine 的過濾快訊），一次一筆')
    days = s.attrs['days']
    for tf in (1, 2, 3, 5):
        x = s[s.tf == tf].sort_values('i')
        print(f'  {tf}m 2R  {fmt(stats(seq(x[RULE(x)], 2.0), 2.0, days[tf]))}')
    x = s[s.tf == 2].sort_values('i'); sub = x[RULE(x)]
    for R in TARGETS:
        print(f'  2m {R:g}R  {fmt(stats(seq(sub, R), R, days[2]))}')
    t = seq(sub, 2.0)
    for c_ in (0.5, 1.5, 2.0):
        net = t.r2 - c_ / t.risk
        print(f'  2m 2R 成本 {c_:g} 點：每筆 {net.mean():+.3f}R')
    for sd, nm in ((1, 'Buy'), (-1, 'Sell')):
        tt = t[t.side == sd]; net = tt.r2 - COST / tt.risk
        print(f'  2m 2R {nm}: {len(tt)} 筆，勝率 {100 * (tt.r2 > 0).mean():.1f}%，每筆 {net.mean():+.3f}R')
    net = t.r2 - COST / t.risk
    mm = pd.DataFrame({'month': t.month, 'net': net, 'win': t.r2 > 0}).groupby('month').agg(n=('net', 'size'), win=('win', 'mean'), net=('net', 'sum'))
    print('  逐月（2m 2R）:'); print(mm.round(3).to_string())
    g = pd.DataFrame({'d': t.date, 'net': net}).groupby('d').net.agg(['sum', 'size'])
    rng = np.random.default_rng(1); bs = []
    for _ in range(4000):
        k = rng.choice(len(g), len(g)); bs.append(g['sum'].values[k].sum() / g['size'].values[k].sum())
    print(f'  以交易日重抽 4000 次：每筆淨 R 的 90% 區間 {np.quantile(bs, .05):+.3f} ~ {np.quantile(bs, .95):+.3f}')
    print('  （這套規則是看過整年資料後組出來的，實際表現大概會比這裡差）')


def part4(s):
    print('\n######## 4. 停損放哪裡（推薦規則的同一批 2m 訊號，一次一筆）')
    df = prepared('NQ', 2)
    B, S, swl, swh = signals_ext(df)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, atr = bar_context(df, 2)
    x = s[s.tf == 2]; sel = x[RULE(x)].sort_values('i')
    STOPS = {
        '兩根極值（現在）': lambda k, i: min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i]),
        '兩根極值外 0.25 ATR': lambda k, i: (min(l[i - 1], l[i]) - 0.25 * atr[i - 1]) if k == 1 else (max(h[i - 1], h[i]) + 0.25 * atr[i - 1]),
        '兩根極值外 0.5 ATR': lambda k, i: (min(l[i - 1], l[i]) - 0.5 * atr[i - 1]) if k == 1 else (max(h[i - 1], h[i]) + 0.5 * atr[i - 1]),
        '波段低點': lambda k, i: swl[i] if k == 1 else swh[i],
        '近 5 根極值': lambda k, i: l[i - 4:i + 1].min() if k == 1 else h[i - 4:i + 1].max(),
        '1 ATR': lambda k, i: (c[i] - atr[i - 1]) if k == 1 else (c[i] + atr[i - 1]),
        '1.5 ATR': lambda k, i: (c[i] - 1.5 * atr[i - 1]) if k == 1 else (c[i] + 1.5 * atr[i - 1]),
    }
    for sn, sf in STOPS.items():
        rows = []
        for i, k, d in zip(sel.i.values, sel.side.values, sel.date.values):
            stop = sf(k, i); risk = (c[i] - stop) * k
            if not risk > 0: continue
            rows.append([i, k, risk, d] + outcome(h, l, c, i, k, stop, min(i + HORIZON, nxt[i])))
        cols = ['i', 'side', 'risk', 'date']
        for R in TARGETS: cols += [f'r{R:g}', f'x{R:g}']
        tt = pd.DataFrame(rows, columns=cols)
        for R in (1.0, 2.0, 3.0):
            m = stats(seq(tt, R), R, s.attrs['days'][2])
            print(f'  {sn:<16} {R:g}R  停損中位數 {tt.risk.median():5.2f} 點  {fmt(m)}')


if __name__ == '__main__':
    s = pd.read_pickle(CACHE) if os.path.exists(CACHE) and '--rebuild' not in sys.argv else build()
    part1(s); part2(s); part3(s); part4(s)
