-- PBZ UnifiedHitstop 0.4.0-preview.2. Modifies only the current feedback output's Frames field.
local source=debug.getinfo(1,'S').source
assert(source:sub(1,1)=='@','Cannot resolve UnifiedHitstop script directory')
local scripts=assert(source:sub(2):match('^(.*[\\/])'),'Script directory missing')
local ROOT=scripts..'../'
-- Bootstrap is independent of UE4SS's C++ ABI and never loads a second runtime.
local function startupError(message)
    local f=io.open(ROOT..'startup.log','a')
    if f then f:write(os.date('!%Y-%m-%dT%H:%M:%SZ')..' '..tostring(message)..'\n');f:close() end
    f=io.open(ROOT..'status.ini','w')
    if f then f:write('Timestamp='..os.time()..'\nReady=false\nFault=true\nEnabled=false\nSeen=0\nChanged=0\nBefore=0\nAfter=0\nError='..tostring(message):gsub('[\r\n]',' ')..'\n');f:close() end
end
for _,name in ipairs({'RegisterHook','UnregisterHook','StaticFindObject','ExecuteInGameThread','LoopAsync'}) do
    if type(_G[name])~='function' then startupError('missing_api:'..name);return end
end
if type(package)~='table' or type(package.loadlib)~='function' then startupError('missing_api:package.loadlib');return end
local initialize,loadError=package.loadlib(scripts..'PBZBootstrap.dll','luaopen_pbz_bootstrap')
if not initialize then startupError('bootstrap_load_failed:'..tostring(loadError));return end
local ok,initError=pcall(initialize)
if not ok then startupError('bootstrap_failed:'..tostring(initError));return end
local bootstrap=io.open(ROOT..'bootstrap.ini','r')
local bootstrapText=bootstrap and bootstrap:read('*a') or ''
if bootstrap then bootstrap:close() end
if not bootstrapText:match('[\r\n]Allowed=true[\r\n]') then startupError('bootstrap_denied:'..bootstrapText:gsub('[\r\n]',' '));return end
local gamePid=bootstrapText:match('[\r\n]GamePid=([^\r\n]+)') or ''
local gameCreatedAt=bootstrapText:match('[\r\n]GameCreatedAt=([^\r\n]+)') or ''
local policy=dofile(ROOT..'Scripts/policy.lua')
local FEEDBACK='/PBZCombatAsset/Prototypes/Hitreact/BP_HitEffectPlayer_Chooser.BP_HitEffectPlayer_Chooser_C:GetEffectData'
local CONSUMER='/Script/SGameCombatSystem.RuntimeSlomoDataHelper:StartSlomoData'
local cfg=nil
local lastRaw=nil
local configSeen=false
local fault=false
local compatibilityFault=false
local compatibilityError=""
local lines=0
local seen,changed,lastBefore,lastAfter=0,0,0,0
local lastAttack,lastGroup,lastProfile,lastStrength,lastMaterial,lastReason='None','Unknown','Global','None','None','none'
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
            {'observe_only',cfg.ObserveOnly},{'add_frames',cfg.AddFrames},{'fixed_frames',cfg.FixedFrames},{'max_frames',cfg.MaxFrames}})
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
        local attackName=safe(function() return attackType:get().TagName:ToString() end)
        local materialName=safe(function() return material:get().TagName:ToString() end)
        local effective,group,profile=policy.select(cfg,attackName)
        local before,after,reason=policy.apply(data,strengthName,effective)
        lastAttack,lastGroup,lastProfile,lastStrength,lastMaterial,lastReason=attackName,group,profile,strengthName,materialName,reason
        seen=seen+1;lastBefore=before;lastAfter=after
        if before~=after then changed=changed+1 end
        log('feedback',{{'attack_type',attackName},{'group',group},{'profile',profile},
            {'strength',strengthName},{'material',materialName},
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
local function statusValue(value) return tostring(value):gsub('[\r\n=]',' ') end
local function writeStatus()
    local ready=true
    for _,s in ipairs(specs) do if not s.ids then ready=false end end
    local f=io.open(ROOT..'status.ini','w')
    if not f then return end
    f:write('Timestamp='..os.time()..'\nGamePid='..gamePid..'\nGameCreatedAt='..gameCreatedAt..'\nReady='..tostring(ready)..'\nFault='..tostring(fault)..
        '\nEnabled='..tostring(cfg~=nil and cfg.Enabled)..'\nSeen='..seen..'\nChanged='..changed..
        '\nBefore='..lastBefore..'\nAfter='..lastAfter..'\nObserveOnly='..tostring(cfg~=nil and cfg.ObserveOnly)..
        '\nAttackType='..statusValue(lastAttack)..'\nWeaponGroup='..lastGroup..'\nProfile='..lastProfile..
        '\nStrength='..statusValue(lastStrength)..'\nMaterial='..statusValue(lastMaterial)..'\nReason='..lastReason..'\nError='..statusValue(compatibilityError)..'\n')
    f:close()
end
local attempts=0
local queued=false
local function stopCompatibility(message)
    compatibilityFault=true;compatibilityError=tostring(message);fault=true;cfg=nil
    for _,s in ipairs(specs) do
        if s.ids then pcall(UnregisterHook,s.path,s.ids[1],s.ids[2]);s.ids=nil end
    end
    startupError(compatibilityError)
    log('compatibility_disabled',{{'error',compatibilityError}})
end
local function tick()
    if compatibilityFault then return end
    refresh()
    attempts=attempts+1
    for _,s in ipairs(specs) do
        if not s.ids and (attempts<=120 or attempts%30==0) then
            local found,object=pcall(StaticFindObject,s.path)
            if not found then stopCompatibility('function_lookup_failed:'..tostring(object));return end
            local validOk,valid=pcall(function() return object~=nil and object:IsValid() end)
            if not validOk then stopCompatibility('function_validation_failed:'..tostring(valid));return end
            if valid then
                local ok,a,b=pcall(RegisterHook,s.path,s.fn)
                if ok and type(a)=='number' and type(b)=='number' then
                    s.ids={a,b};log('hook_registered',{{'path',s.path},{'pre',a},{'post',b}})
                else stopCompatibility('hook_registration_failed:'..s.path..':'..tostring(a));return end
            elseif attempts==1 or attempts%30==0 then log('hook_pending',{{'path',s.path},{'error','function_not_loaded'}}) end
        end
    end
end
local function dispatch()
    if queued then return end
    queued=true
    local ok,err=pcall(ExecuteInGameThread,function()
        local success,msg=pcall(function() tick();writeStatus() end)
        queued=false
        if not success then stopCompatibility('tick_error:'..tostring(msg));writeStatus() end
    end)
    if not ok then queued=false;stopCompatibility('dispatch_error:'..tostring(err));writeStatus() end
end
log('mod_loaded',{{'version','0.4.0-preview.2'},{'scope','all_normal_feedback_including_player_received'},{'log_limit',4000}})
dispatch()
LoopAsync(1000,function() dispatch();return false end)
