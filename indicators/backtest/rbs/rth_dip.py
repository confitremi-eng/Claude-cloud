"""Buying the dip in a strong QQQ uptrend (NQ cash-session 1m bars stand in for QQQ), five years.

  cd indicators/backtest
  python3 -I rbs/rth_dip.py

Strong uptrend (at the moment the dip trade is taken): Trend Judge on the cash-session data is 強UP (spread > 40) when the
dip starts, the last closed 1-hour bar is above its EMA20, and (optional) the price is above the daily SMA5.
Two ways to buy the dip (one trade at a time, 09:45-15:30 entries, out at 16:00 at the latest, 1 point cost):
  A 'slow line' : a limit buy at the 15 s EMA1130 (Trend Judge's slow line) the first time price comes back to it after
                  being strong-up; stop 1 / 1.5 ATR(14, 1m) below the line
  B 'pullback'  : price drops >= k ATR below the 30-bar high while Trend Judge is still UP (spread > 20); buy the close of
                  the first green bar after that; stop below the dip low (1 tick)
Targets 1R / 2R / 3R. Also the mirror (selling rallies in a strong downtrend) for comparison.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def outcome(h, l, c, j, k, entry, stop, R, end):
    risk = (entry - stop) * k; tg = entry + k * R * risk
    for q in range(j + 1, end):
        if (l[q] <= stop) if k == 1 else (h[q] >= stop): return -1.0 - 1 / risk
        if (h[q] >= tg) if k == 1 else (l[q] <= tg): return R - 1 / risk
    return (c[end - 1] - entry) * k / risk - 1 / risk


def main():
    one = oc.load(); D = d5.daily(one)
    cash = mm.cash_only(one); tdm = mm.minute_trend(cash); H = mm.hourly(cash, True)
    df = oc.chart(cash, tdm, 1, 20.0, 40.0)
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
    ny = (dt + pd.Timedelta(minutes=1)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute); day = np.asarray(ny.strftime('%Y-%m-%d'))
    spread = df.tj_diff.values; S = tdm['emaS'].reindex(pd.DatetimeIndex(df.last_min)).values
    _, atr = ss.bar_context(df, 1)
    h1 = pd.merge_asof(pd.DataFrame({'t': df.datetime}), H, on='t', direction='backward').h1.fillna(0).values
    sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
    n = len(c)
    eod = np.zeros(n, int); last = n - 1
    for j in range(n - 1, -1, -1):
        if j == n - 1 or day[j + 1] != day[j]: last = j
        eod[j] = last
    rows = []
    for k in (1, -1):
        strong = (spread * k > 40) & (h1 == k)
        # A: slow-line touch after strong
        armed = False; busy = -1
        for j in range(1, n):
            if day[j] != day[j - 1]: armed = False
            if strong[j]: armed = True
            if not armed or j <= busy or not (585 <= m[j] <= 930) or np.isnan(S[j]): continue
            if spread[j] * k <= 10: armed = False; continue
            if (l[j] <= S[j]) if k == 1 else (h[j] >= S[j]):
                entry = min(o[j], S[j]) if k == 1 else max(o[j], S[j])
                for mult in (1.0, 1.5):
                    stop = S[j] - k * mult * atr[j - 1]
                    for R in (1, 2, 3):
                        rows.append(dict(kind=f'A 慢線 停損 {mult:g} ATR', k=k, date=day[j], R=R, net=outcome(h, l, c, j - 0, k, entry, stop, R, eod[j] + 1) if not ((l[j] <= stop) if k == 1 else (h[j] >= stop)) else -1 - 1 / ((entry - stop) * k),
                                         above5=(c[j] - sma[j]) * k > 0))
                armed = False; busy = j + 30
        # B: pullback of >= kA ATR from the 30-bar extreme, then the first bar closing with the trend
        for kA in (2.0, 3.0):
            want = False; busy = -1
            for j in range(31, n):
                if day[j] != day[j - 30] or j <= busy or not (585 <= m[j] <= 930): continue
                hi = h[j - 30:j].max() if k == 1 else l[j - 30:j].min()
                if (hi - c[j]) * k >= kA * atr[j - 1] and spread[j] * k > 20 and h1[j] == k and strong[j - 30:j].any():
                    want = True; dlo = l[j] if k == 1 else h[j]
                if want:
                    dlo = min(dlo, l[j]) if k == 1 else max(dlo, h[j])
                    if spread[j] * k <= 0: want = False; continue
                    if (c[j] > o[j]) if k == 1 else (c[j] < o[j]):
                        stop = dlo - 0.25 * k
                        if (c[j] - stop) * k > 0:
                            for R in (1, 2, 3):
                                rows.append(dict(kind=f'B 回檔 {kA:g} ATR 後第一根', k=k, date=day[j], R=R, net=outcome(h, l, c, j, k, c[j], stop, R, eod[j] + 1), above5=(c[j] - sma[j]) * k > 0))
                        want = False; busy = j + 30
    t = pd.DataFrame(rows)
    t['yr'] = pd.cut(t.date, [oc.YEARS[0][1]] + [b for nm, a, b in oc.YEARS], labels=[nm[:2] for nm, a, b in oc.YEARS], include_lowest=True)
    for k, lab in ((1, '強上升趨勢買回檔'), (-1, '強下降趨勢賣反彈（對照）')):
        print(f'\n{lab}：每年 勝率 / 合計 R（一筆一個訊號，不考慮重疊）')
        print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   筆 / 年')
        for kind in t.kind.unique():
            for R in (1, 2, 3):
                for sub, z0 in (('', t), ('（日線 SMA5 上方）', t[t.above5])):
                    z = z0[(z0.k == k) & (z0.kind == kind) & (z0.R == R)]
                    if not len(z): continue
                    print(f'   {kind + f" {R}R" + sub:<30}' + ''.join(f'{100 * (q.net > 0).mean():5.0f}% {q.net.sum():+5.0f}R' for q in (z[(z.date >= a) & (z.date <= b)] for nm, a, b in oc.YEARS)) + f'   {len(z) / 5:.0f}')


if __name__ == '__main__':
    main()
