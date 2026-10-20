"""GEX setup signals in Taipei 00:00-01:05 (New York 12:00-13:05): page with the day's NQ chart for each one.

  cd indicators/backtest
  python3 -I rbs/gex_lunch.py <TradingView export.csv> <out.html>

NQ 1m cash-session bars: data/NQ_1m_databento.csv plus the export's newer bars (in memory). Setup (35, 0, 8, 1),
Trend Judge on its side, toward the ZeroGEX minute flip, 2026-06-29 .. the last day with flip data. Each signal on its
own: signal close entry, two-bar stop, 3R target, 60 bars or 16:00 New York, 1 point cost. The page draws the day's
candles (Taipei clock), 5 s / 15 s EMA1130, the QQQ flip in NQ points, and every setup signal of that day; the
00:00-01:05 ones are listed and highlighted. Template: rbs/gex_lunch_template.html.
"""
import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import gex_params as gp
import gex_qqq as gq

COST = 1.0


def bars(tv_path):
    one = mm.read_csv(os.path.join(mm.DATA, 'NQ_1m_databento.csv'))
    tv = pd.read_csv(tv_path); tv.index = pd.to_datetime(tv.time, unit='s', utc=True)
    tv = tv[['open', 'high', 'low', 'close']].astype(float)
    if one.index.tz is None: tv.index = tv.index.tz_localize(None)
    one = pd.concat([one[['open', 'high', 'low', 'close']], tv[tv.index > one.index.max()]])
    one = mm.cash_only(one); one['bad'] = False
    return one


def main():
    tv_path, out = sys.argv[1], sys.argv[2]
    one = bars(tv_path); tdm = mm.minute_trend(one); H = mm.hourly(one, True); df = mm.chart(one, tdm, 1, 20.0, 40.0)
    zg = gq.zg_minute('QQQ'); last_day = zg.ts.max().tz_convert(ss.NY).strftime('%Y-%m-%d')
    y = gp.setup_rows(df, H, 35, 8, '2026-06-29', last_day).sort_values('i')
    dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
    close_t = dt + pd.Timedelta(minutes=1)
    tw = close_t.tz_convert('Asia/Taipei'); ny = close_t.tz_convert(ss.NY)
    fake = ((tw.tz_localize(None) - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s')).values
    nyd = np.asarray(dt.tz_convert(ss.NY).strftime('%Y-%m-%d')); nymin = np.asarray(ny.hour * 60 + ny.minute)
    h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
    # flip in NQ points at every bar (minute flip x NQ / QQQ of that minute)
    known = gq.NS(pd.DatetimeIndex(df.last_min.values).tz_localize('UTC') if pd.DatetimeIndex(df.last_min.values).tz is None else pd.DatetimeIndex(df.last_min.values))
    fl = gq.lookup(known, zg, lambda x: x.gamma_flip, 5); qc = gq.lookup(known, zg, lambda x: x.close, 5)
    flip_nq = fl * c / qc
    lm = pd.DatetimeIndex(df.last_min); fast = tdm['emaF'].reindex(lm).values; slow = tdm['emaS'].reindex(lm).values
    rows = []
    for r in y.itertuples():
        j, k = r.i, r.side
        st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j]); e = c[j]; risk = abs(e - st); tg = e + 3 * (e - st)
        px, x, why = c[j], j, '時間'
        for q in range(j + 1, min(j + 61, len(c))):
            if nyd[q] != nyd[j]: px, x, why = c[q - 1], q - 1, '收盤'; break
            if (l[q] <= st) if k == 1 else (h[q] >= st): px, x, why = st, q, '停損'; break
            if (h[q] >= tg) if k == 1 else (l[q] <= tg): px, x, why = tg, q, '目標'; break
            if nymin[q] >= 960: px, x, why = c[q], q, '收盤'; break
            px, x = c[q], q
        m = tw[j].hour * 60 + tw[j].minute
        rows.append(dict(i=int(j), x=int(x), day=nyd[j], side=int(k), entry=float(e), stop=float(st), tgt=float(tg), exit=why,
                         exit_px=float(px), net=round(float((px - e) * k / risk - COST / risk), 2), risk=round(float(risk), 2),
                         lunch=bool(m <= 65), flipd=round(float(abs(r.flip_d)), 2), tw=tw[j].strftime('%m-%d %H:%M'),
                         twx=tw[x].strftime('%H:%M'), t0=int(fake[j]), t1=int(fake[x])))
    t = pd.DataFrame(rows)
    L, O = t[t.lunch], t[~t.lunch]
    print(f'全部 {len(t)} 筆；台北 00:00–01:05 {len(L)} 筆 勝 {100 * (L.net > 0).mean():.0f}% 合計 {L.net.sum():+.1f}R 每筆 {L.net.mean():+.2f}R；'
          f'其他 {len(O)} 筆 勝 {100 * (O.net > 0).mean():.0f}% 每筆 {O.net.mean():+.2f}R')
    days = []
    for d in sorted(L.day.unique()):
        idx = np.where(nyd == d)[0]
        bars_ = [[int(fake[q]), round(float(o[q]), 2), round(float(h[q]), 2), round(float(l[q]), 2), round(float(c[q]), 2),
                  None if np.isnan(fast[q]) else round(float(fast[q]), 2), None if np.isnan(slow[q]) else round(float(slow[q]), 2),
                  None if np.isnan(flip_nq[q]) else round(float(flip_nq[q]), 2)] for q in idx]
        tt = t[t.day == d]
        days.append(dict(day=d, bars=bars_, trades=tt.drop(columns=['i', 'x']).to_dict('records'),
                         move=round(float(c[idx[-1]] - o[idx[0]]), 2)))
    summ = dict(n=len(L), win=round(100 * float((L.net > 0).mean())), tot=round(float(L.net.sum()), 1), per=round(float(L.net.mean()), 2),
                on=len(O), owin=round(100 * float((O.net > 0).mean())), oper=round(float(O.net.mean()), 2),
                start='2026-06-29', end=last_day, ndays=int(t.day.nunique()))
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gex_lunch_template.html'), encoding='utf-8').read()
    open(out, 'w', encoding='utf-8').write(tpl.replace('/*DATA*/null', json.dumps(dict(summary=summ, days=days), ensure_ascii=False)))
    print('寫好', out, f'{os.path.getsize(out) / 1e3:.0f} KB')
    for r in L.itertuples():
        print(f'   {r.tw} {"買" if r.side == 1 else "賣"} 進 {r.entry:.2f} 停 {r.stop:.2f}（{r.risk:.1f} 點）{r.exit} {r.twx} {r.net:+.2f}R')


if __name__ == '__main__':
    main()
