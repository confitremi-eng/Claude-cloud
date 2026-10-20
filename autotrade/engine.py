"""收到快訊後要不要下單、下什麼單；跟券商無關的規則都在這裡，方便測試。

規則：
- 一次一筆：IBKR 上已經有 MNQ 部位或自動下單的掛單，就不再進場
- 多張圖（2 分、5 分）共用一個倉位：誰先進場倉位就歸誰（owner_tf），持倉期間另一張圖的進場、出場快訊都不理
- 進場用市價，同時掛停損和目標（OCA，一邊成交另一邊取消），價格用快訊給的
- 出場快訊：取消自動下單的掛單，部位市價平掉（已經被停損 / 目標出掉就什麼都不做）
- 安全網（TradingView 的出場快訊沒到也會做）：持有太久平倉、美東休市前平倉、當日虧損上限
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from signals import Signal, round_tick

ET = ZoneInfo("America/New_York")
log = logging.getLogger("engine")


def trading_day(now: datetime) -> str:
    """CME 交易日：美東 18:00 以後算下一天。"""
    return (now.astimezone(ET) + timedelta(hours=6)).date().isoformat()


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


class Engine:
    def __init__(self, broker, cfg: dict, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 events: Optional[Callable[[dict], None]] = None, state_path: Optional[Path] = None):
        self.b = broker
        self.cfg = cfg
        self.clock = clock
        self.events = events or (lambda e: None)
        self.paused = False
        self.halt_day: Optional[str] = None     # 當日虧損到上限的交易日
        self.day = trading_day(clock())
        self.trades_today = 0
        self.entry_time: Optional[datetime] = None
        self.owner_tf: Optional[str] = None     # 目前倉位是哪張圖（週期）的單
        self.state_path = state_path
        self._load()

    # ── 狀態 ──
    def _load(self):
        """重開程式時接回倉位歸屬和進場時間（存在 state.json）。"""
        if not self.state_path or not self.state_path.exists():
            return
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.owner_tf = d.get("owner_tf")
            self.entry_time = datetime.fromisoformat(d["entry_time"]) if d.get("entry_time") else None
        except (ValueError, KeyError, OSError) as e:
            log.warning("state.json 讀不了：%s", e)

    def _set_owner(self, tf: Optional[str], entry_time: Optional[datetime]):
        self.owner_tf, self.entry_time = tf, entry_time
        if self.state_path:
            self.state_path.write_text(json.dumps({"owner_tf": tf, "entry_time": entry_time.isoformat() if entry_time else None}),
                                       encoding="utf-8")

    def tf_of(self, sig: Signal) -> str:
        return sig.tf or self.cfg["default_tf"]

    def max_hold(self, tf: Optional[str]) -> float:
        m = self.cfg["max_hold_minutes"]
        if isinstance(m, dict):
            return float(m.get(tf or self.cfg["default_tf"], max(m.values())))
        return float(m)
    def _roll_day(self, now: datetime):
        d = trading_day(now)
        if d != self.day:
            self.day = d
            self.trades_today = 0

    def in_flat_window(self, now: datetime) -> bool:
        """美東休市前到重新開盤（預設 16:58–18:00）：不進場，有部位就平。"""
        t = now.astimezone(ET).time()
        return _hm(self.cfg["flat_time_et"]) <= t < _hm(self.cfg["reopen_time_et"])

    def status(self) -> dict:
        return {"paused": self.paused, "halted": self.halt_day == self.day, "trading_day": self.day,
                "trades_today": self.trades_today, "connected": self.b.connected(),
                "position": self.b.position(), "working_orders": self.b.working_orders(),
                "daily_pnl": self.b.daily_pnl(),
                "owner_tf": self.owner_tf, "entry_time": self.entry_time.isoformat() if self.entry_time else None}

    def _event(self, kind: str, **kw):
        e = {"time": self.clock().isoformat(), "event": kind, **kw}
        self.events(e)
        log.info("%s %s", kind, kw)

    # ── 快訊 ──
    async def handle(self, sig: Signal):
        now = self.clock()
        self._roll_day(now)
        delay = (now - sig.tv_time).total_seconds() if sig.tv_time else None
        base = {"action": sig.action, "signal": sig.signal, "stop": sig.stop, "target": sig.target,
                "price": sig.price, "contract_month": sig.contract_month, "tf": self.tf_of(sig),
                "tv_delay_sec": round(delay, 1) if delay is not None else None}

        if sig.root not in self.cfg["allowed_roots"]:
            return self._event("reject", reason=f"商品 {sig.root} 不在 allowed_roots", **base)
        tf = self.tf_of(sig)
        if tf not in self.cfg["allowed_tfs"]:
            return self._event("reject", reason=f"{tf} 分不在 allowed_tfs", **base)

        if sig.action == "exit":
            if self.owner_tf and tf != self.owner_tf:
                # 倉位是另一張圖的單：這張圖自己（策略測試器裡）的出場，跟 IBKR 上的倉位無關
                return self._event("ignore", reason=f"倉位是 {self.owner_tf} 分的單，不理 {tf} 分的出場", **base)
            res = await self.b.flatten("快訊出場")
            self._set_owner(None, None)
            return self._event("exit", result=res, **base)

        reason = self._entry_block(sig, now, delay)
        if reason:
            return self._event("reject", reason=reason, **base)

        tick = self.cfg["tick"]
        stop, target = round_tick(sig.stop, tick), round_tick(sig.target, tick)
        side = "BUY" if sig.action == "buy" else "SELL"
        res = await self.b.place_bracket(side, self.cfg["qty"], stop, target, sig.contract_month)
        self.trades_today += 1
        self._set_owner(tf, now)
        self._event("entry", side=side, qty=self.cfg["qty"], result=res, **base)

    def _entry_block(self, sig: Signal, now: datetime, delay: Optional[float]) -> Optional[str]:
        c = self.cfg
        if self.paused:
            return "已暫停（/pause）"
        if self.halt_day == self.day:
            return "今天虧損已到上限"
        if self.trades_today >= c["max_trades_per_day"]:
            return f"今天已做 {self.trades_today} 筆，到上限"
        if self.in_flat_window(now):
            return "美東休市前後不進場"
        waited = (now - sig.received).total_seconds()
        if waited > c["max_entry_delay_sec"]:
            return f"收到後 {waited:.0f} 秒才輪到處理（IBKR 斷線？），太晚不進場"
        if delay is not None and delay > c["max_alert_age_sec"]:
            return f"快訊觸發後 {delay:.0f} 秒才送到，太晚不進場"
        if not self.b.connected():
            return "IBKR 沒連上"
        if self.b.position() != 0 or self.b.working_orders() > 0:
            return f"已經有 {self.owner_tf} 分的單（一次一筆）" if self.owner_tf else "已經有部位或掛單（一次一筆）"
        s, t = sig.stop, sig.target
        if sig.action == "buy" and not s < t:
            return "買單的停損要在目標下面"
        if sig.action == "sell" and not t < s:
            return "賣單的停損要在目標上面"
        if sig.price is not None:
            if sig.action == "buy" and not s < sig.price < t:
                return "買單：進場價不在停損和目標之間"
            if sig.action == "sell" and not t < sig.price < s:
                return "賣單：進場價不在停損和目標之間"
            if abs(sig.price - s) > c["max_stop_points"]:
                return f"停損 {abs(sig.price - s):.2f} 點，超過 max_stop_points"
        return None

    # ── 安全網，每幾秒跑一次 ──
    async def tick(self):
        now = self.clock()
        self._roll_day(now)
        if not self.b.connected():
            return
        pos = self.b.position()
        if pos == 0 and self.b.working_orders() == 0 and (self.owner_tf or self.entry_time):
            self._set_owner(None, None)            # 停損 / 目標在 IBKR 成交了：倉位沒了
        pnl = self.b.daily_pnl()
        if pnl is not None and pnl <= -self.cfg["max_daily_loss_usd"] and self.halt_day != self.day:
            self.halt_day = self.day
            res = await self.b.flatten("當日虧損上限")
            self._event("halt", daily_pnl=pnl, result=res)
            return
        if pos == 0:
            return
        if self.in_flat_window(now):
            res = await self.b.flatten("休市前平倉")
            self._set_owner(None, None)
            return self._event("safety_exit", reason="休市前平倉", result=res)
        if self.entry_time is None:
            self._set_owner(self.owner_tf, now)    # 有部位卻不知道何時進場：從現在起算
        held = (now - self.entry_time).total_seconds() / 60
        if held >= self.max_hold(self.owner_tf):
            res = await self.b.flatten("持有太久")
            self._set_owner(None, None)
            self._event("safety_exit", reason=f"持有 {held:.0f} 分鐘", result=res)
