"""NQ 2m: when do the normal Trend Judge quadrants (UP + Buy, DOWN + Sell) work?

  python3 trend_regime.py NQ_1M.csv NQ_2M.csv

Months of the clean data (rbs.py) plus the TradingView export period, side by side: RTH daily range,
open-to-close move, efficiency (net move / path), share of Trend Judge states, and the trade results
(trend_quadrants_tv.py rules). Then the trades split by conditions known before the trade day (last 10
days' range / move / efficiency, previous day's range; cut points from the clean data only), the
normal quadrants by session, and a random-subset check.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np, pandas as pd
ONE, TWO = sys.argv[1], sys.argv[2]
from trend_quadrants_tv import trades, load_tv, warm_mask
from rbs import prepared, trend_diff_minutes, trend_judge
from remi_export import signals
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)

# ---- 2m bars + Trend Judge + trades for both datasets ----
c2 = prepared('NQ', 2).copy(); c2 = c2[c2.tradable].reset_index(drop=True)
d1 = load_tv(ONE); d2 = load_tv(TWO)
tdm1 = trend_diff_minutes(d1.set_index('datetime')[['open', 'high', 'low', 'close']])
two = d2.set_index(d2.datetime + pd.Timedelta(minutes=1))[['open', 'high', 'low', 'close']]
tdm2 = trend_diff_minutes(two)
b2 = d2[['datetime', 'open', 'high', 'low', 'close']].copy(); b2['last_min'] = b2.datetime + pd.Timedelta(minutes=1)
b2 = trend_judge(b2, tdm2, 2, 'NQ')
m = b2.last_min.isin(tdm1.index) & warm_mask(b2.datetime, 4)
b2x = trend_judge(b2[['datetime', 'open', 'high', 'low', 'close', 'last_min']], tdm1.reindex(tdm1.index.union(b2.last_min)), 2, 'NQ')
b2.loc[m, 'tj_dir'] = b2x.tj_dir[m]; b2.loc[m, 'tj_diff'] = b2x.tj_diff[m]
b2['B'], b2['S'] = d2['BUY 訊號'].values, d2['SELL 訊號'].values
b2 = b2[warm_mask(b2.datetime)].reset_index(drop=True)
B, S = signals(c2); c2['B'], c2['S'] = B, S

def build(df, tag):
    df = df.copy()
    et = df.datetime.dt.tz_convert('America/New_York'); mm = et.dt.hour * 60 + et.dt.minute
    df['date'] = et.dt.date; df['rth'] = (mm >= 570) & (mm < 960)
    df['per'] = tag if tag == 'TV' else et.dt.strftime('%m')
    t = trades(df, df.B.values, df.S.values)
    t['dir'] = df.tj_dir.values[t.i]; t['date'] = df.date.values[t.i]; t['per'] = df.per.values[t.i]; t['rth'] = df.rth.values[t.i]
    t['grp'] = np.where(t.side * t.dir == 1, '一般', np.where(t.side * t.dir == 2, '強勢', np.where(t.dir == 0, 'MIX', '逆勢')))
    return df, t
c2, tc = build(c2, 'clean'); b2, tt = build(b2, 'TV')
bars = pd.concat([c2, b2], ignore_index=True); T = pd.concat([tc, tt], ignore_index=True)

# ---- daily RTH stats ----
r = bars[bars.rth]
day = r.groupby('date').agg(o=('open', 'first'), h=('high', 'max'), l=('low', 'min'), c=('close', 'last'), n=('close', 'size'), per=('per', 'first'))
path = r.groupby('date').close.apply(lambda x: np.abs(np.diff(x.values)).sum())
day = day[day.n >= 150]                                       # full RTH days (195 two-minute bars)
day['range'] = 100 * (day.h - day.l) / day.o
day['move'] = 100 * (day.c - day.o) / day.o
day['er'] = (day.c - day.o).abs() / path.reindex(day.index)  # efficiency: net move / path
st = r.groupby('per').apply(lambda g: pd.Series({
    '一般%': 100 * (g.tj_dir.abs() == 1).mean(), '強%': 100 * (g.tj_dir.abs() == 2).mean(), 'MIX%': 100 * (g.tj_dir == 0).mean(),
    '|差值|中位': np.nanmedian(np.abs(g.tj_diff)), '2m K幅%': 100 * ((g.high - g.low) / g.close).median()}))
dd = day.groupby('per').agg(天數=('range', 'size'), 日幅度=('range', 'mean'), 日漲跌絕對=('move', lambda x: x.abs().mean()),
                             淨漲跌=('move', 'sum'), 效率=('er', 'mean'))
def res(g):
    a, n_ = g, g[g.grp == '一般']
    return pd.Series({'全部筆': len(a), '全部2R': a.r2.mean(), '一般筆': len(n_), '一般1R': n_.r1.mean(), '一般2R': n_.r2.mean(), '一般3R': n_.r3.mean(),
                      '強2R': g[g.grp == '強勢'].r2.mean()})
rr = T.groupby('per').apply(res)
out = dd.join(st).join(rr)
print(out.round(3).to_string())
print('\n跨期相關 (各期 一般2R 對):', {k: round(np.corrcoef(out[k], out['一般2R'])[0, 1], 2) for k in ['日幅度', '日漲跌絕對', '效率', '一般%', '強%', 'MIX%', '|差值|中位', '2m K幅%']})

# ---- trade-level, using only information known before the trade day ----
day = day.sort_index()
day['prev10_range'] = day.range.rolling(10, min_periods=5).mean().shift()
day['prev10_absmove'] = day.move.abs().rolling(10, min_periods=5).mean().shift()
day['prev10_er'] = day.er.rolling(10, min_periods=5).mean().shift()
day['prev_range'] = day.range.shift()
T = T.join(day[['prev10_range', 'prev10_absmove', 'prev10_er', 'prev_range']], on='date')
clean_days = day[day.per != 'TV']
for k in ['prev10_range', 'prev10_absmove', 'prev10_er', 'prev_range']:
    q = clean_days[k].quantile([1 / 3, 2 / 3]).values                  # cut points from the 2-9 month days only
    T['b'] = np.where(T[k] <= q[0], '低', np.where(T[k] <= q[1], '中', '高'))
    print(f'\n{k}（切點取自 2–9 月：{q[0]:.2f} / {q[1]:.2f}）  2R 平均（筆數）')
    for part, P in (('2-9月', T[T.per != 'TV']), ('9/8-10/15', T[T.per == 'TV'])):
        cells = []
        for b in ('低', '中', '高'):
            g = P[(P.b == b) & P[k].notna()]; n_ = g[g.grp == '一般']
            cells.append(f'{b}: 全部 {g.r2.mean():+.2f} ({len(g):3d}) 一般 {n_.r2.mean():+.2f} ({len(n_):3d})')
        tv_share = (T[(T.per == 'TV') & T[k].notna()].b.value_counts(normalize=True) * 100).round(0).to_dict() if part == '9/8-10/15' else ''
        print(f'  {part:<10} ' + '  |  '.join(cells) + (f'   這個月交易日分布 {tv_share}' if tv_share else ''))

print('\n--- 檢查 ---')
o = out.drop(index='09')
print('跨期相關（排除只有 1 天的 9 月）:', {k: round(np.corrcoef(o[k], o['一般2R'])[0, 1], 2) for k in ['日幅度', '日漲跌絕對', '效率', '一般%', '強%', '|差值|中位']})
for part, P in (('2-9月', T[T.per != 'TV']), ('9/8-10/15', T[T.per == 'TV'])):
    g = P[P.grp == '一般']
    for lab, x in (('盤中', g[g.rth]), ('其他時段', g[~g.rth]), ('全部', g)):
        print(f'  {part:<10} 一般兩象限 {lab:<5} n {len(x):3d}  2R {x.r2.mean():+.3f} ± {x.r2.std(ddof=1) / np.sqrt(len(x)):.3f}  3R {x.r3.mean():+.3f}')
g = T[(T.per != 'TV') & (T.grp == '一般')]
print('  2-9月 每月 2R 標準誤約 ±', round(g.r2.std(ddof=1) / np.sqrt(g.groupby('per').size().median()), 2), '（每月中位數', int(g.groupby('per').size().median()), '筆）')

rng = np.random.default_rng(0); h = T[T.per != 'TV']; g = h[h.grp == '一般']
sims = np.array([h.r2.values[rng.choice(len(h), len(g), replace=False)].mean() for _ in range(5000)])
print(f'  2-9月 隨機抽 {len(g)} 筆的 2R 平均 ≥ 一般兩象限 ({g.r2.mean():+.3f}) 的比例 {(sims >= g.r2.mean()).mean():.3f}')
