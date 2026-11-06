<div align="center">

<img src="logo.png" alt="astrbot_plugin_voice_input" width="128" height="128" />

# 语音输入识别（astrbot_plugin_voice_input）

**只判断"这条消息是不是语音发来的"，把结论交给别人。**

[![简体中文](https://img.shields.io/badge/文档-简体中文-blue)](README.md)
[![English](https://img.shields.io/badge/docs-English-blue)](README.en.md)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.27.3-blue)](https://astrbot.app)
[![version](https://img.shields.io/badge/version-1.0.1-blue)](metadata.yaml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**简体中文** ｜ [English](README.en.md)

</div>

---

## 它做什么

AstrBot 在预处理阶段就会做语音转文字（STT），并把消息链里的 `Record` 组件**原地替换**成 `Plain`。
等插件拿到消息时，语音痕迹已经没了 —— 于是"用户刚才是发语音还是打字"这个信息就丢了。

本插件把这条信息捡回来，写进事件：

```python
event.get_extra("voice_input")  # True = 语音，False = 文字
```

## 它不做什么

| | |
| --- | --- |
| ❌ 不决定"要不要用语音回复" | 那是**你的回复策略**。想实现可以照抄 [`examples/`](examples/) |
| ❌ 不改消息内容、不拦截消息、不改变发送行为 | 只读信号 + 写一个 `extra` |
| ❌ 不内置 TTS | 用 AstrBot 自带 TTS 还是第三方插件，由你决定 |

**默认安装后行为完全不变**，只有别的插件（或你打开 `inject_prompt`）才会用到这个标志。

## 安装

**插件市场**：在 AstrBot 管理面板 →「插件」→「插件市场」搜索「语音输入识别」。

**手动**：把本目录放到 `data/plugins/astrbot_plugin_voice_input/`，重启或在 WebUI 重载插件。

**压缩包**：WebUI「插件」页上传 zip（压缩包内只需一层 `astrbot_plugin_voice_input/` 目录）。

## 兼容性

| 项 | 说明 |
| --- | --- |
| AstrBot | **>= 4.27.3**（判定依赖该版本引入的 `_temporary_local_files`；更早版本只能在 STT 关闭时识别） |
| 平台 | `aiocqhttp`（OneBot v11 / NapCat / LLOneBot 等）与 `qq_official`（QQ 官方机器人）均已实测；其它平台退化为“临时音频文件后缀”判定，未经测试 |
| STT | **不需要开启**。检测独立于 STT；但 AI 要读懂语音内容仍需 STT |

## 快速验证

装好后发一条语音、再发一条文字，日志里会各出现一行：

```
[voice_input] 本轮消息判定为语音输入
[voice_input] 本轮消息判定为文字输入
```

想看到三个信号的具体取值，把插件配置里的 `verbose_log` 打开，并把日志级别调到 `DEBUG`。

## 在别的插件里怎么用

`voice_input` 是普通的 `extra`，任何 `event` 都能读。**读取方的 `priority` 要比 100 小**（AstrBot 里数值大的 handler 先执行，本插件是 100）。

```python
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star


class MyVoicePolicy(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

    @filter.on_llm_request(priority=50)  # < 100：确保 voice_input 已经写好
    async def on_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> None:
        if not event.get_extra("voice_input"):
            return
        req.system_prompt += "用户这条消息是语音发来的，请用语音回复。"
```

命令类插件（不走 LLM）在 `on_decorating_result` 里同样能读到这个标志 —— 本插件在两个钩子里都会写。

两个**完整可跑**的示例见 [`examples/`](examples/)：

| 示例 | 效果 | 前置 |
| --- | --- | --- |
| [`01_builtin_tts`](examples/01_builtin_tts/) | 发语音 → 用 **AstrBot 自带 TTS** 回语音说"我看得出你这条是语音"；发文字 → 回文字 | 配一个 TTS 提供商（推荐小米 MiMo，有免费额度） |
| [`02_clone_tts_prompt`](examples/02_clone_tts_prompt/) | 发语音 → 用**克隆音色**回语音 | 安装音色克隆插件 `astrbot_plugin_clonetts` |

## 配置

| 项 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `inject_prompt` | bool | `false` | 检测到语音时，往系统提示词追加 `prompt_text`。**这是可选策略，不是插件的本职** |
| `prompt_text` | text | 见下 | 仅在 `inject_prompt` 打开时生效。默认文案不点名任何 TTS 插件 |
| `verbose_log` | bool | `false` | 把 has_record / 临时文件 / raw_signal 三个信号打到 debug 日志 |

默认文案：

> 【语音输入】用户这条消息是语音发来的，请用语音回复。如果当前没有可用的语音合成能力，就用文字回复并说明原因。

## 原理

三条信号，任一命中即为语音；能拿到平台原始消息段时以它为准：

| 信号 | 来源 | 说明 |
| --- | --- | --- |
| A 残留 `Record` | `event.get_messages()` | STT 关闭或失败时才成立 |
| B 原始消息段 | OneBot：`raw_message.message` 含 `type == "record"`；QQ 官方：`raw_message.attachments` 里 `content_type` 以 `voice` 开头（或音频文件名） | 只看“本条消息自己”，被引用的语音不算 |
| C 临时音频后缀 | `event._temporary_local_files` | 预处理的兜底依据（图片也会登记，故按后缀过滤） |

判定逻辑本身在 [`detection.py`](detection.py)，是不导入 `astrbot` 的纯函数。

## 已知限制

1. 判定依赖 AstrBot 的 `_temporary_local_files`（>= 4.27.3）。属性缺失时插件会打一条 warning 而不是静默失效。
2. 在**拿不到原始消息**的平台（既不是 OneBot v11，也不是 QQ 官方）上，若 STT 开启，一条"文字消息引用了一条语音"会被判为语音输入 —— 因为临时文件里确实有那条语音的音频。想要准，就在 `detection.py` 里给这个平台补一个 `raw_voice_signal()` 分支。
3. 只影响 LLM 请求与发送前钩子，不影响消息内容本身，也不保证在流式输出下时序正确。
4. 插件不产生音频。能不能真的发出语音，取决于你配置的 TTS 能力。

## 排错

- 日志一直没有 `[voice_input]` 行 → 确认 AstrBot 版本 >= 4.27.3、插件已启用。
- 判定永远为 `False` → 打开 `verbose_log`，看是哪个信号没命中；若三个信号都空，多半是平台在预处理前就没把语音交给 AstrBot。
- 发语音却回文字 → 检查 `inject_prompt` 是否打开、以及 TTS 插件/提供商是否可用（见示例 README）。

## 开发

```bash
pip install pytest pyyaml packaging ruff
ruff check . && ruff format --check .
pytest
```

测试覆盖纯函数判定与发布元数据一致性（版本号语义化、`repo` 可访问性字段、配置项与代码对齐、不再使用废弃的 `@register`），**不需要安装 AstrBot**。

## 许可

[MIT](LICENSE) © 2026 Lin-Ruipeng
