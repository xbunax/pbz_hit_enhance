-- Pure configuration and per-call adjustment logic. No UObject references retained.
local M = {}
local keys = {Enabled=true,Mode=true,Scale=true,AddFrames=true,FixedFrames=true,MaxFrames=true}
local groups = {'Blade','DoubleBlade','GreatBlade'}
local profileKeys = {Override=true,Mode=true,Scale=true,AddFrames=true,FixedFrames=true,MaxFrames=true}
local function number(v, lo, hi, integer)
    local n=tonumber(v)
    if not n or n~=n or n<lo or n>hi or (integer and n%1~=0) then error('Invalid numeric setting: '..tostring(v)) end
    return n
end
local function tuning(c)
    assert(c.Mode=='scale' or c.Mode=='add' or c.Mode=='fixed','Invalid mode')
    return {Mode=c.Mode,Scale=number(c.Scale,0,4,false),
        AddFrames=number(c.AddFrames,-30,30,true),FixedFrames=number(c.FixedFrames,0,30,true),
        MaxFrames=number(c.MaxFrames,0,30,true)}
end
local function boolean(v)
    assert(v=='true' or v=='false','Invalid boolean')
    return v=='true'
end
function M.parse(raw)
    assert(type(raw)=='string','Missing configuration')
    raw=raw:gsub('^\239\187\191','')
    local c,profiles={},{}
    for _,group in ipairs(groups) do profiles[group]={} end
    for line in (raw..'\n'):gmatch('(.-)\n') do
        line=line:gsub('[;#].*$',''):match('^%s*(.-)%s*$')
        if line~='' then
            local k,v=line:match('^([%w%.]+)%s*=%s*(.-)%s*$')
            assert(k,'Invalid configuration line: '..line)
            local group,key=k:match('^(%w+)%.(%w+)$')
            if group then
                assert(profiles[group] and profileKeys[key],'Unknown profile setting: '..k)
                assert(profiles[group][key]==nil,'Duplicate setting: '..k)
                profiles[group][key]=v
            else
                assert(keys[k] or k=='ObserveOnly','Unknown setting: '..k)
                assert(c[k]==nil,'Duplicate setting: '..k)
                c[k]=v
            end
        end
    end
    for k in pairs(keys) do assert(c[k]~=nil,'Missing setting: '..k) end
    local result=tuning(c)
    result.Enabled=boolean(c.Enabled)
    result.ObserveOnly=boolean(c.ObserveOnly or 'false')
    result.Profiles={}
    for _,group in ipairs(groups) do
        local p=profiles[group]
        if next(p) then
            for k in pairs(profileKeys) do assert(p[k]~=nil,'Incomplete profile: '..group) end
            result.Profiles[group]=tuning(p)
            result.Profiles[group].Override=boolean(p.Override)
        end
    end
    return result
end
-- Main-weapon categories cross-checked against DT_WeaponData and feedback selection tags.
-- Static associations are not proof of every move or of attacker identity.
-- Unknown/shared generic tags are never assigned from the currently equipped player weapon.
local families={
    tangblade='Blade',bronzesword='Blade',luanying='Blade',wood='Blade',iron='Blade',
    chizhecanjian='Blade',slitheringsword='Blade',ciguhundun='Blade',zimingjian='Blade',
    doubleblade='DoubleBlade',snakedualshort='DoubleBlade',snakeduallong='DoubleBlade',
    dualhook='DoubleBlade',shuangyue='DoubleBlade',jadedualchakram='DoubleBlade',yaoju='DoubleBlade',
    longblade='GreatBlade',horizontal='GreatBlade',zhanma='GreatBlade',zhanmablade='GreatBlade',
    pojun='GreatBlade',jigsaw='GreatBlade',yanyuedao='GreatBlade',baiying='GreatBlade'
}
function M.classify(attack)
    if type(attack)~='string' then return 'Unknown' end
    local kind,suffix=attack:lower():match('^hitreact%.attacktype%.physical%.(%w+)%.(.+)$')
    if not suffix then return 'Unknown' end
    local family=suffix:match('^([%w_]+)')
    if not family then return 'Unknown' end
    if suffix~=family and suffix:sub(#family+1,#family+1)~='.' then return 'Unknown' end
    -- The extracted SlitheringSword rule also has a Slap variant. Do not generalize
    -- this to unrelated kick, punch, energy or Phantom Edge feedback.
    if kind=='slap' and family=='slitheringsword' then return 'Blade' end
    if kind~='slash' and kind~='stab' then return 'Unknown' end
    return families[family] or 'Unknown'
end
function M.select(c,attack)
    local group=M.classify(attack)
    local p=c and c.Profiles and c.Profiles[group]
    if not p or not p.Override then return c,group,'Global' end
    local effective={Enabled=c.Enabled,ObserveOnly=c.ObserveOnly}
    for k,v in pairs(p) do effective[k]=v end
    return effective,group,group
end
function M.calculate(c, frames, usesDuration, strength)
    if not c or not c.Enabled then return frames,'disabled' end
    if c.ObserveOnly then return frames,'observe_only' end
    if type(strength)~='string' or not strength:match('^Hitreact%.Strength%.Income%.Normal%.') then return frames,'non_normal' end
    if usesDuration~=false then return frames,'duration_mode' end
    if type(frames)~='number' or frames~=frames or frames%1~=0 or frames<=0 or frames>120 then return frames,'invalid_or_zero_frames' end
    -- Identity settings leave original values intact, even above the configured cap.
    if (c.Mode=='scale' and c.Scale==1) or (c.Mode=='add' and c.AddFrames==0) then return frames,'identity' end
    local n=frames
    if c.Mode=='scale' then n=math.floor(frames*c.Scale+0.5)
    elseif c.Mode=='add' then n=frames+c.AddFrames
    else n=c.FixedFrames end
    return math.max(0,math.min(c.MaxFrames,n)),'adjusted'
end
function M.apply(data,strength,c)
    local before=data.Frames
    local after,reason=M.calculate(c,before,data.UseSlomoDuration,strength)
    if after==before then return before,after,reason end
    local ok,err=pcall(function()
        data.Frames=after
        assert(data.Frames==after,'Frames write did not read back')
    end)
    if not ok then
        local restored,restoreError=pcall(function()
            data.Frames=before
            assert(data.Frames==before,'Rollback readback mismatch')
        end)
        error(tostring(err)..'; rollback='..tostring(restored)..'; '..tostring(restoreError))
    end
    return before,after,reason
end
return M
