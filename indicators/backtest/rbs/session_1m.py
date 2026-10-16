"""NQ 1m with (40,0,13,1) and (50,0,15,1): Trend Judge strong / normal / both + 1h, by session (RTH, overnight, Asia 20:00-03:00 ET).
Basis of the "1 分亞洲盤快訊" in remis_buy_sell.pine.

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/session_1m.py
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore')
import numpy as np, pandas as pd
from rbs import prepared
from setup_study import bar_context, hourly, seq, COST, SPLIT
from param_compare import sigs, table
H = hourly(); df = prepared('NQ', 1); nxt, atr = bar_context(df, 1)
days = (df.datetime[df.tradable].dt.tz_convert('America/New_York') + pd.Timedelta(hours=6)).dt.date.astype(str).nunique()
LV = {'強趨勢 + 1h': lambda x: (x.side * x.dir == 2) & (x.side == x.h1), '一般趨勢 + 1h': lambda x: (x.side * x.dir == 1) & (x.side == x.h1),
      '順勢合計 + 1h': lambda x: (x.side * x.dir >= 1) & (x.side == x.h1)}
SE = {'現金盤': lambda x: x.rth, '夜盤': lambda x: ~x.rth, '夜盤不含亞洲': lambda x: ~x.rth & ~x.asia, '亞洲盤 20-03': lambda x: x.asia}
for st, el in ((40, 13), (50, 15)):
    B, S = sigs(df, st, el, True); t = table(df, 1, B, S, H, atr, nxt).sort_values('i')
    print(f'\n######## 1m ({st},0,{el},1)')
    for lvl, f in LV.items():
        for sn, g in SE.items():
            for R in (1.0, 2.0, 3.0):
                q = seq(t[f(t) & g(t)], R); r = q[f'r{R:g}']; net = r - COST / q.risk; a = q.date < SPLIT
                print(f'  {lvl:<10} {sn:<8} {R:g}R  {len(q):4d} 筆 {len(q)/days:3.1f}/天 勝率 {100*(r>0).mean():4.1f}% 淨 {net.mean():+.3f}±{net.std()/np.sqrt(len(q)):.3f}'
                      f'（前 {net[a].mean():+.3f} 後 {net[~a].mean():+.3f}） 停損中位 {q.risk.median():.1f}')
