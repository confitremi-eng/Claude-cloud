"""IBKR 下單（透過 TWS / IB Gateway 的 API），和不下單的測試用券商。"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, datetime, timedelta
from typing import Optional

log = logging.getLogger("broker")

ORDER_REF = "RemiAutotrade"          # 自動下單的單都掛這個標記，平倉時只取消這些單
DONE = {"Cancelled", "ApiCancelled", "Filled", "Inactive"}


class LiveAccountRefused(RuntimeError):
    pass


class IBBroker:
    def __init__(self, cfg: dict):
        try:
            import ib_async as ibl
        except ImportError:
            import ib_insync as ibl
        self.ibl = ibl
        self.cfg = cfg
        self.ib = ibl.IB()
        self.account: Optional[str] = None
        self._pnl = None
        self._front = None            # (到期日, Contract)
        self.on_fill = None           # 自動下單的單整張成交時呼叫：dict(side, qty, price, kind)
        self._seen = set()
        self.ib.execDetailsEvent += self._exec

    # ── 連線 ──
    async def run(self):
        """連上 IBKR，斷線就每 10 秒重連（IB Gateway / TWS 每天會自動重啟）。"""
        c = self.cfg
        while True:
            if not self.ib.isConnected():
                try:
                    await self.ib.connectAsync(c["ib_host"], c["ib_port"], clientId=c["ib_client_id"], timeout=10)
                    self._after_connect()
                    log.info("IBKR 已連線：帳戶 %s", self.account)
                except LiveAccountRefused:
                    self.ib.disconnect()
                    raise
                except Exception as e:  # noqa: BLE001
                    log.warning("IBKR 連不上（%s），10 秒後重試", e)
                    self.ib.disconnect()
            await asyncio.sleep(10)

    def _after_connect(self):
        accts = self.ib.managedAccounts()
        want = self.cfg.get("account") or ""
        acct = want if want else (accts[0] if accts else None)
        if not acct or acct not in accts:
            raise LiveAccountRefused(f"找不到帳戶 {want!r}，登入的帳戶有 {accts}")
        # 模擬帳戶的帳號是 DU 開頭；沒打開 allow_live 就不接真倉
        if not acct.startswith("DU") and not self.cfg.get("allow_live"):
            raise LiveAccountRefused(f"{acct} 不是模擬帳戶（DU 開頭），config 的 allow_live 是 false，不連線")
        self.account = acct
        self._pnl = self.ib.reqPnL(acct)

    def connected(self) -> bool:
        return self.ib.isConnected() and self.account is not None

    def _exec(self, trade, fill):
        e = fill.execution
        if trade.order.orderRef != ORDER_REF or fill.contract.symbol != self.cfg["symbol"] or e.execId in self._seen:
            return
        self._seen.add(e.execId)
        if e.cumQty < trade.order.totalQuantity or not self.on_fill:
            return                    # 分批成交：等整張成交完再通知
        kind = {"MKT": "市價", "LMT": "目標", "STP": "停損"}.get(trade.order.orderType, trade.order.orderType)
        self.on_fill({"side": e.side, "qty": int(trade.order.totalQuantity), "price": e.avgPrice, "kind": kind})

    def position_avg(self):
        """(口數, 平均成本價)；重開程式時接續算損益用。"""
        for p in self.ib.positions(self.account) if self.connected() else []:
            if p.contract.symbol == self.cfg["symbol"] and p.contract.secType == "FUT" and p.position:
                mult = float(p.contract.multiplier or self.cfg.get("point_value", 2))
                return int(p.position), p.avgCost / mult
        return 0, None

    # ── 狀態 ──
    def _ours(self):
        return [t for t in self.ib.openTrades()
                if t.contract.symbol == self.cfg["symbol"] and t.order.orderRef == ORDER_REF
                and t.orderStatus.status not in DONE]

    def position(self) -> int:
        if not self.connected():
            return 0
        return int(sum(p.position for p in self.ib.positions(self.account)
                       if p.contract.symbol == self.cfg["symbol"] and p.contract.secType == "FUT"))

    def working_orders(self) -> int:
        return len(self._ours()) if self.connected() else 0

    def daily_pnl(self) -> Optional[float]:
        v = getattr(self._pnl, "dailyPnL", None)
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)

    # ── 合約 ──
    async def contract(self, month: Optional[str]):
        """快訊有給月份（跟 TradingView NQ1! 同一個合約）就用它；沒給就用最近、離到期超過 roll_days 天的合約。"""
        ibl, c = self.ibl, self.cfg
        if month:
            fut = ibl.Future(c["symbol"], month, c["exchange"], currency="USD")
            q = await self.ib.qualifyContractsAsync(fut)
            if q:
                return q[0]
            log.warning("找不到 %s %s，改用近月", c["symbol"], month)
        today = date.today()
        if self._front and self._front[0] - today > timedelta(days=c["roll_days"]):
            return self._front[1]
        cds = await self.ib.reqContractDetailsAsync(ibl.Future(c["symbol"], exchange=c["exchange"], currency="USD"))
        best = None
        for cd in cds:
            exp = datetime.strptime(cd.contract.lastTradeDateOrContractMonth[:8], "%Y%m%d").date()
            if exp - today > timedelta(days=c["roll_days"]) and (best is None or exp < best[0]):
                best = (exp, cd.contract)
        if best is None:
            raise RuntimeError(f"找不到 {c['symbol']} 的期貨合約")
        self._front = best
        return best[1]

    # ── 下單 ──
    async def place_bracket(self, side: str, qty: int, stop: float, target: float, month: Optional[str]) -> dict:
        ibl, ib = self.ibl, self.ib
        con = await self.contract(month)
        rev = "SELL" if side == "BUY" else "BUY"
        common = dict(account=self.account, orderRef=ORDER_REF)
        parent = ibl.MarketOrder(side, qty, orderId=ib.client.getReqId(), transmit=False, tif="DAY", **common)
        tp = ibl.LimitOrder(rev, qty, target, orderId=ib.client.getReqId(), parentId=parent.orderId,
                            transmit=False, tif="GTC", outsideRth=True, **common)
        sl = ibl.StopOrder(rev, qty, stop, orderId=ib.client.getReqId(), parentId=parent.orderId,
                           transmit=True, tif="GTC", outsideRth=True, **common)
        trades = [ib.placeOrder(con, o) for o in (parent, tp, sl)]
        fill = await self._wait_fill(trades[0], 5)
        return {"contract": con.localSymbol, "order_id": parent.orderId, "fill": fill,
                "status": trades[0].orderStatus.status}

    async def _wait_fill(self, trade, secs: float) -> Optional[float]:
        for _ in range(int(secs * 10)):
            if trade.orderStatus.status in DONE:
                break
            await asyncio.sleep(0.1)
        p = trade.orderStatus.avgFillPrice
        return p if p else None

    async def flatten(self, why: str) -> dict:
        """取消自動下單的掛單，等取消完成後，再把剩下的部位市價平掉。"""
        if not self.connected():
            return {"ok": False, "reason": "沒連上"}
        ours = self._ours()
        for t in ours:
            self.ib.cancelOrder(t.order)
        for _ in range(30):
            if not self._ours():
                break
            await asyncio.sleep(0.1)
        closed = []
        for p in self.ib.positions(self.account):
            if p.contract.symbol != self.cfg["symbol"] or p.contract.secType != "FUT" or p.position == 0:
                continue
            con = p.contract
            if not con.exchange:
                con.exchange = self.cfg["exchange"]
            side = "SELL" if p.position > 0 else "BUY"
            t = self.ib.placeOrder(con, self.ibl.MarketOrder(side, abs(p.position), account=self.account,
                                                             orderRef=ORDER_REF, tif="DAY"))
            fill = await self._wait_fill(t, 5)
            closed.append({"contract": con.localSymbol, "qty": p.position, "fill": fill,
                           "status": t.orderStatus.status})
        log.info("平倉（%s）：取消 %d 張單，平掉 %s", why, len(ours), closed)
        return {"ok": True, "cancelled": len(ours), "closed": closed}


class DryRunBroker:
    """不連 IBKR：把要下的單寫進記錄，部位用假的。測 TradingView → webhook 這段用。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.pos = 0
        self.orders = 0
        self.pnl: Optional[float] = 0.0
        self.log: list = []
        self.on_fill = None
        self.last_px: Optional[float] = None

    def position_avg(self):
        return self.pos, self.last_px

    async def run(self):
        while True:
            await asyncio.sleep(3600)

    def connected(self) -> bool:
        return True

    def position(self) -> int:
        return self.pos

    def working_orders(self) -> int:
        return self.orders

    def daily_pnl(self) -> Optional[float]:
        return self.pnl

    async def place_bracket(self, side, qty, stop, target, month) -> dict:
        self.pos = qty if side == "BUY" else -qty
        self.orders = 2
        self.log.append(("bracket", side, qty, stop, target, month))
        self.last_px = round((stop + target) / 2, 2)   # 假的成交價
        if self.on_fill:
            self.on_fill({"side": "BOT" if side == "BUY" else "SLD", "qty": qty, "price": self.last_px, "kind": "市價"})
        return {"dry_run": True, "contract": f"{self.cfg['symbol']} {month or '近月'}", "fill": self.last_px}

    async def flatten(self, why: str) -> dict:
        self.log.append(("flatten", why, self.pos))
        r = {"dry_run": True, "cancelled": self.orders, "closed": self.pos}
        if self.pos and self.on_fill:
            self.on_fill({"side": "SLD" if self.pos > 0 else "BOT", "qty": abs(self.pos), "price": self.last_px, "kind": "市價"})
        self.pos, self.orders = 0, 0
        return r
