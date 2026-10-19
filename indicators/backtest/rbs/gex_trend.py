"""Trend-following signals and the SPY / QQQ gamma (ZeroGEX, 2026-06-29 onward): any relation?

  cd indicators/backtest
  python3 -I rbs/gex_trend.py

Signal sets (cash session only, where ZeroGEX has data):
  QQQ 1m 順勢   (35, 0, 8, 1) original signals with Trend Judge on their side (threshold 0.5 QQQ = 20 NQ points)
  QQQ 1m v3     the ones v3 keeps (ETF filter + NQ 2m not opposite)
  NQ 2m v3      v3's NQ 2-minute trend signals (filtered, trend 0-180 minutes) inside 09:30-16:00 ET
QQQ 1m runs on both price sources (NQ cash-session bars; ZeroGEX's own QQQ candles), NQ 2m on NQ.
GEX features, read at the minute before the signal bar closes:
  regime     price above / below the gamma flip, for SPY and QQQ (= net GEX sign 93% of the time)
  離 flip    QQQ price minus its gamma flip, % of price, on the trade's side (+ = buy above / sell below the flip)
  到牆空間   room from QQQ to the call wall (buys) / put wall (sells), in multiples of the trade's risk (both in %)
Each signal on its own (two-bar stop, 60-bar exit or the session end), 1R / 2R / 3R; plus rank correlations.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import strong_stage as sg
import gex_qqq as gq


def feats(df, s):
    known = gq.NS(pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC'))
    m = gq.zg_minute('QQQ')
    g = lambda col: gq.lookup(known, m, lambda x: x[col], 5)
    px, flip, cw, pw = g('close'), g('gamma_flip'), g('call_wall'), g('put_wall')
    side = s.side.values
    entry = df.close.values[s.i]
    risk_pct = s.risk.values / entry * 100
    room = np.where(side == 1, cw - px, px - pw) / px * 100
    out = pd.DataFrame({'flip_d': (px - flip) / px * 100 * side, 'room_R': room / risk_pct}, index=s.index)
    return pd.concat([out, gq.regimes(df, s)], axis=1)


def rank_corr(a, b):
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 10: return np.nan
    return np.corrcoef(pd.Series(a[ok]).rank(), pd.Series(b[ok]).rank())[0, 1]


def report(name, s, cost):
    s = s[s.QQQ_flip.notna() & s.SPY_flip.notna()]
    d = sorted(s.date.unique()); split = d[len(d) // 2]
    R = lambda y, nm: print(f'   {nm:<24} ' + mm.row_ind(y, cost, split))
    print(f'\n  ## {name}：{len(s)} 筆（{d[0]} .. {d[-1]}，每筆扣 {cost:g}）')
    print(f'   {"":<24}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    R(s, '全部')
    q, p = s.QQQ_flip, s.SPY_flip
    R(s[q > 0], 'QQQ gamma 正'); R(s[q < 0], 'QQQ gamma 負')
    R(s[p > 0], 'SPY gamma 正'); R(s[p < 0], 'SPY gamma 負')
    R(s[(q > 0) & (p > 0)], '都正'); R(s[(q < 0) & (p < 0)], '都負'); R(s[q * p < 0], '一正一負')
    for sd, sn in ((1, '買'), (-1, '賣')):
        R(s[(s.side == sd) & (q > 0)], f'{sn}，QQQ gamma 正'); R(s[(s.side == sd) & (q < 0)], f'{sn}，QQQ gamma 負')
    print('   離 QQQ gamma flip（順著交易方向，% 價格；+ = 買在 flip 上 / 賣在 flip 下）')
    for lo, hi in ((-99, -0.5), (-0.5, 0), (0, 0.5), (0.5, 99)):
        R(s[(s.flip_d >= lo) & (s.flip_d < hi)], f'{"" if lo == -99 else format(lo, "+g")}～{"" if hi == 99 else format(hi, "+g")}%')
    print('   到 call wall（買）/ put wall（賣）的空間，幾倍停損')
    for lo, hi in ((-99, 0), (0, 1), (1, 3), (3, 99)):
        lab = '已經過牆' if lo == -99 else f'{lo}–{hi if hi < 99 else "以上"} 倍'
        R(s[(s.room_R >= lo) & (s.room_R < hi)], lab)
    print('   朝 flip 走（買在 flip 下、賣在 flip 上）vs 離開 flip，再依趨勢已持續')
    tw = s.flip_d < 0
    for nm, m in (('朝 flip 走', tw), ('離開 flip', ~tw)):
        R(s[m], nm)
        for lo, hi in ((0, 60), (60, 180), (180, 10 ** 6)):
            R(s[m & (s.tm >= lo) & (s.tm < hi)], f'　趨勢 {lo}–{hi if hi < 10 ** 6 else "以上"} 分')
    r1, r3 = s.r1.values, s.r3.values
    print(f'   等級相關（-1～+1）：離 flip 對 1R {rank_corr(s.flip_d.values, r1):+.2f}、對 3R {rank_corr(s.flip_d.values, r3):+.2f}；'
          f'到牆空間對 1R {rank_corr(s.room_R.values, r1):+.2f}、對 3R {rank_corr(s.room_R.values, r3):+.2f}')


def qqq_sets(name, one, cost, th, st, nd, start, end):
    tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, th, st)
    s = mm.trend_signals(df, H, 1, 35, 8)
    late = s.date.values > '2026-10-14'
    s['v3'] = mm.filt(s, th, 7.0) & (sg.nq_ok(df, s, nd) | late)
    s = s[(s.date >= start) & (s.date <= end)].copy()
    s = pd.concat([s, feats(df, s)], axis=1)
    same = np.sign(s.dir.values) * s.side.values > 0
    print(f'\n################ {name}')
    report('原版 (35, 0, 8, 1) 順勢（Trend Judge 同向）', s[same], cost)
    report('v3 留下的', s[s.v3], cost)


def nq2m(start, end):
    one = mm.load_market('nq', []); tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    df = mm.chart(one, tdm, 2, 10.0, 35.0)
    s = mm.trend_signals(df, H, 2)
    s = s[mm.filt(s, 10.0) & (s.date >= start) & (s.date <= end)].copy()
    et = pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC').tz_convert(ss.NY)
    mins = et.hour * 60 + et.minute
    s = s[(mins >= 570) & (mins < 960)]
    s = pd.concat([s, feats(df, s)], axis=1)
    print('\n################ NQ 2 分 K（v3 的趨勢訊號，美股盤 09:30–16:00）')
    report('過濾後的趨勢訊號（不限趨勢時間）', s, 1.0)
    report('v3：趨勢 0–180 分', s[s.tm < 180], 1.0)


def main():
    nd = sg.nq2m_dir()
    m = gq.zg_minute('QQQ')
    start = str(m.ts.dt.tz_convert(ss.NY).dt.date.min())
    qqq_sets('QQQ 1 分 K（NQ 美股盤代替）', mm.load_market('qqq', []), 1.0, 20.0, 40.0, nd, start, '2026-10-14')
    one = gq.real_qqq(); days = sorted(set(one.index.tz_convert(ss.NY).date))
    qqq_sets('QQQ 1 分 K（ZeroGEX 的 QQQ 實際 K 棒）', one, 0.024, 0.5, 1.0, nd, str(days[3]), str(days[-1]))
    nq2m(start, '2026-10-14')


if __name__ == '__main__':
    main()
