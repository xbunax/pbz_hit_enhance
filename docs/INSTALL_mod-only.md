# 仅 Mod 包安装（不带 UE4SS）

适用于已经能正常运行 UE4SS 的用户。本包不包含 UE4SS.dll 或根目录代理，不会下载运行库、覆盖公共设置或签名文件。PBZBootstrap.dll 是本 Mod 的面板启动组件。

## 通用安装：直接复制文件夹

1. 确认现有 UE4SS 能正常随游戏启动，然后完全退出游戏和调节面板。
2. 解压名称包含 `mod-only` 的 ZIP。
3. 将包内整个 `UnifiedHitstop` 文件夹复制到现有 UE4SS 实际使用的 `Mods` 文件夹，与其他 UE4SS Mod 放在一起。不要只复制 Lua 文件或 panel 文件夹。

   ```text
   Mods/
   ├─ 其他Mod/
   ├─ UnifiedHitstop/
   │  ├─ Scripts/
   │  ├─ panel/
   │  ├─ config.ini
   │  ├─ dependencies.json
   │  └─ install-mode.txt
   └─ mods.txt
   ```

4. 打开实际控制该 Mods 目录的 `mods.txt`，添加或修改为 `UnifiedHitstop : 1`，保留其他 Mod 条目。
5. 正常启动游戏，首次启动设置面板快捷键。以后面板随游戏自动启动和关闭。

无需固定磁盘或安装路径。自定义 Mods 目录、多个目录或统一控制列表，以原有 UE4SS 配置为准，可参考其他已正常加载的 Mod 所在位置。

升级时先退出游戏，备份原文件夹里的 `config.ini` 和 `ui_settings.json`（若存在），替换新版文件夹后恢复这两个文件。

手动安装的卸载方式：退出游戏，备份配置，将 `UnifiedHitstop` 移出 Mods 目录，并移除或禁用控制列表中的对应条目；共享 UE4SS 与其他 Mod 保留。

## 旧整合包迁移与外置数据

之前装过整合包时，先停用旧整合包加载器，确认独立 UE4SS 能正常随游戏启动，再安装仅 Mod 包。不要根据 DLL 文件名随意删除其他 Mod 的加载器。

需要自动迁移或外置数据时，可在解压目录打开 Windows PowerShell，执行下面的模板。**将尖括号内的文字连同尖括号一起替换为自己的实际目录。**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\Install.ps1" `
  -GameDirectory "<包含真实PBZ.exe的游戏目录>" `
  -UE4SSDirectory "<包含UE4SS.dll的现有运行库目录>" `
  -DataDirectory "<用于存放本Mod数据和备份的目录>"
```

自定义 Mods 或控制列表时，另外传入 `-ModsDirectory "<实际Mods目录>" -ControllingModsFile "<实际mods.txt文件>"`。迁移数据目录可用 `-PreviousInstallRecord "<原install-record.json文件>"` 指定旧安装记录。

脚本将 Mod、面板和配置放到数据目录的版本子目录，在现有 Mods 目录创建 `UnifiedHitstop` 目录联接，仅更新本 Mod 的启用项。旧项目加载器经哈希确认后才移除。原目录为跨磁盘的普通目录时，会在改动前停止，请先备份并移出旧目录后重试；已有目录联接可跨磁盘更新。安装失败时回滚原加载文件及启用配置。

通过脚本安装的卸载方式：退出游戏，在解压目录执行 `Uninstall.ps1 -InstallRecord "<本次生成的install-record.json文件>"`。它只停用本 Mod，保留数据、共享 UE4SS 和其他 Mod，不会自动重新启用旧版。

未知 UE4SS 版本会进行接口能力检查并标明未经实测；检查或 Hook 失败时停用本 Mod，不能保证任意运行库版本和任意 Mod 组合兼容。
