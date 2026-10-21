"""Raw trigger behind the bought indicator's 🦀 / 🍦 (es 3m 2026 v2.1), over years of data.

  cd indicators/backtest
  python3 -I rbs/bought_raw_backtest.py nq 2          # data/NQ_1m_5y.csv (back-adjusted), 2- or 5-minute bars
  python3 -I rbs/bought_raw_backtest.py txf 2 ../../ohlc資料/data_TXFR1_2024.sql ...   # TXFR1 1-minute dumps

Trigger (matched to every 🦀 and most 🍦 on TXF / NQ, 2026-10): a bar makes a new 100-bar low, then a later close
above that low bar's high is a buy; no EMA check (remi_export.signals' current rule with stage 100, EMA off).
The indicator's own extra filter is unknown, so this measures the raw trigger and a few simple filters.

Long at the signal bar's close. Stops: 1 ATR(14), and the low of the signal bar and the bar before (at least
1 ATR). Hit = price reaches the level before the stop (a bar touching both counts as the stop). Exit after 60 bars
or at a session gap over 30 minutes. 每筆 R is after cost (NQ 1 point, TXF 4 points per round trip).
TXF: signals from the expiry night session through the next day are skipped (front-month jump).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np
import pandas as pd
import rbs

STAGE, HORIZON, RS = 100, 60, (1, 1.5, 2, 3)
TPE, NY = 'Asia/Taipei', 'America/New_York'


def raw_buys(h, l, c):
    lo = pd.Series(l).rolling(STAGE).min().shift().values
    out, arm, ref = [], False, np.nan
    for i in range(STAGE, len(c)):
        if arm and c[i] > ref:
            out.append(i); arm = False
        elif l[i] < lo[i]:
            arm, ref = True, h[i]
    return np.array(out)


def load(mkt, tf, paths):
    if mkt == 'nq':
        one = pd.read_csv('data/NQ_1m_5y.csv')
        one.index = pd.to_datetime(one.datetime, utc=True)
        one = one[['open', 'high', 'low', 'close', 'volume']]
        skip = None
    else:
        import txf_check as tc
        tc.TF = tf
        one = tc.read_sql_1m(paths)
        skip = tc.roll_mask
    df = rbs.bars(one, tf)
    df['skip'] = skip(df.datetime) if skip else False
    return df


def study(df, mkt, tf):
    h, l, c = df.high.values, df.low.values, df.close.values
    t = pd.DatetimeIndex(df.datetime)
    sess = (t.to_series().diff() > pd.Timedelta(minutes=30)).cumsum().values
    pc = pd.Series(c).shift()
    tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    ema89 = pd.Series(c).ewm(span=89, adjust=False).mean().values
    cost = 1.0 if mkt == 'nq' else 4.0
    sig = raw_buys(h, l, c)
    rows, prev = [], -10 ** 9
    for i in sig:
        gap_prev, prev = i - prev, i
        if i < 1200 or df.skip.values[i]:
            continue
        r = {'i': i, 't': t[i], 'year': t[i].tz_convert(TPE).year, 'cluster': gap_prev <= 10,
             'above200': c[i] > ema200[i], 'above89': c[i] > ema89[i]}
        if mkt == 'nq':
            et = t[i].tz_convert(NY)
            m = et.hour * 60 + et.minute
            r['part'] = '美股盤' if 9 * 60 + 30 <= m < 16 * 60 else '夜盤'
        else:
            r['part'] = '日盤' if 8 <= t[i].tz_convert(TPE).hour < 14 else '夜盤'
        for name, dist in (('1ATR', atr[i]), ('兩根K', max(c[i] - min(l[i], l[i - 1]), atr[i]))):
            e, best, stopped, end = c[i], 0.0, False, i
            for j in range(i + 1, min(i + 1 + HORIZON, len(c))):
                if sess[j] != sess[i]:
                    break
                end = j
                if l[j] <= e - dist:
                    stopped = True
                    break
                best = max(best, (h[j] - e) / dist)
            r[f'{name}_best'] = best
            for k in RS:
                v = k if best >= k else (-1.0 if stopped else (c[end] - e) / dist)
                r[f'{name}_{k}'] = v - cost / dist
            r[f'{name}_pts'] = dist
        rows.append(r)
    return pd.DataFrame(rows)


def table(g, title):
    print(f'\n== {title}（{len(g)} 筆）')
    if not len(g):
        return
    print(f'{"":<12}{"筆":>6}{"停損點":>8}{"1R 命中":>9}{"1.5R":>7}{"2R":>7}{"3R":>7}  {"每筆R 1R":>9}{"1.5R":>7}{"2R":>7}{"3R":>7}')
    for name in ('1ATR', '兩根K'):
        b = g[f'{name}_best']
        print(f'{name:<12}{len(g):>6}{g[f"{name}_pts"].mean():>8.1f}' + ''.join(f'{(b >= k).mean():>8.0%}' for k in RS) +
              '  ' + ''.join(f'{g[f"{name}_{k}"].mean():>+8.2f}' for k in RS))


def main():
    mkt, tf = sys.argv[1], int(sys.argv[2])
    df = load(mkt, tf, sys.argv[3:])
    s = study(df, mkt, tf)
    t0, t1 = s.t.min().tz_convert(TPE), s.t.max().tz_convert(TPE)
    print(f'{mkt.upper()} {tf}m 原始觸發（{STAGE} 根新低、收盤站回）{t0:%Y-%m-%d} .. {t1:%Y-%m-%d}，做多，'
          f'成本 {"1" if mkt == "nq" else "4"} 點')
    table(s, '全部')
    for y, g in s.groupby('year'):
        table(g, f'{y} 年')
    for p, g in s.groupby('part'):
        table(g, p)
    table(s[~s.cluster], '前 10 根內沒有別的訊號（不是連發）')
    table(s[s.cluster], '連發（前 10 根內有訊號）')
    table(s[s.above200], '收盤在 EMA200 上（順勢回檔）')
    table(s[~s.above200], '收盤在 EMA200 下（逆勢抄底）')
    table(s[~s.above89], '收盤在 EMA89 下')


if __name__ == '__main__':
    main()
