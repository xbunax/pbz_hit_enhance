# 带 UE4SS 整合包安装

适用于尚未安装 UE4SS 的用户。已存在 UE4SS、override.txt 或其他 dwmapi.dll 时，改用同一 Release 的 mod-only 包。

1. 退出游戏和旧调节面板，解压本包到单独目录。
2. 打开 PowerShell，执行下列命令；将尖括号内的文字连同尖括号一起替换为自己的真实游戏目录和数据目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -GameDirectory "<包含真实PBZ.exe的游戏目录>" -DataDirectory "<用于存放本Mod数据和备份的目录>"
```

安装程序校验包和游戏版本，备份本项目的旧加载器及配置，将匹配的运行库、脚本和面板安装到版本目录，并写入 PBZHitEnhance.ini。其他项目的代理 DLL 不会被覆盖。

以后正常从 Steam 启动。首次配置快捷键；游戏退出或崩溃后面板自动结束。游戏未运行时手动打开面板会提示并退出。

卸载：先退出游戏，再运行 `Uninstall.ps1 -InstallRecord "<本次生成的install-record.json文件>"`。保留配置及备份，不会自动重新启用旧版。
