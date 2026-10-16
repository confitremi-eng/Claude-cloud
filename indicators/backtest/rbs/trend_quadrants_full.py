"""NQ 1m / 2m over the Databento year: Remi's Buy/Sell split by Trend Judge state, all hours / RTH / overnight.

  NQ_DATA=data/NQ_1m_databento.csv python3 trend_quadrants_full.py

NQ_DATA is the continuous file from build_databento.py. Same rules and table as trend_quadrants_tv.py
(1R / 1.5R / 2R / 3R, Trend Judge estimated from 1-minute closes). Then the normal quadrants (UP + Buy,
DOWN + Sell) at 2R against all signals of the same hours, a random-subset check, the two halves, and months.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore')
import numpy as np, pandas as pd
from trend_quadrants_tv import trades, report, TARGETS
from rbs import prepared, COST
from remi_export import signals
rng = np.random.default_rng(0)
for tf in (1, 2):
    df = prepared('NQ', tf); B, S = signals(df); t = trades(df, B, S)
    t = t[df.tradable.values[t.i]].reset_index(drop=True); t['dir'] = df.tj_dir.values[t.i]
    et = pd.DatetimeIndex(df.datetime.values[t.i]).tz_localize('UTC').tz_convert('America/New_York')
    m = et.hour * 60 + et.minute; t['rth'] = (m >= 570) & (m < 960); t['mon'] = et.strftime('%y-%m')
    t['half'] = np.where(et < pd.Timestamp('2026-04-01', tz='America/New_York'), 'A', 'B')
    t['grp'] = np.where(t.side * t.dir == 1, '一般', np.where(t.side * t.dir == 2, '強勢', np.where(t.dir == 0, 'MIX', '逆勢')))
    print(f'\n################ NQ {tf}m Databento {et[0]:%Y-%m-%d} .. {et[-1]:%Y-%m-%d}')
    report(f'{tf}m 全部時段', t, COST['NQ'])
    report(f'{tf}m 美股盤中 09:30-16:00', t[t.rth].reset_index(drop=True), COST['NQ'])
    report(f'{tf}m 其他時段（夜盤）', t[~t.rth].reset_index(drop=True), COST['NQ'])
    g = t[t.grp == '一般']
    for lab, x in (('全部', t), ('盤中', t[t.rth]), ('夜盤', t[~t.rth])):
        n = x[x.grp == '一般']
        sims = np.array([x.r2.values[rng.choice(len(x), len(n), replace=False)].mean() for _ in range(5000)])
        se = n.r2.std(ddof=1) / np.sqrt(len(n))
        print(f'  一般兩象限 {lab}: n {len(n)}  2R {n.r2.mean():+.3f} ±{se:.3f}  vs 同時段全部 {x.r2.mean():+.3f}  隨機抽樣一樣好的比例 {(sims >= n.r2.mean()).mean():.3f}')
    print('  前後半（2025-10..2026-03 / 2026-04..10）一般兩象限 2R:',
          {h: f'{x.r2.mean():+.3f} ({len(x)})' for h, x in g.groupby('half')}, ' 全部:', {h: f'{x.r2.mean():+.3f}' for h, x in t.groupby('half')})
    mm = t.groupby('mon').apply(lambda x: pd.Series({'全部2R': x.r2.mean(), '一般n': (x.grp == '一般').sum(), '一般2R': x[x.grp == '一般'].r2.mean(),
                                                     '一般3R': x[x.grp == '一般'].r3.mean(), '強勢2R': x[x.grp == '強勢'].r2.mean()}))
    print(mm.round(2).to_string())
    print(f'  一般兩象限 2R 為正的月份 {(mm.一般2R > 0).sum()}/{len(mm)}，全部訊號 {(mm.全部2R > 0).sum()}/{len(mm)}')
