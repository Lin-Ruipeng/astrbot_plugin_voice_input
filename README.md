<div align="center">

<img src="logo.png" alt="astrbot_plugin_voice_input" width="128" height="128" />

# 语音输入识别（astrbot_plugin_voice_input）

**判断"这条消息是不是语音发来的"。默认只把结论交给你；打开开关后，语音消息的回复会变成语音。**

[![简体中文](https://img.shields.io/badge/文档-简体中文-blue)](README.md)
[![English](https://img.shields.io/badge/docs-English-blue)](README.en.md)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.27.3-blue)](https://astrbot.app)
[![version](https://img.shields.io/badge/version-2.0.0-blue)](metadata.yaml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**简体中文** ｜ [English](README.en.md)

</div>

---

## 它做什么

AstrBot 在预处理阶段就会做语音转文字（STT），并把消息链里的 `Record` 组件**原地替换**成 `Plain`。
等插件拿到消息时，语音痕迹已经没了 —— 于是"用户刚才是发语音还是打字"这个信息就丢了。

本插件做两件事：

1. **判断**：把这条信息捡回来，写进事件，任何插件都能读：

   ```python
   event.get_extra("voice_input")  # True = 语音，False = 文字
   ```

2. **可选的确定性转换**：打开 `voice_reply_probability` 后，语音消息的回复在投递前
   被换成一条语音。`1.0` = 每条语音消息都回语音，`0.0` = 关闭（默认）。

## 它不做什么

| | |
| --- | --- |
| ❌ 默认不改任何回复 | 装完不配置，行为与"只检测"完全一样 |
| ❌ 不改文字消息的回复 | 只对 `voice_input=True` 的消息抽签，打字进来的一律不动 |
| ❌ 不内置 TTS 厂商 | 优先用**你配置的框架 TTS 提供商**；没有时复用 `astrbot_plugin_clonetts` 的火山配置（回退） |
| ❌ 不替你选音色 | 音色由你的 TTS 提供商 / 克隆插件决定 |

## 兼容性

| 项 | 说明 |
| --- | --- |
| AstrBot | **>= 4.27.3**（判定依赖该版本引入的 `_temporary_local_files`） |
| **平台** | **只有 `qq_official`（QQ 官方机器人）实测通过。** `aiocqhttp`（OneBot v11 / NapCat / LLOneBot）保留了代码路径但**未实测**；其它平台退化为"临时音频文件后缀"判定，同样未测试 |
| STT | **不需要开启**。检测独立于 STT；但 AI 要读懂语音内容仍需 STT |

### 实测环境（复现条件）

下表是当前跑通流程的环境，遇到问题时请先对照：

| 项 | 值 |
| --- | --- |
| 平台 | `qq_official` |
| AstrBot | 4.29.4（仓库 pyproject；安装元数据 4.28.2） |
| 音色克隆 | `astrbot_plugin_clonetts` **v3.0.4** |
| STT | `mimo_stt_api`（`mimo-v2.5-asr`） |
| 系统 | Debian 13 / Python 3.12 / Docker 容器 |
| 本插件 | 2.0.0 |

## 快速验证

装好后发一条语音、再发一条文字，日志里会各出现一行：

```
[voice_input] 本轮消息判定为语音输入
[voice_input] 本轮消息判定为文字输入
```

打开 `voice_reply_probability` 后，初始化时还会多一行：

```
[voice_reply] 强制语音回复：概率 1.00；文本上限：300 字
```

想看到三个信号的具体取值与每次抽签结果，把插件配置里的 `verbose_log` 打开，并把日志级别调到 `DEBUG`。

## 配置

两项都可以在 WebUI「插件配置」里直接改，保存后重载插件生效。

| 项 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `voice_reply_probability` | float | `0.0` | `0.0` = 关闭；`1.0` = 每条语音消息都回语音；`0.5` = 一半。只对语音输入生效 |
| `voice_reply_max_chars` | int | `300` | 回复文本超过这个字数就不转语音；`0` = 不限制。太长时 TTS 又慢又贵，所以默认给了上限 |
| `verbose_log` | bool | `false` | 把 has_record / 临时文件 / raw_signal / 抽签结果打到 debug 日志 |

代码对两个数值配置都做了防御：概率钳到 `0.0–1.0`（误填 `80` 这种百分数会 warning 并按 `1.0` 处理），
字数上限的负数按 `0`（不限制）处理。

### 从 1.0.x 升级到 2.0.0

2.0.0 **移除了** `inject_prompt` / `prompt_text`：让模型"自己决定要不要调 TTS 工具"的思路被实测否定。

| 1.0.x 的配置 | 2.0.0 怎么做 |
| --- | --- |
| `inject_prompt: true` | 改成 `voice_reply_probability: 1.0`。效果从"靠模型自觉"变成插件确定性转换 |
| `inject_prompt: false`（默认） | 不用改，默认就是 `0.0` |
| `prompt_text: ...` | 删除。软提示路径已移除；想在提示词里提一句仍可由你自己的插件做 |
| 依赖 `examples/02_clone_tts_prompt` 的注入 | 换成主插件开关；该示例保留为对照 |

旧配置文件里残留的 `inject_prompt` / `prompt_text` 会被忽略，不会报错，可以手动删掉。

## 语音进 → 语音出 是怎么实现的

转换发生在 `on_decorating_result`：回复内容已生成、尚未投递。

1. 只对 `voice_input=True` 的消息抽签。**同一个事件只抽一次**，抽签值缓存在事件上，
   所以 agent 多轮调用不会出现"前半段语音、后半段文字"。
2. 跳过这些情况：已经有别的插件转过了（链里已有 `Record`）、命令 / `yield` 类结果、
   流式输出、带图片等非文本组件、没有可朗读文本、超过 `voice_reply_max_chars`。
3. 合成音频：先问**当前会话的框架 TTS 提供商**；没有（或失败）就回退到
   **复用 `astrbot_plugin_clonetts` 的 `api_key` / `voice_type` 直连火山引擎 v3**。
4. 把整条消息链换成一条 `Record`，失败则保留文字。

为什么不用"往系统提示词里加一句请用语音回复"：执行主体是模型，可能不调工具、调了但失败，
长上下文下遵循率还会下降。回复已经生成之后再替换，才是确定性的。

## 和 astrbot_plugin_clonetts 一起用

`astrbot_plugin_clonetts` 也在 `on_decorating_result` 里按自己的概率（`tts_probability`，默认 80）
把回复转成语音，但它**不区分输入模态**。两个插件同时开着时，如果不做隔离，同一句话可能被
**合成两次**（两次 TTS 调用、两次费用，最终只发一条，前一次白花）。

本插件的处理是：**检测到 clonetts 时，语音消息由本插件独占**，文字消息仍交给 clonetts 的概率机制。
实现是三件套，缺一不可：

| 手段 | 作用 |
| --- | --- |
| 本插件 `on_decorating_result` 的 priority 是 100，clonetts 是默认的 0 | 本插件先执行，先决定语音消息的模态 |
| 转换后 `Record.text` 写成空串 | clonetts 用 `hasattr(component, "text")` 收集文本，空串会让它走"文本为空，跳过"分支 |
| 没转成时把结果类型降级为普通结果 | clonetts 与 AstrBot 内置 TTS 的 `is_llm_result()` 检查失败，都不会再合成一次 |

场景矩阵（只针对**语音消息**）：

| `voice_reply_probability` | 是否装 clonetts | 结果 |
| --- | --- | --- |
| `0.0`（默认） | 任意 | 本插件完全不介入，语音消息交给 clonetts 自己的概率 |
| `0 < p < 1`，抽中 | 任意 | 本插件合成，clonetts 取不到文本，跳过 |
| `0 < p < 1`，未抽中 | 装了 | 本插件标记独占，clonetts 与内置 TTS 都不转，保持文字 |
| `0 < p < 1`，未抽中 | 没装 | 保持文字（不降级；其它插件抢不抢无所谓） |
| `1.0` | 任意 | 语音消息必由本插件转语音；clonetts 的概率只对文字消息生效 |

**代价**：被独占的那条消息不再走 AstrBot 内置 TTS，也不再走"仅 LLM 结果"的分段回复。
内容安全在钩子之前已完成，回复前缀 / @ / 引用 / 文本转图片不受影响。

这依赖 clonetts 的具体实现（用 `hasattr(c, "text")` 取文本），实测版本是 **v3.0.4**；
换版本后请重新验证"一句话不会被合成两次"。

## 写自己的策略（其它插件怎么用）

`voice_input` 是普通的 `extra`，任何 `event` 都能读。**读取方的 `priority` 要比 100 小**
（AstrBot 里数值大的 handler 先执行，本插件是 100）。

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
        req.system_prompt += "用户这条消息是语音发来的，回答时可以更简短些。"
```

命令类插件（不走 LLM）在 `on_decorating_result` 里同样能读到这个标志 —— 本插件在两个钩子里都会写。

两个**完整可跑**的示例见 [`examples/`](examples/)：

| 示例 | 效果 | 前置 |
| --- | --- | --- |
| [`01_builtin_tts`](examples/01_builtin_tts/) | 发语音 → 用 **AstrBot 自带 TTS** 回语音；发文字 → 回文字 | 配一个 TTS 提供商（推荐小米 MiMo） |
| [`02_clone_tts_prompt`](examples/02_clone_tts_prompt/) | 发语音 → 用**克隆音色**回语音（靠提示词，不稳定） | 安装 `astrbot_plugin_clonetts` |

2.0.0 起主插件自带同款能力，这两个示例更适合当作"自己写策略"的参考。

## 原理

三条信号，任一命中即为语音；能拿到平台原始消息段时以它为准：

| 信号 | 来源 | 说明 |
| --- | --- | --- |
| A 残留 `Record` | `event.get_messages()` | STT 关闭或失败时才成立 |
| B 原始消息段 | OneBot：`raw_message.message` 含 `type == "record"`；QQ 官方：`raw_message.attachments` 里 `content_type` 以 `voice` 开头（或音频文件名） | 只看"本条消息自己"，被引用的语音不算 |
| C 临时音频后缀 | `event._temporary_local_files` | 预处理的兜底依据（图片也会登记，故按后缀过滤） |

判定逻辑本身在 [`detection.py`](detection.py)，是不导入 `astrbot` 的纯函数；
回复策略的抽签与跳过规则在 [`reply_policy.py`](reply_policy.py)，同样可脱机单测。

## 已知问题与限制

**已知问题（暂未修复）：`qq_official` 下「文字引用语音」仍可能被误判为语音输入。**

用文字消息引用一条语音时，这条消息本身是文字，但被引用的语音也会被预处理转成 wav 并登记到事件上。
2.0.0 的检测层会优先读 QQ 官方消息的**顶层** `attachments`（被引用的语音在 `msg_elements` 里，
不计入），但实测中这个信号并不总能拿到，仍会回落到临时音频文件判定。**目前没有可靠修复**
（issue #1），先记录为已知问题。后果：如果你打开了 `voice_reply_probability`，这条文字消息可能被回一句语音。

其它限制：

1. 判定依赖 AstrBot 的 `_temporary_local_files`（>= 4.27.3）。属性缺失时插件会打一条 warning 而不是静默失效。
2. 平台上只有 `qq_official` 实测通过；`aiocqhttp` 代码保留但未实测，其它平台更未测试。
3. **流式输出下不会转换语音**（AstrBot 内置 TTS 同样跳过流式）；需要强制语音回复请先关闭流式输出。
4. 命令 / `yield` 类结果与带图片等非纯文本的消息链保持文字，不会转换。
5. 为了让概率型 TTS 插件干净跳过，`Record.text` 写成空串。某些平台在语音发送失败时会拿它做文字回退，
   这时回退文案为空。
6. 回退到火山 v3 需要 `astrbot_plugin_clonetts` 的配置里有 `api_key` / `voice_type`；
   都没有时只回文字并打一条 warning。
7. 插件本身不产生音频。能不能真的发出语音，取决于框架 TTS 提供商或 clonetts 的火山配置。

## 排错

- 日志一直没有 `[voice_input]` 行 → 确认 AstrBot 版本 >= 4.27.3、插件已启用。
- 判定永远为 `False` → 打开 `verbose_log`，看是哪个信号没命中；若三个信号都空，多半是平台在预处理前就没把语音交给 AstrBot。
- 发语音却回文字 → 看 `[voice_reply]` 日志：`概率 0`？抽签没中？文本超长？没有可用 TTS？流式输出？
- 收到两条语音 / 被合成两次 → 确认 `astrbot_plugin_clonetts` 版本是 v3.0.4，且本插件 priority 仍是 100。
- 想精确控制比例 → 装了 clonetts 时 `voice_reply_probability` 的中间值也能精确生效（未抽中的会被独占降级），
  此时文字消息仍按 clonetts 的概率出语音。

## 开发

```bash
pip install pytest pyyaml packaging ruff
ruff check . && ruff format --check .
pytest
```

测试覆盖纯函数判定（检测信号、概率钳值、抽签、跳过规则、火山流式解析）与发布元数据一致性
（版本号语义化、`repo` 字段、配置项与代码对齐、不再使用废弃的 `@register`），**不需要安装 AstrBot**。

## 许可

[MIT](LICENSE) © 2026 Lin-Ruipeng
