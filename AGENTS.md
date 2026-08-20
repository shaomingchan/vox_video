# AI Agent 操作指南

本文档是为 AI 编程助手（如 Claude Code、Codex、Workbuddy）编写的，用于自动化配置和运行 VoxFlow。

## 执行步骤

当用户要求"帮我配置并运行 VoxFlow 项目"时，请按以下步骤执行：

### 步骤 1：环境预检查

```bash
python agents/preflight_check.py
```

如果检查失败，提示用户安装缺失的依赖（Python 3.11+, FFmpeg, Git）。

### 步骤 2：询问 API Key

在开始配置前，询问用户：

```
需要以下 API Key 才能运行 VoxFlow：

1. **RunningHub API Key**（必需）
   - 用途：图生视频（H3 模型）
   - 获取地址：https://runninghub.ai/
   - 会员模式支持 3 路并发

是否已准备好这些 Key？
```

等待用户确认后，引导用户设置环境变量：

**Windows (PowerShell)**:
```powershell
$env:RUNNINGHUB_API_KEY = "用户的Key"
```

**Mac/Linux (Bash)**:
```bash
export RUNNINGHUB_API_KEY="用户的Key"
```

### 步骤 3：运行自动配置

```bash
python agents/auto_setup.py
```

该脚本会：
- ✅ 检查环境变量
- ✅ 生成 `config.local.toml`（自动填充路径）
- ✅ 安装 Python 依赖
- ✅ 创建项目目录
- ✅ 运行健康检查

### 步骤 4：试运行 Demo

配置完成后，自动运行一个小样验证：

```bash
# Windows
scripts/voxflow.ps1 run --project demo --script examples/demo-script.txt --dry-run
scripts/voxflow.ps1 videos --project demo --limit 3

# Mac/Linux（如果有 Python CLI 版本）
python -m voxflow.cli run --project demo --script examples/demo-script.txt --dry-run
python -m voxflow.cli videos --project demo --limit 3
```

`--limit 3` 只生成 3 个镜头，快速验证流程。

### 步骤 5：展示结果

运行完成后，告知用户：

```
✅ Demo 运行成功！生成了 3 个镜头。

生成的文件位于：
- 关键帧：projects/demo/images/
- 视频片段：projects/demo/clips/
- 预览视频：projects/demo/final/

如需生成完整视频，运行：
  scripts/voxflow.ps1 run --project demo --script examples/demo-script.txt --all
```

---

## 常见问题处理

### 问题 1：找不到 whiteboard 项目

如果用户没有 whiteboard 项目，有两个解决方案：

**方案 A：询问用户是否有 whiteboard**
```
检测到你没有配置 whiteboard 项目路径。

VoxFlow 的 image2 和 TTS 适配器默认复用 whiteboard 项目。

是否已有 whiteboard 项目？
[1] 是，我有（请提供路径）
[2] 否，没有（将使用替代方案）
```

**方案 B：复制内置适配器**
如果用户选择 [2]，检查 `src/voxflow/adapters/` 是否有内置适配器。如果没有，告知用户：

```
当前版本需要 whiteboard 项目才能运行。

临时方案：
1. 克隆 whiteboard 项目（如果你有访问权限）
2. 或等待未来版本的内置适配器

如需帮助，请参考项目文档或联系维护者。
```

### 问题 2：API Key 权限不足

如果 RunningHub API 返回权限错误：

```
❌ RunningHub API 测试失败：权限不足

可能的原因：
1. API Key 无效或已过期
2. 账户配额已用完
3. 使用了错误的 instance_type

建议：
- 检查 Key 是否正确
- 访问 https://runninghub.ai/ 查看账户状态
- 如果是企业账户，设置 RUNNINGHUB_API_PROFILE=enterprise
```

### 问题 3：FFmpeg 未安装

如果 FFmpeg 检查失败，提供平台特定的安装指令：

**Windows**:
```powershell
winget install ffmpeg
# 或下载：https://ffmpeg.org/download.html#build-windows
```

**Mac**:
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update && sudo apt install ffmpeg
```

---

## 高级配置（可选）

### 自定义画面比例

如果用户明确表示要横屏或竖屏，修改 `config.local.toml`：

```toml
[project]
aspect = "16:9"  # 横屏，或 "9:16" 竖屏

[assembly]
width = 1920     # 横屏：1920×1080，竖屏：1080×1920
height = 1080
```

### 企业模式配置

如果用户有 RunningHub 企业账户：

```bash
# 设置环境变量
$env:RUNNINGHUB_API_PROFILE = "enterprise"
$env:RUNNINGHUB_ENTERPRISE_API_KEY = "企业Key"
```

修改 `config.local.toml`：
```toml
[runninghub]
api_profile = "enterprise"
enterprise_instance_type = "plus"
enterprise_concurrency = 100
```

---

## 输出格式规范

执行每个步骤时，使用清晰的进度提示：

```
🤖 VoxFlow 自动配置
==================================================
[1/5] ✅ 环境检查通过
[2/5] ✅ API Key 已设置
[3/5] ✅ 配置文件已生成
[4/5] ⏳ 安装依赖中...
      ✅ 依赖安装完成
[5/5] ⏳ 运行健康检查...
      ✅ 所有检查通过

🎉 配置完成！开始运行 Demo...
==================================================
```

---

## 安全注意事项

1. **不要在日志中输出完整的 API Key**
   ```python
   # ❌ 错误
   print(f"使用 Key: {api_key}")
   
   # ✅ 正确
   print(f"使用 Key: {api_key[:8]}...")
   ```

2. **不要将 API Key 写入配置文件**
   - 所有敏感信息只通过环境变量传递
   - `config.local.toml` 不应包含任何密钥

3. **提示用户不要提交敏感文件**
   ```
   ⚠️  提醒：请勿将以下文件提交到 Git：
   - config.local.toml
   - .env
   - projects/（包含生成的视频）
   ```

---

## 总结：完整的自动化流程

```python
# AI Agent 执行的完整流程伪代码

def setup_and_run_voxflow():
    # 1. 预检查
    if not run_preflight_check():
        guide_user_install_dependencies()
        return
    
    # 2. 询问 API Key
    api_keys = prompt_user_for_keys()
    set_environment_variables(api_keys)
    
    # 3. 自动配置
    if not run_auto_setup():
        show_error_and_troubleshooting()
        return
    
    # 4. 运行 Demo
    run_demo_with_limit(3)
    
    # 5. 展示结果
    show_generated_files()
    prompt_next_steps()
```

---

## 支持的 AI Agent 平台

- ✅ Claude Code（Anthropic）
- ✅ Codex（GitHub Copilot X）
- ✅ Workbuddy
- ✅ Cursor
- ✅ 任何支持 Python 脚本执行的 AI 助手

关键是确保 Agent 能够：
1. 执行 Python 脚本
2. 读写文件
3. 运行命令行工具
4. 与用户交互（询问 API Key）
