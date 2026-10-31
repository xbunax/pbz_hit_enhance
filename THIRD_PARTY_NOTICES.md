# 第三方依赖说明

- **UE4SS**：UE4SS-RE 团队及贡献者，MIT 许可证。源码：https://github.com/UE4SS-RE/RE-UE4SS ，固定提交见 dependencies.json。发行包保留 `ue4ss/LICENSE`。
- **PBZ 适配配置**：来自 KintaroModding 发布的 Phantom Blade Zero 专用 UE4SS 包；包括 MemberVariableLayout.ini 和两个扫描签名。来源：https://github.com/KintaroModding/ue4ss/releases/tag/v3.0.1-1183-gcdbc0b66 。归档 SHA256 固定在 dependencies.json；不使用其中的默认 helper mods 或代理 DLL。
- **CPython、Tcl/Tk**：面板打包所需运行时，由 GitHub Actions 的 Python 环境和 PyInstaller 收集。适用其各自的开源许可证；构建时会将 Python 及可用的 Tcl/Tk 许可证复制到数据目录的 licenses。
- **PyInstaller**：GPL 2.0 或更新版本，附带允许分发生成程序的引导加载器例外。https://pyinstaller.org/en/stable/license.html
- **Lupa、Ruff、CMake 和 Visual Studio Build Tools**：仅用于构建/测试，不作为 Mod 功能代码。

本项目不包含游戏可执行文件、存档或游戏资源，不包含 ReShade 运行库。
