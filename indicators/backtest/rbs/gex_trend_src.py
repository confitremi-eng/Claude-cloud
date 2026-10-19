"""GEX setup on NQ RTH: which trend should it read -- NQ RTH's own Trend Judge, or the 24-hour (ETH) one?

  cd indicators/backtest
  python3 -I rbs/gex_trend_src.py

Signals: (35, 0, 8, 1) on NQ 1-minute cash-session bars, QQQ below its gamma flip for buys / above for sells
(ZeroGEX, 2026-06-29 .. 10-14). Trend filters compared:
  RTH 1m      Trend Judge from the cash-session bars only (what v3's GEX setup reads on an RTH chart), threshold 20
  ETH 1m      Trend Judge from the 24-hour NQ minutes at the same minute (threshold 10, 2-minute lock)
  ETH 2m      the previous completed 24-hour NQ 2-minute bar (v3's 「NQ 2m」 row), threshold 10
plus both, and none. Each signal on its own (two-bar stop, 60-bar exit or 16:00), then one at a time; 1 point cost.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import strong_stage as sg
import gex_trend as gt
import qqq_3008 as q3


def main(stage=35, ema=8, cost=1.0):
    one = mm.load_market('qqq', []); tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, 20.0, 40.0)
    s = mm.trend_signals(df, H, 1, stage, ema)
    s = s[(s.date >= '2026-06-29') & (s.date <= '2026-10-14')].copy()
    s = pd.concat([s, gt.feats(df, s)], axis=1); s = s[s.QQQ_flip.notna() & (s.flip_d < 0)]
    # ETH 1m Trend Judge at the signal's last minute, locked every 2 minutes like the chart
    nq = mm.load_market('nq', []); te = mm.minute_trend(nq)['diff']
    lock = te.copy(); lock[te.index.minute % 2 == 1] = np.nan; lock = lock.ffill()
    lm = pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC')
    eth = lock.reindex(lm).values * s.side.values
    s['rth'] = np.sign(s.dir.values) * s.side.values
    s['eth1'] = np.where(eth > 10, 1, np.where(eth < -10, -1, 0))
    s['eth2'] = q3.nq_rel(df, s, sg.nq2m_dir())
    d = sorted(s.date.unique()); split = d[len(d) // 2]
    R = lambda y, nm: print(f'   {nm:<30} ' + mm.row_ind(y, cost, split))
    print(f'({stage}, 0, {ema}, 1) NQ RTH 1 分 K，朝 QQQ gamma flip 走，{d[0]} .. {d[-1]}（{len(d)} 天），每筆扣 {cost:g} 點')
    print(f'   {"":<30}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    rows = [('不看趨勢', s.side != 0), ('RTH 1m 順勢（v3 現在）', s.rth > 0), ('ETH 1m 順勢', s.eth1 > 0),
            ('ETH 2m 順勢', s.eth2 > 0), ('ETH 2m 不逆勢（同向或 MIX）', s.eth2 >= 0),
            ('RTH 1m + ETH 1m 都順勢', (s.rth > 0) & (s.eth1 > 0)), ('RTH 1m + ETH 2m 都順勢', (s.rth > 0) & (s.eth2 > 0)),
            ('RTH 1m 順勢 + ETH 2m 不逆勢', (s.rth > 0) & (s.eth2 >= 0)), ('RTH 1m 順勢、ETH 1m 不是', (s.rth > 0) & (s.eth1 <= 0)),
            ('ETH 1m 順勢、RTH 1m 不是', (s.eth1 > 0) & (s.rth <= 0))]
    for nm, m in rows:
        R(s[m], nm)
    print('  一次一筆 3R')
    for nm, m in rows[:8]:
        t = ss.seq(s[m].sort_values('i'), 3.0)
        n = t.r3.values - cost / t.risk.values; eq = np.cumsum(n)
        dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq) if len(eq) else 0
        print(f'   {nm:<30} {len(t):3d} 筆  勝率 {100 * (n > 0).mean():4.1f}%  合計 {n.sum():+6.1f}R  回撤 {dd:4.1f}R')


if __name__ == '__main__':
    main()
