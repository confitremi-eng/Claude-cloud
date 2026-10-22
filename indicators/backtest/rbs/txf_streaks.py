"""Remi TXF (2m): how often do stops come in a row, and which simple rule avoids the streaks without giving up the edge?

  cd indicators/backtest
  python3 -I rbs/txf_streaks.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Signals as the indicator: super-trend sells (Trend Judge below -90, stage 3, event windows avoided, trend under 400
minutes) + v3 TXF trend signals ((20, 0, 8, 1), Trend Judge 30, 1h EMA20, stop >= 1 ATR, slow line <= 3 ATR, 60-120
minutes); two-bar stop, 3R, 60 bars, one at a time, 2 points cost. Data as txf_super_grid.py.
Part 1: losing-streak lengths, worst drawdown. Part 2: rules applied while trading (they depend on earlier results):
  停 N 次就休息到下一盤     after N stops in a row, no new trade until the next session (day 08:45 / night 15:00)
  一盤最多停 N 次           at most N stops per session
  停損後冷卻 K 根           no new trade for K bars after a stop
  再進要比上一筆好           after a stop on a sell, the next sell must enter below the stopped one's entry (buys: above)
  TJ 回升就不做             super sells only while Trend Judge is within X of its lowest value in this trend
Per year: 3R win rate / net R, then max streak and max drawdown.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import txf_check as tx

COST = 2.0


def load(args):
    tv = None
    if '--tv' in args: k = args.index('--tv'); tv = args[k + 1]; del args[k:k + 2]
    one = tx.read_sql_1m(args)[['open', 'high', 'low', 'close']]; one['bad'] = tx.roll_mask(one.index)
    if tv:
        r = pd.read_csv(tv, usecols=[0, 1, 2, 3, 4]); r.index = pd.DatetimeIndex(pd.to_datetime(r.time, unit='s', utc=True))
        r = r[r.index > one.index[-1]][['open', 'high', 'low', 'close']]
        r['bad'] = r.index < r.index[0] + pd.Timedelta(days=5)
        one = pd.concat([one, r])
    return one


def run(T, df, sess, rule=None, arg=None):
    """Trade signals one at a time with an optional rule. T: signals with i, side, x3 (exit bar), r3, risk, kind, tj."""
    out = []; busy = -1; streak = 0; s_loss = {}; last_stop = (None, -10 ** 9, None)
    for row in T.itertuples():
        i = row.i
        if i < busy: continue
        sid = sess[i]
        if rule == 'streak' and streak >= arg and last_stop[2] == sid: continue
        if rule == 'session' and s_loss.get(sid, 0) >= arg: continue
        if rule == 'cool' and i - last_stop[1] < arg: continue
        if rule == 'better' and last_stop[0] is not None and last_stop[2] == sid and row.side == last_stop[0][0] and (df.close.values[i] - last_stop[0][1]) * row.side >= 0: continue
        if rule == 'tjfade' and row.kind == '超強' and row.tj_off > arg: continue
        out.append(row); busy = row.x3
        if row.r3 < 0:
            streak = streak + 1 if last_stop[2] == sid else 1          # stops in a row within this session
            s_loss[sid] = s_loss.get(sid, 0) + 1
            last_stop = ((row.side, df.close.values[i]), row.x3, sid)
        else:
            streak = 0
    t = pd.DataFrame(out)
    t['n'] = t.r3 - COST / t.risk
    return t


def summary(t):
    loss = (t.r3 < 0).values; best = cur = 0; runs = []
    for x in loss:
        if x: cur += 1
        else:
            if cur: runs.append(cur)
            cur = 0
        best = max(best, cur)
    if cur: runs.append(cur)
    eq = np.cumsum(t.n.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    return best, dd, runs


def main():
    one = load(sys.argv[1:])
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    df = mm.chart(one, tdm, 2, 30.0, 60.0)
    tw = pd.DatetimeIndex(df.datetime); tw = (tw.tz_localize('UTC') if tw.tz is None else tw).tz_convert('Asia/Taipei') + pd.Timedelta(minutes=2)
    mins = tw.hour * 60 + tw.minute
    s0 = np.where((mins > 525) & (mins <= 825), tw.floor('D').strftime('%Y-%m-%d') + ' 日', np.where(mins > 900, tw.floor('D').strftime('%Y-%m-%d') + ' 夜',
                  (tw.floor('D') - pd.Timedelta(days=1)).strftime('%Y-%m-%d') + ' 夜'))
    sess = np.asarray(s0)
    tj = df.tj_diff.values
    s = mm.trend_signals(df, H, 2, 20, 8); base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)].assign(kind='趨勢')
    x = mm.trend_signals(df, H, 2, 3, 8); x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 400) & (x.spread > 90) & ~x.i.isin(base.i)].assign(kind='超強')
    # how far Trend Judge has come back up from its lowest value since this down trend began
    low = np.full(len(tj), np.nan); cur = np.nan
    for k in range(len(tj)):
        if not np.isfinite(tj[k]) or tj[k] > -30: cur = np.nan
        else: cur = tj[k] if not np.isfinite(cur) else min(cur, tj[k])
        low[k] = cur
    T = pd.concat([base, x]).sort_values('i')
    T['tj_off'] = tj[T.i.values] - low[T.i.values]
    yrs = sorted(T.date.str[:4].unique())

    t = run(T, df, sess)
    best, dd, runs = summary(t)
    print(f'Remi TXF（趨勢 + 超強賣 TJ 90 / 階段 3，3R），{len(t)} 筆，到 {tw[-1]:%Y-%m-%d}')
    vc = pd.Series(runs).value_counts().sort_index()
    print('連續停損次數分布：' + '、'.join(f'{k} 次 {v} 回' for k, v in vc.items()))
    print(f'最長連續停損 {best} 次，最大回撤 {dd:.1f}R')
    # where do long streaks happen
    t['sess'] = sess[t.i.values]; t['tw'] = [tw[i] for i in t.i]
    lo = (t.r3 < 0).astype(int).values; ids = np.cumsum(np.r_[1, (lo[1:] != lo[:-1])])
    t['grp'] = ids
    g = t[t.r3 < 0].groupby('grp').agg(n=('r3', 'size'), start=('tw', 'first'), end=('tw', 'last'), sess=('sess', 'nunique'), kinds=('kind', lambda z: '/'.join(sorted(set(z)))))
    print('\n連續停損 ≥ 5 次的時段：')
    for r in g[g.n >= 5].itertuples(): print(f'   {r.start:%Y-%m-%d %H:%M} .. {r.end:%m-%d %H:%M}  {r.n} 次，跨 {r.sess} 盤，{r.kinds}')
    same = t[t.r3 < 0].groupby('sess').size()
    print(f'\n同一盤停損次數：' + '、'.join(f'{k} 次 {v} 盤' for k, v in same.value_counts().sort_index().items()))

    print(f'\n######## 規避方法（一次一筆，3R，每格：勝率 / 淨 R / 筆數）')
    print(f'   {"":<24}' + ''.join(f'{y:>18}' for y in yrs) + f'{"合計":>18}{"最長連停":>8}{"最大回撤":>8}')
    rules = [('現在', None, None)] + [(f'停 {n} 次就休息到下一盤', 'streak', n) for n in (2, 3, 4)] + \
            [(f'一盤最多停 {n} 次', 'session', n) for n in (1, 2, 3)] + [(f'停損後冷卻 {k} 根', 'cool', k) for k in (2, 3, 5, 8, 10, 15, 30)] + \
            [('再進要比上一筆好（同盤）', 'better', None)] + [(f'超強賣：TJ 回升 < {v} 才做', 'tjfade', v) for v in (20, 40, 60)]
    for lab, rule, arg in rules:
        t = run(T, df, sess, rule, arg); best, dd, _ = summary(t)
        cells = [t[t.date.str[:4] == y] for y in yrs] + [t]
        print(f'   {lab:<24}' + ''.join(f'{100 * (z.r3 > 0).mean():6.0f}% {z.n.sum():+5.1f}R {len(z):3d}' for z in cells) + f'{best:7d}{dd:9.1f}R', flush=True)


if __name__ == '__main__':
    main()
