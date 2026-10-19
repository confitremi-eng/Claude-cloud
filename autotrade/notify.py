"""Discord 通知：進場、出場（含這筆損益）、沒下單的原因、安全網、斷線、盤後總結。

config.json 的 discord_webhook_url 沒填就不送。送不出去只記在 log，不影響下單。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from engine import ET, trading_day

log = logging.getLogger("notify")

SIDE = {"BUY": "買", "SELL": "賣", "BOT": "買", "SLD": "賣"}


def _fmt(p) -> str:
    return "—" if p is None else f"{p:,.2f}"


def _usd(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}${abs(v):,.2f}"


def _pts(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}{abs(v):.2f} 點"


class Tracker:
    """用 IBKR 的成交算每一筆的損益（不含手續費）。"""

    def __init__(self, point_value: float):
        self.pv = point_value
        self.pos = 0
        self.entry: Optional[float] = None
        self.closed: List[dict] = []      # {"day", "pts", "usd", "kind"}

    def on_fill(self, f: dict) -> Optional[dict]:
        """f：side（BOT/SLD）、qty、price、kind。平倉時回傳這筆的結果。"""
        d = 1 if f["side"] in ("BOT", "BUY") else -1
        qty = int(f["qty"])
        if self.pos == 0:
            self.pos, self.entry = d * qty, f["price"]
            return None
        if (self.pos > 0) == (d > 0):            # 加碼（照理不會發生）：攤平
            n = abs(self.pos) + qty
            self.entry = (self.entry * abs(self.pos) + f["price"] * qty) / n
            self.pos += d * qty
            return None
        q = min(qty, abs(self.pos))
        dirn = 1 if self.pos > 0 else -1
        pts = (f["price"] - self.entry) * dirn
        res = {"day": f["day"], "pts": pts, "usd": pts * self.pv * q, "qty": q, "kind": f["kind"],
               "entry": self.entry, "exit": f["price"], "dir": dirn}
        self.pos += d * qty
        if self.pos == 0:
            self.entry = None
        self.closed.append(res)
        return res

    def day_stats(self, day: str) -> dict:
        t = [x for x in self.closed if x["day"] == day]
        wins = sum(1 for x in t if x["usd"] > 0)
        return {"n": len(t), "wins": wins, "usd": sum(x["usd"] for x in t), "pts": sum(x["pts"] for x in t)}


class Notifier:
    def __init__(self, cfg: dict, poster: Optional[Callable] = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.url = cfg.get("discord_webhook_url") or ""
        self.label = "模擬" if not cfg.get("allow_live") else "真倉"
        self.tracker = Tracker(cfg.get("point_value", 2.0))
        self.clock = clock
        self.q: asyncio.Queue = asyncio.Queue()
        self._post = poster or self._discord
        self.down_since: Optional[datetime] = None
        self.down_sent = False
        self.summary_day: Optional[str] = None
        self.disconnect_alert_min = cfg.get("disconnect_alert_min", 5)
        self.summary_time_et = cfg.get("summary_time_et", "17:00")

    @property
    def on(self) -> bool:
        return bool(self.url)

    def send(self, text: str):
        if self.on:
            self.q.put_nowait(text)

    async def run(self):
        while True:
            text = await self.q.get()
            try:
                await self._post(text)
            except Exception as e:  # noqa: BLE001
                log.warning("Discord 送不出去：%s", e)

    async def _discord(self, text: str):
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.post(self.url, json={"content": text[:1900], "username": "Remi Autotrade"}) as r:
                if r.status >= 300:
                    raise RuntimeError(f"HTTP {r.status} {await r.text()}")

    # ── engine 的事件 ──
    def on_event(self, e: dict):
        k = e.get("event")
        if k == "entry":
            r = e.get("result") or {}
            fill, px = r.get("fill"), e.get("price")
            d = 1 if e["side"] == "BUY" else -1
            lines = [f"{'🟢' if d > 0 else '🔴'} **進場 {SIDE[e['side']]} {e['qty']} 口 {r.get('contract', '')}**（{self.label}）"
                     f" @ {_fmt(fill)}　{e.get('signal', '')}"]
            if fill:
                lines.append(f"停損 {_fmt(e['stop'])}（{abs(fill - e['stop']):.2f} 點）｜目標 {_fmt(e['target'])}"
                             f"（{abs(e['target'] - fill):.2f} 點）")
            if fill and px:
                lines.append(f"滑價 {(fill - px) * d:+.2f} 點（策略價 {_fmt(px)}）")
            if e.get("tv_delay_sec") is not None:
                lines.append(f"快訊延遲 {e['tv_delay_sec']:.0f} 秒")
            if not fill:
                lines.append(f"⚠️ 5 秒內沒有成交回報，狀態 {r.get('status')}")
            self.send("\n".join(lines))
        elif k == "reject":
            what = {"buy": "買", "sell": "賣", "exit": "出場"}.get(e.get("action"), e.get("action"))
            self.send(f"⛔ 沒下單（{what} {e.get('signal') or ''}）：{e.get('reason')}")
        elif k == "safety_exit":
            self.send(f"⚠️ 安全網平倉：{e.get('reason')}")
        elif k == "halt":
            self.send(f"🛑 當日損益 {_usd(e.get('daily_pnl', 0))}，到虧損上限，平倉並停止進場到下一個交易日")
        elif k == "manual_flatten":
            self.send("✋ 手動平倉")
        elif k == "pause":
            self.send("⏸ 已暫停：不再進場，出場照做")
        elif k == "resume":
            self.send("▶️ 恢復進場")
        elif k == "start":
            self.send(f"🚀 autotrade 啟動（{self.label}，{e.get('symbol')} {e.get('qty')} 口）")
        elif k == "bad_payload":
            self.send(f"⚠️ 收到格式不對的快訊：{e.get('error')}")

    # ── IBKR 成交（broker.on_fill） ──
    def on_fill(self, f: dict):
        f.setdefault("day", trading_day(self.clock()))
        res = self.tracker.on_fill(f)
        if res is None:
            return                       # 進場的成交，engine 的 entry 事件已經通知
        icon = "✅" if res["usd"] > 0 else "❌" if res["usd"] < 0 else "➖"
        st = self.tracker.day_stats(res["day"])
        self.send(f"{icon} **出場（{f['kind']}）{SIDE[f['side']]} {res['qty']} 口 @ {_fmt(res['exit'])}**\n"
                  f"這筆 {_pts(res['pts'])}｜{_usd(res['usd'])}（進場 {_fmt(res['entry'])}，未扣手續費）\n"
                  f"今天 {st['n']} 筆，{_usd(st['usd'])}")

    # ── 每幾秒看一次：斷線、盤後總結 ──
    def tick(self, connected: bool):
        now = self.clock()
        if connected:
            if self.down_sent:
                self.send("✅ IBKR 已重新連線")
            self.down_since, self.down_sent = None, False
        else:
            self.down_since = self.down_since or now
            mins = (now - self.down_since).total_seconds() / 60
            if mins >= self.disconnect_alert_min and not self.down_sent:
                self.down_sent = True
                self.send(f"⚠️ IBKR 斷線 {mins:.0f} 分鐘（快訊來了也不會進場），程式持續重連中")
        et = now.astimezone(ET)
        h, m = (int(x) for x in self.summary_time_et.split(":"))
        day = trading_day(now)
        if et.weekday() < 5 and (et.hour, et.minute) >= (h, m) and et.hour < 18 and self.summary_day != day:
            self.summary_day = day
            st = self.tracker.day_stats(day)
            if st["n"] == 0:
                self.send(f"📊 {day} 盤後：今天沒有交易")
            else:
                self.send(f"📊 {day} 盤後：{st['n']} 筆，勝 {st['wins']} 敗 {st['n'] - st['wins']}，"
                          f"{_pts(st['pts'])}（每口），{_usd(st['usd'])}（未扣手續費）")
