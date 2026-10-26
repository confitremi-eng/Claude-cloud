"""QQQ 1m strategy as traded now (NQ RTH 1m chart + v3 strategy + autotrade, MNQ 2 contracts), the last year in detail.

  cd indicators/backtest
  python3 -I rbs/qqq1m_year.py [start date, default the v3 year]

Setups on one shared position (one at a time, first come; same-bar order trend > 高開低走 > 大低開買):
  趨勢     (35, 0, 8, 1), Trend Judge 20 / 40, 1h EMA20, stop >= 1 ATR, slow line <= 7 ATR, NQ 2m not opposite,
           buys within 1.0 ATR of the 5s fast line; two-bar stop; 3R
  超強買   Trend Judge > 120, stage 10, buys only; two-bar stop; 3R
  高開低走 gap up >= 0.75%, first 2 minutes down but above the previous close -> short 09:32; stop at their high; 1R
  大低開買 gap down >= 1.1%, first up 5-minute bar after 09:45 -> buy; stop at the day's low; 1R
Events, FOMC days, Friday cut-off as v3 (the two gap setups ignore the event windows, as the strategy does).
Exits as the strategy's default two groups: 2 contracts, one at 1R, one at the setup's target (both at 1R when the
target is 1R), stop first when both are touched in a bar, flat after 60 bars or at the 16:00 close. 1 point cost per
contract. Writes data/qqq1m_year.json for the report page.
"""
import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import gapdown_long as gl

COST, USD = 1.0, 2.0


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else oc.YEARS[-1][1]
    one = oc.load()
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    df = oc.chart(cash, tdq, 1, 20.0, 40.0)
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    dts = pd.DatetimeIndex(df.datetime); dts = dts.tz_localize('UTC') if dts.tz is None else dts
    ny = dts.tz_convert(ss.NY); bm = np.asarray(ny.hour * 60 + ny.minute); dday = np.asarray(ny.strftime('%Y-%m-%d'))
    tw = (dts + pd.Timedelta(minutes=1)).tz_convert('Asia/Taipei')
    late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
    # NQ 2m (24-hour) Trend Judge direction for the not-opposite filter
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    fast = df.emaS.values + df.tj_diff.values

    sig = {}                                               # bar -> (setup, side, stop, R)
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
    far = (s.side == 1) & ((c[s.i] - fast[s.i]) / atr[s.i] > 1.0)
    T = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0)
          & ~late[s.i] & ~s.date.isin(ss.FOMC) & ~far]
    for i, sd in zip(T.i.values, T.side.values):
        sig.setdefault(int(i), ('趨勢', int(sd), (min(l[i - 1], l[i]) if sd == 1 else max(h[i - 1], h[i])), 3.0))
    x = mm.trend_signals(df, Hq, 1, 10, 8)
    x = x[(x.side == 1) & (x.spread > 120) & ~ss.EVT(x) & ~x.date.isin(ss.FOMC) & ~late[x.i]]
    for i in x.i.values:
        sig.setdefault(int(i), ('超強買', 1, min(l[i - 1], l[i]), 3.0))
    # gap setups (per cash day)
    days = pd.Series(np.arange(len(c))).groupby(dday).agg(['first', 'last'])
    prev = None
    for d, (a, b) in days.iterrows():
        if prev is not None and bm[a] == 570 and b - a > 200:
            gap = 100 * (o[a] / prev - 1)
            if gap >= 0.75 and bm[a + 1] == 571:                 # 高開低走
                j = a + 1; fh = max(h[a], h[a + 1])
                if c[j] < o[a] and c[j] > prev and not late[j] and d not in ss.FOMC:
                    sig.setdefault(int(j), ('高開低走', -1, fh + 0.25, 1.0))
            if gap <= -1.1:                                         # 大低開買
                for s0 in range(585, 720, 5):
                    w = np.flatnonzero((bm[a:b + 1] >= s0) & (bm[a:b + 1] < s0 + 5)) + a
                    if len(w) < 5: continue
                    if c[w[-1]] > o[w[0]]:
                        j = int(w[-1]); sig.setdefault(j, ('大低開買', 1, l[a:j + 1].min() - 0.25, 1.0)); break
        prev = c[b]
    # simulate one position, two groups
    trades = []; pos = None
    lastbar = np.r_[dday[1:] != dday[:-1], True] | (bm + 1 >= 960)
    for j in range(len(c)):
        if pos is not None and j > pos['i']:
            sd = pos['side']; st = pos['stop']; done = False
            for leg in pos['legs']:
                if leg['r'] is not None: continue
                if (l[j] <= st) if sd == 1 else (h[j] >= st): leg['r'] = -1.0
                elif (h[j] >= leg['px']) if sd == 1 else (l[j] <= leg['px']): leg['r'] = leg['R']
            if all(g['r'] is not None for g in pos['legs']): done = True
            elif j - pos['i'] >= 60 or lastbar[j]:
                for leg in pos['legs']:
                    if leg['r'] is None: leg['r'] = (c[j] - pos['e']) * sd / pos['risk']
                done = True
            if done:
                legs = [g['r'] for g in pos['legs']]
                trades.append(dict(date=dday[pos['i']], tw=str(tw[pos['i']]), et=int(bm[pos['i']] + 1), setup=pos['setup'], side=sd,
                                   entry=pos['e'], risk=pos['risk'], legs=legs, R=float(np.mean(legs)),
                                   net=float(np.mean(legs)) - COST / pos['risk'], pts=float(sum(r * pos['risk'] for r in legs) - 2 * COST), bars=j - pos['i']))
                pos = None
        if pos is None and j in sig and not lastbar[j]:
            setup, sd, st, R = sig[j]; e = c[j]; risk = (e - st) * sd
            if risk <= 0: continue
            legs = [dict(R=1.0, px=e + sd * risk, r=None), dict(R=R, px=e + sd * R * risk, r=None)]
            pos = dict(i=j, setup=setup, side=sd, e=e, stop=st, risk=risk, legs=legs)
    t = pd.DataFrame(trades)
    t = t[t.date >= start].reset_index(drop=True)
    print(f'NQ RTH 1m（QQQ 策略），{t.date.min()} .. {t.date.max()}，MNQ 2 口（兩組出場），每口扣 {COST:g} 點')
    eq = np.cumsum(t.pts.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    print(f'  合計 {len(t)} 筆，勝率 {100 * (t.pts > 0).mean():.0f}%，淨 {t.net.sum():+.1f}R、{t.pts.sum():+.0f} 點（{USD * t.pts.sum():+,.0f} 美元），最大回撤 {dd:.0f} 點（{USD * dd:,.0f} 美元）')
    for kd, z in t.groupby('setup'):
        print(f'  {kd}：{len(z)} 筆，勝率 {100 * (z.pts > 0).mean():.0f}%，到 1R {100 * np.mean([g[0] >= 1 for g in z.legs]):.0f}%，淨 {z.net.sum():+.1f}R、{z.pts.sum():+.0f} 點，停損中位 {z.risk.median():.0f} 點')
    json.dump(dict(start=t.date.min(), end=t.date.max(), trades=t.to_dict('records'), dd=dd),
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'qqq1m_year.json'), 'w', encoding='utf-8'), ensure_ascii=False, default=float)


if __name__ == '__main__':
    main()
