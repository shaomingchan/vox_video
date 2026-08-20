# VoxFlow AI Agent 快速启动指南

**为 AI 编程助手设计的一键部署方案**

---

## 🎯 目标

用户只需告诉 AI Agent：
> "帮我配置并运行 https://github.com/shaomingchan/vox_video"

AI Agent 就能自动完成所有配置，只需用户提供 RunningHub API Key。

---

## ✅ 已完成的工作

### 1. 自动化脚本

**agents/preflight_check.py**
- 检查 Python 3.11+
- 检查 FFmpeg
- 检查 Git
- 失败时给出平台特定的安装指令

**agents/auto_setup.py**
- 验证环境变量（RUNNINGHUB_API_KEY）
- 自动生成 config.local.toml
- 智能检测 whiteboard 和 vox-director 路径
- 安装 Python 依赖
- 创建项目目录
- 运行健康检查

### 2. 文档

**AGENTS.md**
- 完整的 AI Agent 操作指南
- 5 步执行流程
- 常见问题处理方案
- 安全注意事项
- 输出格式规范

**docs/OPENSOURCE_ROADMAP.md**
- 开源化优化路线图
- 6 个优化方向（优先级排序）
- 最小可行版本（MVP）方案
- 3 周实施计划

---

## 🚀 AI Agent 执行流程

```
用户：帮我配置并运行 VoxFlow 项目

AI Agent 执行：

[1/5] 运行预检查
      python agents/preflight_check.py
      ✅ Python 3.11+, FFmpeg, Git 已安装

[2/5] 引导用户设置 API Key
      询问：请提供 RunningHub API Key
      用户：rh-xxxxx
      设置：$env:RUNNINGHUB_API_KEY = "rh-xxxxx"

[3/5] 自动配置
      python agents/auto_setup.py
      ✅ config.local.toml 已生成
      ✅ 依赖已安装
      ✅ 健康检查通过

[4/5] 运行 Demo（3 个镜头）
      scripts/voxflow.ps1 run --project demo --limit 3
      ✅ 生成 3 个镜头（约 2-3 分钟）

[5/5] 展示结果
      关键帧：projects/demo/images/
      视频片段：projects/demo/clips/
      预览视频：projects/demo/final/
```

---

## 🔑 核心设计原则

### 1. 零手动配置
- ❌ 不需要手动编辑 TOML 文件
- ✅ 所有配置通过脚本自动生成

### 2. 智能路径检测
- 自动查找 whiteboard 项目（如果有 WHITEBOARD_ROOT 环境变量）
- 自动查找 vox-director skill（~/.codex/skills 或 ~/.claude/skills）
- 找不到外部依赖时优雅降级，不报错

### 3. 友好的错误提示
```
❌ FFmpeg 未安装

安装方法：
  Windows: winget install ffmpeg
  Mac:     brew install ffmpeg
  Linux:   sudo apt install ffmpeg
```

### 4. 快速验证
- `--limit 3` 只生成 3 个镜头
- 2-3 分钟内完成，立即看到效果
- 避免用户误触大批量任务

---

## 📊 对比：优化前 vs 优化后

| 步骤 | 优化前 | 优化后 |
|------|--------|--------|
| 克隆仓库 | ✅ | ✅ |
| 安装依赖 | 手动 pip install | ✅ 自动 |
| 创建配置 | 复制 example，手动编辑 | ✅ 自动生成 |
| 填写路径 | whiteboard_root, vox_director_root | ✅ 自动检测 |
| 设置 BGM | 手动填写绝对路径 | ✅ 可选，自动查找 |
| 设置 API Key | 手动写入配置文件 | ✅ 环境变量 |
| 验证配置 | 手动运行 doctor | ✅ 自动检查 |
| 首次运行 | 不知道用什么参数 | ✅ 自动运行 --limit 3 |
| **总时间** | **30+ 分钟** | **5 分钟** |

---

## 🛡️ 安全保护

1. **API Key 永远不写入文件**
   - 只通过环境变量传递
   - 日志中只显示前 8 位

2. **不复制 whiteboard 的密钥**
   - 只复用其适配器代码
   - 不访问其配置文件

3. **自动 .gitignore**
   - config.local.toml
   - .env
   - projects/

---

## 🌟 支持的 AI Agent 平台

- ✅ **Claude Code** (Anthropic)
- ✅ **Codex** (GitHub Copilot X)
- ✅ **Workbuddy**
- ✅ **Cursor**
- ✅ 任何支持 Python 脚本执行和文件操作的 AI 助手

---

## 📝 Git 提交记录

### Commit 1: README 重设计
```
docs: redesign README with visual showcase and improved information architecture

- Add 4 new SVG assets: hero-redesign, showcase, flow-simple, features
- Include real project demos (drinking culture, watermelon, subway map)
- Reorder content: proof-first, then explanation, then configuration
```

### Commit 2: AI Agent 自动化
```
feat: add AI Agent automation for one-click setup

- Add agents/preflight_check.py: validate Python/FFmpeg/Git
- Add agents/auto_setup.py: auto-generate config, install deps, run doctor
- Update AGENTS.md: complete AI Agent operation guide
- Add docs/OPENSOURCE_ROADMAP.md: open-source optimization roadmap

AI Agent can now:
1. Run preflight check automatically
2. Guide user to set RUNNINGHUB_API_KEY
3. Generate config.local.toml with smart path detection
4. Install dependencies and create project directories
5. Run demo with --limit 3 for quick validation

Zero manual TOML editing required - just provide API key.
```

---

## 🚀 下一步建议

如果你现在推送到 GitHub：

```powershell
git push origin main
```

用户就可以直接用 AI Agent 一键部署了！

**测试方法**：
1. 在另一台电脑上克隆仓库
2. 告诉 Claude Code / Codex：
   > "帮我配置并运行这个项目，我的 RunningHub Key 是 rh-xxxxx"
3. AI Agent 会自动执行 5 步流程
4. 5 分钟内看到生成的视频

---

## 💡 未来可选优化（不改核心逻辑）

参考 `docs/OPENSOURCE_ROADMAP.md`：

1. **内置 whiteboard 适配器**（复制代码到 src/voxflow/adapters/）
2. **Docker 镜像**（一行命令运行）
3. **预设配置模板**（quick-start.toml, cost-optimized.toml）
4. **费用估算命令**（voxflow estimate --project demo）

这些都不需要改分镜、提示词、合成等核心逻辑。
