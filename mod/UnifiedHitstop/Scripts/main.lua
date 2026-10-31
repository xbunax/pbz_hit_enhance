-- PBZ UnifiedHitstop 0.3.0. Modifies only the current feedback output's Frames field.
local source=debug.getinfo(1,'S').source
assert(source:sub(1,1)=='@','Cannot resolve UnifiedHitstop script directory')
local scripts=assert(source:sub(2):match('^(.*[\\/])'),'Script directory missing')
local ROOT=scripts..'../'
local policy=dofile(ROOT..'Scripts/policy.lua')
local FEEDBACK='/PBZCombatAsset/Prototypes/Hitreact/BP_HitEffectPlayer_Chooser.BP_HitEffectPlayer_Chooser_C:GetEffectData'
local CONSUMER='/Script/SGameCombatSystem.RuntimeSlomoDataHelper:StartSlomoData'
local cfg=nil
local lastRaw=nil
local configSeen=false
local fault=false
local lines=0
local seen,changed,lastBefore,lastAfter=0,0,0,0
local function log(kind,fields)
    if lines>=4000 then return end
    lines=lines+1
    local parts={os.date('!%Y-%m-%dT%H:%M:%SZ'),tostring(lines),kind}
    for _,p in ipairs(fields or {}) do parts[#parts+1]=p[1]..'='..tostring(p[2]):gsub('[\r\n\t]',' ') end
    local f=io.open(ROOT..'runtime.log','a')
    if f then f:write(table.concat(parts,'\t')..'\n');f:close() end
end
local function safe(fn)
    local ok,v=pcall(fn)
    return ok and tostring(v) or '<unavailable>'
end
local function refresh()
    local f=io.open(ROOT..'config.ini','rb')
    local raw=f and f:read('*a') or nil
    if f then f:close() end
    if configSeen and raw==lastRaw then return end
    configSeen=true;lastRaw=raw
    local ok,value=pcall(policy.parse,raw)
    if ok then
        cfg=value;fault=false
        log('config_loaded',{{'enabled',cfg.Enabled},{'mode',cfg.Mode},{'scale',cfg.Scale},
            {'add_frames',cfg.AddFrames},{'fixed_frames',cfg.FixedFrames},{'max_frames',cfg.MaxFrames}})
    else
        cfg=nil
        log('config_invalid_disabled',{{'error',value}})
    end
end
local function onFeedback(context,attackType,strength,material,particles,param,camera,sound)
    if fault then return end
    local ok,err=pcall(function()
        local strengthName=strength:get().TagName:ToString()
        local data=param:get()
        local before,after,reason=policy.apply(data,strengthName,cfg)
        seen=seen+1;lastBefore=before;lastAfter=after
        if before~=after then changed=changed+1 end
        log('feedback',{{'attack_type',safe(function() return attackType:get().TagName:ToString() end)},
            {'strength',strengthName},{'material',safe(function() return material:get().TagName:ToString() end)},
            {'before',before},{'after',after},{'reason',reason},{'multiplier',data.Multiplier},
            {'curve',safe(function() return data.SlomoCurve:GetFullName() end)}})
    end)
    if not ok then
        fault=true
        log('write_fault_disabled',{{'error',err}})
    end
    -- Nil return: no function return-value override. Only Frames is assigned above.
end
local function onConsumer(context,runtime,id,param)
    local ok,err=pcall(function()
        local name=id:get():ToString()
        if name~='Hitreact' then return end
        local data=param:get()
        log('consumer',{{'id',name},{'frames',data.Frames},{'multiplier',data.Multiplier},
            {'duration_mode',data.UseSlomoDuration},
            {'curve',safe(function() return data.SlomoCurve:GetFullName() end)},
            {'owner',safe(function() return runtime:get().Owner:GetFullName() end)}})
    end)
    if not ok then log('consumer_read_error',{{'error',err}}) end
end
local specs={{path=FEEDBACK,fn=onFeedback},{path=CONSUMER,fn=onConsumer}}
local function writeStatus()
    local ready=true
    for _,s in ipairs(specs) do if not s.ids then ready=false end end
    local f=io.open(ROOT..'status.ini','w')
    if not f then return end
    f:write('Timestamp='..os.time()..'\nReady='..tostring(ready)..'\nFault='..tostring(fault)..
        '\nEnabled='..tostring(cfg~=nil and cfg.Enabled)..'\nSeen='..seen..'\nChanged='..changed..
        '\nBefore='..lastBefore..'\nAfter='..lastAfter..'\n')
    f:close()
end
local attempts=0
local queued=false
local function tick()
    refresh()
    attempts=attempts+1
    for _,s in ipairs(specs) do
        if not s.ids and (attempts<=120 or attempts%30==0) then
            local ok,a,b=pcall(RegisterHook,s.path,s.fn)
            if ok and a~=nil then
                s.ids={a,b};log('hook_registered',{{'path',s.path},{'pre',a},{'post',b}})
            elseif attempts==1 or attempts%30==0 then log('hook_pending',{{'path',s.path},{'error',a}}) end
        end
    end
end
local function dispatch()
    if queued then return end
    queued=true
    local ok,err=pcall(ExecuteInGameThread,function()
        local success,msg=pcall(function() tick();writeStatus() end)
        queued=false
        if not success then cfg=nil;fault=true;log('tick_error_disabled',{{'error',msg}}) end
    end)
    if not ok then queued=false;log('dispatch_error',{{'error',err}}) end
end
log('mod_loaded',{{'version','0.3.0'},{'scope','all_normal_feedback_including_player_received'},{'log_limit',4000}})
dispatch()
LoopAsync(1000,function() dispatch();return false end)
