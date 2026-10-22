"""NQ 2m v3 trend trades in the night session (ET 18:00 .. 09:30): are they worse after a big cash-session day?

  cd indicators/backtest
  python3 -I rbs/nq_night_after_big.py

Cash-session move = the 15:59 close vs the 09:30 open of the cash session just before the night (%, ET). Five years.
Part 1, each night trend signal on its own: by the previous cash move (big down .. big up), the v3 year and the four
years before: trades, 1R / 1.5R / 3R hit rate, 3R net R per trade.
Part 2, v3 2m traded as now (trend + MIX, one at a time) but skipping night trend signals after |move| >= X:
per year 1R and 3R win rate / net R.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import gapdown_long as gl

BANDS = ((-99, -2.0, '大跌 ≤ −2%'), (-2.0, -1.0, '跌 −2 ~ −1%'), (-1.0, -0.5, '小跌 −1 ~ −0.5%'), (-0.5, 0.5, '平 ±0.5%'),
         (0.5, 1.0, '小漲 0.5 ~ 1%'), (1.0, 2.0, '漲 1 ~ 2%'), (2.0, 99, '大漲 ≥ 2%'))


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df; th = df.thr.values
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=2); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); off = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    base = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < 400)
             & ~s.date.isin(ss.FOMC) & ~off[s.i]].copy()
    # cash sessions
    cash = gl.load(oc.DATA)
    cs = cash.groupby('day').agg(o=('open', 'first'), c=('close', 'last'))
    cs['move'] = 100 * (cs.c / cs.o - 1)
    days = np.array(sorted(cs.index))
    em = m[base.i.values]; ed = np.asarray(ny[base.i.values].strftime('%Y-%m-%d'))
    night = (em >= 1080) | (em < 570)
    # the cash session just before: same ET date if after 18:00, else the last cash day before this date
    key = np.where(em >= 1080, ed, '')
    k = np.searchsorted(days, ed, 'left') - 1
    prevd = np.where(em >= 1080, ed, days[np.maximum(k, 0)])
    base['night'] = night; base['cday'] = prevd
    base['move'] = cs.move.reindex(prevd).values
    split = oc.YEARS[-1][1]
    N = base[base.night & base.move.notna()]
    print(f'NQ 2m v3 夜盤趨勢訊號：{len(N)} 個（前一個現金盤漲跌 = 收盤 / 開盤）')
    print('######## 1. 每個訊號單獨算')
    print(f'   {"前一天現金盤":<16}{"":>9}{"筆":>5}{"1R":>6}{"1.5R":>6}{"3R":>6}{"3R 每筆":>9}')
    for a, b, lab in BANDS:
        for per, z in (('v3 那年', N[N.date >= split]), ('前 4 年', N[N.date < split])):
            q = z[(z.move > a) & (z.move <= b)] if a > -99 else z[z.move <= b]
            if not len(q): continue
            n3 = q.r3 - oc.COST / q.risk
            print(f'   {lab:<16}{per:>9}{len(q):5d}' + ''.join(f'{100 * (q[f"r{R:g}"] >= R - 1e-9).mean():5.0f}%' for R in (1.0, 1.5, 3.0)) + f'{n3.mean():+8.2f}R')
    for per, z in (('v3 那年', base[base.date >= split]), ('前 4 年', base[base.date < split])):
        q = z[~z.night]; n3 = q.r3 - oc.COST / q.risk
        print(f'   {"對照：日盤訊號":<16}{per:>9}{len(q):5d}' + ''.join(f'{100 * (q[f"r{R:g}"] >= R - 1e-9).mean():5.0f}%' for R in (1.0, 1.5, 3.0)) + f'{n3.mean():+8.2f}R')

    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print('\n######## 2. 一次一筆（趨勢 + MIX），每格：勝率 / 淨 R')
    print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}')
    for R in (1.0, 3.0):
        print(f'目標 {R:g}R')
        rows = [('v3 現在', base)]
        for X in (1.0, 1.5, 2.0):
            big = base.night & (base.move.abs() >= X)
            rows += [(f'前一天 |漲跌| ≥ {X:g}% 夜盤不做', base[~big]),
                     (f'前一天大跌 ≥ {X:g}% 夜盤不做', base[~(base.night & (base.move <= -X))]),
                     (f'前一天大漲 ≥ {X:g}% 夜盤不做', base[~(base.night & (base.move >= X))])]
        for lab, T in rows:
            t = oc.sim(C, T.sort_values('i'), mix, R, R)
            cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
            print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.0f}R' for z in cells), flush=True)


if __name__ == '__main__':
    main()
