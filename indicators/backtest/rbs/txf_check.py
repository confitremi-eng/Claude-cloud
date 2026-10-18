"""Remi Superb filtered alerts on TXF, 2-minute chart.

  cd indicators/backtest
  python3 -I rbs/txf_check.py "TAIFEX_TXF1!, 2_xxxxx.csv" [成本,成本]           # TradingView 2-minute export
  python3 -I rbs/txf_check.py data_TXFR1_2024.sql data_TXFR1_2025.sql ... [成本,成本]   # 1-minute TXFR1 dumps

Data:
  TradingView export: only 2-minute bars, so the Trend Judge spread (5s - 15s EMA1130) is estimated from the
    2-minute closes (each bar advances the fast EMA 24 steps and the slow EMA 8 steps of a 1130 EMA). Where the
    export has the real Trend Judge spread (column 趨勢差值, only the last few days because second data on
    TradingView is short) the estimate is compared with it.
  .sql dumps (PostgreSQL COPY blocks of futures_1min: datetime in Taipei time, TXFR1 = front month, not
    back-adjusted): only the COPY rows are read as text, nothing is executed. Synthetic rows are dropped.
    Trend Judge is estimated per minute (12 / 4 steps), like rbs.py for NQ, and the 2-minute bars start at each
    session open (08:45, 15:00) like TradingView. Bars match TradingView's TXF1! up to its back-adjustment offset.
    The front month changes after the third-Wednesday expiry, so the price jumps across that session gap;
    signals from the expiry day's night session through the next day session are skipped. The 1-hour EMA20 uses clock-hour closes of the 2-minute
bars. Everything else as superb_sweep.py / setup_study.py: the user's stop (two-bar extreme), stop >= 1 ATR,
close - slow EMA <= 3 ATR, the indicator's New York event windows avoided, fixed R, 60-bar time exit, flat
before a hole longer than 30 minutes, one position at a time, cost in TXF points per round trip (default 2 and 4).
前 / 後 = the two halves of the file by date.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np
import pandas as pd
import setup_study as ss
from remi_export import signals

TF = 2
WARM_BARS = 1200                       # about four trading days before signals count
TPE = 'Asia/Taipei'


def load(path):
    raw = pd.read_csv(path)
    df = pd.DataFrame({'datetime': pd.to_datetime(raw.time, unit='s', utc=True),
                       'open': raw.open, 'high': raw.high, 'low': raw.low, 'close': raw.close})
    df['tv_diff'] = raw['趨勢差值'] if '趨勢差值' in raw else np.nan
    c = df.close.values
    aF = 1 - (1 - 2 / 1131) ** (12 * TF); aS = 1 - (1 - 2 / 1131) ** (4 * TF)
    f = np.empty(len(c)); s = np.empty(len(c)); f[0] = s[0] = c[0]
    for i in range(1, len(c)):
        f[i] = f[i - 1] + aF * (c[i] - f[i - 1]); s[i] = s[i - 1] + aS * (c[i] - s[i - 1])
    df['emaF'], df['emaS'], df['tj_diff'] = f, s, f - s
    df['tradable'] = np.arange(len(df)) >= WARM_BARS
    return df


def load_sql(paths):
    import io
    parts = []
    for f in paths:
        lines = open(f, encoding='utf-8', errors='replace').read().split('\n')
        i = next(k for k, l in enumerate(lines) if l.startswith('COPY ')) + 1
        j = lines.index('\\.', i)
        parts.append(pd.read_csv(io.StringIO('\n'.join(lines[i:j])), sep='\t', header=None,
                                 names=['datetime', 'product', 'open', 'high', 'low', 'close', 'volume', 'trading_date', 'syn']))
    d = pd.concat(parts, ignore_index=True)
    d = d[d.syn != 't']
    d['datetime'] = pd.to_datetime(d.datetime).dt.tz_localize(TPE).dt.tz_convert('UTC')
    one = d.drop_duplicates('datetime').set_index('datetime').sort_index()[['open', 'high', 'low', 'close', 'volume']]
    c = one.close.values
    aF = 1 - (1 - 2 / 1131) ** 12; aS = 1 - (1 - 2 / 1131) ** 4
    f = np.empty(len(c)); s = np.empty(len(c)); f[0] = s[0] = c[0]
    for i in range(1, len(c)):
        f[i] = f[i - 1] + aF * (c[i] - f[i - 1]); s[i] = s[i - 1] + aS * (c[i] - s[i - 1])
    import rbs
    df = rbs.bars(one, TF)
    lm = pd.DatetimeIndex(df.last_min)
    df['emaF'] = pd.Series(f, index=one.index).reindex(lm).values
    df['emaS'] = pd.Series(s, index=one.index).reindex(lm).values
    df['tj_diff'] = df.emaF - df.emaS
    df['tv_diff'] = np.nan
    # front-month roll: skip from the expiry day's night session through the next day session
    loc = df.datetime.dt.tz_convert(TPE)
    day = loc.dt.normalize().dt.tz_localize(None)
    sess = day.where(loc.dt.hour >= 8, day - pd.Timedelta(days=1))             # night session belongs to its start day
    sess = sess.where(~((loc.dt.hour >= 15) | (loc.dt.hour < 8)), sess)
    exp = pd.Series(pd.date_range(day.min() - pd.Timedelta(days=40), day.max(), freq='WOM-3WED'))
    roll = np.zeros(len(df), bool)
    for e in exp:
        nxt = e + pd.Timedelta(days=1)
        roll |= ((sess == e) & (loc.dt.hour >= 15)).values | ((sess == e) & (loc.dt.hour < 8)).values | (sess == nxt).values
    df['tradable'] = (np.arange(len(df)) >= WARM_BARS) & ~roll
    return df


def hourly(df):
    hc = df.set_index('datetime').close.resample('60min').last().dropna()
    he = hc.ewm(span=20, adjust=False).mean()
    return pd.DataFrame({'t': hc.index + pd.Timedelta(minutes=60), 'h1': np.sign(hc - he).values}).dropna()


def build(df):
    B, S = signals(df)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, atr = ss.bar_context(df, TF)
    rows = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if not df.tradable.values[i]: continue
        end = min(i + ss.HORIZON, nxt[i])
        if end <= i: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        rows.append([TF, i, k, risk, (h[i] - l[i]) / atr[i - 1], risk / atr[i - 1]] + ss.outcome(h, l, c, i, k, stop, end))
    cols = ['tf', 'i', 'side', 'risk', 'bar_atr', 'risk_atr']
    for R in ss.TARGETS: cols += [f'r{R:g}', f'x{R:g}']
    s = pd.DataFrame(rows, columns=cols)
    df['tj_dir'] = 0
    s = ss.add_context(s, df, TF, hourly(df))
    s['spread'] = df.tj_diff.values[s.i] * s.side
    s['tjSlow'] = (c[s.i] - df.emaS.values[s.i]) * s.side / atr[s.i]
    return s.sort_values('i').reset_index(drop=True)


def run(sub, R):
    t = ss.seq(sub, R)
    r = t[f'r{R:g}'].values; net = r - ss.COST / t.risk.values; a = t.date.values < ss.SPLIT
    pts = r * t.risk.values - ss.COST
    L, S = t.side.values == 1, t.side.values == -1
    m = lambda v: v.mean() if len(v) else np.nan
    return (f'{len(t):4d} 筆  勝率 {100 * m(r > 0):4.1f}%  每筆 {m(net):+.3f}R（前 {m(net[a]):+.3f} 後 {m(net[~a]):+.3f}）'
            f'  合計 {pts.sum():+6.0f} 點 | 多 {L.sum():3d} {100 * m(r[L] > 0):4.1f}% {m(net[L]):+.3f}'
            f'  空 {S.sum():3d} {100 * m(r[S] > 0):4.1f}% {m(net[S]):+.3f}')


def main():
    args = sys.argv[1:]
    costs = [2.0, 4.0]
    if args and not os.path.exists(args[-1]):
        costs = [float(v) for v in args.pop().split(',')]
    sql = [a for a in args if a.endswith('.sql')]
    df = load_sql(sql) if sql else load(args[0])
    tw = df.datetime.dt.tz_convert('Asia/Taipei')
    print(f'TXF 2 分 K：{tw.iloc[0]:%Y-%m-%d %H:%M} .. {tw.iloc[-1]:%Y-%m-%d %H:%M}（台北），{len(df)} 根，換月排除 {(~df.tradable).sum()} 根')
    m = df.tv_diff.notna().values
    if m.any():
        d = df.tj_diff.values[m] - df.tv_diff.values[m]
        same = np.sign(df.tj_diff.values[m]) == np.sign(df.tv_diff.values[m])
        print(f'Trend Judge 推算 vs 匯出的真實差值（{m.sum()} 根）：差距中位數 {np.median(np.abs(d)):.1f} 點，'
              f'真實差值中位數 {np.median(np.abs(df.tv_diff.values[m])):.1f} 點，正負號相同 {100 * same.mean():.1f}%')
    s = build(df)
    d = sorted(s.date.unique()); ss.SPLIT = d[len(d) // 2]
    print(f'訊號 {len(s)} 個，前 / 後 分界 {ss.SPLIT}，停損中位數 {s.risk.median():.0f} 點')
    print('spread 分布（訊號方向，點）：', ' '.join(f'{q:.0%}={v:.0f}' for q, v in s.spread.quantile([.1, .25, .5, .75, .9]).items()))
    base = (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s)
    for cost in costs:
        ss.COST = cost
        for fname, fm in (('距離 ≤ 3 ATR（Remi Superb 預設）', s.tjSlow < 3), ('不加距離', s.side != 0)):
            for R in (1.0, 2.0, 3.0):
                print(f'\n  ## 成本 {cost:g} 點，{fname}，{R:g}R')
                for th in (10, 20, 30, 40, 50, 60, 80):
                    print(f'   門檻 {th:<3g} ' + run(s[base & fm & (s.spread > th)], R))
                print('   不看 TJ  ' + run(s[base & fm], R))
    s['bp'] = s.spread / df.close.values[s.i] * 1e4            # spread in basis points of price
    s['year'] = pd.to_datetime(s.date).dt.year
    years = sorted(s.year.unique())
    if len(years) > 1:
        ss.COST = costs[0]
        print(f'\n######## 門檻改用價格的萬分比（spread / 收盤 × 10000），成本 {costs[0]:g} 點')
        for fname, fm in (('距離 ≤ 3 ATR', s.tjSlow < 3), ('不加距離', s.side != 0)):
            for R in (2.0, 3.0):
                print(f'\n  ## {fname}，{R:g}R')
                for th in (2, 4, 6, 8, 10, 12, 15, 20):
                    print(f'   萬分之 {th:<3g} ' + run(s[base & fm & (s.bp > th)], R))
        print(f'\n######## 逐年（成本 {costs[0]:g} 點）')
        for nm, m_ in (('點數門檻 30，距離 ≤ 3 ATR', (s.spread > 30) & (s.tjSlow < 3)),
                       ('點數門檻 30，不加距離', s.spread > 30),
                       ('萬分之 10，距離 ≤ 3 ATR', (s.bp > 10) & (s.tjSlow < 3)),
                       ('萬分之 10，不加距離', s.bp > 10)):
            for R in (2.0, 3.0):
                for y in years:
                    print(f'   {nm:<20} {R:g}R {y}  ' + run(s[base & m_ & (s.year == y)], R))


if __name__ == '__main__':
    main()
