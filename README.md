# VoxFlow

VoxFlow 是一套面向中文知识视频的自动化生产工作流。它把逐字稿拆成分镜，生成 Vox 风格纸张拼贴关键帧，通过 RunningHub MiniMax H3 将图片转为视频，再生成口播、字幕和最终成片，并可把素材交给 ChatCut 继续编辑。

```text
中文逐字稿
  -> 分句、节拍与分镜规划（beats.json）
  -> image2 批量生成纸张拼贴关键帧
  -> RunningHub MiniMax H3 图生视频
  -> TTS 口播与 SRT 字幕
  -> FFmpeg 自动合成
  -> ChatCut 可编辑工程交接（可选）
```

## 功能

- 中文逐字稿自动分句、估时和分镜
- Vox 风格编辑型纸张拼贴提示词
- MiniMax H3 I2VA 图生视频提示词
- 横屏 `16:9` 与竖屏 `9:16`
- image2 并发生图，默认可配置为 16 路
- RunningHub 会员 API 最多 3 路并发
- RunningHub 企业共享 API 最多 100 路并发，并默认使用 Plus 机型
- 任务级缓存、断点续跑和并发锁，减少重复付费任务
- 视频批量保护，超过阈值时要求显式确认
- 本地 FFmpeg 合成、响度标准化和字幕烧录
- ChatCut 原生可编辑素材、口播、BGM 和字幕交接

## 当前默认成片规范

| 项目 | 默认值 |
| --- | --- |
| 帧率 | 24 fps |
| 竖屏画布 | 1080 x 1920 |
| 横屏画布 | 1920 x 1080 |
| 视频编码 | H.264 / yuv420p |
| 音频编码 | AAC 192 kbps |
| 口播目标响度 | -16 LUFS |
| 真峰值上限 | -1.5 dBTP |
| BGM 音量 | -28 dB |
| 字幕位置 | 画面下方居中 |
| 字幕底边距 | 40 px |
| 默认字体 | Microsoft YaHei |

## 目录结构

```text
vox_video/
  examples/                 可提交的示例逐字稿
  scripts/
    voxflow.ps1             PowerShell 入口
    check_secrets.py        提交前密钥扫描
  src/voxflow/
    planner.py              分句、节拍、分镜和提示词
    image_adapter.py        whiteboard image2 适配器
    runninghub.py           上传、并发提交、轮询和下载
    tts_adapter.py          whiteboard TTS 适配器
    assembler.py            FFmpeg 合成、混音和字幕
    chatcut.py              ChatCut 交接文件和启动器
    cli.py                  命令行入口
  tests/                    单元测试
  config.example.toml       无密钥配置模板
  projects/                 本地生成项目，不进入 Git
```

## 依赖

- Windows PowerShell 7 或 Windows PowerShell 5.1
- Python 3.11 或更高版本
- FFmpeg 与 ffprobe，并已加入 `PATH`
- 一个可用的 whiteboard 项目或兼容适配器：
  - `skills/whiteboard-video-workflow/scripts/generate-image.py`
  - `auto-whiteboard/scripts/generate_voiceover.py`
- RunningHub API Key
- ChatCut Codex 插件（仅 ChatCut 交接需要）

VoxFlow 本身只使用 Python 标准库。图片和 TTS 的服务端依赖由 whiteboard 项目管理。

## 安装

```powershell
git clone https://github.com/shaomingchan/vox_video.git
Set-Location vox_video

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .

Copy-Item config.example.toml config.local.toml
```

编辑 `config.local.toml`，至少设置：

```toml
[paths]
whiteboard_root = "D:/path/to/whiteboard"
vox_director_root = "C:/Users/you/.codex/skills/vox-director"
projects_root = "projects"

[assembly]
bgm = "D:/path/to/background-music.mp3"
```

`config.local.toml` 已被 `.gitignore` 排除，不会被正常的 `git add .` 加入提交。

## API Key 安全

仓库中不应出现任何真实密钥。VoxFlow 只从环境变量、Windows 用户环境变量或 whiteboard 的本地忽略配置读取凭据。

会员 API：

```powershell
$env:RUNNINGHUB_API_KEY = "<your-member-key>"
```

企业共享 API：

```powershell
$env:RUNNINGHUB_API_PROFILE = "enterprise"
$env:RUNNINGHUB_ENTERPRISE_API_KEY = "<your-enterprise-key>"
```

需要跨终端保存时，可以写入 Windows 用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable(
  "RUNNINGHUB_API_KEY",
  "<your-member-key>",
  "User"
)
```

安全原则：

- 不要把密钥写入 `config.example.toml`、README、测试或命令历史
- 不要提交 `.env`、`config.toml`、`config.local.toml`、whiteboard 私有配置
- 不要在错误日志中打印完整请求头
- 不要提交 `projects/`、`outputs/`、口播音频或临时下载链接
- 密钥一旦进入 Git 历史，应立即在服务端撤销并重新生成；删除文件不能让历史中的密钥失效

提交前运行：

```powershell
.\.venv\Scripts\python.exe scripts/check_secrets.py
```

扫描器只输出疑似凭据所在的文件、行号和规则名称，不打印匹配内容。

## 配置

### 画面方向

竖屏：

```toml
[project]
aspect = "9:16"

[assembly]
width = 1080
height = 1920
```

横屏：

```toml
[project]
aspect = "16:9"

[assembly]
width = 1920
height = 1080
```

图片与 RunningHub 视频必须使用相同的 `aspect`。合成器会把视频缩放并裁切到配置画布，但不应依赖裁切修复错误方向的源素材。

### RunningHub 会员模式

```toml
[runninghub]
api_profile = "member"
instance_type = "default"
concurrency = 3
```

会员模式的代码级并发上限固定为 3，即使配置了更大的数字也会被压回 3。

### RunningHub 企业共享模式

```toml
[runninghub]
api_profile = "enterprise"
enterprise_instance_type = "plus"
enterprise_concurrency = 100
```

企业模式应同时设置 `RUNNINGHUB_API_PROFILE=enterprise` 和 `RUNNINGHUB_ENTERPRISE_API_KEY`。代码会默认选择 Plus 机型，并把并发限制在 1 到 100 之间。

### Lite 机型

```toml
[runninghub]
instance_type = "lite"
```

Lite 模式提交时不发送 `instanceType`，由 RunningHub 调度机型。

### 混音与字幕

```toml
[assembly]
bgm_volume_db = -28
voice_target_lufs = -16
burn_captions = true
caption_font = "Microsoft YaHei"
caption_font_size = 88
caption_margin_bottom = 40
```

本地 FFmpeg 合成使用 `loudnorm=I=-16:TP=-1.5:LRA=11`。ChatCut 交接会要求：

- 所有图生视频素材原声静音
- 口播优先，目标 -16 LUFS
- BGM 基线 -28 dB
- 中文字幕下方居中，底边距约 40 px

## 使用

PowerShell 包装脚本默认按以下顺序选择 Python：

1. `VOXFLOW_PYTHON` 环境变量
2. 相邻 whiteboard 项目的 `.venv` Python
3. `PATH` 中的 `python`

配置文件按以下顺序选择：

1. `VOXFLOW_CONFIG` 环境变量
2. `config.local.toml`
3. `config.toml`
4. `config.example.toml`

### 免费环境检查

```powershell
scripts/voxflow.ps1 doctor
```

`doctor` 不调用付费生成 API，用于检查 FFmpeg、whiteboard 适配器、Vox 技能、RunningHub Key 和 ChatCut 插件。

### 只规划分镜

```powershell
scripts/voxflow.ps1 plan `
  --project demo `
  --script examples/demo-script.txt
```

结果写入 `projects/demo/beats.json`。正式生成前建议检查镜头数量、画面方向、开场钩子、画面文字和运镜是否符合预算。

### 分阶段生成

```powershell
scripts/voxflow.ps1 voice --project demo
scripts/voxflow.ps1 images --project demo
scripts/voxflow.ps1 videos --project demo --limit 3
scripts/voxflow.ps1 preview --project demo --limit 3
scripts/voxflow.ps1 assemble --project demo
```

指定镜头：

```powershell
scripts/voxflow.ps1 videos `
  --project demo `
  --shot-id 001 `
  --shot-id 004
```

完整运行：

```powershell
scripts/voxflow.ps1 run `
  --project demo `
  --script examples/demo-script.txt
```

仅规划但不生成：

```powershell
scripts/voxflow.ps1 run `
  --project demo `
  --script examples/demo-script.txt `
  --dry-run
```

### ChatCut 交接

```powershell
scripts/voxflow.ps1 chatcut --project demo
```

生成：

```text
projects/demo/final/chatcut_handoff.json
projects/demo/final/chatcut_prompt.txt
```

已完成 ChatCut OAuth 登录时，可直接启动交接任务：

```powershell
scripts/voxflow.ps1 chatcut --project demo --launch
```

前 N 个镜头的小样也可单独交接：

```powershell
scripts/voxflow.ps1 chatcut --project demo --limit 10 --launch
```

## 缓存和断点续跑

图片和视频都根据提示词、画面比例、工作流 ID 和输入文件哈希生成指纹。重新执行相同命令时，已完成且指纹一致的文件会被复用。

- `image_manifest.json` 保存图片指纹与文件哈希
- `video_manifest.json` 保存 RunningHub task ID、视频指纹和结果信息
- 每个任务完成后立即更新 manifest，进程中断时可继续
- Windows 使用命名 Mutex，其他系统使用文件锁，避免同一项目重复启动生成
- `--force` 会绕过缓存，应仅在明确需要重新付费生成时使用

## 成本保护

`videos` 默认最多允许 `max_unconfirmed_batch` 个待生成镜头。超过阈值时任务会停止，并要求：

- 使用 `--limit N` 生成小样
- 使用一个或多个 `--shot-id`
- 确认全量生产后显式传入 `--all`

```powershell
scripts/voxflow.ps1 videos --project demo --all
```

推荐先生成 3 到 10 个镜头完成质量检查，再启动全量任务。不要在不清楚缓存状态时使用 `--force --all`。

## 输出

```text
projects/<name>/
  script.txt
  beats.json
  image_manifest.json
  video_manifest.json
  images/shot-001.png
  clips/shot-001.mp4
  audio/voiceover.wav
  audio/subtitles.srt
  previews/first-010/preview.mp4
  final/final_video.mp4
  final/composition_report.json
  final/chatcut_handoff.json
```

RunningHub 返回的下载链接具有时效性，工作流在任务成功后立即下载到 `clips/`，不要把临时 URL 当作长期素材地址。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe scripts/check_secrets.py
```

依赖本机 whiteboard 项目的适配器测试在该项目不可用时会跳过，其余测试不调用付费 API。

## 常见问题

### 图片是横屏，视频却是竖屏

检查 `project.aspect` 是否同时传给 image2 和 RunningHub，并确认 `assembly.width/height` 与它一致。已经生成的错误方向素材不会因修改合成配置自动恢复构图，需要修正源阶段配置。

### BGM 压过口播

确认 `bgm_volume_db = -28`、`voice_target_lufs = -16`。如果在 ChatCut 中继续编辑，需要同时静音全部源视频原声，避免素材音轨叠加。

### 任务看起来重复提交

检查是否有两个终端同时运行、是否使用了 `--force`，以及 manifest 是否仍然存在。当前版本会对同一项目加锁，并在缓存异常可能触发大批重生成时主动停止。

### `doctor` 找不到 RunningHub Key

确认当前 profile 与环境变量匹配：会员模式读取 `RUNNINGHUB_API_KEY`，企业模式读取 `RUNNINGHUB_ENTERPRISE_API_KEY`。

## 项目状态

本项目目前主要针对 Windows、本地 whiteboard 工程、RunningHub 中国站 API 与 ChatCut Codex 插件。提交代码不会包含任何模型凭据、用户逐字稿或生成素材。
