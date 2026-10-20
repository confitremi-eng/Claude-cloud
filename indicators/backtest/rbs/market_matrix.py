"""Win-rate matrix of the Remi Superb strategies on SPY / QQQ (1m, 2m), NQ / ES / TXF (2m, 3m).

  cd indicators/backtest
  python3 -I rbs/market_matrix.py [market ...] [--txf data_TXFR1_2024.sql,data_TXFR1_2025.sql,data_TXFR1_2026.sql]
  markets: nq es txf qqq spy (default: all that have data)

Data
  NQ, ES   Databento 1-minute files (data/NQ_1m_databento.csv, data/ES_1m_databento.csv), all hours
  TXF      the TXFR1 1-minute .sql dumps (txf_check.read_sql_1m), roll windows skipped
  QQQ      stand-in: NQ bars cut to what a QQQ chart shows (weekdays 09:30-16:00 ET, NYSE holidays out), every
           indicator computed on those bars only (param_sweep_1m.py's qqq mode); prices stay in NQ points
           (QQQ ~ NQ / 41)
  SPY      the same with ES bars (SPY ~ ES / 10); prices in ES points
Per market: Trend Judge 一般 threshold and cost per trade in its points (NQ 10 / 1, ES 4 / 0.5, TXF 30 / 2,
QQQ 10 / 1 NQ point ~ 2.4 cents, SPY 4 / 0.2 ES point ~ 2 cents). Trend Judge = 5 s - 15 s EMA1130 fed 1-minute
closes (no fill-in of missing minutes), locked every 2 minutes on 1-minute charts.
Strategies (Remi Superb / v2 rules on that chart)
  趨勢全部      filtered alerts: spread > threshold, last complete 1-hour close on the trade's side of its EMA20
                (stock-chart hours from 09:30 for SPY / QQQ), stop >= 1 ATR, close - 15 s EMA1130 <= 3 ATR, the
                New York event windows avoided; signal close entry, two-bar stop, 60-bar time exit
  趨勢 0-180 / 60-120 / 90-120   the same, trend minutes (the indicator's count) inside the window
  ETF 設定      (SPY / QQQ 1m) the QQQ 1-minute setting: (35, 0, 8, 1), threshold x 2, distance 7 ATR
  MIX 突破      60-minute MIX box, first 10% break within 60 minutes, stop order at the break, stop at the middle
  v2 組合       趨勢 0-180 + MIX, one at a time (stop, target, 60 bars, 17:00 ET halt, data holes)
Each signal on its own for win rates (前 / 後 = the two halves of the dates); v2 one at a time, per year.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore')
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import mix_range as mr
import mix_breakout as mb
from remi_export import signals

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data')
MARKETS = {  # name: (threshold, strong, cost, timeframes, etf)
    'nq': ('NQ', 10.0, 35.0, 1.0, (2, 3), False),
    'es': ('ES', 4.0, 8.0, 0.5, (2, 3), False),
    'txf': ('TXF', 30.0, 60.0, 2.0, (2, 3), False),
    'qqq': ('QQQ（NQ 美股盤代替）', 10.0, 35.0, 1.0, (1, 2), True),
    'spy': ('SPY（ES 美股盤代替）', 4.0, 8.0, 0.2, (1, 2), True),
}
TARGETS = (1.0, 2.0, 3.0)
NYSE_CLOSED = {'2021-11-25', '2021-12-24',
               '2022-01-17', '2022-02-21', '2022-04-15', '2022-05-30', '2022-06-20', '2022-07-04', '2022-09-05', '2022-11-24', '2022-12-26',
               '2023-01-02', '2023-01-16', '2023-02-20', '2023-04-07', '2023-05-29', '2023-06-19', '2023-07-04', '2023-09-04', '2023-11-23', '2023-12-25',
               '2024-01-01', '2024-01-15', '2024-02-19', '2024-03-29', '2024-05-27', '2024-06-19', '2024-07-04', '2024-09-02', '2024-11-28', '2024-12-25',
               '2025-01-01', '2025-01-09', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26', '2025-06-19', '2025-07-04', '2025-09-01',
               '2025-11-27', '2025-12-25', '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
               '2026-06-19', '2026-07-03', '2026-09-07'}
EARLY_CLOSE = {'2021-11-26', '2022-11-25', '2023-07-03', '2023-11-24', '2024-07-03', '2024-11-29', '2024-12-24', '2025-07-03',
               '2025-11-28', '2025-12-24'}


def read_csv(path):
    return pd.read_csv(path, parse_dates=['datetime']).set_index('datetime').sort_index()[['open', 'high', 'low', 'close']]


def cash_only(one):
    et = one.index.tz_convert(ss.NY)
    m = et.hour * 60 + et.minute; d = et.strftime('%Y-%m-%d')
    end = np.where(np.isin(d, list(EARLY_CLOSE)), 780, 960)
    return one[(et.weekday < 5) & (m >= 570) & (m < end) & ~np.isin(d, list(NYSE_CLOSED))]


def load_market(key, txf_paths):
    if key in ('nq', 'qqq'):
        one = read_csv(os.path.join(DATA, 'NQ_1m_databento.csv'))
    elif key in ('es', 'spy'):
        one = read_csv(os.path.join(DATA, 'ES_1m_databento.csv'))
    else:
        import txf_check as tx
        one = tx.read_sql_1m(txf_paths)[['open', 'high', 'low', 'close']]
        one['bad'] = tx.roll_mask(one.index)
        return one
    if MARKETS[key][5]:
        one = cash_only(one)
    one['bad'] = False
    return one


def minute_trend(one):
    """5 s / 15 s EMA1130 per 1-minute close, restarted after holes longer than 4 days."""
    seg = rbs.segments(one.index); parts = []
    for s in np.unique(seg):
        c = one.close[seg == s]
        ef = c.ewm(alpha=rbs.A_FAST, adjust=False).mean(); es = c.ewm(alpha=rbs.A_SLOW, adjust=False).mean()
        parts.append(pd.DataFrame({'diff': ef - es, 'emaF': ef, 'emaS': es}))
    return pd.concat(parts)


def hourly(one, etf):
    if etf:
        et = one.index.tz_convert(ss.NY)
        k = (et.hour * 60 + et.minute - 570) // 60
        g = pd.DataFrame({'c': one.close.values, 'key': et.normalize() + pd.to_timedelta(570 + 60 * k, unit='min'),
                          't': one.index + pd.Timedelta(minutes=1)})
        hb = g.groupby('key').agg(c=('c', 'last'), t=('t', 'last')).sort_values('t')
        he = hb.c.ewm(span=20, adjust=False).mean()
        return pd.DataFrame({'t': hb.t.reset_index(drop=True), 'h1': np.sign(hb.c - he).values})
    hc = one.close.resample('60min').last().dropna(); he = hc.ewm(span=20, adjust=False).mean()
    return pd.DataFrame({'t': hc.index + pd.Timedelta(minutes=60), 'h1': np.sign(hc - he).values}).dropna()


def chart(one, tdm, tf, th, st):
    df = rbs.bars(one[['open', 'high', 'low', 'close']].assign(volume=0), tf)
    lm = pd.DatetimeIndex(df.last_min)
    d = tdm['diff'].reindex(lm).values
    if tf == 1:                                   # Trend Judge locks its value every 2 minutes
        newwin = (df.datetime.dt.minute % 2 == 0).values
        cur = np.nan; lk = np.full(len(d), np.nan)
        for i in range(len(d)):
            if newwin[i]: cur = d[i]
            lk[i] = cur
        d = lk
    df['tj_diff'] = d
    df['emaS'] = tdm['emaS'].reindex(lm).values
    df['tj_dir'] = np.where(np.isnan(d), 0, np.where(d > st, 2, np.where(d > th, 1, np.where(d < -st, -2, np.where(d < -th, -1, 0)))))
    seg = rbs.segments(pd.DatetimeIndex(df.datetime))
    day = df.datetime.dt.tz_convert(ss.NY).dt.date
    warm = {x for _, g in day.groupby(seg) for x in sorted(g.unique())[:rbs.WARM_DAYS]}
    bad = one['bad'].reindex(lm).fillna(True).values.astype(bool)
    df['tradable'] = ~day.isin(warm).values & ~bad
    tdir = np.sign(df.tj_dir.values); tb = np.zeros(len(df), int)
    for j in range(len(df)):
        tb[j] = (tb[j - 1] + 1) if (j and tdir[j] != 0 and tdir[j] == tdir[j - 1]) else (1 if tdir[j] != 0 else 0)
    df['tmin'] = tb * tf
    return df.reset_index(drop=True)


def trend_signals(df, H, tf, stage=20, ema_len=8):
    B, S = signals(df, stage, ema_len)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, atr = ss.bar_context(df, tf)
    rows = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 15 or not df.tradable.values[i]: continue
        end = min(i + ss.HORIZON, nxt[i])
        if end <= i: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        rows.append([tf, i, k, risk, (h[i] - l[i]) / atr[i - 1], risk / atr[i - 1]] + ss.outcome(h, l, c, i, k, stop, end))
    cols = ['tf', 'i', 'side', 'risk', 'bar_atr', 'risk_atr']
    for R in ss.TARGETS: cols += [f'r{R:g}', f'x{R:g}']
    s = ss.add_context(pd.DataFrame(rows, columns=cols), df, tf, H)
    s['spread'] = df.tj_diff.values[s.i] * s.side
    s['slow'] = (c[s.i] - df.emaS.values[s.i]) * s.side / atr[s.i]
    s['tm'] = df.tmin.values[s.i]
    return s.sort_values('i').reset_index(drop=True)


def filt(s, th, dist=3.0):
    return (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < dist) & (s.spread > th)


def mix_breaks(df, tf, th, cost):
    """mix_breakout.py on this chart: rows per breakout for each target."""
    mr.TF, mr.TH, mr.HOLD, mb.COST = tf, th, 60, cost
    rbs._cache[('NQ', tf)] = df
    B = mr.load()
    W = max(1, round(60 / tf)); boxes = mb.causal_boxes(B, W, grace=max(0, round(4 / tf)))
    out = {}
    for R in TARGETS:
        bo = mb.breakouts(B, boxes, R, max_age=W, entry='stop')
        out[R] = bo
    return B, boxes, out


def v2_combo(df, s, th, B, boxes, R, cost, lo=0, hi=180, F=None, mix_on=True):
    """Remi Superb v2 one at a time (v2_port.py logic) on this chart. F: the trend signals to use (else the
    filtered alerts inside lo-hi); mix_on=False leaves the MIX breakouts out."""
    h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
    n = len(c)
    f = s[filt(s, th) & (s.tm >= lo) & (s.tm < hi)] if F is None else F
    trend = {int(i): int(k) for i, k in zip(f.i.values, f.side.values)}
    mix = {}
    hb, lb, ob, hole, evt = B['h'], B['l'], B['o'], B['hole'], B['evt']
    W = max(1, round(60 / mr.TF))
    for s0, fm, top, bot in (boxes if mix_on else []):
        Hh = top - bot
        if Hh <= 0: continue
        bu, bd, mid = top + 0.1 * Hh, bot - 0.1 * Hh, (top + bot) / 2
        for j in range(fm + 1, min(fm + W, n - 1) + 1):
            if hole[j]: break
            up, dn = hb[j] >= bu, lb[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            k = 1 if up else -1
            mix[j] = (k, max(ob[j], bu) if k == 1 else min(ob[j], bd), mid)
            break
    et = (df.datetime + pd.Timedelta(minutes=mr.TF)).dt.tz_convert(ss.NY)
    halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    date = df.datetime.dt.tz_convert(ss.NY).dt.date.astype(str).values
    trad = df.tradable.values
    trades = []; pos = 0
    for j in range(n):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                trades.append((kind, pos, ve, px, abs(ve - vs), d0)); pos = 0
        if not trad[j]: continue
        if pos == 0 and j in mix and not halt[j]:
            k, px, mid = mix[j]
            pos, ve, vs, vt, vb, kind, d0 = k, px, mid, px + R * (px - mid), j, 'MIX', date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                trades.append((kind, pos, ve, vs, abs(ve - vs), d0)); pos = 0
        if pos == 0 and j in trend and not halt[j]:
            k = trend[j]
            stop = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, kind, d0 = k, c[j], stop, c[j] + R * (c[j] - stop), j, '趨勢', date[j]
    t = pd.DataFrame(trades, columns=['kind', 'side', 'entry', 'exit', 'risk', 'date'])
    t['R'] = (t.exit - t.entry) * t.side / t.risk
    t['net'] = t.R - cost / t.risk
    return t


def row_ind(y, cost, split):
    """Signals on their own: n, then per target win % / net R, and whether both halves are positive at 3R."""
    if len(y) == 0: return '   0'
    a = y.date.values < split; cells = []
    for R in TARGETS:
        r = y[f'r{R:g}'].values if f'r{R:g}' in y else y['R'].values
        nn = r - cost / y.risk.values
        cells.append(f'{100 * (r > 0).mean():4.1f}% {nn.mean():+.3f}')
    r3 = (y['r3'].values if 'r3' in y else y['R'].values) - cost / y.risk.values
    both = '✓' if (r3[a].mean() > 0 and r3[~a].mean() > 0) else '✗'
    return f'{len(y):5d}  ' + '  '.join(cells) + f'   3R 前/後 {r3[a].mean():+.2f}/{r3[~a].mean():+.2f} {both}'


def mix_rows(bo):
    """MIX rows for each target -> a frame like the trend signals (R per target)."""
    base = bo[1.0][['i', 'side', 'risk', 'date']].copy()
    for R in TARGETS:
        base[f'r{R:g}'] = bo[R]['R'].values
    return base


def combo_line(t, years):
    if len(t) == 0: return '   0'
    n = t.net.values; eq = np.cumsum(n); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = pd.Series(n).groupby(t.date.str[:7].values).sum()
    return (f'{len(t) / years:6.0f} 筆/年  勝率 {100 * (t.R > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  每年 {n.sum() / years:+6.1f}R'
            f'  回撤 {dd:5.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}')


def run_market(key, txf_paths):
    name, th, st, cost, tfs, etf = MARKETS[key]
    one = load_market(key, txf_paths)
    tdm = minute_trend(one)
    H = hourly(one, etf)
    span_days = (one.index[-1] - one.index[0]).days
    years = span_days / 365.25
    print(f'\n################ {name}：{one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}（{years:.1f} 年），門檻 {th:g}，每筆扣 {cost:g} 點')
    for tf in tfs:
        df = chart(one, tdm, tf, th, st)
        s = trend_signals(df, H, tf)
        d = sorted(s.date.unique()); split = d[len(d) // 2]
        F = s[filt(s, th)]
        print(f'\n  ## {name} {tf} 分 K（前 / 後 分界 {split}）    筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
        for nm, y in (('趨勢全部', F), ('趨勢 0–180 分', F[(F.tm >= 0) & (F.tm < 180)]),
                      ('趨勢 60–120 分', F[(F.tm >= 60) & (F.tm < 120)]), ('趨勢 90–120 分', F[(F.tm >= 90) & (F.tm < 120)])):
            print(f'   {nm:<14} ' + row_ind(y, cost, split))
        if etf and tf == 1:
            s2 = trend_signals(df, H, tf, 35, 8)
            F2 = s2[filt(s2, th * 2, 7.0)]
            print(f'   {"ETF 設定(35,8)":<14} ' + row_ind(F2, cost, split))
        B, boxes, bo = mix_breaks(df, tf, th, cost)
        M = mix_rows(bo)
        print(f'   {"MIX 突破":<14} ' + row_ind(M, cost, split))
        for R in (2.0, 3.0):
            t = v2_combo(df, s, th, B, boxes, R, cost)
            print(f'   v2 組合 {R:g}R（一次一筆）  ' + combo_line(t, years))
        rbs._cache.pop(('NQ', tf), None)


V3 = {  # (market, tf): (stage, ema, threshold multiple, distance, window lo, hi, MIX, target R, label)
    ('nq', 2): (20, 8, 1, 3.0, 0, 180, True, 3.0, '趨勢 0–180 分 + MIX 突破，3R'),
    ('nq', 3): (20, 8, 1, 3.0, 90, 120, False, 1.0, '趨勢 90–120 分，1R'),
    ('txf', 2): (20, 8, 1, 3.0, 60, 120, False, 3.0, '趨勢 60–120 分，3R'),
    ('txf', 3): (20, 8, 1, 3.0, 60, 120, False, 3.0, '趨勢 60–120 分，3R'),
    ('qqq', 1): (35, 8, 2, 7.0, 0, 10 ** 9, False, 3.0, 'ETF 設定 (35, 0, 8, 1)，門檻 ×2，距離 7 ATR，3R'),
    ('spy', 1): (35, 8, 2, 7.0, 0, 10 ** 9, False, 3.0, 'ETF 設定 (35, 0, 8, 1)，門檻 ×2，距離 7 ATR，3R'),
}


def v3(keys, txf_paths):
    """Remi Superb v3's rule set for each market and timeframe, one position at a time."""
    print('\n################ Remi Superb v3：每個商品 / 週期自動套用的做法，一次一筆')
    for key in keys:
        name, th, st, cost, tfs, etf = MARKETS[key]
        mine = [tf for (k, tf) in V3 if k == key]
        if not mine: continue
        one = load_market(key, txf_paths); tdm = minute_trend(one); H = hourly(one, etf)
        years = (one.index[-1] - one.index[0]).days / 365.25
        for tf in mine:
            stage, ema, mult, dist, lo, hi, mix_on, R, label = V3[(key, tf)]
            df = chart(one, tdm, tf, th * mult, st * mult)
            s = trend_signals(df, H, tf, stage, ema)
            F = s[filt(s, th * mult, dist) & (s.tm >= lo) & (s.tm < hi)]
            B, boxes, _ = mix_breaks(df, tf, th * mult, cost)
            t = v2_combo(df, s, th * mult, B, boxes, R, cost, F=F, mix_on=mix_on)
            a = t.date.values < sorted(t.date.unique())[len(t.date.unique()) // 2]
            print(f'   {name} {tf}m（{label}）\n      ' + combo_line(t, years) + f'  前 / 後 {t.net[a].mean():+.3f} / {t.net[~a].mean():+.3f}')
            rbs._cache.pop(('NQ', tf), None)


def main():
    args = sys.argv[1:]
    if '--v3' in args:
        args.remove('--v3')
        tp = []
        if '--txf' in args:
            k = args.index('--txf'); tp = args[k + 1].split(','); del args[k:k + 2]
        v3(args or ['nq', 'qqq', 'spy'] + (['txf'] if tp else []), tp)
        return
    txf_paths = []
    if '--txf' in args:
        k = args.index('--txf'); txf_paths = args[k + 1].split(','); del args[k:k + 2]
    keys = args or ['nq', 'es', 'qqq', 'spy'] + (['txf'] if txf_paths else [])
    for key in keys:
        run_market(key, txf_paths)


if __name__ == '__main__':
    main()
