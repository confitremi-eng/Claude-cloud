"""SPY and QQQ both long gamma / both short gamma, and the +-1B net GEX rule: do v3 trades differ? (2026-06-29 on)

  cd indicators/backtest
  python3 -I rbs/gex_both.py

Regime per symbol from the hourly ZeroGEX net GEX (used from the end of its hour, at most 4 hours old):
long if net GEX >= +T, short if <= -T, otherwise neutral; T = 0, 1B, 2B (dollars). Groups: both long, both short,
mixed / neutral. Trades: v3 NQ 2m as taken (trend + MIX, one at a time, FOMC days off), every v3 2m trend signal on its
own, NQ RTH 1m (QQQ setting).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc
import v3_kline as vk
import flip_wait as fw
import gex_regime as gr

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def hourly(sym):
    g = pd.read_csv(os.path.join(HERE, 'data', 'zerogex', f'{sym}_hourly.csv')).dropna(subset=['net_gex'])
    g['known'] = pd.to_datetime(g.ts, utc=True) + pd.Timedelta(hours=1)
    return g[['known', 'net_gex']].rename(columns={'net_gex': sym}).sort_values('known')


def tag(t, df, tf, Q, S):
    t = t.copy(); t['tin'] = pd.to_datetime(df.datetime.values[t.i.values], utc=True) + pd.Timedelta(minutes=tf)
    t = t.sort_values('tin')
    for G in (Q, S):
        sym = G.columns[1]
        t = pd.merge_asof(t, G.rename(columns={'known': 'k_' + sym}), left_on='tin', right_on='k_' + sym, direction='backward')
        t.loc[(t.tin - t['k_' + sym]).dt.total_seconds() > 4 * 3600, sym] = np.nan
    et = t.tin.dt.tz_convert(ss.NY); mi = et.dt.hour * 60 + et.dt.minute
    t['cash'] = (mi > 570) & (mi <= 960) & (et.dt.weekday < 5)
    return t.dropna(subset=['QQQ', 'SPY'])


def show(t, title):
    print(f'\n   {title}（{len(t)} 筆有資料）')
    print(f'      {"門檻":<6} {"":<4} {"都 Long":>22} {"都 Short":>22} {"不一致 / 中間":>22}')
    for T in (0, 1e9, 2e9):
        q = np.where(t.QQQ >= T, 1, np.where(t.QQQ <= -T, -1, 0)) if T else np.sign(t.QQQ)
        s = np.where(t.SPY >= T, 1, np.where(t.SPY <= -T, -1, 0)) if T else np.sign(t.SPY)
        both_l = (q == 1) & (s == 1); both_s = (q == -1) & (s == -1); other = ~both_l & ~both_s
        for lab, sd in (('買', 1), ('賣', -1), ('全部', 0)):
            m = (t.side == sd) if sd else np.ones(len(t), bool)
            print(f'      {("±%gB" % (T / 1e9)) if lab == "買" else "":<6} {lab:<4} {gr.cell(t[m & both_l]):>22} {gr.cell(t[m & both_s]):>22} {gr.cell(t[m & other]):>22}')


def main():
    one = oc.load(); M = oc.Market(one); Q, S = hourly('QQQ'), hourly('SPY')
    C = M.ctx(2); df = C.df
    T = oc.trend_set(df, M.H, 2, 20, df.thr.values, 3.0, 0, 180); T = T[~T.date.isin(ss.FOMC)]
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
    t = vk.trades(C, T, mix, 3.0); t = tag(t[t.date >= gr.START], df, 2, Q, S)
    print(f'NQ 2m v3（3R，{gr.START} 起；net GEX 用每小時資料）')
    show(t, 'v3 實際做的單（趨勢 + MIX）')
    show(t[~t.cash], '   只看夜盤'); show(t[t.cash], '   只看現金盤')
    Ts = T[T.date >= gr.START].copy(); Ts['net'] = fw.each(C, Ts, 3.0)
    show(tag(Ts.reset_index(drop=True), df, 2, Q, S), '每個趨勢訊號單獨進場')
    dr, tr = oc.nq_rth(one, detail=True)
    tr = tr[tr.date >= gr.START].copy(); tr['net'] = tr.r3 - oc.COST / tr.risk
    print(f'\nNQ RTH 1m（QQQ 做法，3R）')
    show(tag(tr.reset_index(drop=True), dr, 1, Q, S), 'NQ RTH 1m')


if __name__ == '__main__':
    main()
