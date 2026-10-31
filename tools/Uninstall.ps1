[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$loader = Join-Path $PSScriptRoot 'dwmapi.dll'
$manifestPath = Join-Path $PSScriptRoot 'PBZHitEnhance\package_manifest.json'
if (-not (Test-Path -LiteralPath $loader)) { Write-Host '未检测到加载 DLL。'; exit 0 }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$expected = $manifest.'dwmapi.dll'
if (-not $expected -or (Get-FileHash -LiteralPath $loader -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'dwmapi.dll 与本包记录不一致，已停止卸载，避免删除其他 Mod。'
}
Remove-Item -LiteralPath $loader
Write-Host '已移除自动加载 DLL。请重新启动游戏使卸载生效。配置与数据文件夹已保留。'
