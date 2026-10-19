"""TradingView 快訊訊息的解析：Remi Superb v3 策略的 alert_message（JSON）。"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

MONTH_CODES = "FGHJKMNQUVXZ"

# 例：NQZ2026、CME_MINI:NQZ2026、MNQH27
_CONTRACT_RE = re.compile(r"^(?:[A-Z_]+:)?([A-Z]{1,4}?)([FGHJKMNQUVXZ])(\d{4}|\d{2})$")
# 例：NQ1!、CME_MINI:MNQ1!
_CONT_RE = re.compile(r"^(?:[A-Z_]+:)?([A-Z]{1,4})\d!$")


@dataclass
class Signal:
    action: str                  # buy / sell / exit
    root: str                    # 圖上的商品：NQ、MNQ
    contract_month: Optional[str]  # YYYYMM，快訊沒給就是 None
    stop: Optional[float] = None
    target: Optional[float] = None
    price: Optional[float] = None
    signal: str = ""
    tv_time: Optional[datetime] = None
    received: Optional[datetime] = None
    raw: str = ""


def parse_contract(code: str) -> Optional[tuple]:
    """'NQZ2026' → ('NQ', '202612')；認不出來回 None。"""
    m = _CONTRACT_RE.match(code.strip().upper())
    if not m:
        return None
    root, mon, yr = m.groups()
    year = int(yr) if len(yr) == 4 else 2000 + int(yr)
    return root, f"{year}{MONTH_CODES.index(mon) + 1:02d}"


def ticker_root(ticker: str) -> Optional[str]:
    """'NQ1!' → 'NQ'，'MNQZ2026' → 'MNQ'。"""
    t = ticker.strip().upper()
    m = _CONT_RE.match(t)
    if m:
        return m.group(1)
    c = parse_contract(t)
    return c[0] if c else None


def round_tick(px: float, tick: float) -> float:
    return round(round(px / tick) * tick, 10)


def _num(v) -> Optional[float]:
    if v is None or v == "":
        return None
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        raise ValueError(f"數字不對：{v}")
    return f


def _tv_time(v) -> Optional[datetime]:
    # {{timenow}} 展開成 2026-10-19T14:30:05Z；沒展開（還是 {{timenow}}）就當作沒給
    if not v or "{" in str(v):
        return None
    try:
        return datetime.strptime(str(v), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_payload(text: str, received: datetime) -> Signal:
    try:
        d = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"不是 JSON：{e}") from None
    if not isinstance(d, dict):
        raise ValueError("JSON 不是物件")

    action = str(d.get("action", "")).lower()
    if action not in ("buy", "sell", "exit"):
        raise ValueError(f"action 不對：{action!r}")

    ticker = str(d.get("ticker", ""))
    root = ticker_root(ticker)
    month = None
    cc = d.get("contract")
    if cc:
        parsed = parse_contract(str(cc))
        if parsed:
            root = root or parsed[0]
            month = parsed[1]
    if not root:
        raise ValueError(f"認不出商品：ticker={ticker!r} contract={cc!r}")

    sig = Signal(action=action, root=root, contract_month=month, signal=str(d.get("signal", "")),
                 tv_time=_tv_time(d.get("tv_time")), received=received, raw=text)
    if action != "exit":
        sig.stop = _num(d.get("stop"))
        sig.target = _num(d.get("target"))
        sig.price = _num(d.get("price"))
        if sig.stop is None or sig.target is None:
            raise ValueError("進場快訊缺停損或目標")
    return sig
