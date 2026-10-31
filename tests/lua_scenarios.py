from pathlib import Path
import json, datetime

from lupa.lua54 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1] / "mod/UnifiedHitstop"
lua = LuaRuntime(unpack_returned_tuples=True)
policy = lua.execute((ROOT / "Scripts/policy.lua").read_text(encoding="utf-8"))
BASE = (ROOT / "config.ini").read_text(encoding="utf-8")
passed = []


def check(name, fn):
    fn()
    passed.append(name)


def eq(a, b):
    assert a == b, (a, b)


def config(**kw):
    c = policy.parse(BASE)
    for k, v in kw.items():
        c[k] = v
    return c


normal = "Hitreact.Strength.Income.Normal.Light"
check(
    "identity_preserves_original_even_above_cap",
    lambda: eq(policy.calculate(config(), 50, False, normal), (50, "identity")),
)
check(
    "scale_rounds_4_to_6",
    lambda: eq(policy.calculate(config(Scale=1.5), 4, False, normal)[0], 6),
)
check(
    "add_one",
    lambda: eq(policy.calculate(config(Mode="add", AddFrames=1), 4, False, normal)[0], 5),
)
check(
    "negative_add_clamps_zero",
    lambda: eq(policy.calculate(config(Mode="add", AddFrames=-30), 4, False, normal)[0], 0),
)
check(
    "fixed_and_cap",
    lambda: eq(
        policy.calculate(config(Mode="fixed", FixedFrames=9, MaxFrames=8), 4, False, normal)[0],
        8,
    ),
)
check("scale_zero", lambda: eq(policy.calculate(config(Scale=0), 4, False, normal)[0], 0))
check(
    "disabled_preserves",
    lambda: eq(policy.calculate(config(Enabled=False, Scale=2), 4, False, normal)[0], 4),
)
check(
    "skip_zero",
    lambda: eq(policy.calculate(config(Mode="fixed"), 0, False, normal)[0], 0),
)
check(
    "skip_duration_mode",
    lambda: eq(policy.calculate(config(Scale=2), 4, True, normal)[0], 4),
)
check(
    "skip_deflect",
    lambda: eq(
        policy.calculate(config(Scale=2), 4, False, "Hitreact.Strength.Income.Deflect.Attacker")[0],
        4,
    ),
)
check(
    "skip_unknown_strength",
    lambda: eq(policy.calculate(config(Scale=2), 4, False, "Unknown")[0], 4),
)
check(
    "skip_invalid_frames",
    lambda: eq(policy.calculate(config(Scale=2), 121, False, normal)[0], 121),
)
for idx, bad in enumerate(
    [
        BASE.replace("Scale=1", "Scale=nan"),
        BASE.replace("Scale=1", "Scale=5"),
        BASE + "\nMode=add",
        BASE.replace("Enabled=true", "Enabled=yes"),
        BASE.replace("FixedFrames=5", "FixedFrames=1.5"),
        BASE + "\nInjected=1",
        BASE.replace("MaxFrames=30", ""),
    ]
):

    def reject(bad=bad):
        try:
            policy.parse(bad)
        except Exception:
            return
        raise AssertionError("Invalid config accepted")

    check("reject_bad_config_" + str(idx), reject)
check(
    "accept_bom_crlf",
    lambda: eq(policy.parse("\ufeff" + BASE.replace("\n", "\r\n"))["Enabled"], True),
)
data = lua.table_from(
    {"Frames": 4, "UseSlomoDuration": False, "Multiplier": 0.7, "SlomoCurve": "curve"}
)
check(
    "write_only_frames",
    lambda: eq(policy.apply(data, normal, config(Scale=1.5)), (4, 6, "adjusted")),
)
check(
    "preserve_other_fields",
    lambda: eq((data.Multiplier, data.SlomoCurve, data.UseSlomoDuration), (0.7, "curve", False)),
)
# A simulated property write silently coerces the requested value. Rollback must restore the original.
badData = lua.execute(
    """local v=4;return setmetatable({}, {__index=function(_,k) if k=='Frames' then return v elseif k=='UseSlomoDuration' then return false end end,__newindex=function(_,k,n) if k=='Frames' then if n==4 then v=4 else v=99 end end end})"""
)


def rollback():
    try:
        policy.apply(badData, normal, config(Scale=1.5))
    except Exception as e:
        assert "rollback=true" in str(e)
    else:
        raise AssertionError("Expected write failure")
    eq(badData.Frames, 4)


check("write_readback_failure_restores_original", rollback)
# Execute actual entry script with mocked UE4SS scheduling, wrappers and log I/O.
lua.globals().CONFIG_RAW = BASE.replace("Mode=scale", "Mode=add")
lua.execute("""
TEST_LOG='';HOOKS={};POLL=nil
io.open=function(path,mode)
 if path:match('config.ini$') then
  if CONFIG_RAW==nil then return nil end
  return {read=function() return CONFIG_RAW end,close=function() end}
 end
 return {write=function(_,s) TEST_LOG=TEST_LOG..s end,close=function() end}
end
RegisterHook=function(path,fn) HOOKS[path]=fn;return 1,2 end
ExecuteInGameThread=function(fn) fn() end
LoopAsync=function(_,fn) POLL=fn end
function wrap(v) return {get=function() return v end} end
function tag(s) return wrap({TagName={ToString=function() return s end}}) end
function fire(d,strength)
 for path,fn in pairs(HOOKS) do if path:match(':GetEffectData$') then
 fn(nil,tag('Test.Attack'),tag(strength),tag('Hitreact.Material.Meat'),nil,wrap(d),nil,nil)
 end end
end
""")
lua.eval("function(path) return assert(loadfile(path)) end")(str(ROOT / "Scripts/main.lua"))()
d = lua.table_from(
    {
        "Frames": 4,
        "Multiplier": 0.7,
        "UseSlomoDuration": False,
        "SlomoCurve": "unchanged",
    }
)
check(
    "entry_registers_two_hooks",
    lambda: eq(
        lua.eval("(function() local n=0;for _ in pairs(HOOKS) do n=n+1 end;return n end)()"),
        2,
    ),
)
lua.globals().fire(d, normal)
check("entry_actual_output_written", lambda: eq(d.Frames, 5))
check(
    "entry_keeps_multiplier_curve",
    lambda: eq((d.Multiplier, d.SlomoCurve), (0.7, "unchanged")),
)
lua.globals().CONFIG_RAW = BASE.replace("Enabled=true", "Enabled=false")
lua.globals().POLL()
d.Frames = 4
lua.globals().fire(d, normal)
check("hot_disable_next_hit_original", lambda: eq(d.Frames, 4))
lua.globals().CONFIG_RAW = BASE.replace("Scale=1", "Scale=2")
lua.globals().POLL()
d.Frames = 4
lua.globals().fire(d, normal)
check("hot_enable_new_settings", lambda: eq(d.Frames, 8))
lua.globals().CONFIG_RAW = "invalid"
lua.globals().POLL()
d.Frames = 4
lua.globals().fire(d, normal)
check("malformed_config_disables", lambda: eq(d.Frames, 4))
lua.globals().CONFIG_RAW = None
lua.globals().POLL()
d.Frames = 4
lua.globals().fire(d, normal)
check("missing_config_disables", lambda: eq(d.Frames, 4))
result = {
    "time": datetime.datetime.now().astimezone().isoformat(),
    "lua_version": lua.eval("_VERSION"),
    "passed": len(passed),
    "tests": passed,
    "scope": "Offline Lua execution using mocked UE4SS. Does NOT establish live UE output mutation.",
}
print(json.dumps(result, ensure_ascii=False, indent=2))
