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

保留旧外置数据目录时，先确认实际运行库与 Mods 路径，再备份并替换 UnifiedHitstop 文件夹，恢复 config.ini 和 ui_settings.json。新版 ZIP 不附带 PowerShell 脚本。

如果旧 PBZHitEnhance 加载器因游戏更新记录 unsupported_game_skipped，仅替换 mod-only 不会更新它：需要从同版本 with-UE4SS 包取得本项目的 dwmapi.dll，备份并替换 PBZ.exe 旁的旧本项目代理。保留 PBZHitEnhance.ini 和现有 UE4SS、其他 Mod。不要覆盖其他来源的同名 DLL。手动替换后，旧脚本的安装记录不再代表新文件；后续按本说明手动维护。

本项目不依赖 PBZ Damage Test。两个项目的独立整合包不能覆盖叠装。未知 UE4SS 版本会进行接口能力检查并标明未经实测；检查或 Hook 失败时停用本 Mod。

完整使用说明：https://github.com/xbunax/pbz_hit_enhance#使用
