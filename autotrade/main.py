"""Remi's Autotrade：TradingView 快訊（webhook）→ IBKR 下單。

  python main.py              # 連 IBKR（config.json 的 ib_port）
  python main.py --dry-run    # 不連 IBKR，只記錄要下的單

兩個本機服務：
  webhook（config 的 webhook_port）：POST /hook/<webhook_secret>，給 TradingView 透過通道（ngrok / Cloudflare）打進來
  管理（config 的 admin_port，只聽 127.0.0.1，不要接到通道上）：GET /status，POST /pause /resume /flatten
"""
from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

from broker import DryRunBroker, IBBroker, LiveAccountRefused
from engine import Engine
from notify import Notifier
from signals import parse_payload

HERE = Path(__file__).resolve().parent
LOGS = HERE / "logs"
# TradingView 送 webhook 的 IP（TradingView 說明文件公布的）
TV_IPS = {"52.89.214.238", "34.212.75.30", "54.218.53.128", "52.32.178.7"}

DEFAULTS = {
    "listen_host": "127.0.0.1", "webhook_port": 8080, "admin_port": 8081,
    "ib_host": "127.0.0.1", "ib_port": 7497, "ib_client_id": 17, "account": "", "allow_live": False,
    "symbol": "MNQ", "exchange": "CME", "qty": 2, "tick": 0.25, "allowed_roots": ["NQ", "MNQ"],
    "max_entry_delay_sec": 15, "max_alert_age_sec": 30, "max_stop_points": 120,
    "max_trades_per_day": 20, "max_daily_loss_usd": 600, "split_first_r": 1.0,
    "allowed_tfs": ["1", "2", "5"], "default_tf": "2", "max_hold_minutes": {"1": 65, "2": 125, "5": 305},
    "flat_time_et": "16:58", "reopen_time_et": "18:00", "roll_days": 8, "tradingview_ips_only": False, "client_ip_header": "",
    "discord_webhook_url": "", "point_value": 2.0, "disconnect_alert_min": 5, "summary_time_et": "17:00",
}

log = logging.getLogger("main")


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(json.loads(path.read_text(encoding="utf-8")))
    sec = cfg.get("webhook_secret", "")
    if len(sec) < 16 or "換成" in sec:
        sys.exit("config.json 的 webhook_secret 要換成至少 16 個字的隨機字串")
    return cfg


def setup_logging():
    LOGS.mkdir(exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOGS / f"{day}.log", encoding="utf-8")])
    logging.getLogger("ib_insync").setLevel(logging.WARNING)
    logging.getLogger("ib_async").setLevel(logging.WARNING)


def write_event(e: dict):
    day = datetime.now().strftime("%Y-%m-%d")
    LOGS.mkdir(exist_ok=True)
    with open(LOGS / f"events-{day}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")


def client_ip(req: web.Request, header: str) -> str:
    # 經過反向代理 / 通道時，真正的來源 IP 在代理設定的標頭（Caddy：X-Forwarded-For，Cloudflare：CF-Connecting-IP）。
    # 只讀 config 指定的那一個，其他標頭可以被偽造
    if header:
        v = req.headers.get(header)
        if v:
            return v.split(",")[-1].strip()
    return req.remote or ""


def webhook_app(cfg: dict, queue: asyncio.Queue) -> web.Application:
    secret = cfg["webhook_secret"].encode()

    async def hook(req: web.Request):
        received = datetime.now(timezone.utc)
        if not hmac.compare_digest(req.match_info["secret"].encode(), secret):
            raise web.HTTPNotFound()
        ip = client_ip(req, cfg["client_ip_header"])
        if cfg["tradingview_ips_only"] and ip not in TV_IPS:
            log.warning("擋掉不是 TradingView 的來源 %s", ip)
            raise web.HTTPForbidden()
        text = await req.text()
        try:
            sig = parse_payload(text, received)
        except ValueError as e:
            write_event({"time": received.isoformat(), "event": "bad_payload", "error": str(e), "raw": text, "ip": ip})
            log.warning("快訊格式不對：%s｜%s", e, text)
            return web.Response(status=400, text=str(e))
        write_event({"time": received.isoformat(), "event": "webhook", "raw": text, "ip": ip})
        queue.put_nowait(sig)
        return web.Response(text="ok")       # TradingView 3 秒內沒收到回應會放棄，所以先回、再排隊下單

    app = web.Application()
    app.router.add_post("/hook/{secret}", hook)
    return app


def admin_app(engine: Engine) -> web.Application:
    async def status(_):
        return web.json_response(engine.status(), dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))

    async def pause(_):
        engine.paused = True
        engine._event("pause")
        return web.Response(text="已暫停：不再進場，出場快訊照做\n")

    async def resume(_):
        engine.paused = False
        engine._event("resume")
        return web.Response(text="恢復進場\n")

    async def flatten(_):
        res = await engine.b.flatten("手動平倉")
        engine._set_owner(None, None)
        engine._event("manual_flatten", result=res)
        return web.json_response(res)

    app = web.Application()
    app.router.add_get("/status", status)
    app.router.add_post("/pause", pause)
    app.router.add_post("/resume", resume)
    app.router.add_post("/flatten", flatten)
    return app


async def worker(engine: Engine, queue: asyncio.Queue):
    while True:
        sig = await queue.get()
        try:
            if sig.action in ("buy", "sell"):
                # IBKR 斷線時等一下再處理；等太久 engine 會判定太晚不進場
                for _ in range(engine.cfg["max_entry_delay_sec"] * 2):
                    if engine.b.connected():
                        break
                    await asyncio.sleep(0.5)
            elif sig.action == "exit":
                while not engine.b.connected():      # 出場一定要做到
                    await asyncio.sleep(1)
            await engine.handle(sig)
        except Exception:  # noqa: BLE001
            log.exception("處理快訊出錯：%s", sig.raw)


async def safety(engine: Engine, notifier: Notifier):
    seeded = False
    while True:
        await asyncio.sleep(5)
        try:
            await engine.tick()
            connected = engine.b.connected()
            if connected and not seeded:
                # 重開程式時已經有部位：從 IBKR 的平均成本接著算這筆的損益
                pos, avg = engine.b.position_avg()
                if pos and notifier.tracker.pos == 0:
                    notifier.tracker.pos, notifier.tracker.entry = pos, avg
                seeded = True
            notifier.tick(connected)
        except Exception:  # noqa: BLE001
            log.exception("安全網出錯")


async def main_async(cfg: dict, dry: bool):
    broker = DryRunBroker(cfg) if dry else IBBroker(cfg)
    notifier = Notifier(cfg)

    def events(e: dict):
        write_event(e)
        notifier.on_event(e)

    def fills(f: dict):
        write_event({"time": datetime.now(timezone.utc).isoformat(), "event": "fill", **f})
        notifier.on_fill(f)

    broker.on_fill = fills
    engine = Engine(broker, cfg, events=events, state_path=HERE / "state.json")
    queue: asyncio.Queue = asyncio.Queue()

    runners = []
    for app, host, port in ((webhook_app(cfg, queue), cfg["listen_host"], cfg["webhook_port"]),
                            (admin_app(engine), "127.0.0.1", cfg["admin_port"])):
        r = web.AppRunner(app, access_log=None)
        await r.setup()
        await web.TCPSite(r, host, port).start()
        runners.append(r)
    log.info("webhook 在 %s:%d，管理在 127.0.0.1:%d，%s", cfg["listen_host"], cfg["webhook_port"],
             cfg["admin_port"], "DRY RUN（不下單）" if dry else f"IBKR {cfg['ib_host']}:{cfg['ib_port']}")
    events({"time": datetime.now(timezone.utc).isoformat(), "event": "start", "dry_run": dry,
            "qty": cfg["qty"], "symbol": cfg["symbol"], "ib_port": cfg["ib_port"]})
    log.info("Discord 通知：%s", "開" if notifier.on else "關（config 沒填 discord_webhook_url）")
    try:
        await asyncio.gather(broker.run(), worker(engine, queue), safety(engine, notifier), notifier.run())
    finally:
        for r in runners:
            await r.cleanup()


def main():
    ap = argparse.ArgumentParser(description="Remi's Autotrade")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--dry-run", action="store_true", help="不連 IBKR，只記錄要下的單")
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(Path(args.config))
    try:
        asyncio.run(main_async(cfg, args.dry_run))
    except LiveAccountRefused as e:
        sys.exit(f"停止：{e}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
