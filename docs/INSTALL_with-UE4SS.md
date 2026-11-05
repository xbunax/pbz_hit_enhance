# 带 UE4SS 整合包：手动安装

适用于尚未安装 UE4SS 的用户。通过复制文件夹安装，无需运行安装脚本或填写固定磁盘路径。若已有独立 UE4SS、override.txt 或其他来源的 dwmapi.dll，应使用同一 Release 的 mod-only 包，保留现有加载器。

## 安装步骤

1. 完全退出游戏和调节面板，下载并解压名称包含 `with-UE4SS` 的 ZIP。
2. 在 Steam 中右键《影之刃零》→“管理”→“浏览本地文件”，进入 `platform\steam`，确认该目录内有真实的 `PBZ.exe`。
3. 将压缩包内的 **`dwmapi.dll` 和整个 `PBZHitEnhance` 文件夹**复制到这个 `PBZ.exe` 旁，保持文件夹结构：

   ```text
   platform/steam/
   ├─ PBZ.exe
   ├─ dwmapi.dll
   └─ PBZHitEnhance/
      └─ ue4ss/
         ├─ UE4SS.dll
         └─ Mods/
            ├─ mods.txt
            └─ UnifiedHitstop/
               ├─ Scripts/
               ├─ panel/
               └─ config.ini
   ```

4. 正常从 Steam 启动游戏。首次启动设置面板快捷键，以后面板随游戏自动启动和关闭。

整合包已包含匹配的运行库、脚本和独立面板。完整复制 `PBZHitEnhance` 文件夹，不要只复制 DLL、Lua 文件或面板程序。图中仅列出主要文件，其余包内文件应保持完整。

加载器默认读取 `dwmapi.dll` 旁的 `PBZHitEnhance` 文件夹。新安装按上述结构放置即可，不需要创建 `PBZHitEnhance.ini`。

## 更新或从旧版迁移

1. 完全退出游戏和调节面板。
2. 找到旧安装实际使用的 `UnifiedHitstop` 文件夹，备份其中的 `config.ini` 和 `ui_settings.json`（若存在），保留武器设置和快捷键。默认位于 `PBZHitEnhance\ue4ss\Mods\UnifiedHitstop`。
3. 如果游戏目录中已有本项目的 `PBZHitEnhance.ini`，先查看它的 `DataDirectory`；旧配置可能位于该外置目录。完成备份后，把这个 INI 文件移出游戏目录，避免它继续指向旧版本。
4. 备份本项目旧版的 `dwmapi.dll` 和 `PBZHitEnhance` 文件夹，再按上方步骤放入新版。
5. 将备份的 `config.ini` 和 `ui_settings.json` 恢复到新版 `PBZHitEnhance\ue4ss\Mods\UnifiedHitstop`。
6. 正常启动游戏，检查面板能否呼出及设置是否保留。

不要根据文件名覆盖其他 Mod 的代理 DLL。只有确认原文件属于本整合包时才替换；已有其他 UE4SS 安装时使用 mod-only 方式。

## 手动卸载

退出游戏和调节面板，将自己从本整合包复制的 `dwmapi.dll` 移出游戏目录，停止自动加载。`PBZHitEnhance` 文件夹可备份后移出，以保留个人设置。若曾设置本项目的 `PBZHitEnhance.ini`，也将其备份并移出。

该方式只处理本整合包文件，不删除共享 UE4SS 或其他 Mod。游戏正在运行时，移除文件不会卸载已经加载的代码，需要重新启动游戏才能生效。

## 保留旧外置运行库的最小升级

如果已有 PBZHitEnhance.ini 指向外置数据目录，而且希望保留其中的其他 Mod：退出游戏，备份旧文件，将本包根目录 dwmapi.dll 替换到 PBZ.exe 旁；将包内 PBZHitEnhance/ue4ss/Mods/UnifiedHitstop 的新版内容复制到实际外置 Mods/UnifiedHitstop，随后恢复 config.ini 和 ui_settings.json。保留原 PBZHitEnhance.ini、UE4SS 设置、mods.txt 和其他 Mod，不复制本包默认启用列表去覆盖它们。只有确认代理属于本项目时才替换。

手动更新会使旧脚本安装记录中的文件哈希过时，后续按手动方式维护。本版发行包不含安装或卸载 PowerShell 脚本。使用默认布局迁移时，也应先备份旧外置运行库的其他 Mod 和启用列表，避免迁移后遗漏。

本项目与 PBZ Damage Test 独立运行，本包不包含木桩。不要把两者的独立整合包覆盖叠装。

完整使用说明：https://github.com/xbunax/pbz_hit_enhance#使用
