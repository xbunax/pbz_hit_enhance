# 仅 Mod 包安装（不带 UE4SS）

适用于已经能正常运行 UE4SS 的用户。本包不包含 UE4SS.dll 或根目录代理，不会下载运行库、覆盖公共设置或签名文件。PBZBootstrap.dll 是本 Mod 的面板启动组件，不是 UE4SS。

1. 确认原有 UE4SS 可以正常运行，退出游戏和旧调节面板。
2. 解压本包，执行下列命令，填写实际游戏目录、UE4SS 运行库目录和数据目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -GameDirectory "D:\Applications\Steam\steamapps\common\PBZ\platform\steam" -UE4SSDirectory "D:\YourUE4SS" -DataDirectory "D:\Game_mod\PhantomBladeZero\installed"
```

使用自定义或多个 Mods 目录时，额外传入 `-ModsDirectory "实际Mods目录" -ControllingModsFile "实际控制列表mods.txt"`。不确定时根据原有 UE4SS 配置确认路径，不要创建另一份运行库。

脚本把 Mod、面板和用户配置放到数据目录的版本子目录，在选定 Mods 目录创建 `UnifiedHitstop` 目录联接，并仅更新本 Mod 的启用项。旧版本项目加载器经哈希确认后才移除，其他 Mod 保留。

普通单 Mods 目录也可手动复制 UnifiedHitstop 到该目录并添加 `UnifiedHitstop : 1`，但旧整合安装应使用脚本迁移，防止留下双运行库。外置数据需求请使用脚本。

正常启动游戏后面板自动启动，并在游戏结束后自动退出。未知 UE4SS 版本会进行接口能力检查并标明未经实测；检查或 Hook 失败时只停用本 Mod，不能保证任意运行库版本和任意 Mod 组合兼容。

卸载：先退出游戏，再运行 `Uninstall.ps1 -InstallRecord "数据目录\install-record.json"`。只移除本 Mod 联接和启用项，保留共享 UE4SS、其他 Mod 和用户数据。

迁移数据目录时，可用 `-PreviousInstallRecord "旧数据目录\install-record.json"` 明确指定原安装记录。原目录为跨磁盘的普通目录时，脚本会在改动前停止，请先备份并移出旧目录后再安装；已有目录联接可跨磁盘安全更新。安装失败保留准备目录供检查，原加载文件和启用配置会回滚。
