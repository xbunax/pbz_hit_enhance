-- Pure configuration and per-call adjustment logic. No UObject references retained.
local M = {}
local keys = {Enabled=true,Mode=true,Scale=true,AddFrames=true,FixedFrames=true,MaxFrames=true}
local function number(v, lo, hi, integer)
    local n=tonumber(v)
    if not n or n~=n or n<lo or n>hi or (integer and n%1~=0) then error('Invalid numeric setting: '..tostring(v)) end
    return n
end
function M.parse(raw)
    assert(type(raw)=='string','Missing configuration')
    raw=raw:gsub('^\239\187\191','')
    local c={}
    for line in (raw..'\n'):gmatch('(.-)\n') do
        line=line:gsub('[;#].*$',''):match('^%s*(.-)%s*$')
        if line~='' then
            local k,v=line:match('^(%w+)%s*=%s*(.-)%s*$')
            assert(k and keys[k],'Unknown configuration line: '..line)
            assert(c[k]==nil,'Duplicate setting: '..k)
            c[k]=v
        end
    end
    for k in pairs(keys) do assert(c[k]~=nil,'Missing setting: '..k) end
    assert(c.Enabled=='true' or c.Enabled=='false','Enabled must be true or false')
    assert(c.Mode=='scale' or c.Mode=='add' or c.Mode=='fixed','Mode must be scale, add or fixed')
    return {Enabled=c.Enabled=='true',Mode=c.Mode,Scale=number(c.Scale,0,4,false),
        AddFrames=number(c.AddFrames,-30,30,true),FixedFrames=number(c.FixedFrames,0,30,true),
        MaxFrames=number(c.MaxFrames,0,30,true)}
end
function M.calculate(c, frames, usesDuration, strength)
    if not c or not c.Enabled then return frames,'disabled' end
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
