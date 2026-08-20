# VoxFlow 开源化优化方案

## 当前痛点分析

### 1. 配置复杂度
- ❌ 需要手动编辑 TOML 文件（whiteboard_root, vox_director_root）
- ❌ 外部依赖路径硬编码
- ❌ 环境变量和配置文件混用
- ❌ 新用户不知道 whiteboard 和 vox-director 是什么

### 2. 依赖不透明
- ❌ image2 和 TTS 适配器藏在 whiteboard 项目里
- ❌ RunningHub 工作流版本和节点映射不可见
- ❌ 用户需要先有另一个项目才能运行这个项目

### 3. 上手门槛高
- ❌ 没有零配置 demo
- ❌ 第一次运行必须有真实 API Key
- ❌ 错误信息不友好（"找不到 whiteboard_root"）

---

## 🎯 优化方向（按优先级）

### 优先级 1：内置 Provider 系统 ⭐⭐⭐⭐⭐

**目标**：用户无需外部项目即可运行

**方案**：
```
src/voxflow/providers/
├── __init__.py
├── base.py                    # Provider 接口定义
├── image_providers/
│   ├── whiteboard_image2.py   # 当前的 whiteboard 适配器
│   ├── replicate_flux.py      # 新增：Replicate FLUX
│   ├── openai_dalle.py        # 新增：OpenAI DALL-E
│   └── local_comfyui.py       # 新增：本地 ComfyUI
├── tts_providers/
│   ├── whiteboard_tts.py
│   ├── openai_tts.py
│   ├── azure_tts.py
│   └── elevenlabs.py
└── video_providers/
    ├── runninghub.py          # 当前实现
    ├── replicate_video.py     # 备选
    └── local_comfyui.py       # 本地方案
```

**配置简化**：
```toml
[providers]
image = "openai-dalle"         # 或 "whiteboard", "replicate-flux"
tts = "openai-tts"             # 或 "whiteboard", "azure"
video = "runninghub"           # 或 "replicate"

[providers.openai-dalle]
# API key 从环境变量读取
model = "dall-e-3"

[providers.openai-tts]
voice = "alloy"
```

**收益**：
- ✅ 新用户可以用 OpenAI API 直接跑通（无需 whiteboard）
- ✅ 支持多种服务商，降低成本
- ✅ 配置从 2 个外部路径简化为 1 个 provider 名称

---

### 优先级 2：交互式配置向导 ⭐⭐⭐⭐⭐

**目标**：首次运行自动引导配置

**方案**：
```powershell
scripts/voxflow.ps1 setup
```

**流程**：
```
VoxFlow 配置向导
=================

1. 选择 image 生成服务：
   [1] OpenAI DALL-E（推荐新手）
   [2] Replicate FLUX
   [3] Whiteboard image2（需要外部项目）
   [4] 本地 ComfyUI
> 输入选项：1

2. 请输入 OpenAI API Key（或按 Enter 从 OPENAI_API_KEY 环境变量读取）：
> sk-...

3. 选择 TTS 服务：
   [1] OpenAI TTS（推荐，与 image 共用 Key）
   [2] Azure TTS
   [3] ElevenLabs
> 输入选项：1

4. 选择 video 生成服务：
   [1] RunningHub（需要单独注册）
   [2] Replicate
> 输入选项：1

5. 请输入 RunningHub API Key：
> rh-...

6. 选择默认画面比例：
   [1] 16:9 横屏
   [2] 9:16 竖屏
> 输入选项：2

✅ 配置已保存到 config.local.toml
✅ 运行 'scripts/voxflow.ps1 doctor' 验证配置
```

**收益**：
- ✅ 零手动编辑 TOML
- ✅ 实时验证 API Key 可用性
- ✅ 自动创建 .env 文件
- ✅ 友好的错误提示

---

### 优先级 3：Mock Mode（零成本试跑）⭐⭐⭐⭐

**目标**：用户无 API Key 也能体验完整流程

**方案**：
```powershell
scripts/voxflow.ps1 run --project demo --script examples/demo-script.txt --mock
```

**实现**：
```python
class MockImageProvider:
    def generate(self, prompt, aspect):
        # 返回预生成的占位图片（红色背景 + 提示词文字）
        return create_placeholder_image(prompt, aspect)

class MockVideoProvider:
    def generate(self, image_path, prompt):
        # 返回静态图片的 5 秒循环（带简单缩放动画）
        return create_static_video(image_path, duration=5)

class MockTTSProvider:
    def synthesize(self, text):
        # 返回无声音频或文本转语音的开源库（pyttsx3）
        return create_silent_audio(len(text) * 0.1)
```

**收益**：
- ✅ 新用户可以立即看到完整流程
- ✅ 开发者可以快速测试分镜和合成逻辑
- ✅ 降低试错成本（不会误触付费 API）

---

### 优先级 4：预设配置模板 ⭐⭐⭐⭐

**目标**：一键切换常见场景

**方案**：
```
configs/
├── quick-start.toml           # OpenAI + RunningHub，最简配置
├── cost-optimized.toml        # Replicate + 开源 TTS
├── high-quality.toml          # FLUX + ElevenLabs + RunningHub Plus
├── local-offline.toml         # ComfyUI 全本地
└── whiteboard-legacy.toml     # 当前配置（兼容）
```

**使用**：
```powershell
scripts/voxflow.ps1 setup --template quick-start
```

**收益**：
- ✅ 用户只需选场景，不需理解所有参数
- ✅ 避免新手配错导致高成本

---

### 优先级 5：Docker 一键部署 ⭐⭐⭐

**目标**：无需本地 Python 环境

**方案**：
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY . .
RUN pip install -e .

ENV RUNNINGHUB_API_KEY=""
ENV OPENAI_API_KEY=""

ENTRYPOINT ["python", "-m", "voxflow.cli"]
```

**使用**：
```bash
docker run -v $(pwd)/projects:/app/projects \
  -e OPENAI_API_KEY=sk-... \
  -e RUNNINGHUB_API_KEY=rh-... \
  voxflow/voxflow:latest \
  run --project demo --script examples/demo-script.txt
```

**收益**：
- ✅ 跨平台一致性
- ✅ 无需手动安装 FFmpeg
- ✅ 适合 CI/CD 集成

---

### 优先级 6：Web UI（可选）⭐⭐

**目标**：非技术用户友好

**方案**：
```
streamlit run src/voxflow/webui.py
```

**功能**：
- 📝 粘贴逐字稿
- ⚙️ 可视化配置（下拉菜单选 provider）
- 📊 实时进度条（分镜 → 图片 → 视频 → 合成）
- 🎬 在线预览生成的视频
- 💾 一键下载 MP4 或 ChatCut 工程

**收益**：
- ✅ 适合内容团队批量使用
- ✅ 降低命令行门槛

---

## 📊 优先级总结

| 优化项 | 影响面 | 开发成本 | 推荐优先级 |
|--------|--------|----------|------------|
| Provider 系统 | 消除外部依赖 | 中等 | ⭐⭐⭐⭐⭐ |
| 配置向导 | 零手动配置 | 低 | ⭐⭐⭐⭐⭐ |
| Mock Mode | 零成本试跑 | 低 | ⭐⭐⭐⭐ |
| 预设模板 | 降低选择成本 | 低 | ⭐⭐⭐⭐ |
| Docker | 环境一致性 | 低 | ⭐⭐⭐ |
| Web UI | 非技术用户 | 高 | ⭐⭐ |

---

## 🎯 推荐实施路径（3周）

### Week 1：核心简化
1. ✅ Provider 接口抽象
2. ✅ 内置 OpenAI image/TTS provider
3. ✅ Mock provider（占位图+静态视频）
4. ✅ 交互式配置向导

### Week 2：体验优化
1. ✅ 预设配置模板（3-4个）
2. ✅ 改进错误提示（"找不到 OpenAI Key" 而非 "找不到 whiteboard"）
3. ✅ doctor 命令增强（检测 provider 连通性）
4. ✅ 完善文档（各 provider 配置示例）

### Week 3：部署优化
1. ✅ Docker 镜像 + docker-compose
2. ✅ GitHub Actions 示例（CI 自动生成视频）
3. ✅ 费用估算命令（`voxflow estimate --project demo`）
4. ✅ 视频示例库（10个不同主题的成片）

---

## 💡 不改变的部分（保持质量）

✅ **分镜算法**：句子拆分、时长估算、运镜规划保持不变
✅ **提示词模板**：纸张拼贴风格的核心提示词不变
✅ **合成逻辑**：FFmpeg 参数、响度标准化、字幕定位不变
✅ **缓存机制**：指纹计算、并发控制、批次确认不变

只是把**外部依赖解耦**，让用户**更容易配置和替换服务商**。

---

## 🔥 最小可行版本（MVP）

如果只有 3 天，先做这 3 件事：

1. **Provider 接口 + OpenAI 实现**（1天）
   - 让新用户用 OpenAI Key 直接跑通
2. **交互式配置向导**（1天）
   - 消除手动编辑 TOML
3. **Mock Mode**（1天）
   - 零成本演示完整流程

完成后，80% 的新用户可以在 5 分钟内跑出第一个视频。

