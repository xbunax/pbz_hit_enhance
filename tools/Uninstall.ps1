[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$InstallRecord)
$ErrorActionPreference='Stop'
function Full([string]$p){[IO.Path]::GetFullPath($p).TrimEnd('\')}
$r=Get-Content -LiteralPath $InstallRecord -Raw|ConvertFrom-Json
if($r.mode -notin @('with-UE4SS','mod-only')){throw '无效安装记录。'}
if(Get-Process -Name PBZ -ErrorAction SilentlyContinue){throw '请先正常退出游戏。'}
$data=Full $r.data
$expectedMod=if($r.mode -eq 'with-UE4SS'){Join-Path $data 'ue4ss\Mods\UnifiedHitstop'}else{Join-Path $data 'UnifiedHitstop'}
# Validate all owned paths before removing anything.
if($r.mode -eq 'with-UE4SS') {
    $dll=Join-Path (Full $r.game) 'dwmapi.dll';$ini=Join-Path (Full $r.game) 'PBZHitEnhance.ini'
    if((Test-Path -LiteralPath $dll) -and (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant() -ne $r.loader_hash){throw '加载 DLL 已变化，停止卸载以保护其他 Mod。'}
    if((Test-Path -LiteralPath $ini) -and (Get-FileHash -LiteralPath $ini -Algorithm SHA256).Hash.ToLowerInvariant() -ne $r.ini_hash){throw '外置数据配置已变化，停止卸载，请先检查当前安装。'}
} else {
    $link=Full $r.mod_link
    if((Split-Path -Leaf $link) -ne 'UnifiedHitstop' -or (Full $r.mod_target) -ne $expectedMod){throw '无效卸载记录。'}
    $item=Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
    if($item -and ($item.LinkType -ne 'Junction' -or (Full ([string]$item.Target)) -ne $expectedMod)){throw 'Mod 路径已变化，停止卸载。'}
}
$panel=Join-Path $expectedMod 'panel\HitstopPanel.exe'
Get-CimInstance Win32_Process -Filter "Name='HitstopPanel.exe'"|Where-Object {$_.ExecutablePath -eq $panel}|ForEach-Object {Stop-Process -Id $_.ProcessId}
if($r.mode -eq 'with-UE4SS') {
    if(Test-Path -LiteralPath $dll){Remove-Item -LiteralPath $dll}
    if(Test-Path -LiteralPath $ini){Remove-Item -LiteralPath $ini}
} else {
    if($item){[IO.Directory]::Delete($link)}
    if(Test-Path -LiteralPath $r.mods_file) {
        $text=[IO.File]::ReadAllText($r.mods_file)
        $text=[regex]::Replace($text,'(?m)^[ \t]*UnifiedHitstop[ \t]*:[ \t]*[01][^\r\n]*(?:\r?\n|$)','')
        [IO.File]::WriteAllText($r.mods_file,$text,(New-Object Text.UTF8Encoding($false)))
    }
}
Write-Host '已停用本 Mod，保留配置、数据和备份。共享 UE4SS 及其他 Mod 未删除；旧版不会自动重新启用。'
