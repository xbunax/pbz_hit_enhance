# 影之刃零 · 卡肉调节 Mod

[![构建与发布](https://github.com/xbunax/pbz_hit_enhance/actions/workflows/release.yml/badge.svg)](https://github.com/xbunax/pbz_hit_enhance/actions/workflows/release.yml)

通过共享命中反馈入口调整卡肉帧数，提供中文调节面板、快捷键呼出和随游戏启动自动加载。可以按原帧数缩放、增加/减少帧数，或固定帧数。默认 **1 倍**，保留游戏原始时长。

## 下载

打开 [Releases](https://github.com/xbunax/pbz_hit_enhance/releases/latest)，下载 `PBZHitEnhance-v版本号-windows-x64.zip`。不要下载 GitHub 自动生成的 Source code 压缩包用于安装。

发布包由 GitHub Actions 编译，包含加载 DLL、匹配的 UE4SS 运行库和独立面板程序，使用者无需安装 Python、Visual Studio 或 ReShade。

## 安装

1. **完全退出游戏。**
2. 在 Steam 中右键《影之刃零》→ 管理 → 浏览本地文件。
3. 进入 `platform\steam` 文件夹，确认这里有体积约 487 MiB 的真实 `PBZ.exe`。本项目验证的路径为 `…\steamapps\common\PBZ\platform\steam\PBZ.exe`。
4. 解压 Release，把 `dwmapi.dll` 和整个 `PBZHitEnhance` 文件夹复制到这个 `PBZ.exe` 旁。保留文件夹结构。
5. 正常从 Steam 启动游戏。首次启动会打开快捷键设置，选择组合键并点击“保存快捷键”。以后面板在后台启动，使用保存的快捷键呼出或隐藏。

安装后结构如下：

```text
PBZ/platform/steam/
├─ PBZ.exe
├─ dwmapi.dll                    ← 自动加载器
└─ PBZHitEnhance/                ← 必须保留的运行数据
   ├─ panel/HitstopPanel.exe
   ├─ ue4ss/
   │  ├─ UE4SS.dll
   │  ├─ UE4SS-settings.ini
   │  └─ Mods/UnifiedHitstop/
   │     ├─ Scripts/
   │     └─ config.ini
   ├─ logs/
   └─ temp/
```

**如果目录已经有其他来源的 `dwmapi.dll`，请先确认它属于哪个 Mod，不要直接覆盖。** 本项目没有配置与其他 DLL 代理的串联加载。

### 把运行数据放在游戏目录之外

也可以只把 `dwmapi.dll` 放在真实 `PBZ.exe` 旁，把完整 `PBZHitEnhance` 文件夹移到例如 `D:\Game_mod\PBZHitEnhance`，再在 DLL 旁新建 `PBZHitEnhance.ini`：

```ini
[Paths]
DataDirectory=D:\Game_mod\PBZHitEnhance
```

路径指向含有 `panel` 和 `ue4ss` 子目录的文件夹。外置方式下，配置、日志和面板临时文件也写在该文件夹中。移动数据目录后，应在游戏退出时更新上述路径。

## 使用

面板有“卡肉设置、快捷键、运行状态”三个页签。它采用深色半透明置顶窗口，适用于**窗口化或无边框**游戏模式。拖动滑块后自动保存，游戏继续运行时约 1 秒内应用到后续命中；首次初始化可能需要数十秒。

| 设置 | 含义 |
| --- | --- |
| 启用卡肉时长调整 | 关闭后，后续命中恢复原始帧数 |
| 按比例缩放 | 原帧数 × 比例；1 倍是原值，范围 0–4 |
| 增加 / 减少帧数 | 在原值上增减，范围 -30–30 |
| 固定帧数 | 符合条件的普通命中使用固定帧数，范围 0–30 |
| 帧数上限 | 修改结果上限，范围 0–30；结果最低为 0 |
| 恢复默认 | 恢复启用状态和 1 倍原始帧数 |

例如原值 4 帧，设置 1.5 倍会变为 6 帧；设置“增加 1 帧”会变为 5 帧。比例 1、增减 0 时保留原值，不额外裁剪。

本版只写当次命中反馈的 `Frames`，保留倍率和曲线。作用于经过共享入口的普通命中，**包含玩家受击**；跳过原本零帧、格挡、其他特殊标签和按持续时间计时的反馈。帧数是游戏内部单位，尚未换算成现实毫秒。未验证所有武器。

隐藏或退出面板不会停止已经加载的 Mod。面板是独立后台程序，游戏退出后仍可呼出，可在“运行状态”页退出调节器。若需要手动打开，可运行 `PBZHitEnhance\panel\HitstopPanel.exe`。

## 兼容版本

- Windows 11 x64。
- Steam build **26266538**，UE **5.7.4**。
- `PBZ.exe` SHA256：`7b4fcd286a350780faf0824d73aa150b21cbf1bccde883e6a96386cbe09973b4`。

加载器会检查游戏和运行库校验值。游戏更新后不匹配时跳过加载，不能直接认为新版本可用。配置错误或回调写入校验失败时停止修改。

共享命中入口、修改后参数到达下游、关闭恢复原值，以及旧版加载器随游戏启动均已在上述版本验证。本仓库的可分发构建会运行离线逻辑测试、真实系统接口转发检查、完整包校验和独立面板自检；CI 不运行游戏，不能代替长期实战稳定性测试。

## 更新和卸载

更新前退出游戏，并在面板“运行状态”页退出调节器。备份 `ue4ss\Mods\UnifiedHitstop\config.ini` 和 `ui_settings.json`（若存在），替换本项目的 DLL 与数据文件夹后恢复这两份设置。不要保留旧运行库混用，也不要覆盖其他 Mod 的 DLL。

卸载时先退出游戏和面板，再移除本项目的 `dwmapi.dll`。之后正常启动游戏便不会加载本 Mod。`PBZHitEnhance` 文件夹可以保留以保存设置；使用外置方式时也可保留 `PBZHitEnhance.ini`。

压缩包中的 `Uninstall.ps1` 可放在 DLL 旁执行，会在校验 DLL 确实属于本包后将其移除，保留数据目录。

临时跳过加载：在数据文件夹创建 `disabled.flag`，或给游戏添加启动参数 `--disable-unified-hitstop`。移除标记/参数后，下次启动重新启用。

## 常见问题

- **按快捷键无反应**：确认游戏为窗口化/无边框。手动运行面板程序，在“快捷键”页换一个未被其他程序占用的组合键。首次可先选 Ctrl+F10。
- **显示未连接**：检查 DLL 是否放在真实 `platform\steam\PBZ.exe` 旁，文件夹结构是否完整，并等待游戏进入场景。
- **游戏更新后失效**：查看 `PBZHitEnhance\logs\loader.log`，若出现 `unsupported_game_skipped`，需等待兼容更新。
- **找不到运行库或校验失败**：重新解压完整 Release；不要只复制 DLL。检查外置数据路径是否正确。
- **需要日志**：加载日志在数据目录的 `logs\loader.log`；UE4SS 日志在 `ue4ss\UE4SS.log`；反馈日志和状态在 `ue4ss\Mods\UnifiedHitstop`。

## 从源码构建

需要 Windows x64、Visual Studio 2022 C++ Build Tools（包含 MASM）、Windows SDK、CMake ≥ 3.24、Python 3.14（包含 Tk）。

```powershell
python -m pip install -r requirements-build.txt
python tools/build.py
```

产物位于 `dist/`。只编译 DLL 可使用 `python tools/build.py --native-only`。构建时会下载并校验固定版本的 UE4SS 依赖，记录见 `dependencies.json`。

GitHub Actions 在推送 `main` 或创建 PR 时检查构建；推送与 `VERSION` 一致的 `v*` 标签会在通过检查后发布 Release，例如 `VERSION=0.3.0` 对应 `v0.3.0`。工作流也可手动触发构建。

源码结构与接口说明见 [架构说明](docs/ARCHITECTURE.md)。项目源码使用 MIT 许可证；打包依赖与来源见 [第三方说明](THIRD_PARTY_NOTICES.md)。
