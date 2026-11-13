# 配置与共存

面向已经跑通基础配置、想知道"某个开关为什么必须这样设"的人。
只想快速用起来，看 [README](../README.md) 的「快速上手」；
想从头装一遍、或按清单逐项配一遍，看 [安装与配置](install.md)。

## AstrBot 的 TTS / STT 解析规则

本插件取 TTS 用的是：

```python
provider = await context.get_using_tts_provider_async(event.unified_msg_origin)
```

它在 `ProviderManager._resolve_using_provider()` 里的行为（v4.27.3 / v4.29.4 / master 一致）：

| 条件 | 结果 |
| --- | --- |
| `provider_tts_settings.enable == false` | **返回 `None`** |
| `provider_tts_settings.provider_id` 为空 | **返回 `None`** |
| 两者都满足，但 ID 找不到 | 回退到第一个 TTS provider |
| 两者都满足且找得到 | 返回 provider |

STT 同理（`provider_stt_settings.enable` / `provider_id`）。

**所以"在模型提供商里加了 TTS" ≠ "插件能用 TTS"**：必须在
「配置文件 → AI → 语音回复」里打开并选中默认模型。这也是旧版示例文档里最容易误导人的一句。

## 框架 TTS 的自动转换

`astrbot/core/pipeline/result_decorate/stage.py` 在插件钩子**之后**执行，条件是：

```
provider_tts_settings.enable
&& result.is_llm_result()
&& 会话级「启用 TTS」
&& random() <= provider_tts_settings.trigger_probability
&& tts_provider
```

且只转换 `len(text) > 1` 的 `Plain` 组件。由此得到两个实用结论：

1. **`TTS 触发概率` 必须设 `0`**，否则文字消息也会被框架 TTS 转成语音，
   和本插件"只有语音消息回语音"的语义冲突。
2. 本插件转换后链里是 `Record`（不是 `Plain`），框架 TTS 的循环会原样保留，**不会二次合成**。

### 三个容易踩的边界

- **流式输出必须关**：`STREAMING_RESULT` 会被框架 TTS 与本插件同时跳过。
- **会话级「启用 TTS」开关只影响框架 TTS**：本插件直接调 provider，不受它限制。
  想让某个会话完全不出语音，请把插件开关设 `0.0`。
- `dual_output`（开启 TTS 时同时输出语音和文字）只影响框架 TTS；本插件转换后只发语音。

## 四种典型配置

四种开关组合怎么配、Edge / 百炼 Cosy / MiMo / clonetts 怎么选，都是**操作**，
已搬到 [安装与配置](install.md#四种典型配置)（选型见 [TTS 提供商选型](install.md#tts-提供商选型)）。
本文只解释它们为什么必须这样设。

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
| 没转成时把结果类型降级为 `GENERAL_RESULT` | clonetts 与框架 TTS 的 `is_llm_result()` 检查失败，都不会再合成一次 |

场景矩阵（只针对**语音消息**）：

| `voice_reply_probability` | 是否装 clonetts | 结果 |
| --- | --- | --- |
| `0.0`（默认） | 任意 | 本插件完全不介入，语音消息交给 clonetts 自己的概率 |
| `0 < p < 1`，抽中 | 任意 | 本插件合成，clonetts 取不到文本，跳过 |
| `0 < p < 1`，未抽中 | 装了 | 本插件标记独占，clonetts 与框架 TTS 都不转，保持文字 |
| `0 < p < 1`，未抽中 | 没装 | 保持文字（不降级；其它插件抢不抢无所谓） |
| `1.0` | 任意 | 语音消息必由本插件转语音；clonetts 的概率只对文字消息生效 |

**代价**：被独占的那条消息不再走框架 TTS，也不再走"仅 LLM 结果"的分段回复。
内容安全在钩子之前已完成，回复前缀 / @ / 引用 / 文本转图片不受影响。

这依赖 clonetts 的具体实现（用 `hasattr(c, "text")` 取文本），实测版本是 **v3.0.4**；
换版本后请重新验证"一句话不会被合成两次"。

## TTS 来源与失败降级

合成按顺序尝试：

1. **当前会话的框架 TTS provider**（上一节的前置必须满足）。
2. 失败或没有 → **火山回退**：复用 `astrbot_plugin_clonetts` 配置里的 `api_key` / `voice_type`，
   直连火山引擎 v3 流式接口（`clonetts_tts.py`）。
3. 都失败 → 保留文字，打一条 warning。

火山回退需要 clonetts 已安装且配置里有 `api_key` / `voice_type`；都没有时只回文字。

## 字数上限与钳值

- `voice_reply_max_chars`（默认 `300`）：回复文本超过上限就不转语音；`0` = 不限制。
  太长时 TTS 又慢又贵，默认给了上限。
- `voice_reply_probability` 会被钳到 `0.0–1.0`；误填 `80` 会 warning 并按 `1.0` 处理。
- 字数上限的负数按 `0`（不限制）处理。

## 相关

- [安装与配置](install.md) —— 装、配、验证、回报的完整操作链
- [实现细节](internals.md) —— 三信号、hook 时序、独占实现、火山回退
- [自定义回复策略](custom-policy.md) —— 自己写 `on_decorating_result`
- [README](../README.md) —— 面向使用者的快速上手与配置表
