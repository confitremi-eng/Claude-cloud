"""MIX-box breakout on 1 / 2 / 3 / 5-minute charts (NQ, the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/mix_breakout_tf.py

Same rules, in minutes, on every chart (as the indicator converts them): box = the first 60 minutes of a MIX period
(trend blips of up to 4 minutes allowed), first break 10% beyond it within 60 minutes, stop at the box middle;
entry with a stop order at the breakout price or at the close of the breakout bar; 1 point cost. Time exit after
60 bars like the other timeframe tables, and after 2 hours for a like-for-like check.
Then the filtered alerts of the same chart (Remi Superb defaults, 3R) alone and together with the breakout (3R,
stop orders), one position at a time.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import mix_range as mr
import mix_breakout as mb


def main():
    rows = []
    for tf in (1, 2, 3, 5):
        mr.TF = tf
        B = mr.load()
        W, grace, age = round(60 / tf), max(0, round(4 / tf)), round(60 / tf)
        bx = mb.causal_boxes(B, W, grace=grace)
        print(f'\n######## {tf} 分 K：{len(bx)} 個 MIX 區間（觀察 {W} 根、有效 {age} 根）')
        for hold_nm, hold in (('60 根出場', 60), ('2 小時出場', round(120 / tf))):
            mr.HOLD = hold
            for entry, enm in (('stop', '掛突破單'), ('close', '收盤進場')):
                for R in (2.0, 3.0):
                    t = mb.breakouts(B, bx, R, max_age=age, entry=entry)
                    print(f'  {hold_nm} {enm} {R:g}R  {mb.summ(t)}')
        mr.HOLD = 60
        tw.TF = tf
        tw.CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl' if tf == 2 else f'NQ_1m_databento_th_sweep_{tf}m.pkl')
        fl = mb.filtered(3.0)
        bo = mb.breakouts(B, bx, 3.0, max_age=age, entry='stop')
        both = mb.seq_all(pd.concat([fl, bo[fl.columns]], ignore_index=True))
        print(f'  過濾快訊（3R）單獨      {mb.summ(mb.seq_all(fl))}')
        print(f'  + MIX 突破（掛單 3R）   {mb.summ(both)}  突破貢獻 {both.net[both.kind == "突破"].sum():+.1f}R')


if __name__ == '__main__':
    main()
