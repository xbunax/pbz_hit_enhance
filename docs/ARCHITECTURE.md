# 架构说明

## 自动加载

`dwmapi.dll` 为 x64 系统代理。导出表来自已检查的 dwmapi 导出清单，MASM 桩直接跳转到系统 DLL 的真实地址。转发在 DllMain 中准备；版本校验、加载 UE4SS 和启动面板由后台线程执行。

后台只处理文件名为 PBZ.exe 的进程；游戏 SHA256 与已测试版本不同只记录 untested_game_warning_continuing，不阻止加载。默认从 DLL 旁的 PBZHitEnhance 查找数据；可由 PBZHitEnhance.ini 的 Paths/DataDirectory 覆盖。运行库校验通过后仅加载 ue4ss/UE4SS.dll。Mod 的 Lua 入口通过 PBZBootstrap.dll 启动面板，传入 --mod-dir 和真实游戏的 PID、创建时间与路径。不会注册服务或系统开机启动项。

`PBZHitEnhanceStatus` 为测试导出：2 表示非游戏进程被跳过；发布检查在 Python 测试宿主中验证不会加载 UE4SS。

## 统一反馈入口

`/PBZCombatAsset/Prototypes/Hitreact/BP_HitEffectPlayer_Chooser.BP_HitEffectPlayer_Chooser_C:GetEffectData`

使用蓝图函数后置回调，游戏选择完反馈数据后，仅修改当次输出 SlomoData.Frames。不改武器表，不用“上次攻击者”推断归属。StartSlomoData Hook 只记录下游消费，避免给双方重复加帧。

policy.lua 负责配置解析、作用范围与帧数计算。仅处理 Hitreact.Strength.Income.Normal.*、原值 >0 且 UseSlomoDuration=false 的反馈。写后读回校验失败时尝试恢复原值，随后停止修改直到配置内容变化。

## 面板

Python/Tk 源码由 PyInstaller 生成包含解释器和 Tk 的独立目录包；用户不需要安装 Python。全局快捷键由当前按键状态采样工作线程处理，Tk 主线程负责显示和原子保存配置。已设置快捷键时，自动启动模式默认隐藏。

配置不作为 Lua 执行，只接受白名单键与合法数值。后台按约一秒周期在游戏线程应用新配置。UI 与脚本通过配置和状态文件通信，不进行外部进程内存写入。

## 构建与验证

CMake 构建代理 DLL，Python 工具生成完整发行包。依赖归档与 UE4SS DLL 均锁定 SHA256。发行包还包含每个文件的校验清单及压缩包 SHA256。

测试覆盖原始 Lua 回调执行、配置热更新、无效配置停用、写入失败回滚；Windows 检查验证所有导出可解析、两个真实系统调用、非游戏宿主保护及冻结后的面板自检。构建不包含游戏文件、存档、用户快捷键或实战日志。

## 0.4 预览：类别路由

policy.select(config, attackTag) 先按候选攻击标签族分类，再返回启用覆盖的类别配置或全局配置。它不保留 UObject，不读取全局“当前武器”来代替攻击来源；来源过滤仍未解决。GetEffectData 只写一次，StartSlomoData 只观察，避免给攻击双方重复调整。

配置继续采用白名单平面键：原有六项必填，ObserveOnly 可选；Blade / DoubleBlade / GreatBlade 的 Override、Mode、Scale、AddFrames、FixedFrames、MaxFrames 使用点号前缀。某类完全缺省表示继承全局；部分缺失、未知键、重复键或越界值会使整份配置失效，停止写入。总 Enabled 和 ObserveOnly 对所有类别生效。

分类表是基于攻击标签的初始候选，不能由 EWeaponType 枚举存在推导出所有标签的准确归属。界面提供三类编辑选项，候选映射的验证范围见 README；运行状态和日志输出 attack_type、group、profile、reason，便于三类武器分段采样校正。未知标签不猜测，回退全局。

面板切换类别前保存当前编辑值；模式切换分别保留各模式数值；重置只作用于当前类别。123 项 Lua 场景涵盖实际回调、三类交替命中、未知标签回退、禁用/只读、热更新与错误恢复。Tk 测试使用隔离配置与假快捷键工作线程，不注册系统快捷键。

## 三类武器实战验证（2026-10-31）

在重载包含 LuanYing、SnakeDualShort、SnakeDualLong 的映射后，使用独立固定帧数 5/7/9 测试单手、双持、双手重武器。67 次 GetEffectData 反馈中，分别有 19、11、10 次写入；全部 40 次修改后都紧邻出现一致的 StartSlomoData 帧数、倍率和曲线。另一次双持零帧保持为零，13 次非普通反馈、13 次全局恒等反馈保持原值，无错误记录。

单手样本包括 16 次 LuanYing、3 次 TangBlade.Player，不能把后者未经来源关联就算作乱莺剑特有标签。双持的长、短刃都归 DoubleBlade；ZhanMaBlade 归 GreatBlade。材质为 Shield.Iron / Vessel，敌我身份过滤、全武器覆盖、肉体材质及总开关关闭恢复验证仍有范围限制。后续单手 3/4 倍和双持 3/4 倍已验证参数热更新后的下游匹配。相邻下游匹配不能替代完整调用栈关联。

## 主武器覆盖审计

DT_WeaponData 中 WeaponType 枚举值 1/2/3 对应 Blade/DoubleBlade/GreatBlade，33 条配置的数量为 15/8/10。实际读取的主武器配置中，多数资源未加载，已加载的 Attack Type Mapping 字段为空；因此没有使用这个空字段自动推导所有招式。新增分类只根据武器资料的类别、命名可关联的资源/标签及反馈选择规则建立候选关联，未强制加载额外资源或调用游戏函数。

24 个标签族为 25 条配置提供候选关联。已审查的选择规则标签无跨类别冲突，但不代表所有未枚举标签无冲突。SlitheringSword.Slap 是明确单独处理的例外；煞器标签 Mojian/BrutalAxe/XueDiZi、通用 Default、能量与踢击不被误塞进这三类。剩余 8 条记录和每把武器的招式完整性仍需补充证据。新增映射写入预览目录后，当前已加载 Lua 不热重载，需下一次游戏进程加载才生效。

## 快捷键录入与匹配

快捷键保存在 ui_settings.json，以规范化键名表示，兼容旧 CTRL+F10。后台线程使用 GetAsyncKeyState 的当前按下状态位，录入时暂时停止触发，按键全部松开后提供待保存组合；取消、失焦和超时保留旧配置。匹配支持常规键盘单键与多个普通键，左右修饰键等价。

仅采样支持绑定的常规键盘键，不扫描保留 VK 或媒体设备状态。已复现本机媒体播放/暂停键持续置位；旧“全键集合完全相等”逻辑因此阻断 Ctrl+F10。现匹配要求绑定键全部按下且修饰键集合准确，无关普通键不阻断；完整松开绑定键后才能再次触发。原始按键状态不写入日志，仅保存用户确认的快捷键。该机制不拦截游戏输入，也不覆盖 Windows 系统保留行为。

## 0.4.0-preview.2：进程会话与双发行包

面板使用 SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION 打开游戏句柄，核对路径、PID 和 FILETIME 创建时间，每 250 ms 检查进程是否结束；不根据 Lua 心跳判断游戏退出。自动启动面板还由游戏持有的 KILL_ON_JOB_CLOSE Job 管理，子进程以挂起状态创建，加入 Job 后才恢复，且不继承 Job 句柄。面板自己监听进程退出作为另一条清理路径。真实 HWND/Tk 测试与原生生产启动函数测试分别验证正常及强制退出。

PBZBootstrap 以 lua_CFunction 形式导出零参数启动入口，不读取 Lua 栈或导入 Lua/UE4SS SDK 符号；通过自身路径解析 Mod 的规范化目录。它记录游戏是否匹配已测试版本、读取实际已加载 UE4SS、建立游戏会话级所有者互斥，再启动面板。未知游戏版本写入 GameVerified=false 和 GameWarning=untested_game_continuing，不作为启动失败。不同 Mod 副本的重复实例被拒绝；同一脚本被 UE4SS 正常重载时使用已初始化的本组件。允许状态、运行库路径与哈希写入 bootstrap.ini，启动故障另记 startup.log。status.ini 带会话身份，面板不把上一轮游戏的状态当成新会话。

整合包使用自有代理和锁定运行库；发现外部 UE4SS、override.txt 或 --ue4ss-path 时停止自带加载。仅 Mod 包不含根目录代理、UE4SS.dll、公共设置或签名，复用用户现有运行库。Lua 检测接口后再初始化；对象尚未加载时等待，已找到对象而 Hook 失败时撤销本 Mod 已注册的 Hook 并保持停用。未知外部版本允许尝试，不等同于已验证兼容。

安装器把数据放在版本目录，兼容模式通过 Mods 目录中的联接引用外部数据。仅替换自身启用条目，失败回滚联接、加载器、路径配置和启用列表。安装及卸载测试使用隔离假游戏文件验证，不依赖真正游戏，也不在测试中执行假游戏。完整回归还覆盖旧配置迁移、篡改包拒绝、其他代理保护和只读控制列表造成的失败恢复。
