[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$GameDirectory,
    [string]$DataDirectory,
    [string]$UE4SSDirectory,
    [string]$ModsDirectory,
    [string]$ControllingModsFile,
    [string]$PreviousInstallRecord
)
$ErrorActionPreference='Stop'
function Full([string]$p) { [IO.Path]::GetFullPath($p).TrimEnd('\') }
function Hash([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() }
function WriteUtf8([string]$p,[string]$s) { [IO.File]::WriteAllText($p,$s,(New-Object Text.UTF8Encoding($false))) }
function ReadDataDirectory([string]$ini,[string]$base) {
    $section=''
    foreach($line in (Get-Content -LiteralPath $ini)) {
        if($line -match '^\s*\[(.+)\]'){$section=$Matches[1]}
        if($section -eq 'Paths' -and $line -match '^\s*DataDirectory\s*=\s*(.+)') {
            $value=$Matches[1].Trim().Trim('"')
            if([IO.Path]::IsPathRooted($value)){return Full $value}
            return Full (Join-Path $base $value)
        }
    }
    return Full (Join-Path $base 'PBZHitEnhance')
}
$game=Full $GameDirectory
if(!$DataDirectory){$DataDirectory=Join-Path $game 'PBZHitEnhanceData'}
$DataDirectory=Full $DataDirectory
$exe=Join-Path $game 'PBZ.exe'
$metadata=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package.json') -Raw | ConvertFrom-Json
if($metadata.mode -notin @('with-UE4SS','mod-only')){throw '安装包模式无效。'}
if(!(Test-Path -LiteralPath $exe -PathType Leaf)){throw '请选择含 PBZ.exe 的真实 platform\steam 游戏目录。'}
if((Hash $exe) -ne $metadata.game_hash){Write-Warning '游戏版本未经验证，将继续安装并尝试加载；请在游戏内确认兼容性。'}
if(Get-Process -Name PBZ -ErrorAction SilentlyContinue){throw '请先正常退出游戏。'}
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package_manifest.json') -Raw | ConvertFrom-Json
foreach($entry in $manifest.PSObject.Properties) {
    $path=Full (Join-Path $PSScriptRoot $entry.Name)
    if(!$path.StartsWith((Full $PSScriptRoot)+'\',[StringComparison]::OrdinalIgnoreCase) -or !(Test-Path -LiteralPath $path -PathType Leaf) -or (Hash $path) -ne $entry.Value){throw ('安装包校验失败：'+$entry.Name)}
}
$loader=Join-Path $game 'dwmapi.dll';$ini=Join-Path $game 'PBZHitEnhance.ini'
$oldRoot=if(Test-Path -LiteralPath $ini){ReadDataDirectory $ini $game}else{Join-Path $game 'PBZHitEnhance'}
$oldMod=Join-Path $oldRoot 'ue4ss\Mods\UnifiedHitstop'
$previous=$null
if(!$PreviousInstallRecord -and (Test-Path -LiteralPath (Join-Path $DataDirectory 'install-record.json'))){$PreviousInstallRecord=Join-Path $DataDirectory 'install-record.json'}
if($PreviousInstallRecord){
    $previous=Get-Content -LiteralPath $PreviousInstallRecord -Raw|ConvertFrom-Json
    if((Full $previous.game) -ne $game -or $previous.mode -notin @('with-UE4SS','mod-only')){throw '旧安装记录与所选游戏不匹配。'}
    $oldRoot=Full $previous.data
    $oldMod=if($previous.mode -eq 'with-UE4SS'){Join-Path $oldRoot 'ue4ss\Mods\UnifiedHitstop'}else{Join-Path $oldRoot 'UnifiedHitstop'}
}
$known=@('77bdfbd688cd9ae8d545c558e3a3463007b11f6b08bdadf16176a2bc2daef8b7','1128314835118cc5c01ce5a2fd0caac3fa63d58e627492aa187899f57b27478d')
if($previous -and $previous.loader_hash){$known+=$previous.loader_hash}
foreach($file in @((Join-Path $oldRoot 'package_manifest.json'),(Join-Path $oldRoot 'installed-manifest.json'))) {
    if(Test-Path -LiteralPath $file){$old=Get-Content -LiteralPath $file -Raw|ConvertFrom-Json;if($old.'dwmapi.dll'){$known+=$old.'dwmapi.dll'};if($old.loader_hash){$known+=$old.loader_hash}}
}
$ownedLoader=(Test-Path -LiteralPath $loader) -and ($known -contains (Hash $loader))
$link=$null;$oldLink=$null
if($metadata.mode -eq 'with-UE4SS') {
    if((Test-Path -LiteralPath $loader) -and !$ownedLoader){throw '已有其他 dwmapi.dll，请保留原文件并改用 mod-only 包。'}
    foreach($relative in @('UE4SS.dll','ue4ss\UE4SS.dll','override.txt')) {
        if(Test-Path -LiteralPath (Join-Path $game $relative)){throw '检测到现有 UE4SS 安装，请使用 mod-only 包。'}
    }
    if($previous -and $previous.mode -eq 'mod-only'){throw '现有安装使用共享 UE4SS，请继续使用 mod-only 包；切换前需先停用原共享加载器。'}
} else {
    if(!$UE4SSDirectory) {
        $candidates=@(@($game,(Join-Path $game 'ue4ss')) | Where-Object {Test-Path -LiteralPath (Join-Path $_ 'UE4SS.dll')})
        if($candidates.Count -ne 1){throw '无法唯一确定 UE4SS，请通过 -UE4SSDirectory 指定实际运行库目录。候选目录：' + ($candidates -join ', ')}
        $UE4SSDirectory=$candidates[0]
    }
    $UE4SSDirectory=Full $UE4SSDirectory
    if(!(Test-Path -LiteralPath (Join-Path $UE4SSDirectory 'UE4SS.dll'))){throw '所选目录没有 UE4SS.dll。'}
    $settings=Join-Path $UE4SSDirectory 'UE4SS-settings.ini'
    if(Test-Path -LiteralPath $settings) {
        $raw=Get-Content -LiteralPath $settings -Raw
        if(!$ModsDirectory -and $raw -match '(?m)^[ \t]*\+ModsFolderPaths[ \t]*='){throw '检测到多个 Mods 目录，请明确指定 -ModsDirectory 和实际启用列表。'}
        if(!$ModsDirectory -and $raw -match '(?m)^[ \t]*ModsFolderPath[ \t]*=[ \t]*([^;\r\n]+)') {
            $value=$Matches[1].Trim().Trim('"')
            $ModsDirectory=if([IO.Path]::IsPathRooted($value)){$value}else{Join-Path $UE4SSDirectory $value}
        }
        if(!$ControllingModsFile -and $raw -match '(?m)^[ \t]*ControllingModsTxt[ \t]*=[ \t]*([^;\r\n]+)') {
            $value=$Matches[1].Trim().Trim('"')
            $ControllingModsFile=if([IO.Path]::IsPathRooted($value)){$value}else{Join-Path $UE4SSDirectory $value}
        }
    }
    if(!$ModsDirectory){$ModsDirectory=Join-Path $UE4SSDirectory 'Mods'}
    $ModsDirectory=Full $ModsDirectory
    if(!(Test-Path -LiteralPath $ModsDirectory -PathType Container)){throw '所选 Mods 目录不存在，请确认现有 UE4SS 工作目录。'}
    if(!$ControllingModsFile){$ControllingModsFile=Join-Path $ModsDirectory 'mods.txt'}
    $ControllingModsFile=Full $ControllingModsFile
    if(!(Test-Path -LiteralPath (Split-Path -Parent $ControllingModsFile) -PathType Container)){throw '启用列表的父目录不存在。'}
    $link=Full (Join-Path $ModsDirectory 'UnifiedHitstop')
    $oldLink=Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
    if($oldLink){
        if(!(Test-Path -LiteralPath (Join-Path $link 'Scripts\main.lua')) -or (Get-Content -LiteralPath (Join-Path $link 'Scripts\main.lua') -TotalCount 1) -notmatch '^-- PBZ UnifiedHitstop'){throw '已有同名目录无法确认为本 Mod，停止安装。'}
        if($oldLink.Attributes -band [IO.FileAttributes]::ReparsePoint){
            if($oldLink.LinkType -ne 'Junction'){throw '同名路径不是可识别的目录联接，停止安装。'}
        } elseif([IO.Path]::GetPathRoot($link) -ne [IO.Path]::GetPathRoot($DataDirectory)) {throw '旧 Mod 是跨磁盘的普通目录，请先将其备份并移出 Mods 目录，再重试。'}
        $oldMod=$link
    }
}
$version=$metadata.version
if($version -notmatch '^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?$'){throw '版本号格式无效。'}
$stage=Full (Join-Path $DataDirectory ('versions\'+$version+'-'+$metadata.mode))
if(Test-Path -LiteralPath $stage){$stage+='-'+(Get-Date -Format 'yyyyMMddHHmmssfff')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)}
if(!$stage.StartsWith($DataDirectory+'\',[StringComparison]::OrdinalIgnoreCase)){throw '版本目标目录无效。'}
$backup=Full (Join-Path $DataDirectory ('backups\'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')))
New-Item -ItemType Directory -Path $backup -Force|Out-Null
$record=[ordered]@{version=$version;mode=$metadata.mode;game=$game;data=$stage;backup=$backup;loader_hash=$null;ini_hash=$null;mod_link=$null;mod_target=$null;mods_file=$null;old_link_backup=$null;old_link_target=$null;old_loader_backup=$null;old_ini_backup=$null;previous_record=$PreviousInstallRecord}
$oldPanels=@((Join-Path $oldRoot 'panel\HitstopPanel.exe'),(Join-Path $oldMod 'panel\HitstopPanel.exe'))
if($oldLink -and $oldLink.LinkType -eq 'Junction'){$oldPanels+=Join-Path ([string]$oldLink.Target) 'panel\HitstopPanel.exe'}
Get-CimInstance Win32_Process -Filter "Name='HitstopPanel.exe'"|Where-Object {$oldPanels -contains $_.ExecutablePath}|ForEach-Object {Stop-Process -Id $_.ProcessId -ErrorAction Stop}
$madeLink=$false;$oldLinkRemoved=$false;$loaderChanged=$false;$iniChanged=$false;$modsChanged=$false
$modsExisted=$false
try {
    New-Item -ItemType Directory -Path $stage -Force|Out-Null
    if($metadata.mode -eq 'with-UE4SS') {
        Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'PBZHitEnhance') -Force|ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse}
        $newMod=Join-Path $stage 'ue4ss\Mods\UnifiedHitstop'
    } else {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'UnifiedHitstop') -Destination $stage -Recurse
        $newMod=Join-Path $stage 'UnifiedHitstop'
    }
    foreach($name in @('config.ini','ui_settings.json')) {
        $source=Join-Path $oldMod $name
        if(Test-Path -LiteralPath $source){Copy-Item -LiteralPath $source -Destination (Join-Path $newMod $name);Copy-Item -LiteralPath $source -Destination (Join-Path $backup $name)}
    }
    if($PreviousInstallRecord){Copy-Item -LiteralPath $PreviousInstallRecord -Destination (Join-Path $backup 'previous-install-record.json')}
    if($ownedLoader){$record.old_loader_backup=Join-Path $backup 'dwmapi.dll';Copy-Item -LiteralPath $loader -Destination $record.old_loader_backup}
    if(Test-Path -LiteralPath $ini){$record.old_ini_backup=Join-Path $backup 'PBZHitEnhance.ini';Copy-Item -LiteralPath $ini -Destination $record.old_ini_backup}
    if($metadata.mode -eq 'with-UE4SS') {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'dwmapi.dll') -Destination $loader -Force;$loaderChanged=$true
        $record.loader_hash=Hash $loader
        [IO.File]::WriteAllText($ini,"[Paths]`r`nDataDirectory=$stage`r`n",[Text.Encoding]::Unicode);$iniChanged=$true
        $record.ini_hash=Hash $ini
    } else {
        if($oldLink){
            if((Split-Path -Parent $link) -ne $ModsDirectory){throw '无效 Mod 目录。'}
            if($oldLink.LinkType -eq 'Junction'){
                $record.old_link_target=Full ([string]$oldLink.Target)
                [IO.Directory]::Delete($link);$oldLinkRemoved=$true
            } else {
                $record.old_link_backup=Full (Join-Path $backup 'UnifiedHitstop.previous')
                if(!$record.old_link_backup.StartsWith($backup+'\',[StringComparison]::OrdinalIgnoreCase)){throw '无效备份路径。'}
                [IO.Directory]::Move($link,$record.old_link_backup);$oldLinkRemoved=$true
            }
        }
        New-Item -ItemType Junction -Path $link -Target ([WildcardPattern]::Escape($newMod))|Out-Null;$madeLink=$true
        $record.mod_link=$link;$record.mod_target=Full $newMod;$record.mods_file=$ControllingModsFile
        $modsExisted=Test-Path -LiteralPath $ControllingModsFile
        $raw=if($modsExisted){[IO.File]::ReadAllText($ControllingModsFile)}else{''}
        if($modsExisted){Copy-Item -LiteralPath $ControllingModsFile -Destination (Join-Path $backup 'mods.txt.before')}
        # Replace only our own entry, preserving all other text and relative order.
        $pattern='(?m)^[ \t]*UnifiedHitstop[ \t]*:[ \t]*[01][^\r\n]*'
        $entries=[regex]::Matches($raw,$pattern)
        if($entries.Count){
            $next=$raw
            for($index=$entries.Count-1;$index -ge 0;$index--){$entry=$entries[$index];$replacement=if($index -eq 0){'UnifiedHitstop : 1'}else{''};$next=$next.Remove($entry.Index,$entry.Length).Insert($entry.Index,$replacement)}
        } else {$separator=if(!$raw -or $raw.EndsWith("`n")){''}else{"`r`n"};$next=$raw+$separator+"UnifiedHitstop : 1`r`n"}
        WriteUtf8 $ControllingModsFile $next;$modsChanged=$true
        if($ownedLoader){Remove-Item -LiteralPath $loader;$loaderChanged=$true}
        if($ownedLoader -and (Test-Path -LiteralPath $ini)){Remove-Item -LiteralPath $ini;$iniChanged=$true}
    }
    WriteUtf8 (Join-Path $stage 'installed-manifest.json') ($record|ConvertTo-Json -Depth 6)
    WriteUtf8 (Join-Path $DataDirectory 'install-record.json') ($record|ConvertTo-Json -Depth 6)
    Write-Host ('安装完成：'+$metadata.mode+'。数据：'+$stage+'。请正常启动游戏。')
} catch {
    if($modsChanged){if($modsExisted){Copy-Item -LiteralPath (Join-Path $backup 'mods.txt.before') -Destination $ControllingModsFile -Force}else{Remove-Item -LiteralPath $ControllingModsFile -ErrorAction SilentlyContinue}}
    if($madeLink -and (Test-Path -LiteralPath $record.mod_link)){[IO.Directory]::Delete($record.mod_link)}
    if($oldLinkRemoved){
        if($record.old_link_target){New-Item -ItemType Junction -Path $link -Target ([WildcardPattern]::Escape($record.old_link_target))|Out-Null}
        elseif($record.old_link_backup -and (Test-Path -LiteralPath $record.old_link_backup)){[IO.Directory]::Move($record.old_link_backup,$link)}
    }
    if($loaderChanged){if($record.old_loader_backup){Copy-Item -LiteralPath $record.old_loader_backup -Destination $loader -Force}else{Remove-Item -LiteralPath $loader -ErrorAction SilentlyContinue}}
    if($iniChanged){if($record.old_ini_backup){Copy-Item -LiteralPath $record.old_ini_backup -Destination $ini -Force}else{Remove-Item -LiteralPath $ini -ErrorAction SilentlyContinue}}
    if($PreviousInstallRecord -and (Test-Path -LiteralPath (Join-Path $backup 'previous-install-record.json'))){Copy-Item -LiteralPath (Join-Path $backup 'previous-install-record.json') -Destination (Join-Path $DataDirectory 'install-record.json') -Force}
    throw
}
