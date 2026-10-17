"""Checks on the QQQ 1-minute settings picked with param_sweep_1m.py (NQ cut to the cash session as a QQQ chart).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/qqq_1m_check.py

(35, 0, 8, 1), now the QQQ default of Remi Superb 1m, and the starting point (30, 0, 13, 1); filter = Remi Superb's
with threshold 20 NQ points (QQQ 0.5) and distance 7 ATR, 3R, 1 point cost, one position at a time.
Prints
  1. longs / shorts, each filter taken out, 1.5 point cost, entry hour, months, no entries from 15:00
  2. the MIX-box breakout on the same bars (60-minute box, first 10% break within 60 minutes, stop at the middle),
     alone and together with the filtered alerts
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import mix_range as mr
import mix_breakout as mb
import param_sweep_1m as ps

TI = {R: k for k, R in enumerate(ps.TARGETS)}
SETS = ((35, 8), (30, 13))


def trades(A, cache, N, E, th=20.0, dist=7.0, R=3.0, cost=1.0, drop=()):
    T = ps.signal_table(A, N, E, True, *cache)
    m = np.ones(len(T['i']), np.bool_)
    if 'tj' not in drop: m &= T['spread'] > th
    if 'h1' not in drop: m &= T['h1'] == T['side']
    if 'risk' not in drop: m &= T['risk_atr'] >= 1.0
    if 'dist' not in drop: m &= T['slow'] < dist
    if 'evt' not in drop: m &= ~T['evt']
    sel = np.where(m)[0]; t = TI[R]
    keep = sel[ps.seq_nb(T['i'][sel], T['X'][sel, t])]
    out = pd.DataFrame(dict(i=T['i'][keep], x=T['X'][keep, t], side=T['side'][keep], risk=T['risk'][keep],
                            r=T['R'][keep, t], date=T['date'][keep], month=T['month'][keep], kind='趨勢'))
    out['net'] = out.r - cost / out.risk
    return out


def mix_bars(A, th=20.0):
    df = A['df']; d = df.tj_diff.values; t = df.datetime
    return dict(df=df, h=A['h'], l=A['l'], c=A['c'], o=df.open.values, atr=A['atr'],
                state=np.where(np.isnan(d), 9, np.where(d > th, 1, np.where(d < -th, -1, 0))),
                hole=np.r_[True, (t.diff() > pd.Timedelta(minutes=30)).values[1:]], evt=A['evt'],
                sess=np.full(len(d), '美股'), date=A['date'], tradable=A['tradable'])


def main():
    A = ps.bar_arrays('qqq')
    cache = ({}, {})
    days = len(set(A['date'][A['tradable']]))
    et = (A['df'].datetime + pd.Timedelta(minutes=1)).dt.tz_convert(ss.NY)
    entry_min = (et.dt.hour * 60 + et.dt.minute).values                      # bar close = entry, ET minutes
    print(f'QQQ 圖（NQ 只留美股盤），{days} 個交易日；門檻 20 距離 7 3R，扣 1 點，一次一筆')

    print('\n######## 1. 細看')
    for N, E in SETS:
        base = trades(A, cache, N, E)
        print(f'\n  ({N}, 0, {E}, 1)  每天 {len(base) / days:.1f} 筆，停損中位數 {base.risk.median():.1f} 點（QQQ 約 {base.risk.median() / 41:.2f}）')
        print(f'    全部            {mb.summ(base)}')
        for k, nm in ((1, '只看多'), (-1, '只看空')):
            print(f'    {nm}          {mb.summ(base[base.side == k])}')
        for d, nm in (('tj', '拿掉 TJ'), ('h1', '拿掉 1 小時'), ('risk', '拿掉停損 ≥ 1 ATR'), ('dist', '拿掉距離'), ('evt', '拿掉避開時段')):
            print(f'    {nm:<14}{mb.summ(trades(A, cache, N, E, drop=(d,)))}')
        print(f'    扣 1.5 點        {mb.summ(trades(A, cache, N, E, cost=1.5))}')
        mins = entry_min[base.i.values]
        for a, b in ((600, 660), (660, 720), (720, 840), (840, 900), (900, 961)):
            s = (mins >= a) & (mins < b)
            print(f'    {a // 60:02d}:{a % 60:02d} 起進場     {mb.summ(base[s])}')
        print(f'    15:00 後不進場   {mb.summ(base[mins < 900])}')
        mo = base.groupby('month').net.sum()
        print('    每月 R：' + ' '.join(f'{m[2:]} {v:+.1f}' for m, v in mo.items()))

    print('\n######## 2. MIX 區間突破（同樣的 K 棒，TJ 門檻 20）')
    mr.TF, mr.HOLD = 1, 60
    B = mix_bars(A)
    bx = mb.causal_boxes(B, 60, grace=4)
    print(f'  MIX 佔 {np.mean(B["state"][A["tradable"]] == 0):.0%} 的時間，{len(bx)} 個區間（每天 {len(bx) / days:.2f} 個）')
    for entry, nm in (('stop', '掛突破單'), ('close', '收盤進場')):
        for R in (2.0, 3.0):
            print(f'    {nm} {R:g}R  {mb.summ(mb.breakouts(B, bx, R, max_age=60, entry=entry))}')
    fl = trades(A, cache, *SETS[0])
    bo = mb.breakouts(B, bx, 3.0, max_age=60, entry='stop')
    both = mb.seq_all(pd.concat([fl[bo.columns.intersection(fl.columns)], bo[fl.columns.intersection(bo.columns)]], ignore_index=True))
    print(f'  過濾快訊 ({SETS[0][0]}, 0, {SETS[0][1]}, 1) 單獨  {mb.summ(mb.seq_all(fl))}')
    print(f'  + MIX 突破（掛單 3R）   {mb.summ(both)}  突破貢獻 {both.net[both.kind == "突破"].sum():+.1f}R')


if __name__ == '__main__':
    main()
