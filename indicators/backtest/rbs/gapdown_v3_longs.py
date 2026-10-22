"""Big gap-down mornings: v3's QQQ / NQ RTH 1m buy signals that the trend filters block. (NQ cash-session 1m bars)

  cd indicators/backtest
  python3 -I rbs/gapdown_v3_longs.py

Raw (35, 0, 8, 1) buy signals entered 09:45-12:00 on days that open <= -0.75% below the previous close; how often each
v3 filter passes, and their results with only the non-trend filters kept (stop >= 0.95 ATR, slow line <= 7 ATR, event
windows, no FOMC days), one at a time, 1 point cost. Control: the same on flat-open days (|gap| <= 0.3%).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import setup_study as ss, market_matrix as mm, gapdown_v3 as gv
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'NQ_1m_databento.csv')
one = mm.read_csv(path); one['bad'] = False
cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
df = mm.chart(cash, tdq, 1, 20.0, 40.0)
t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
s = mm.trend_signals(df, Hq, 1, 35, 8)
k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
s['nq'] = ndir[k] * s.side.values
et = pd.DatetimeIndex(df.datetime.values[s.i.values]); et = (et.tz_localize('UTC') if et.tz is None else et).tz_convert(ss.NY) + pd.Timedelta(minutes=1)
s['emin'] = et.hour * 60 + et.minute; s['day'] = et.strftime('%Y-%m-%d')
s['gap'] = s.day.map(gv.day_gaps(cash))
L = s[(s.side == 1) & (s.gap <= -0.75) & (s.emin >= 585) & (s.emin < 720) & ~s.date.isin(ss.FOMC)].sort_values('i')
base = (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 7.0)
conds = {'TJ 同向': s.spread > 20, '1h 同向': s.side == s.h1, 'NQ 2m 不反向': s.nq >= 0}
print(f'大低開日 09:45–12:00 的原始買訊：{len(L)} 個（{L.day.nunique()} 天）')
for nm, m in conds.items(): print(f'  {nm} 通過 {100*m[L.index].mean():3.0f}%')
def ln(lab, z):
    if not len(z): print(f'  {lab:<28}   0'); return
    q = ss.seq(z, 1.0); n1 = q.r1 - 1/q.risk; q3 = ss.seq(z, 3.0); n3 = q3.r3 - 1/q3.risk
    print(f'  {lab:<28}{len(z):4d} 個 一次一筆 1R {len(q):3d} 筆 勝 {100*(q.r1>0).mean():3.0f}% {n1.sum():+5.1f}R ｜ 3R {n3.sum():+5.1f}R')
b = base[L.index]
ln('不過濾', L)
ln('只留停損/距離/時段', L[b])
ln('  + 只拿掉 TJ（留 1h、NQ2m）', L[b & conds['1h 同向'][L.index] & conds['NQ 2m 不反向'][L.index]])
ln('  + 只拿掉 1h', L[b & conds['TJ 同向'][L.index] & conds['NQ 2m 不反向'][L.index]])
ln('  + 只拿掉 NQ 2m', L[b & conds['TJ 同向'][L.index] & conds['1h 同向'][L.index]])
ln('  + 只要 TJ 同向', L[b & conds['TJ 同向'][L.index]])
# control: same raw longs on flat days
F = s[(s.side == 1) & (s.gap.abs() <= 0.3) & (s.emin >= 585) & (s.emin < 720) & ~s.date.isin(ss.FOMC)].sort_values('i')
ln('對照 平開日 不過濾', F); ln('對照 平開日 停損/距離/時段', F[base[F.index]])
print('\n--- 大低開早盤原始買訊（只留停損/距離/時段）')
Z = L[b]
days = sorted(s.day.unique()); mid = days[len(days)//2]
for nm, z in (('前半', Z[Z.day < mid]), ('後半', Z[Z.day >= mid])): ln(nm, z)
for gm in (-0.5, -0.75, -1.0):
    z = s[(s.side == 1) & (s.gap <= gm) & (s.emin >= 585) & (s.emin < 720) & ~s.date.isin(ss.FOMC)]
    ln(f'缺口 ≤ {gm:g}%', z[base[z.index]])
for a, bb in ((585, 630), (630, 660), (660, 720)):
    ln(f'{a//60}:{a%60:02d} 起', Z[(Z.emin >= a) & (Z.emin < bb)])
q = ss.seq(Z, 2.0); print(f'  2R 一次一筆 {len(q)} 筆 勝 {100*(q.r2>0).mean():.0f}% {(q.r2 - 1/q.risk).sum():+.1f}R')
first = Z.groupby('day').head(1); ln('每天只做第一個', first)
print('  停損中位', Z.risk.median(), '點')
import gapdown_long as gl
t, _ = gl.build(gl.load(path)); orb = t[(t.setup == 'ORB 5') & (t.gap <= -0.75)]
print(f'  ORB 5 的 {orb.date.nunique()} 天 vs 這組 {Z.day.nunique()} 天，重疊 {len(set(orb.date) & set(Z.day))} 天')
