"""Remi Superb v3: every strategy with today's default rules, five years (NQ data; QQQ = NQ cash-session bars).

  cd indicators/backtest
  python3 -I rbs/v3_summary.py [txf .sql dumps ... --tv TXF1!.csv]

Strategies (one at a time each, its own target; 1 point cost on NQ, 2 points on TXF):
  NQ 2m    trend 0-400 min (stop >= 0.95 ATR, slow line <= 3 ATR, 1h EMA20) + super-trend sells (TJ < -55, stage 10)
           + MIX; events, FOMC, junk time, ET 15:15-18:30, Monday Taipei 06-15, Friday cut-off; 3R
  NQ 3m    trend 90-120 min, 1R (no MIX)
  NQ 5m    trend 0-180 min + MIX, daily SMA5 side (trend and MIX), MIX >= 0.25% from SMA5; 2R
  QQQ 1m   (35, 0, 8, 1), TJ 20 / 40, slow line <= 7 ATR, NQ 2m not opposite, buys within 1.0 ATR of the fast line,
           + super-trend buys (TJ > 120, stage 10); 3R
  QQQ 2m   same ETF filters on 2-minute cash-session bars; 1R
  高開低走  gap up >= 0.75%, first 2-minute bar down but above the previous close -> short at 09:32, 1R
  大低開買  gap down >= 1.1%, first up 5-minute bar after 09:45 -> buy, stop at the day's low, 1R (separate indicator)
  TXF 2m   (only with the TXF files) trend 60-120 min + super-trend sells (TJ < -90, stage 10, 0-400 min); 3R
Not included: the stop-out re-entry (NQ 2m), the GEX setup (only 3.5 months of flip data), SPY (no five-year ES data).
Per year: trades, win rate, net R; total; max drawdown (R).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as dsm
import rth_open_gap as rog
import gapdown_long as gl

YRS = list(oc.YEARS); YRS[-1] = (YRS[-1][0], YRS[-1][1], '2099-12-31')
OUT = []


def report(name, t, rcol='R', ncol='net', yrs=None):
    yrs = yrs or YRS
    eq = np.cumsum(t[ncol].values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(t) else 0.0
    cells = []
    for nm, a, b in yrs:
        z = t[(t.date >= a) & (t.date <= b)]
        cells.append((len(z), 100 * (z[rcol] > 0).mean() if len(z) else np.nan, z[ncol].sum()))
    tot = (len(t), 100 * (t[rcol] > 0).mean() if len(t) else np.nan, t[ncol].sum())
    OUT.append(dict(name=name, years=[nm for nm, a, b in yrs], cells=cells, total=tot, dd=dd))
    print(f'   {name:<12}' + ''.join(f'{n:4d}筆 {w:3.0f}% {r:+6.1f}R  ' for n, w, r in cells) + f'| {tot[0]:5d}筆 {tot[1]:3.0f}% {tot[2]:+6.1f}R  回撤 {dd:4.1f}R', flush=True)


def nq_charts(one, M):
    D = dsm.daily(one)
    for tf, lo, hi, R, mix_on, sup, d5 in ((2, 0, 400, 3.0, True, True, False), (3, 90, 120, 1.0, False, False, False), (5, 0, 180, 2.0, True, False, True)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
        tp = ny.tz_convert('Asia/Taipei'); tm = np.asarray(tp.hour * 60 + tp.minute)
        off = ((m >= 720) & (m <= 785)) | ((m >= 915) & (m < 1110)) | ((np.asarray(tp.weekday) == 0) & (tm >= 360) & (tm < 900))
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm >= lo) & (s.tm < hi)
              & ~s.date.isin(ss.FOMC) & ~off[s.i]]
        if sup:
            x = mm.trend_signals(df, M.H, tf, 10, 8)
            x = x[(x.side == -1) & (x.spread > 55) & ~ss.EVT(x) & (x.tm < hi) & ~x.date.isin(ss.FOMC) & ~off[x.i] & ~x.i.isin(T.i)]
            T = pd.concat([T, x])
        mix = [z for z in oc.mix_list(C) if C.date[z[0]] not in ss.FOMC and not off[z[0]]] if mix_on else []
        if d5:
            day = (dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize(); sma = D.sma.reindex(day).values
            T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
            mix = [z for z in mix if np.sign(z[2] - sma[z[0]]) == z[1] and abs(z[2] - sma[z[0]]) / z[2] * 100 >= 0.25]
        report(f'NQ {tf}m', oc.sim(C, T.sort_values('i'), mix, R, R))


def etf_charts(one):
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    for tf, R in ((1, 3.0), (2, 1.0)):
        df = oc.chart(cash, tdq, tf, 20.0, 40.0)
        t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
        tw = pd.DatetimeIndex(df.datetime + pd.Timedelta(minutes=tf)); tw = (tw.tz_localize('UTC') if tw.tz is None else tw).tz_convert('Asia/Taipei')
        late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
        h, l, c = df.high.values, df.low.values, df.close.values
        tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]])))
        atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
        fast = df.emaS.values + df.tj_diff.values
        s = mm.trend_signals(df, Hq, tf, 35, 8)
        k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
        far = (s.side == 1) & ((c[s.i] - fast[s.i]) / atr[s.i] > 1.0) if tf == 1 else np.zeros(len(s), bool)
        T = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0)
              & ~late[s.i] & ~s.date.isin(ss.FOMC) & ~far]
        if tf == 1:
            x = mm.trend_signals(df, Hq, 1, 10, 8)
            x = x[(x.side == 1) & (x.spread > 120) & ~ss.EVT(x) & ~x.date.isin(ss.FOMC) & ~late[x.i] & ~x.i.isin(T.i)]
            T = pd.concat([T, x])
        q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - oc.COST / q.risk
        report(f'QQQ {tf}m', q, f'r{R:g}', 'n')


def setups(one, path):
    t = rog.study(one, 2); t = t[(t.side == -1) & (t.gap_pct >= 0.75)]
    report('高開低走', t.assign(R=t.r1, net=t.n1))
    g = gl.load(path); rows = []; prev = None
    for d, x in g.groupby('day', sort=True):
        o, h, l, c, m = x.open.values, x.high.values, x.low.values, x.close.values, x['min'].values
        if prev is not None and 100 * (o[0] / prev - 1) <= -1.1:
            for s0 in range(585, 720, 5):
                w = np.flatnonzero((m >= s0) & (m < s0 + 5))
                if len(w) < 5: continue
                if c[w[-1]] > o[w[0]]:
                    k = w[-1]; e = c[k]; st = l[:k + 1].min() - 0.25
                    risk, (r1,) = gl.trade(h, l, c, k, st, len(c), (e + (e - st),))
                    rows.append(dict(date=d, R=r1, net=r1 - oc.COST / risk)); break
        prev = c[-1]
    report('大低開買', pd.DataFrame(rows))


def txf(args):
    import txf_streaks as ts
    one = ts.load(args); tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    df = mm.chart(one, tdm, 2, 30.0, 60.0)
    s = mm.trend_signals(df, H, 2, 20, 8); base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)]
    x = mm.trend_signals(df, H, 2, 10, 8); x = x[(x.side == -1) & (x.spread > 90) & ~ss.EVT(x) & (x.tm < 400) & ~x.i.isin(base.i)]
    q = ss.seq(pd.concat([base, x]).sort_values('i'), 3.0).copy(); q['n'] = q.r3 - 2.0 / q.risk
    yrs = [(y, f'{y}-01-01', f'{y}-12-31') for y in sorted(q.date.str[:4].unique())]
    print('   （TXF 用曆年）')
    report('TXF 2m', q, 'r3', 'n', yrs)


def main():
    args = sys.argv[1:]
    one = oc.load(); M = oc.Market(one)
    print('v3 各策略，五年（每格：筆數、勝率、淨 R；最後是合計和最大回撤）')
    print('   ' + ' ' * 12 + ''.join(f'{nm[:2] + " " + nm[3:8]:<22}' for nm, a, b in YRS))
    nq_charts(one, M)
    etf_charts(one)
    setups(one, oc.DATA)
    if args: txf(args)
    import json
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'v3_summary.json'), 'w', encoding='utf-8').write(json.dumps(OUT, ensure_ascii=False, default=float))


if __name__ == '__main__':
    main()
