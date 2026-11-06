# 强制语音回复下沉到主插件，用 hook 做确定性转换

**Status: Accepted**（supersedes [ADR 0001](0001-detect-only-expose-flag.md)）

## Context

ADR 0001 选择「只暴露输入模态，不替使用者决定回复方式」，并把「检测 + 强制语音回复」列为被否决的选项。
当时的顾虑是：要写死某个 TTS 插件的工具名，且对不想语音回复的人是意外行为。

实测后（issue #1）这些顾虑有了更准确的答案：

- 靠 `inject_prompt` 往系统提示词里追加「请用语音回复」，执行主体仍然是模型：
  可能不调用 TTS 工具、调用了但参数异常、长上下文下遵循率下降。结果是概率性的，不是「语音进 → 语音出」。
- 「意外行为」可以用默认关闭 + 显式配置解决，不需要把能力整个排除。
- 同时装 `astrbot_plugin_clonetts` 时，它也在 `on_decorating_result` 里按自己的概率转语音。
  两套抽签器并存，同一句话可能被**合成两次**：两次 TTS 调用、两次费用，最终只发一条，前一次白花。

检测层的 `qq_official`「文字引用语音」误判已在 2.0.0 修复：优先读平台原始消息的顶层
`attachments`，被引用语音在 `msg_elements` 里，不计入本条消息。真机实测确认判为文字输入，
不属于本 ADR 的范围。

## Decision

在主插件内置**强制语音回复**：回复已生成、尚未投递时（`on_decorating_result`），
把纯文本回复整体换成一条 `Record`。是否转换由 `voice_reply_probability`（0.0–1.0，默认 0.0）抽签决定，
且**只对语音输入的消息抽签**；文字消息永远不转。

同时移除 `inject_prompt` / `prompt_text`（软提示路径），升级为 2.0.0。

### 与概率型 TTS 插件共存：独占

检测到 `astrbot_plugin_clonetts` 时，语音消息的回复模态**只由本插件决定**，避免重复合成。
实现是三件套，缺一不可：

1. **钩子顺序**：本插件 `on_decorating_result` 的 priority 是 100，clonetts v3.0.4 未指定（默认 0），
   AstrBot 按 priority 降序执行，所以本插件先决定。
2. **转换后的消息链**：写成 `Record(text="")`。clonetts 用 `hasattr(component, "text")` 收集文本，
   空串让它走自身的「文本为空，跳过」分支；若写成 `text=None`，它会在 `"".join([None])` 抛异常。
3. **没抽中时**：把 `result.result_content_type` 降级为 `GENERAL_RESULT`，
   让 clonetts 与内置 TTS 的 `is_llm_result()` 检查失败，保持文字。

`voice_reply_probability = 0.0` 是唯一的例外：完全关闭、不介入、不降级，语音消息交回 clonetts 的概率。

### TTS 来源

优先用当前会话的框架 TTS provider。没有时回退到复用 clonetts 的 `api_key` / `voice_type`
直连火山引擎 v3 流式接口 —— 因为 clonetts 注册的是 LLM 工具而不是 `TTSProvider`，
只装它时框架层拿不到任何 TTS 能力，没有这条回退，`voice_reply_probability = 1.0` 也只会回文字。

## Considered Options

- **只做 examples 里的示例**：用户需要装两个插件才有开关，issue 的「一个开关」诉求落空。
- **只靠 `extra` 标记去重**（参考实现的做法）：`astrbot_plugin_clonetts` 不读别人的 extra，防不住重复合成。
- **`event.stop_event()` 阻止后续处理器**：会终止后续 pipeline stage，
  响应阶段被跳过，消息根本发不出去（`pipeline/scheduler.py`）。
- **改 `event.plugins_name` 过滤掉 clonetts**：钩子列表在进入 `ResultDecorateStage` 时就取好了，改它对本轮无效。
- **临时改 clonetts 实例的 `tts_probability` 再恢复**：跨事件竞态，恢复失败会永久禁用对方。
- **给 `Record.text` 填原文**（上游内置 TTS 的做法）：会触发 clonetts 的第二次合成，正是要避免的。
- **通用的自定义 HTTP TTS 接口**：配置面和出错面都翻倍；先把已经跑通的那条链路固化成回退。

## Consequences

- 插件定位从「只检测」变成「检测 + 一个可选的确定性策略」。默认（0.0）行为与 1.0.x 完全一致。
- 与 clonetts 的耦合落在**实现细节**上（依赖它用 `hasattr(c, "text")` 取文本）。
  文档记录实测版本 v3.0.4；clonetts 换实现方式后需要重新验证「不会重复合成」。
- 独占降级会让「没抽中」的那条消息跳过内置 TTS，以及「仅 LLM 结果」的分段回复。
- 流式输出不转换（与内置 TTS 一致）。
- 新增一条网络链路（火山回退），多一个失败面；失败时一律保留文字。
- `Record.text` 写成空串，意味着某些平台在语音发送失败时拿不到文字回退文案。
