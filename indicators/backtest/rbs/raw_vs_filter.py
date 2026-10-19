"""How do the unfiltered (gray-triangle) signals do, and what does each Remi Superb filter add? Plus the Friday
cut-off (no new signals from Taipei Saturday 02:00 = the last hours of the US Friday) on v3. NQ 2 minutes.

  cd indicators/backtest
  python3 -I rbs/raw_vs_filter.py

Raw = the original indicator's signals (20, 0, 8, 1). 順勢 = Trend Judge on the signal's side (有趨勢, > 10).
Each filter is taken out of the full set one at a time. Signals on their own (1 point cost); v3 one at a time.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import trend_follow as tf


def main():
    cost, th, st = 1.0, 10.0, 35.0
    one, tdm, H, df, nxt, atr, h1, evt, date = tf.frame('nq', th, st)
    years = (one.index[-1] - one.index[0]).days / 365.25
    s = mm.trend_signals(df, H, 2)
    trend = s.side * s.dir >= 1
    h1ok = s.side == s.h1
    risk = s.risk_atr >= 1.0
    evtok = ~ss.EVT(s)
    dist = s.slow < 3
    win = (s.tm >= 0) & (s.tm < 180)
    full = trend & h1ok & risk & evtok & dist & (s.spread > th) & win
    print('NQ 2 分 K 一年：原版訊號（灰色三角）各自獨立，每筆扣 1 點')
    print(f'{"":<26}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    rows = [('全部灰色三角', s.side != 0), ('逆勢（TJ 反向或 MIX）', ~trend), ('順勢（TJ 同向）', trend),
            ('v3 全部條件（趨勢 0–180）', full)]
    for nm, m in (('拿掉 1 小時同向', trend & risk & evtok & dist & win), ('拿掉 停損 ≥ 1 ATR', trend & h1ok & evtok & dist & win),
                  ('拿掉 避開事件時段', trend & h1ok & risk & dist & win), ('拿掉 離慢線 ≤ 3 ATR', trend & h1ok & risk & evtok & win),
                  ('拿掉 趨勢 0–180 分', trend & h1ok & risk & evtok & dist)):
        rows.append((nm, m))
    rows.append(('只被「趨勢 > 180 分」擋掉的', trend & h1ok & risk & evtok & dist & ~win))
    rows.append(('只被「離慢線 > 3 ATR」擋掉的', trend & h1ok & risk & evtok & ~dist & win))
    for nm, m in rows:
        print(f'   {nm:<24} ' + mm.row_ind(s[m], cost, sorted(s.date.unique())[len(s.date.unique()) // 2]))

    print('\n週五收盤前不交易（台北週六 02:00 以後不發新訊號），v3 NQ 2m 一次一筆 3R')
    h, l = df.high.values, df.low.values
    et = (df.datetime + pd.Timedelta(minutes=2)).dt.tz_convert(ss.NY)
    halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
    tw = (df.datetime + pd.Timedelta(minutes=2)).dt.tz_convert('Asia/Taipei')
    late = ((tw.dt.weekday == 5) & (tw.dt.hour * 60 + tw.dt.minute >= 120)).values
    F = s[full]
    mix = tf.mix_dict(df, th, cost)
    for nm, cut in (('原本', False), ('週五 02:00 後不交易', True)):
        ce = {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(F.i, F.side) if not (cut and late[i])}
        mx = {j: v for j, v in mix.items() if not (cut and late[j])}
        t = tf.simulate(df, ce, mx, 3.0, cost, halt)
        print(f'   {nm:<16} ' + tf.seq_line(t, years))
    tt = tf.simulate(df, {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(F.i, F.side)}, mix, 3.0, cost, halt)
    tt['late'] = False
    print(f'   被這條規則拿掉的訊號：趨勢 {int(sum(late[int(i)] for i in F.i))} 個、MIX {int(sum(late[j] for j in mix))} 個（一年）')


if __name__ == '__main__':
    main()
