# 奶龙桌宠

一个由本地视频驱动的 Windows 桌面宠物。程序会实时提取视频帧、移除灰白背景，并通过 Windows 色键透明窗口显示角色；支持动画原声、托盘控制、多显示器、尺寸与位置记忆以及开机自启动。

> 当前版本：1.0.0。仅支持 Windows 10/11；源码运行需要 Python 3.11 或更高版本。

## 功能特性

- 单击播放约 1.7 秒侧看动画，双击播放前 8 秒完整动画。
- 播放视频原声，支持静音及 0%–100% 音量预设。
- 左键拖动、边缘吸附及负坐标多显示器支持。
- Ctrl + 左键拖动或滚轮连续缩放，显示宽度限制为 60–720 px。
- 可选闲置动作：空闲约 30 秒后随机眨眼或侧看。
- 托盘显示、隐藏、播放、静音和退出控制。
- 当前用户级开机自启动，无需管理员权限。
- 源码启动与安装程序两种使用方式。

## 快速开始

### 直接运行源码

1. 安装 64 位 Python 3.11 或更高版本，并确保 `python` 命令可用。
2. 下载或克隆本仓库。
3. 双击 `start.bat`。

首次启动会在项目目录创建 `.venv`，并从 `requirements.txt` 安装运行依赖。后续启动会复用该虚拟环境。

也可以在 PowerShell 中手动启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

### 使用安装程序

如果仓库的 [Releases](https://github.com/SolitudeSailor/nailong-desktop-pet/releases) 页面提供安装包，可下载 `奶龙桌宠-安装程序-<版本>-x64.exe` 后运行。安装位置默认为当前用户的 `%LOCALAPPDATA%\Programs\奶龙桌宠`，不要求管理员权限。

## 操作说明

| 操作 | 效果 |
|---|---|
| 单击桌宠 | 播放侧看动画 |
| 双击桌宠 | 播放完整动画及原声 |
| 左键拖动 | 移动桌宠；松开时可吸附屏幕边缘 |
| Ctrl + 左键左右拖动 | 连续调整尺寸 |
| 鼠标滚轮 | 每次放大或缩小 12 px |
| 右键 | 打开尺寸、声音、显示器、自启动等菜单 |
| 托盘图标双击 | 显示桌宠 |

动画结束后会自动回到第一帧。闲置动作和开机自启动默认关闭。

## 配置与本地数据

程序保存位置、尺寸、声音、音量、闲置动作和吸附偏好。配置内容在读取时会进行类型和范围校验，单个无效字段会恢复默认值，不影响其他配置。

| 运行方式 | 配置和音频缓存位置 |
|---|---|
| 源码运行 | 项目目录下的 `settings.json` 与 `.cache/` |
| 安装版 | `%LOCALAPPDATA%\nailong\settings.json` 与 `%LOCALAPPDATA%\nailong\.cache\` |

卸载安装版时会清理 `%LOCALAPPDATA%\nailong`。源码运行产生的本地配置、缓存和错误日志已列入 `.gitignore`。

## 命令行参数

```powershell
.\.venv\Scripts\python.exe app.py `
  --video ".\奶龙大笑_video.mp4" `
  --width 720 `
  --display-width 180 `
  --chroma-tolerance 55
```

| 参数 | 默认值 | 有效范围 | 说明 |
|---|---:|---:|---|
| `--video` | `奶龙大笑_video.mp4` | 有效文件路径 | 动画视频素材 |
| `--width` | 720 | 60–4096 | 去背和内部渲染宽度 |
| `--display-width` | 180 | 60–720 | 首次运行时的桌面显示宽度 |
| `--chroma-tolerance` | 55 | 0–255 | 灰白背景最大饱和度；越大去除范围越宽 |

如果已有 `settings.json`，其中保存的显示宽度优先于 `--display-width`。

## 项目结构

```text
奶龙桌宠/
├── app.py                    # Tk 桌宠窗口、交互和动画调度
├── desktop_services.py       # Windows 显示器、托盘、音频和自启动服务
├── nailong_pet/
│   ├── __init__.py           # 应用元数据
│   ├── imaging.py            # 去背、透明缩放与色键转换
│   └── settings.py           # 配置模型、默认值和输入校验
├── launcher.pyw              # 无控制台源码启动入口与错误记录
├── start.bat                 # 虚拟环境初始化和日常启动
├── tests/                    # 单元测试与 GUI 交互回归测试
├── assets/                   # 安装图标源文件
├── packaging/nailong.iss     # Inno Setup 安装脚本
├── build_installer.ps1       # 测试、PyInstaller 和安装器构建流程
├── requirements.txt          # 运行依赖
├── requirements-build.txt    # 构建依赖
├── 奶龙大笑_video.mp4        # 运行时动画素材
└── 奶娃.png                  # 设计参考图，不参与当前运行
```

## 测试

项目使用 Python 标准库 `unittest`，无需额外测试框架：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app.py desktop_services.py launcher.pyw nailong_pet tests
```

测试覆盖配置校验、图像色键处理、桌宠交互、动画复位、多显示器定位、自启动注册表操作和安装器命名约束。GUI 测试需要 Windows 图形桌面环境。

## 构建 Windows 安装程序

### 前置条件

- 64 位 Python 3.11 或更高版本；
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)；
- 项目虚拟环境中的构建依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build_installer.ps1
```

构建脚本会先运行全部测试，再调用 PyInstaller 和 Inno Setup。输出位置：

- `build\奶龙桌宠\`：PyInstaller 目录版程序；
- `installer\奶龙桌宠-安装程序-1.0.0-x64.exe`：最终安装程序。

脚本会自动检查 Inno Setup 的常见安装位置。若使用自定义位置，可显式传入：

```powershell
.\build_installer.ps1 -InnoCompiler 'D:\Tools\Inno Setup 6\ISCC.exe'
```

## 实现说明

- 视频帧先缩放到内部渲染宽度，再检测与画面边缘连通的低饱和灰白区域。
- 缩放透明图像时采用预乘 Alpha，随后将透明度二值化，以减少 Windows `transparentcolor` 产生的紫边。
- 音频由 `imageio-ffmpeg` 从视频前 8 秒提取到本地缓存；视频无音轨或音频设备不可用时，动画仍可正常播放。
- 托盘和音频准备在后台线程中运行，界面事件通过线程安全队列回到 Tk 主线程处理。

## 常见问题

### 双击 `start.bat` 后没有出现桌宠

检查项目目录中的 `desktop_pet_error.log`。常见原因包括 Python 未加入 PATH、依赖安装失败、视频文件缺失或图形环境不可用。

### 没有声音

确认右键菜单中的“播放视频原声”已开启，并查看“声音状态”。视频无音轨、系统没有可用音频设备或 FFmpeg 解码失败时，程序会保持静音。

### 开机自启动失效

源码目录移动或虚拟环境重建后，旧启动命令会失效。关闭并重新开启右键菜单中的“开机自启动”，即可写入当前路径。

### 桌宠移到已断开的显示器

通过托盘重新显示，或从右键菜单选择当前显示器。程序会将窗口限制在可用工作区内。

## 隐私与网络

桌宠运行时不主动访问网络。首次通过 `start.bat` 安装依赖时，`pip` 会访问其配置的软件包索引。配置、缓存和错误日志均保存在本机，不会由程序上传。

## 授权与素材

仓库当前未包含开源许可证，因此公开可见不等同于授予复制、修改或再分发许可。代码或素材用于再发布前，请分别确认相应权利与授权范围。
