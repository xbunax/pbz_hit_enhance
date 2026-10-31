# 影之刃零 · 卡肉调节 Mod

[![构建与发布](https://github.com/xbunax/pbz_hit_enhance/actions/workflows/release.yml/badge.svg)](https://github.com/xbunax/pbz_hit_enhance/actions/workflows/release.yml)

通过共享命中反馈入口调整卡肉帧数，提供中文调节面板、快捷键呼出和随游戏启动自动加载。可以按原帧数缩放、增加/减少帧数，或固定帧数。默认 **1 倍**，保留游戏原始时长。

## 分武器类别设置（0.4 预览）

“卡肉设置”新增“编辑类别”：全局默认、单手刀剑、双持武器、双手重武器。各类别可以单独选择倍率、增减帧数或固定帧数，并设置自己的上限。勾选“此类别使用独立设置”后覆盖全局；取消后沿用全局。总开关关闭会停止所有类别的调整。恢复默认只重置当前编辑类别。

分类依据是**本次命中的攻击标签**，不是玩家当前装备。当前候选映射：

| 类别 | 支持的 Slash / Stab 攻击标签族 |
| --- | --- |
| 单手刀剑 | TangBlade、BronzeSword、LuanYing、Wood、Iron、ChiZheCanJian、SlitheringSword、CiGuHunDun、ZiMingJian |
| 双持 | DoubleBlade、SnakeDualShort、SnakeDualLong、DualHook、ShuangYue、JadeDualChakram、YaoJu |
| 双手重武器 | LongBlade、Horizontal、ZhanMa、ZhanMaBlade、PoJun、Jigsaw、YanYueDao、BaiYing |

SlitheringSword 另支持配置中存在的 Slap 挥击类型；其他武器不由此泛化到 Slap。

接受上述标签的点分子标签（例如 TangBlade.Player），比较不区分大小写。其他标签、踢击、能量攻击等未分类事件沿用全局。该映射根据提取的反馈规则建立，**已对乱莺剑、白蟒赤练、亡命斩马刀完成分类与固定帧数实测，尚未证明覆盖全部装备**；新武器需要核对实际标签后补充映射。敌人可能共用这些标签，本版仍包含双方匹配命中，不能当作“仅玩家攻击”。暂不支持单件武器或轻、中、重命中分别覆盖。

乱莺剑的 `Slash.LuanYing.Default` 和 `Stab.LuanYing` 已归入单手分类并通过重载后的实测。样本集中在 Shield.Iron 和 Vessel 材质，不能代替肉体命中及所有敌人类型测试。

白蟒赤练的 `SnakeDualShort.Player` 和 `SnakeDualLong.Player`（含 Slash / Stab）均归入双持，不能因 Long 或共用单手卡肉表而划为其他类别。亡命斩马刀的 ZhanMaBlade 归入双手重武器。

一次三类武器实测中共记录 67 次反馈，单手类别 19 次改为 5 帧（其中乱莺剑标签 16 次、TangBlade.Player 3 次），双持 11 次改为 7 帧，双手重武器 10 次改为 9 帧。40 次修改均与紧随其后的下游 Hitreact 消费参数一致，未记录错误；双持原本 0 帧的一次反馈仍为 0。该验证证明这些样本的独立设置路径有效，不是全武器、全材质或完整调用栈验证。5/7/9 为测试值，不作为默认推荐调校。

覆盖审计直接读取了当前版本的 `DT_WeaponData`：33 条记录全部属于这三类（15 / 8 / 10），包含序章、马车战变体和 Placeholder 资源，不能理解为 33 把独立可收集武器。当前为其中 25 条记录建立了候选标签关联（单手 12、双持 6、双手 7）；仅三把完成实战验证，其余是武器类别、资源名称与反馈规则的静态交叉关联，不能据此保证所有招式。

仍缺少可靠标签证据的 8 条记录：红妆鬼斩、白山风雷剑、珠光宝气、邪火、圣母邪扇、魔切、黑魔伤、黑魔伤（序章）。其中包含占位和变体。未知标签继续沿用全局；主武器的能量、踢击等特殊招式也不保证跟随武器类别。范围目前仅为三个主武器类别，煞器保持现有全局回退行为。

“仅记录命中，不修改帧数”优先于全部调整设置，用于核对类别。运行状态页显示最近命中的标签、识别类别、采用设置、原始与结果帧数；这些是最近反馈，不是当前装备显示。类别未启用独立设置时，识别类别与采用设置可以不同。

旧版六项配置可直接读取，原有值保留；第一次通过新版面板保存时自动补齐类别配置。默认类别均沿用全局，新增设置保存在同一个 config.ini 中并原子替换。新版扩展配置不能直接交回 0.3 的旧脚本使用，回退前恢复旧配置备份。

扩展验证顺序：对新武器先开仅记录模式，核对标签与类别，再以独立固定帧数检查下游输出。本次已完成三件武器的固定帧数测试；后续已验证单手 3 倍（32 次）、4 倍（6 次）及双持 3/4 倍（9 次）的下游帧数匹配；本轮尚未实测总开关关闭后的恢复，该行为已有离线回归覆盖。离线测试不代替实战。

## 下载

打开 [Releases](https://github.com/xbunax/pbz_hit_enhance/releases)，选择 **v0.4.0-preview.1（预览版）**，下载 `PBZHitEnhance-v版本号-windows-x64.zip`。不要下载 GitHub 自动生成的 Source code 压缩包用于安装。

发布包由 GitHub Actions 编译，包含加载 DLL、匹配的 UE4SS 运行库和独立面板程序，使用者无需安装 Python、Visual Studio 或 ReShade。

## 安装

1. **完全退出游戏。**
2. 在 Steam 中右键《影之刃零》→ 管理 → 浏览本地文件。
3. 进入 `platform\steam` 文件夹，确认这里有体积约 487 MiB 的真实 `PBZ.exe`。本项目验证的路径为 `…\steamapps\common\PBZ\platform\steam\PBZ.exe`。
4. 解压 Release，把 `dwmapi.dll` 和整个 `PBZHitEnhance` 文件夹复制到这个 `PBZ.exe` 旁。保留文件夹结构。
5. 正常从 Steam 启动游戏。首次启动会打开快捷键设置，点击“点击录入按键”，按住所需单键或同时按住组合键，全部松开后点击“保存快捷键”。以后面板在后台启动，使用保存的快捷键呼出或隐藏。

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

本版只写当次命中反馈的 `Frames`，保留倍率和曲线。作用于经过共享入口的普通命中，**包含玩家受击**；跳过原本零帧、格挡、其他特殊标签和按持续时间计时的反馈。帧数是游戏内部单位，尚未换算成现实毫秒。日志证明参数传入执行接口，不能代替实际停顿时长测量。本版尚无独立“停顿强度”调节；增加帧数不会同时降低原始减速倍率或改变恢复曲线，因此主观打击感不一定按相同比例增强。未验证所有武器。

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

- **按快捷键无反应**：确认游戏为窗口化/无边框。手动运行面板程序，在“快捷键”页点击录入，直接按下所需按键并松开，再保存。支持 Insert 等单键、Ctrl+Insert 等修饰组合，以及 A+B 等多个普通键同时组合；也支持方向键、标点键和数字小键盘。左右 Ctrl/Alt/Shift/Win 视为同一个键。按住不会连续开关，需松开整组按键才能再次触发。无关的移动键或媒体键不会阻断快捷键，额外按住未配置的修饰键则不触发。录入支持常规键盘键，不包含媒体键和鼠标键。录入超时或失去焦点会取消，旧快捷键保持有效；录入结果保存前不生效。Windows 保留的系统快捷键可能被系统优先处理；面板不拦截游戏输入，避免选用常用战斗键组合。
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
