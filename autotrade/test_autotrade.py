"""python -m unittest test_autotrade -v（在 autotrade/ 裡跑）"""
import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone

from aiohttp.test_utils import TestClient, TestServer

from broker import DryRunBroker
from engine import ET, Engine, trading_day
from main import DEFAULTS, webhook_app
from notify import Notifier, Tracker
from signals import parse_contract, parse_payload, round_tick, ticker_root

SECRET = "test-secret-1234567890"


def cfg(**kw):
    c = dict(DEFAULTS, webhook_secret=SECRET)
    c.update(kw)
    return c


def et(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=ET).astimezone(timezone.utc)


def msg(action="buy", stop=24990.0, target=25030.0, price=25000.0, contract="NQZ2026", tv_time="{{timenow}}"):
    d = {"strategy": "Remi Superb v3", "ticker": "NQ1!", "contract": contract, "action": action, "qty": 1,
         "signal": "趨勢", "stop": stop, "target": target, "price": price, "tv_time": tv_time}
    if action == "exit":
        d = {"strategy": "Remi Superb v3", "ticker": "NQ1!", "contract": contract, "action": "exit"}
    return json.dumps(d, ensure_ascii=False)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class TestSignals(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(parse_contract("NQZ2026"), ("NQ", "202612"))
        self.assertEqual(parse_contract("CME_MINI:MNQH2027"), ("MNQ", "202703"))
        self.assertEqual(parse_contract("NQM27"), ("NQ", "202706"))
        self.assertIsNone(parse_contract("NQ1!"))

    def test_root(self):
        self.assertEqual(ticker_root("NQ1!"), "NQ")
        self.assertEqual(ticker_root("CME_MINI:MNQ1!"), "MNQ")
        self.assertEqual(ticker_root("MNQZ2026"), "MNQ")

    def test_round(self):
        self.assertEqual(round_tick(25000.13, 0.25), 25000.25)
        self.assertEqual(round_tick(25000.12, 0.25), 25000.0)

    def test_payload(self):
        now = datetime.now(timezone.utc)
        s = parse_payload(msg(tv_time="2026-10-19T14:30:05Z"), now)
        self.assertEqual((s.action, s.root, s.contract_month, s.stop), ("buy", "NQ", "202612", 24990.0))
        self.assertEqual(s.tv_time, datetime(2026, 10, 19, 14, 30, 5, tzinfo=timezone.utc))
        self.assertIsNone(parse_payload(msg(), now).tv_time)          # {{timenow}} 沒展開
        self.assertEqual(parse_payload(msg("exit"), now).action, "exit")
        for bad in ("hello", '{"action":"buy","ticker":"NQ1!"}', '{"action":"hold","ticker":"NQ1!"}'):
            with self.assertRaises(ValueError):
                parse_payload(bad, now)


class TestEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock(et(2026, 10, 19, 10, 0))
        self.b = DryRunBroker(cfg())
        self.e = Engine(self.b, cfg(), clock=self.clock)

    def sig(self, *a, **kw):
        return parse_payload(msg(*a, **kw), self.clock())

    async def test_entry_bracket_two_lots(self):
        await self.e.handle(self.sig(stop=24990.1, target=25030.2))
        self.assertEqual(self.b.log, [("bracket", "BUY", 2, 24990.0, 25030.25, "202612")])
        self.assertEqual(self.b.pos, 2)

    async def test_sell(self):
        await self.e.handle(self.sig("sell", stop=25010, target=24970, price=25000))
        self.assertEqual(self.b.log[0][:3], ("bracket", "SELL", 2))

    async def test_one_at_a_time(self):
        await self.e.handle(self.sig())
        await self.e.handle(self.sig())
        self.assertEqual(len(self.b.log), 1)

    async def test_exit_then_new_entry(self):
        await self.e.handle(self.sig())
        await self.e.handle(self.sig("exit"))
        await self.e.handle(self.sig())
        self.assertEqual([x[0] for x in self.b.log], ["bracket", "flatten", "bracket"])

    async def test_bad_sides(self):
        await self.e.handle(self.sig(stop=25010, target=25030, price=25000))      # 買單停損在進場價上面
        await self.e.handle(self.sig("sell", stop=24990, target=24970, price=25000))
        await self.e.handle(self.sig(stop=24800, target=25500, price=25000))      # 停損 200 點
        self.assertEqual(self.b.log, [])

    async def test_stale(self):
        s = self.sig()
        self.clock.t += timedelta(seconds=20)          # 排隊 20 秒才處理
        await self.e.handle(s)
        s2 = self.sig(tv_time=(self.clock.t - timedelta(seconds=45)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        await self.e.handle(s2)                        # 快訊觸發 45 秒後才到
        self.assertEqual(self.b.log, [])

    async def test_other_symbol(self):
        await self.e.handle(parse_payload(msg().replace("NQ1!", "ES1!").replace("NQZ2026", "ESZ2026"), self.clock()))
        self.assertEqual(self.b.log, [])

    async def test_pause(self):
        self.e.paused = True
        await self.e.handle(self.sig())
        self.assertEqual(self.b.log, [])

    async def test_flat_window(self):
        self.clock.t = et(2026, 10, 19, 16, 59)
        await self.e.handle(self.sig())
        self.assertEqual(self.b.log, [])
        self.clock.t = et(2026, 10, 19, 16, 50)
        await self.e.handle(self.sig())
        self.clock.t = et(2026, 10, 19, 16, 58)
        await self.e.tick()
        self.assertEqual([x[0] for x in self.b.log], ["bracket", "flatten"])

    async def test_max_hold(self):
        await self.e.handle(self.sig())
        self.clock.t += timedelta(minutes=124)
        await self.e.tick()
        self.assertEqual(self.b.pos, 2)
        self.clock.t += timedelta(minutes=2)
        await self.e.tick()
        self.assertEqual(self.b.pos, 0)

    async def test_daily_loss_halt(self):
        await self.e.handle(self.sig())
        self.b.pnl = -650.0
        await self.e.tick()
        self.assertEqual(self.b.pos, 0)
        await self.e.handle(self.sig())
        self.assertEqual([x[0] for x in self.b.log], ["bracket", "flatten"])
        self.clock.t = et(2026, 10, 19, 18, 5)        # 新的交易日
        self.b.pnl = 0.0
        await self.e.handle(self.sig())
        self.assertEqual(self.b.log[-1][0], "bracket")

    def test_trading_day(self):
        self.assertEqual(trading_day(et(2026, 10, 19, 17, 59)), "2026-10-19")
        self.assertEqual(trading_day(et(2026, 10, 19, 18, 0)), "2026-10-20")


class TestNotify(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock(et(2026, 10, 19, 10, 0))
        self.sent = []
        self.n = Notifier(cfg(discord_webhook_url="https://discord.example/x"), clock=self.clock)
        self.n.send = self.sent.append
        self.b = DryRunBroker(cfg())
        self.b.on_fill = self.n.on_fill
        self.e = Engine(self.b, cfg(), clock=self.clock, events=self.n.on_event)

    def test_tracker_pnl(self):
        t = Tracker(2.0)
        self.assertIsNone(t.on_fill({"side": "BOT", "qty": 2, "price": 25000.0, "kind": "市價", "day": "d"}))
        r = t.on_fill({"side": "SLD", "qty": 2, "price": 25010.5, "kind": "目標", "day": "d"})
        self.assertEqual((r["pts"], r["usd"]), (10.5, 42.0))
        t.on_fill({"side": "SLD", "qty": 2, "price": 25000.0, "kind": "市價", "day": "d"})
        r = t.on_fill({"side": "BOT", "qty": 2, "price": 25004.0, "kind": "停損", "day": "d"})
        self.assertEqual((r["pts"], r["usd"]), (-4.0, -16.0))
        self.assertEqual(t.day_stats("d"), {"n": 2, "wins": 1, "usd": 26.0, "pts": 6.5})

    async def test_entry_exit_messages(self):
        await self.e.handle(parse_payload(msg(stop=24990, target=25030, price=25000), self.clock()))
        await self.e.handle(parse_payload(msg("exit"), self.clock()))
        self.assertEqual(len(self.sent), 2)
        self.assertIn("進場 買 2 口", self.sent[0])
        self.assertIn("滑價 +10.00 點", self.sent[0])        # 假成交價 25010
        self.assertIn("出場（市價）賣 2 口", self.sent[1])

    async def test_reject_message(self):
        self.e.paused = True
        await self.e.handle(parse_payload(msg(), self.clock()))
        self.assertTrue(self.sent[0].startswith("⛔ 沒下單（買 趨勢）"))

    def test_disconnect_and_summary(self):
        self.n.tick(False)
        self.clock.t += timedelta(minutes=6)
        self.n.tick(False)
        self.n.tick(False)
        self.n.tick(True)
        self.assertEqual(len(self.sent), 2)
        self.assertIn("斷線 6 分鐘", self.sent[0])
        self.assertIn("重新連線", self.sent[1])
        self.clock.t = et(2026, 10, 19, 17, 0)
        self.n.tick(True)
        self.n.tick(True)
        self.assertEqual(len(self.sent), 3)
        self.assertIn("今天沒有交易", self.sent[2])

    def test_off_without_url(self):
        n = Notifier(cfg())
        n.send("x")
        self.assertEqual(n.q.qsize(), 0)


class TestWebhook(unittest.IsolatedAsyncioTestCase):
    async def test_secret_and_queue(self):
        q = asyncio.Queue()
        async with TestClient(TestServer(webhook_app(cfg(), q))) as c:
            r = await c.post("/hook/wrong-secret-xxxxxxxx", data=msg())
            self.assertEqual(r.status, 404)
            r = await c.post(f"/hook/{SECRET}", data="not json")
            self.assertEqual(r.status, 400)
            r = await c.post(f"/hook/{SECRET}", data=msg(), headers={"Content-Type": "text/plain"})
            self.assertEqual(r.status, 200)
        self.assertEqual(q.qsize(), 1)

    async def test_tradingview_ips_only(self):
        q = asyncio.Queue()
        app = webhook_app(cfg(tradingview_ips_only=True, client_ip_header="X-Forwarded-For"), q)
        async with TestClient(TestServer(app)) as c:
            r = await c.post(f"/hook/{SECRET}", data=msg(), headers={"CF-Connecting-IP": "52.89.214.238"})
            self.assertEqual(r.status, 403)               # 偽造的標頭不算
            r = await c.post(f"/hook/{SECRET}", data=msg(), headers={"X-Forwarded-For": "52.89.214.238"})
            self.assertEqual(r.status, 200)
        self.assertEqual(q.qsize(), 1)


if __name__ == "__main__":
    unittest.main()
