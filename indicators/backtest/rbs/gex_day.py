"""Re-run the GEX setup on one day with NQ bars exported from TradingView (for days after the Databento file ends).

  cd indicators/backtest
  python3 -I rbs/zerogex_fetch.py "../../ZEROGEX API.txt" range      # the day's minute flip
  python3 -I rbs/gex_day.py <TradingView export.csv> 2026-10-19

The export's OHLC bars newer than data/NQ_1m_databento.csv are appended in memory (nothing is written). Prints the
setup signals that day with the ZeroGEX minute flip, how each one ended (stop / target / time), and the setup's
markers recorded in the export itself (its 'GEX 進場' column, which used one manually entered flip for every bar).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import gex_params as gp


def main():
    path, day = sys.argv[1], sys.argv[2]
    one = mm.read_csv(os.path.join(mm.DATA, 'NQ_1m_databento.csv'))
    tv = pd.read_csv(path); tv.index = pd.to_datetime(tv.time, unit='s', utc=True)
    tv = tv[['open', 'high', 'low', 'close']].astype(float)
    if one.index.tz is None: tv.index = tv.index.tz_localize(None)
    new = tv[tv.index > one.index.max()]
    one = pd.concat([one[['open', 'high', 'low', 'close']], new]); one = mm.cash_only(one); one['bad'] = False
    print(f'接上 TradingView {len(new)} 根（{new.index.min()} .. {new.index.max()}）')
    tdm = mm.minute_trend(one); H = mm.hourly(one, True); df = mm.chart(one, tdm, 1, 20.0, 40.0)
    s = mm.trend_signals(df, H, 1, 35, 8); s = s[s.date == day].copy()
    s = pd.concat([s, gp.gt.feats(df, s)], axis=1)
    h, l, c = df.high.values, df.low.values, df.close.values
    tw = pd.DatetimeIndex(df.datetime).tz_convert('Asia/Taipei') if pd.DatetimeIndex(df.datetime).tz else pd.DatetimeIndex(df.datetime).tz_localize('UTC').tz_convert('Asia/Taipei')
    print(f'\n{day} 原版 (35, 0, 8, 1) 訊號（台北時間，訊號 K 收盤）：')
    for r in s.itertuples():
        j = r.i; k = r.side; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j]); e = c[j]; tg = e + 3 * (e - st)
        res = '時間'
        for q in range(j + 1, min(j + 61, len(c))):
            if (l[q] <= st) if k == 1 else (h[q] >= st): res = f'停損 {tw[q] + pd.Timedelta(minutes=1):%H:%M}'; break
            if (h[q] >= tg) if k == 1 else (l[q] <= tg): res = f'目標 {tw[q] + pd.Timedelta(minutes=1):%H:%M}'; break
        tj = '順勢' if np.sign(r.dir) * k > 0 else '逆勢'
        fl = '沒有 flip' if np.isnan(r.flip_d) else ('朝 flip' if r.flip_d < 0 else '離開 flip')
        ok = tj == '順勢' and fl == '朝 flip'
        print(f'   {tw[j] + pd.Timedelta(minutes=1):%m-%d %H:%M} {"買" if k == 1 else "賣"} 進 {e:.2f} 停 {st:.2f} 標 {tg:.2f}  TJ {tj}  {fl}（QQQ 離 flip {abs(r.flip_d):.2f}%）'
              f'  {"→ GEX setup" if ok else ""}  {res if ok else ""}')
    x = pd.read_csv(path); x['tw'] = pd.to_datetime(x.time, unit='s', utc=True).dt.tz_convert('Asia/Taipei')
    ny = pd.to_datetime(x.time, unit='s', utc=True).dt.tz_convert('America/New_York').dt.date.astype(str)
    g = x[(ny == day) & x['GEX 進場'].notna()]
    print(f'\nTradingView 匯出裡 {day} 的 🧲：')
    for _, r in g.iterrows():
        print(f'   {r.tw:%m-%d %H:%M} 進 {r["GEX 進場"]:.2f} 停 {r["GEX 停損"]:.2f} 標 {r["GEX 目標"]:.2f}')


if __name__ == '__main__':
    main()
