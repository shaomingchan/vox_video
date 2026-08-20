# VoxFlow 内置适配器

这个目录包含不依赖 whiteboard 项目的内置适配器。

## 当前状态

- ⚠️  `__init__.py` - 图片生成适配器（占位实现）
- ⚠️  `tts_builtin.py` - TTS 适配器（占位实现）

## 使用方式

### 方式 1：使用 whiteboard 项目（推荐）

如果你有 whiteboard 项目的访问权限，在 `config.local.toml` 中配置：

```toml
[paths]
whiteboard_root = "D:/path/to/whiteboard"
```

### 方式 2：使用内置适配器（开发中）

未来版本将支持直接使用 OpenAI、Replicate 等 API，无需 whiteboard 项目。

```bash
export OPENAI_API_KEY="sk-..."
# VoxFlow 将自动使用 OpenAI DALL-E 和 TTS
```

## 贡献

如果你想贡献内置适配器的实现，欢迎提交 PR：

1. 实现 `generate_image_builtin` 函数
2. 实现 `generate_tts_builtin` 函数
3. 添加对应的测试
4. 更新文档

参考 `whiteboard` 项目的接口规范。
