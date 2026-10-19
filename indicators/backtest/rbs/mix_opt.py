"""Can the MIX-box breakout be improved? NQ 2 minutes (the Databento year); 5 minutes as a check.

  cd indicators/backtest
  python3 -I rbs/mix_opt.py [2 5]

Baseline = Remi Superb v3: Trend Judge MIX (spread within +-10) for 60 minutes (trend blips up to 4 minutes
ignored) -> box; within 60 minutes the first bar reaching 10% of the box height beyond it is the breakout, a stop
order at that price, stop at the middle, target R, 60-bar time exit; a bar breaking both sides or in an event
window ends the box. 1 point cost.
Prints, each MIX trade on its own (n / year, win %, net R per trade at 2R and 3R, both halves at 3R):
  1. trade the moment Trend Judge turns MIX (entry at that bar's close; fade or follow the trend that just
     ended; stop at the swing extreme or n ATR), by how long the trend lasted
  2. box time (how long MIX must last), breakout distance, how long the box stays valid, where the stop is
  3. filters on the baseline: side, 1-hour EMA20 side, the trend before the MIX, Trend Judge at the breakout,
     box height in ATR, minutes after the box formed, session; target R
  4. one position at a time with the v3 trend signals (trend 0-180 minutes), baseline against the variants
  5. the conditions from 3 put back into v3; 6. v3's default rules (Friday cut-off, no MIX 16-20 New York)
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import mix_range as mr
import mix_breakout as mb
import market_matrix as mm
import trend_follow as tfw

TH, ST, COST, HOLD = 10.0, 35.0, 1.0, 60


class Ctx:
    def __init__(self, tf, one, tdm, H):
        self.tf = tf
        self.df = df = mm.chart(one, tdm, tf, TH, ST)
        mr.TF, mr.TH = tf, TH
        rbs._cache[('NQ', tf)] = df
        self.B = B = mr.load()
        rbs._cache.pop(('NQ', tf), None)
        self.h, self.l, self.c, self.o = B['h'], B['l'], B['c'], B['o']
        self.n = len(self.c)
        self.hole = B['hole']
        self.date = B['date']
        d = sorted(set(self.date)); self.split = d[len(d) // 2]
        self.years = (one.index[-1] - one.index[0]).days / 365.25
        t0 = pd.DataFrame({'t': df.datetime})
        self.h1 = pd.merge_asof(t0, H, on='t', direction='backward').h1.fillna(0).values      # hours done by the bar's start
        self.h1c = pd.merge_asof(pd.DataFrame({'t': df.datetime + pd.Timedelta(minutes=tf)}), H, on='t',
                                 direction='backward').h1.fillna(0).values                   # ... by its close
        et = (df.datetime + pd.Timedelta(minutes=tf)).dt.tz_convert(ss.NY)
        self.halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
        self.tmin = df.tmin.values
        s = mm.trend_signals(df, H, tf)
        F = s[mm.filt(s, TH) & (s.tm < 180)]
        self.trend = {int(i): (int(k), (min(self.l[i - 1], self.l[i]) if k == 1 else max(self.h[i - 1], self.h[i])), '趨勢')
                      for i, k in zip(F.i, F.side)}

    def bars(self, minutes):
        return max(1, round(minutes / self.tf))


def boxes(C, box_min=60, grace_min=4):
    return mb.causal_boxes(C.B, C.bars(box_min), grace=max(0, round(grace_min / C.tf)))


def breaks(C, bx, buf=0.1, valid_min=60, stop_f=0.5, skip_min=0, delay_min=0):
    """First breakout of each box: list of (bar, side, price, stop, info). skip_min: a breakout this soon after the
    box forms ends the box without a trade; delay_min: price is not watched until then (valid_min counts from forming)."""
    B = C.B; state, evt, atr = B['state'], B['evt'], B['atr']
    h, l, o, hole = C.h, C.l, C.o, C.hole; age = C.bars(valid_min); out = []
    for s0, fm, top, bot in bx:
        H = top - bot
        if H <= 0: continue
        bu, bd = top + buf * H, bot - buf * H
        for j in range(fm + 1, min(fm + age, C.n - 1) + 1):
            if hole[j]: break
            if (j - fm) * C.tf <= delay_min: continue
            up, dn = h[j] >= bu, l[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j] or (j - fm) * C.tf <= skip_min: break
            k = 1 if up else -1
            px = max(o[j], bu) if k == 1 else min(o[j], bd)
            stop = top - stop_f * H if k == 1 else bot + stop_f * H
            prior = state[s0 - 1] if s0 > 0 and state[s0 - 1] in (1, -1) else 0
            out.append((j, k, px, stop, dict(hh=H / atr[fm], after=(j - fm) * C.tf, prior=prior * k,
                                              ptm=C.tmin[s0 - 1] if s0 > 0 else 0, h1=C.h1[j] * k,
                                              tj=state[j - 1] * k if state[j - 1] in (1, -1) else 0, sess=B['sess'][j])))
            break
    return out


def turns(C, mode, stop_kind, min_prior=0):
    """Trend Judge turns MIX (trend -> MIX on this bar): enter at the close, fade or follow the trend that ended."""
    B = C.B; state, evt, atr, trad = B['state'], B['evt'], B['atr'], B['tradable']
    h, l, c = C.h, C.l, C.c; out = []
    for j in range(2, C.n):
        if state[j] != 0 or state[j - 1] not in (1, -1) or not trad[j] or evt[j] or C.hole[j]: continue
        if C.tmin[j - 1] < min_prior: continue
        prev = state[j - 1]; k = -prev if mode == 'fade' else prev
        if stop_kind.startswith('swing'):
            w = C.bars(int(stop_kind[5:])); lo, hi = l[max(0, j - w + 1):j + 1].min(), h[max(0, j - w + 1):j + 1].max()
            stop = lo if k == 1 else hi
        else:
            stop = c[j] - k * float(stop_kind[3:]) * atr[j - 1]
        if (c[j] - stop) * k <= 0: continue
        out.append((j, k, c[j], stop, dict(ptm=C.tmin[j - 1], h1=C.h1c[j] * k)))
    return out


def result(C, j, k, px, stop, R, at_close):
    h, l, c, hole = C.h, C.l, C.c, C.hole
    risk = (px - stop) * k; tgt = px + k * R * risk; last = min(j + HOLD, C.n - 1)
    if not at_close and ((l[j] <= stop) if k == 1 else (h[j] >= stop)): return -1.0, risk
    for q in range(j + 1, last + 1):
        if hole[q]: return (c[q - 1] - px) * k / risk, risk
        if (l[q] <= stop) if k == 1 else (h[q] >= stop): return -1.0, risk
        if (h[q] >= tgt) if k == 1 else (l[q] <= tgt): return R, risk
        if C.halt[q]: return (c[q] - px) * k / risk, risk
    return (c[last] - px) * k / risk, risk


def frame(C, cands, at_close=False, Rs=(2.0, 3.0)):
    rows = []
    for j, k, px, stop, info in cands:
        if not C.B['tradable'][j]: continue
        r = {'i': j, 'side': k, 'date': C.date[j], **info}
        for R in Rs:
            res, risk = result(C, j, k, px, stop, R, at_close)
            r[f'n{R:g}'] = res - COST / risk; r['risk'] = risk
        rows.append(r)
    return pd.DataFrame(rows)


def line(C, y, Rs=(2.0, 3.0)):
    if len(y) == 0: return '     0'
    a = y.date.values < C.split; cells = []
    for R in Rs:
        v = y[f'n{R:g}'].values
        cells.append(f'{R:g}R {100 * (v > 0).mean():4.1f}% {v.mean():+.3f}')
    v = y[f'n{Rs[-1]:g}'].values
    ok = '✓' if (v[a].mean() > 0 and v[~a].mean() > 0) else '✗'
    return (f'{len(y) / C.years:5.0f}/年  ' + '  '.join(cells) +
            f'  {Rs[-1]:g}R 前/後 {v[a].mean():+.2f}/{v[~a].mean():+.2f} {ok}  每年 {v.sum() / C.years:+5.0f}R')


def seq(C, cands, R, with_trend=True, close_cands=None):
    mix = {j: (k, px, stop) for j, k, px, stop, _ in cands}
    ce = dict(C.trend) if with_trend else {}
    for j, k, px, stop, _ in (close_cands or []):
        ce.setdefault(j, (k, stop, '轉 MIX'))
    t = tfw.simulate(C.df, ce, mix, R, COST, C.halt)
    a = t.date.values < C.split
    return mm.combo_line(t, C.years) + f'  前/後 {t.net[a].mean():+.3f}/{t.net[~a].mean():+.3f}'


def run(C, R_main):
    Rs = (2.0, 3.0)
    base = breaks(C, boxes(C))
    fb = frame(C, base)
    print(f'\n################ NQ {C.tf} 分 K（{C.years:.1f} 年，每筆扣 1 點；每筆是扣成本後的 R）')
    print(f'   {"基準（v3：MIX 60 分、突破 10%、60 分內有效、停損中線）":<34} ' + line(C, fb))

    print('\n######## 1. 一轉 MIX 就交易（轉 MIX 那根 K 收盤進場）')
    for mode, nm in (('fade', '反向（賭前一段趨勢結束）'), ('follow', '順著前一段趨勢')):
        for sk, snm in (('swing20', '停損：近 20 分高低點'), ('swing60', '停損：近 60 分高低點'), ('atr1', '停損：1 ATR'), ('atr2', '停損：2 ATR')):
            for mp in (0, 30, 60):
                y = frame(C, turns(C, mode, sk, mp), at_close=True)
                print(f'   {nm} {snm} 前段趨勢 ≥ {mp:>2} 分 '.ljust(40) + line(C, y))
    y = frame(C, turns(C, 'fade', 'swing20'), at_close=True)
    print(f'   {"反向、近 20 分、1 小時 EMA 同向":<36} ' + line(C, y[y.h1 > 0]))
    y = frame(C, turns(C, 'follow', 'swing20'), at_close=True)
    print(f'   {"順勢、近 20 分、1 小時 EMA 同向":<36} ' + line(C, y[y.h1 > 0]))

    print('\n######## 2. 改區間的定義')
    print('  MIX 要持續多久才成形（突破 10%、成形後 60 分內有效、停損中線）')
    for bm in (10, 20, 30, 40, 50, 56, 60, 64, 70, 80, 90, 120):
        if bm < C.tf * 2 or bm % C.tf: continue
        y = frame(C, breaks(C, boxes(C, bm)))
        print(f'   {"MIX " + str(bm) + " 分":<36} ' + line(C, y))
        if bm <= 30:
            print(f'   {"　突破方向 = MIX 之前的趨勢":<35} ' + line(C, y[y.prior > 0]))
    print('  突破距離（區間高度的幾 %）')
    bx = boxes(C)
    for buf in (0.0, 0.05, 0.1, 0.2, 0.3):
        print(f'   {"突破 " + format(buf * 100, ".0f") + "%":<36} ' + line(C, frame(C, breaks(C, bx, buf=buf))))
    print('  成形後多久內有效')
    for vm in (20, 40, 60, 90, 120, 180):
        print(f'   {str(vm) + " 分內":<36} ' + line(C, frame(C, breaks(C, bx, valid_min=vm))))
    print('  停損位置（從突破那邊算進區間幾成；0.5 = 中線，1 = 對面）')
    for sf in (0.25, 0.4, 0.5, 0.75, 1.0):
        print(f'   {"停損 " + format(sf, "g"):<36} ' + line(C, frame(C, breaks(C, bx, stop_f=sf))))

    print('\n######## 3. 基準加條件')
    rows = [('作多', fb.side == 1), ('做空', fb.side == -1),
            ('1 小時 EMA 同向', fb.h1 > 0), ('1 小時 EMA 反向', fb.h1 < 0),
            ('突破方向 = MIX 之前的趨勢', fb.prior > 0), ('突破方向 ≠ MIX 之前的趨勢', fb.prior < 0),
            ('MIX 之前的趨勢 < 60 分', fb.ptm < 60), ('MIX 之前的趨勢 ≥ 60 分', fb.ptm >= 60),
            ('突破時 TJ 還是 MIX', fb.tj == 0), ('突破時 TJ 已同向', fb.tj > 0), ('突破時 TJ 反向', fb.tj < 0)]
    for lo, hi in ((0, 2), (2, 3), (3, 4), (4, 6), (6, 99)):
        rows.append((f'區間高度 {lo}–{hi if hi < 99 else "以上"} ATR', (fb.hh >= lo) & (fb.hh < hi)))
    for lo, hi in ((0, 10), (10, 30), (30, 61)):
        rows.append((f'成形後 {lo}–{min(hi, 60)} 分突破', (fb.after > lo) & (fb.after <= hi) if lo else (fb.after <= hi)))
    for k in ('亞洲 20-03', '歐洲 03-09:30', '美股 09:30-16', '收盤後 16-20'):
        rows.append((k, fb.sess == k))
    for nm, m in rows:
        print(f'   {nm:<36} ' + line(C, fb[m]))
    print('  目標')
    ft = frame(C, base, Rs=(1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0))
    for R in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        v = ft[f'n{R:g}'].values; a = ft.date.values < C.split
        print(f'   {format(R, "g") + "R":<6} 勝率 {100 * (v > 0).mean():4.1f}%  每筆 {v.mean():+.3f}R  前/後 {v[a].mean():+.3f}/{v[~a].mean():+.3f}  每年 {v.sum() / C.years:+5.0f}R')

    print(f'\n######## 4. 跟 v3 的趨勢訊號一起做（趨勢 0–180 分，一次一筆，{R_main:g}R）')
    print(f'   {"只有趨勢訊號":<30} ' + seq(C, [], R_main))
    print(f'   {"v3 現在（趨勢 + MIX 基準）":<30} ' + seq(C, base, R_main))
    bxs = {bm: boxes(C, bm) for bm in (30, 40, 90)}
    variants = [('MIX 30 分成形', breaks(C, bxs[30])), ('MIX 40 分成形', breaks(C, bxs[40])), ('MIX 90 分成形', breaks(C, bxs[90])),
                ('突破 0%', breaks(C, bx, buf=0.0)), ('突破 20%', breaks(C, bx, buf=0.2)),
                ('有效 120 分', breaks(C, bx, valid_min=120)), ('停損 0.4', breaks(C, bx, stop_f=0.4)), ('停損 0.75', breaks(C, bx, stop_f=0.75)),
                ('只做 1 小時 EMA 同向', [x for x in base if x[4]['h1'] > 0]),
                ('不做突破時 TJ 反向', [x for x in base if x[4]['tj'] >= 0])]
    for nm, cands in variants:
        print(f'   {"趨勢 + " + nm:<30} ' + seq(C, cands, R_main))
    for mode, nm in (('fade', '反向'), ('follow', '順勢')):
        print(f'   {"趨勢 + MIX 基準 + 一轉 MIX " + nm:<30} ' + seq(C, base, R_main, close_cands=turns(C, mode, 'swing20')))

    print(f'\n######## 5. 第 3 節看起來有用的條件，放回 v3（一次一筆，{R_main:g}R）')
    sk = breaks(C, bx, skip_min=10); dl = breaks(C, bx, delay_min=10); dl70 = breaks(C, bx, delay_min=10, valid_min=70)
    no1620 = lambda xs: [x for x in xs if x[4]['sess'] != '收盤後 16-20']
    fsk = frame(C, sk); fdl = frame(C, dl)
    print(f'   {"（各自獨立）成形後 10 分內突破就作廢":<34} ' + line(C, fsk))
    print(f'   {"（各自獨立）成形後 10 分才開始看":<34} ' + line(C, fdl))
    for nm, cands in (('成形後 10 分內突破就作廢', sk), ('成形後 10 分才開始看（到 60 分）', dl), ('成形後 10 分才開始看（到 70 分）', dl70),
                      ('不做美東 16–20', no1620(base)), ('只做前段趨勢 ≥ 60 分', [x for x in base if x[4]['ptm'] >= 60]),
                      ('只做突破方向 = 前段趨勢', [x for x in base if x[4]['prior'] > 0]),
                      ('10 分內作廢 + 不做 16–20', no1620(sk))):
        print(f'   {"趨勢 + MIX " + nm:<34} ' + seq(C, cands, R_main))
    sess = C.B['sess']; keep = dict(C.trend)
    C.trend = {i: v for i, v in keep.items() if sess[i] != '收盤後 16-20'}
    print(f'   {"趨勢訊號在美東 16–20（各自獨立）":<34} {sum(sess[i] == "收盤後 16-20" for i in keep) / C.years:.0f} 筆/年')
    print(f'   {"趨勢和 MIX 都不做美東 16–20":<34} ' + seq(C, no1620(base), R_main))
    print(f'   {"　+ MIX 成形後 10 分內作廢":<34} ' + seq(C, no1620(sk), R_main))
    C.trend = keep

    print(f'\n######## 6. v3 的預設規則：週五台北週六 02:00 以後不發新訊號 + MIX 不做美東 16–20（一次一筆，{R_main:g}R）')
    tw = (C.df.datetime + pd.Timedelta(minutes=C.tf)).dt.tz_convert('Asia/Taipei')
    late = ((tw.dt.weekday == 5) & (tw.dt.hour * 60 + tw.dt.minute >= 120)).values
    for nm, fri, pm in (('都不加', False, False), ('只加週五', True, False), ('只加 MIX 16–20', False, True), ('兩個都加（v3 預設）', True, True)):
        C.trend = {i: v for i, v in keep.items() if not (fri and late[i])}
        cands = [x for x in base if not (fri and late[x[0]]) and not (pm and x[4]['sess'] == '收盤後 16-20')]
        print(f'   {nm:<30} ' + seq(C, cands, R_main))
    C.trend = keep


def main():
    tfs = [int(a) for a in sys.argv[1:]] or [2]
    one = mm.load_market('nq', [])
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    for tf in tfs:
        run(Ctx(tf, one, tdm, H), 3.0 if tf == 2 else 2.0)


if __name__ == '__main__':
    main()
