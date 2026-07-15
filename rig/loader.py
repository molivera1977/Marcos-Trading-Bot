"""Rig loader: imports marcos_trading_bot.py as a module on Python 3.9.

- Stubs external modules (anthropic/resend/webull/websocket) — the rig tests LOGIC, never APIs.
- Prepends `from __future__ import annotations` so PEP-604 annotations (`dict | None`)
  don't evaluate on 3.9. Executed logic is byte-identical to production.
"""
import sys, types, pathlib

BOT_PATH = pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py"

class _Stub(types.ModuleType):
    __path__ = []
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        v = _Stub(self.__name__ + "." + name); setattr(self, name, v); return v
    def __call__(self, *a, **k):
        return _Stub(self.__name__ + "()")

def load_bot():
    if "marcos_trading_bot" in sys.modules:
        return sys.modules["marcos_trading_bot"]
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, _Stub(m))
    src = BOT_PATH.read_text()
    src = "from __future__ import annotations\n" + src
    mod = types.ModuleType("marcos_trading_bot")
    mod.__file__ = str(BOT_PATH)
    sys.modules["marcos_trading_bot"] = mod
    exec(compile(src, str(BOT_PATH), "exec"), mod.__dict__)
    return mod
