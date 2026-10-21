"""Three kinds of 起漲點 seen in the bought indicator (es 3m 2026 v2.1, 🦀 / 🍦), studied on NQ 1-minute data
2021-10 .. 2026-10: under which conditions do they work.

  cd indicators/backtest
  python3 -I rbs/rise_points.py 2            # 2-minute bars (or 5); builds data/rise_events_2m.pkl, prints the tables
  python3 -I rbs/rise_points.py 2 --search   # pairs of conditions, checked against shuffled outcomes
  add --rebuild after changing the events

Events, long, entered at the signal bar's close:
  慢跌收復 / 急跌反轉: a new 100-bar low, then a green bar closes above that low bar's high (the 🦀 / green 🍦
      trigger). RSI(14) >= 38 at the signal is 慢跌收復 (🦀-like), below 38 急跌反轉 (green-🍦-like).
      Stop: under the swing low (lowest low since the new low), at least 1 ATR.
  中繼急殺: a red bar of at least 1.1 ATR closing in its lower half, within 3.5 ATR of the 30-bar high and not more
      than 1.5 ATR under EMA89 (the red 🍦). At most one every 10 bars. Stop 1 ATR.
Hit = price reaches the level before the stop (a bar touching both counts as the stop). Exit after 60 bars or at a
session gap over 30 minutes. 每筆 R after 1 point per round trip. The condition tables use a fixed 1-ATR stop for
every type, so a bucket is not better just because its stop is smaller; with that stop a random walk hits
1R / 1.5R / 2R / 3R first 50% / 40% / 33% / 25% of the time.

Conditions are measured at the signal bar's close (the hour and the day use only finished hours / days).
Each table splits the events into buckets (quintiles for numbers) and shows 前 2021-10 .. 2023-12 and
後 2024-01 .. 2026-10 separately: a condition counts only if it helps in both halves.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np
import pandas as pd
import rbs

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE, HORIZON, COST = 100, 60, 1.0
RS = (1, 1.5, 2, 3)
SPLIT = pd.Timestamp('2024-01-01', tz='UTC')
NY = 'America/New_York'


def rsi(c, n=14):
    d = pd.Series(c).diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn)).values


def context(one, df):
    """Last finished hour vs its EMA20, and the previous trading day (New York, 18:00 roll) vs its EMA20."""
    close_t = pd.DatetimeIndex(df.last_min) + pd.Timedelta(minutes=1)
    hc = one.close.resample('60min').last().dropna()
    he = hc.ewm(span=20, adjust=False).mean()
    h1 = pd.DataFrame({'t': hc.index + pd.Timedelta(minutes=60), 'h1': np.sign(hc - he).values})
    out = pd.merge_asof(pd.DataFrame({'t': close_t}), h1, on='t', direction='backward')
    day = (one.index.tz_convert(NY) + pd.Timedelta(hours=6)).normalize()
    dc = one.close.groupby(day).last()
    de = dc.ewm(span=20, adjust=False).mean()
    prev = pd.DataFrame({'d_close': dc.shift(), 'd_trend': np.sign(dc - de).shift()})
    bday = (close_t.tz_convert(NY) + pd.Timedelta(hours=6)).normalize()
    p = prev.reindex(bday)
    return out.h1.values, p.d_close.values, p.d_trend.values


def outcome(h, l, c, sess, i, dist):
    e, best, stopped, end = c[i], 0.0, False, i
    for j in range(i + 1, min(i + 1 + HORIZON, len(c))):
        if sess[j] != sess[i]:
            break
        end = j
        if l[j] <= e - dist:
            stopped = True
            break
        best = max(best, (h[j] - e) / dist)
    ev = {k: (k if best >= k else (-1.0 if stopped else (c[end] - e) / dist)) - COST / dist for k in RS}
    return best, stopped, ev


def build(tf):
    one = pd.read_csv(os.path.join(HERE, 'data', 'NQ_1m_5y.csv'))
    one.index = pd.to_datetime(one.datetime, utc=True)
    one = one[['open', 'high', 'low', 'close', 'volume']]
    df = rbs.bars(one, tf)
    df = rbs.trend_judge(df, rbs.trend_diff_minutes(one), tf, 'NQ')
    o, h, l, c, v = (df[k].values for k in ('open', 'high', 'low', 'close', 'volume'))
    t = pd.DatetimeIndex(df.datetime)
    sess = (t.to_series().diff() > pd.Timedelta(minutes=30)).cumsum().values
    atr = rbs.atr(h, l, c)
    r = rsi(c)
    e20, e89, e200 = rbs.ema(c, 20), rbs.ema(c, 89), rbs.ema(c, 200)
    hi30 = pd.Series(h).rolling(30).max().values
    lo60 = pd.Series(l).rolling(60).min().values
    rng100 = (pd.Series(h).rolling(STAGE).max() - pd.Series(l).rolling(STAGE).min()).values
    vavg = pd.Series(v).rolling(20).mean().shift().values
    atr_slow = pd.Series(atr).ewm(span=500, adjust=False).mean().values
    h1, d_close, d_trend = context(one, df)
    et = t.tz_convert(NY)
    mins = et.hour * 60 + et.minute

    def common(i, kind, dist):
        best, stopped, ev = outcome(h, l, c, sess, i, dist)
        b1, s1, e1 = outcome(h, l, c, sess, i, atr[i])
        m = mins[i]
        row = {'kind': kind, 't': t[i], 'year': et[i].year, 'half': '前' if t[i] < SPLIT else '後',
               'stop_atr': dist / atr[i], 'best': best, 'stopped': stopped, 'mfe_atr': best * dist / atr[i],
               'RSI': r[i], '離EMA20': (c[i] - e20[i]) / atr[i], '離EMA89': (c[i] - e89[i]) / atr[i],
               '離EMA200': (c[i] - e200[i]) / atr[i], 'EMA89斜率': (e89[i] - e89[i - 20]) / atr[i],
               '離30根高點': (hi30[i] - c[i]) / atr[i], '100根振幅': rng100[i] / atr[i],
               '收盤位置': (c[i] - l[i]) / (h[i] - l[i]) if h[i] > l[i] else 0.5, 'K棒長': (h[i] - l[i]) / atr[i],
               '量比': v[i] / vavg[i] if vavg[i] > 0 else np.nan,
               '前5根最大量比': v[i - 4:i + 1].max() / vavg[i - 4] if vavg[i - 4] > 0 else np.nan,
               'ATR相對': atr[i] / atr_slow[i], '1h': h1[i], '日線': d_trend[i],
               '今日漲跌%': (c[i] / d_close[i] - 1) * 100, 'TJ': df.tj_dir.values[i],
               '時段': ('亞洲 18-03' if m >= 18 * 60 or m < 3 * 60 else '歐洲 03-09:30' if m < 570 else
                       '開盤 09:30-11' if m < 660 else '午盤 11-14' if m < 840 else '收盤 14-17')}
        for k in RS:
            row[f'ev{k:g}'] = ev[k]
            row[f'a_ev{k:g}'] = e1[k]
        row['a_best'] = b1
        return row

    rows = []
    lo = pd.Series(l).rolling(STAGE).min().shift().values
    arm, ref, arm_i, recent = False, np.nan, -1, []
    for i in range(STAGE, len(c)):
        if arm and c[i] > ref:
            arm = False
            recent = [k for k in recent if k > i - STAGE]
            if i >= 1200 and c[i] > o[i]:
                swing = l[arm_i:i + 1].min()
                dist = max(c[i] - swing + 0.25, atr[i])
                row = common(i, '慢跌收復' if r[i] >= 38 else '急跌反轉', dist)
                row.update({'新低後根數': i - arm_i, '離低點': (c[i] - swing) / atr[i], '前100根已觸發': len(recent)})
                rows.append(row)
            recent.append(i)
        elif l[i] < lo[i]:
            arm, ref, arm_i = True, h[i], i
    last3 = -10 ** 9
    for i in range(1200, len(c)):
        if c[i] < o[i] and h[i] - l[i] >= 1.1 * atr[i] and (c[i] - l[i]) <= 0.5 * (h[i] - l[i]) \
                and hi30[i] - c[i] <= 3.5 * atr[i] and c[i] >= e89[i] - 1.5 * atr[i] and i - last3 >= 10:
            last3 = i
            row = common(i, '中繼急殺', atr[i])
            row['前60根漲幅'] = (c[i] - lo60[i]) / atr[i]
            rows.append(row)
    ev = pd.DataFrame(rows)
    ev.to_pickle(os.path.join(HERE, 'data', f'rise_events_{tf}m.pkl'))
    return ev


def stats(g, p=''):
    """n, 1R hit, 1.5R hit, R per trade at 1.5R and at 3R. p='a_' uses the fixed 1-ATR stop."""
    if not len(g):
        return [0, np.nan, np.nan, np.nan, np.nan]
    b = g[f'{p}best']
    return [len(g), (b >= 1).mean(), (b >= 1.5).mean(), g[f'{p}ev1.5'].mean(), g[f'{p}ev3'].mean()]


def line(label, g, p='a_'):
    a, f, b = stats(g, p), stats(g[g.half == '前'], p), stats(g[g.half == '後'], p)
    return (f'{label:<20}{a[0]:>6}{a[1]:>7.0%}{a[2]:>7.0%}{a[3]:>+7.2f}{a[4]:>+7.2f}   '
            f'{f[0]:>5}{f[2]:>7.0%}{f[3]:>+7.2f}   {b[0]:>5}{b[2]:>7.0%}{b[3]:>+7.2f}')


HEAD = (f'{"":<20}{"筆":>6}{"1R":>7}{"1.5R":>7}{"R@1.5":>7}{"R@3":>7}   '
        f'{"前筆":>5}{"1.5R":>7}{"R@1.5":>7}   {"後筆":>5}{"1.5R":>7}{"R@1.5":>7}')
NUM = ['RSI', '離EMA20', '離EMA89', '離EMA200', 'EMA89斜率', '離30根高點', '100根振幅', '收盤位置', 'K棒長', '量比',
       '前5根最大量比', 'ATR相對', '今日漲跌%', '新低後根數', '離低點', '前100根已觸發', '前60根漲幅']
CAT = ['時段', '1h', '日線', 'TJ']


def buckets(g):
    """(feature, label, mask) for every condition bucket: categories as they are, numbers in quintiles."""
    out = []
    for col in CAT + NUM:
        if col not in g or g[col].isna().all():
            continue
        s = g[col]
        if col in CAT or s.nunique() <= 6:
            for k in sorted(s.dropna().unique()):
                lab = f'{col} {k:g}' if not isinstance(k, str) else f'{col} {k}'
                out.append((col, lab, (s == k).values))
        else:
            q = np.unique(s.quantile([0, .2, .4, .6, .8, 1]).values)
            for a, b in zip(q[:-1], q[1:]):
                m = (s >= a) & (s <= b) if b == q[-1] else (s >= a) & (s < b)
                out.append((col, f'{col} {a:.2f}~{b:.2f}', m.values))
    return out


def report(g, kind):
    print(f'\n######## {kind}（{len(g)} 筆，{g.t.min():%Y-%m-%d} .. {g.t.max():%Y-%m-%d}）')
    print(HEAD)
    if kind != '中繼急殺':
        print(line('低點停損（≥1ATR）', g, ''))
    print(line('1 ATR 停損', g))
    print('  隨機漫步（1 ATR 停損）：1R 50%、1.5R 40%、2R 33%、3R 25%')
    print('  每年 1.5R 命中（1 ATR）：' + '  '.join(f'{y} {(x.a_best >= 1.5).mean():.0%}' for y, x in g.groupby('year')))
    col0 = None
    for col, lab, m in buckets(g):
        if col != col0:
            print(f'-- {col}')
            col0 = col
        print(line(lab, g[m]))


def search(g, kind, lift=0.06, min_n=100, shuffles=30, seed=1):
    """Pairs of condition buckets (two different features) whose 1.5R hit (1-ATR stop) beats the type's own rate by
    `lift` in both halves, each half with at least `min_n` events. The same count with outcomes shuffled inside
    each half says how many such pairs luck alone produces."""
    B = buckets(g)
    M = np.column_stack([m for _, _, m in B]).astype(float)
    feat = np.array([f for f, _, _ in B])
    halves = [(g.half == h).values for h in ('前', '後')]
    y = (g.a_best >= 1.5).values.astype(float)
    diff = feat[:, None] != feat[None, :]
    iu = np.triu(np.ones((len(B), len(B)), bool), 1) & diff

    @np.errstate(all='ignore')          # macOS Accelerate flags spurious overflow on 0/1 matrix products
    def passing(yv):
        ok = iu.copy()
        rates = []
        for hm in halves:
            Mh, yh = M[hm], yv[hm]
            n = Mh.T @ Mh
            hit = Mh.T @ (Mh * yh[:, None])
            r = np.divide(hit, n, out=np.zeros_like(hit), where=n > 0)
            ok &= (n >= min_n) & (r >= yh.mean() + lift)
            rates.append((n, r))
        return ok, rates

    ok, rates = passing(y)
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(shuffles):
        ys = y.copy()
        for hm in halves:
            ys[hm] = rng.permutation(ys[hm])
        null.append(passing(ys)[0].sum())
    null = np.array(null)
    print(f'\n== {kind}：兩個條件組合，前後兩段 1.5R 命中都比自己高 {lift:.0%} 以上（每段至少 {min_n} 筆）')
    print(f'   找到 {ok.sum()} 組；把結果打亂 {shuffles} 次，運氣平均也會找到 {null.mean():.1f} 組（最多 {null.max()}）')
    idx = np.argwhere(ok)
    rows = []
    for a, b in idx:
        m = B[a][2] & B[b][2]
        x = g[m]
        rows.append(((x.a_best >= 1.5).mean(), B[a][1], B[b][1], x))
    rows.sort(key=lambda r: -r[0])
    for rate, la, lb, x in rows[:12]:
        print(line(f'{la} + {lb}'[:20], x) + f'   {la} + {lb}')
    return rows


def main():
    tf = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    path = os.path.join(HERE, 'data', f'rise_events_{tf}m.pkl')
    ev = pd.read_pickle(path) if os.path.exists(path) and '--rebuild' not in sys.argv else build(tf)
    print(f'NQ {tf}m，做多收盤進場，成本 {COST:g} 點；R@1.5 / R@3 = 1.5R / 3R 出場的每筆 R；條件表用 1 ATR 停損')
    for kind in ('慢跌收復', '急跌反轉', '中繼急殺'):
        g = ev[ev.kind == kind]
        if '--search' in sys.argv:
            search(g, kind)
        else:
            report(g, kind)


if __name__ == '__main__':
    main()
