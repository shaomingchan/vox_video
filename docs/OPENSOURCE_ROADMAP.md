# VoxFlow 开源化路线图

> 本文档记录开源化的进展与后续方向。上次更新：随首个公开版本发布。

## ✅ 已完成

### 内置 Provider 适配器（原优先级 1）

外部 whiteboard 项目依赖已完全移除（commit `36fa4be`），适配器内置在仓库中：

- **图片生成**：RunningHub（默认）、APIMart Image2、Kie Image2、T8 Image2、MaCode Image2
- **语音合成**：RunningHub（默认）、MiniMax Speech 2.8、Fish Audio、IndexTTS2 (302.ai)

通过环境变量切换：

```powershell
$env:IMAGE_PROVIDER = "apimart_image2"
$env:TTS_PROVIDER = "minimax"
```

### 其他已交付

- ✅ 预设配置模板：`configs/quick-start.toml`、`high-quality.toml`、`cost-optimized.toml`
- ✅ 费用估算：`scripts/voxflow.ps1 estimate --script <逐字稿>`
- ✅ 健康检查：`scripts/voxflow.ps1 doctor`（FFmpeg / 适配器 / API Key / ChatCut）
- ✅ AI Agent 自动化：`agents/preflight_check.py` + `agents/auto_setup.py`（见 AGENTS.md）
- ✅ 密钥安全：`scripts/check_secrets.py` 扫描 + 全量凭据走环境变量
- ✅ CI：GitHub Actions（编译检查 / 单元测试 / 密钥扫描 / 安装验证）

---

## 🎯 后续方向（按优先级）

### 1. Mock Mode（零成本试跑）⭐⭐⭐⭐

无 API Key 也能体验完整流程：占位关键帧 + 静态视频循环 + 静音音轨。

```powershell
scripts/voxflow.ps1 run --project demo --script examples/demo-script.txt --mock
```

收益：新用户立即可见完整流程；开发者可低成本调试分镜与合成逻辑。

### 2. 交互式配置向导 ⭐⭐⭐⭐

在现有 `agents/auto_setup.py` 基础上提供 `scripts/voxflow.ps1 setup`：选择 Provider → 校验 Key → 生成 `config.local.toml` → 自动运行 doctor。消除首次使用时手动编辑 TOML 的步骤。

### 3. RunningHub 工作流 Schema 化 ⭐⭐⭐

当前工作流版本与节点 ID 映射硬编码在适配器中。目标：把节点映射抽成可配置 schema，支持用户替换自己的工作流版本并做启动校验。

### 4. Docker 一键部署 ⭐⭐⭐

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg
```

挂载 `projects/` 与环境变量即可运行，解决非 Windows 环境的 FFmpeg 安装门槛。

### 5. 跨平台适配 ⭐⭐

当前主入口与验证环境以 Windows 为主。`src/voxflow/util.py` 的文件锁已为 Unix 保留路径，需要补齐 PowerShell 入口的 Bash 等价物并在 CI 中增加 Linux/macOS 矩阵。

### 6. Web UI（可选）⭐⭐

Streamlit 原型：粘贴逐字稿 → 可视化配置 → 进度条 → 在线预览。适合内容团队批量使用，优先级最低。

---

## 💡 保持不变的部分

- 分镜算法：句子拆分、时长估算、镜头分配
- 提示词体系：纸张拼贴风格关键帧提示词 + MiniMax H3 官方三段式 I2VA 视频提示词
- 合成管线：FFmpeg 参数、响度标准化、字幕规范
- 成本保护：指纹缓存、并发锁、`--limit` 批次确认
