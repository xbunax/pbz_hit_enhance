"""Exercise actual entry script with different UE4SS API/Hook capabilities."""

from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1] / "mod/UnifiedHitstop"


class CompatibilityTests(unittest.TestCase):
    def runtime(self, setup=""):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.globals().BASE = (ROOT / "config.ini").read_text()
        lua.execute("""
  OUTPUT='';HOOKS={};CLEANED=0;INITIALIZED=false;ALLOWED=true;LOADED=true
  io.open=function(path,mode)
   if path:match('bootstrap.ini$') then return {read=function() return '[Session]\\nAllowed='..tostring(ALLOWED)..'\\n' end,close=function() end} end
   if path:match('config.ini$') then return {read=function() return BASE end,close=function() end} end
   return {write=function(_,s) OUTPUT=OUTPUT..s end,close=function() end}
  end
  package.loadlib=function() return function() INITIALIZED=true end end
  RegisterHook=function(path,fn) HOOKS[path]=fn;return 1,2 end
  UnregisterHook=function(path) HOOKS[path]=nil;CLEANED=CLEANED+1 end
  StaticFindObject=function() return {IsValid=function() return LOADED end} end
  ExecuteInGameThread=function(fn) fn() end
  LoopAsync=function(_,fn) POLL=fn end
  """)
        lua.execute(setup)
        lua.eval("function(path) return assert(loadfile(path)) end")(
            str(ROOT / "Scripts/main.lua")
        )()
        return lua

    def count(self, lua):
        return lua.eval("(function() local n=0;for _ in pairs(HOOKS) do n=n+1 end;return n end)()")

    def test_missing_api_stops_before_bootstrap_and_hooks(self):
        lua = self.runtime("UnregisterHook=nil")
        self.assertFalse(lua.globals().INITIALIZED)
        self.assertEqual(self.count(lua), 0)
        self.assertIn("missing_api:UnregisterHook", lua.globals().OUTPUT)

    def test_duplicate_or_denied_bootstrap_never_registers(self):
        lua = self.runtime("ALLOWED=false")
        self.assertEqual(self.count(lua), 0)
        self.assertIn("bootstrap_denied", lua.globals().OUTPUT)

    def test_unloaded_scene_waits_then_registers(self):
        lua = self.runtime("LOADED=false")
        self.assertEqual(self.count(lua), 0)
        self.assertNotIn("compatibility_disabled", lua.globals().OUTPUT)
        lua.globals().LOADED = True
        lua.globals().POLL()
        self.assertEqual(self.count(lua), 2)

    def test_hook_failure_cleans_only_this_mod_and_stays_disabled(self):
        lua = self.runtime(
            "RegisterHook=function(path,fn) if path:match(':StartSlomoData$') then error('unsupported hook') end;HOOKS[path]=fn;return 1,2 end"
        )
        self.assertEqual(lua.globals().CLEANED, 1)
        self.assertEqual(self.count(lua), 0)
        lua.globals().POLL()
        self.assertEqual(self.count(lua), 0)
        self.assertIn("hook_registration_failed", lua.globals().OUTPUT)

    def test_game_thread_dispatch_failure_is_reported(self):
        lua = self.runtime("ExecuteInGameThread=function() error('unavailable') end")
        self.assertEqual(self.count(lua), 0)
        self.assertIn("dispatch_error", lua.globals().OUTPUT)
