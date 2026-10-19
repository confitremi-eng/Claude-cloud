"""Win-rate matrix of v3's GEX setup on NQ RTH (ZeroGEX months).

  cd indicators/backtest
  python3 -I rbs/gex_matrix.py
  python3 -I rbs/gex_matrix.py --tj      # by the NQ RTH Trend Judge state instead (trend / MIX / against)

GEX setup as v3 runs it: (35, 0, 8, 1) on NQ 1-minute cash-session bars, NQ RTH Trend Judge on the signal's side
(threshold 20), QQQ below its gamma flip for buys / above for sells, no new signals 00:00-01:05 Taipei; signal close
entry, two-bar stop, 60-bar exit or 16:00. Rows: all (and with the Taipei window), side, Trend Judge strength, trend
minutes, distance to the flip, room to the wall, time of day, month. Columns: win % / net R per trade at 1, 1.5, 2
and 3R (each signal on its own, 1 point cost). Then one position at a time for each target.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import gex_trend as gt

TG = (1.0, 1.5, 2.0, 3.0)


def cells(y, cost):
    if len(y) == 0: return f'{0:4d}'
    out = []
    for R in TG:
        r = y[f'r{R:g}'].values
        out.append(f'{100 * (r > 0).mean():5.1f}% {(r - cost / y.risk.values).mean():+.2f}')
    return f'{len(y):4d}  ' + '   '.join(out)


def by_tj(cost=1.0):
    """Same setup without the trend condition, split by the NQ RTH Trend Judge state at the signal."""
    one = mm.load_market('qqq', []); tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, 20.0, 40.0)
    s = mm.trend_signals(df, H, 1, 35, 8)
    s = s[(s.date >= '2026-06-29') & (s.date <= '2026-10-14')].copy()
    s = pd.concat([s, gt.feats(df, s)], axis=1); s = s[s.QQQ_flip.notna() & (s.flip_d < 0)].copy()
    close_t = pd.DatetimeIndex(df.datetime.values[s.i]).tz_localize('UTC') + pd.Timedelta(minutes=1)
    tw = close_t.tz_convert('Asia/Taipei')
    s = s[(tw.hour * 60 + tw.minute) > 65]
    s['tj'] = np.sign(s.dir.values) * s.side.values
    print('GEX setup 依 NQ RTH Trend Judge 狀態：(35, 0, 8, 1) + 朝 QQQ flip 走，去掉台北 00:00–01:05，2026-06-29 .. 10-14，每筆扣 1 點')
    print(f'   {"":<28}  筆數    ' + '     '.join(f'{R:g}R 勝率 每筆' for R in TG))
    rows = [('順勢（v3 現在）', s.tj > 0), ('MIX', s.tj == 0), ('順勢或 MIX', s.tj >= 0), ('逆勢', s.tj < 0), ('不看趨勢', s.tj > -9)]
    for nm, m in rows:
        print(f'   {nm:<28}  ' + cells(s[m], cost))
    for side, sn in ((1, '買'), (-1, '賣')):
        print(f'   {"MIX，" + sn:<28}  ' + cells(s[(s.tj == 0) & (s.side == side)], cost))
    print('一次一筆')
    for nm, m in rows[:4]:
        for R in (2.0, 3.0):
            t = ss.seq(s[m].sort_values('i'), R)
            n = t[f'r{R:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
            dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq) if len(eq) else 0
            print(f'   {nm:<12} {R:g}R：{len(t):3d} 筆  勝率 {100 * (n > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  合計 {n.sum():+6.1f}R  回撤 {dd:4.1f}R')


def main(cost=1.0):
    one = mm.load_market('qqq', []); tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, 20.0, 40.0)
    s = mm.trend_signals(df, H, 1, 35, 8)
    s = s[(s.date >= '2026-06-29') & (s.date <= '2026-10-14')].copy()
    s = pd.concat([s, gt.feats(df, s)], axis=1); s = s[s.QQQ_flip.notna()]
    s = s[(np.sign(s.dir) * s.side > 0) & (s.flip_d < 0)].copy()
    close_t = pd.DatetimeIndex(df.datetime.values[s.i]).tz_localize('UTC') + pd.Timedelta(minutes=1)
    tw = close_t.tz_convert('Asia/Taipei'); et = close_t.tz_convert(ss.NY)
    s['lunch'] = (tw.hour * 60 + tw.minute) <= 65
    s['etm'] = et.hour * 60 + et.minute
    s['strong'] = s.spread > 40
    a = s[~s.lunch]
    d = sorted(s.date.unique())
    print(f'GEX setup 勝率矩陣：NQ RTH 1 分 K，(35, 0, 8, 1) + RTH 趨勢 + 朝 QQQ flip 走，2026-06-29 .. 2026-10-14（有訊號的 {len(d)} 天），每筆扣 {cost:g} 點')
    print('每格：勝率 每筆（扣成本後的 R）；各自獨立')
    print(f'   {"":<28}  筆數    ' + '     '.join(f'{R:g}R 勝率 每筆' for R in TG))
    rows = [('全部（v3 預設，去掉台北 00:00–01:05）', a), ('含台北 00:00–01:05', s), ('只有台北 00:00–01:05', s[s.lunch]),
            ('買', a[a.side == 1]), ('賣', a[a.side == -1]),
            ('趨勢一般（差值 20–40）', a[~a.strong]), ('趨勢強（差值 > 40）', a[a.strong])]
    for lo, hi in ((0, 60), (60, 180), (180, 10 ** 6)):
        rows.append((f'趨勢已持續 {lo}–{hi if hi < 10 ** 6 else "以上"} 分', a[(a.tm >= lo) & (a.tm < hi)]))
    for lo, hi in ((0, 0.5), (0.5, 1.0), (1.0, 99)):
        rows.append((f'離 flip {lo:g}–{hi if hi < 99 else "以上"}%', a[(-a.flip_d >= lo) & (-a.flip_d < hi)]))
    for lo, hi, nm in ((-99, 1, '到牆不到 1 倍停損'), (1, 3, '到牆 1–3 倍'), (3, 99, '到牆 3 倍以上')):
        rows.append((nm, a[(a.room_R >= lo) & (a.room_R < hi)]))
    for lo, hi, nm in ((570, 630, '美東 09:30–10:30'), (630, 720, '美東 10:30–12:00'), (720, 840, '美東 12:00–14:00'), (840, 961, '美東 14:00–16:00')):
        rows.append((nm, a[(a.etm > lo) & (a.etm <= hi)]))
    for mo in sorted(a.date.str[:7].unique()):
        rows.append((f'{mo}', a[a.date.str[:7] == mo]))
    for nm, y in rows:
        print(f'   {nm:<28}  ' + cells(y, cost))
    print('\n一次一筆（v3 預設）')
    for R in TG:
        t = ss.seq(a.sort_values('i'), R)
        n = t[f'r{R:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
        dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        mo = pd.Series(n).groupby(t.date.str[:7].values).sum()
        print(f'   {R:g}R：{len(t)} 筆  勝率 {100 * (n > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  合計 {n.sum():+6.1f}R  回撤 {dd:4.1f}R  每月 ' + ' '.join(f'{v:+.0f}' for v in mo.values))


if __name__ == '__main__':
    by_tj() if '--tj' in sys.argv else main()
