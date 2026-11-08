# 实现细节

面向想读懂代码、改判定逻辑或排查"为什么这条没转语音"的人。
只想知道怎么用，看 [README](../README.md)；只想知道怎么配，看 [配置与共存](configuration.md)。

## 目录与分层

| 文件 | 职责 | 能否脱机单测 |
| --- | --- | --- |
| `detection.py` | 三信号 → 一个布尔值 | ✅ 不导入 `astrbot` |
| `reply_policy.py` | 概率钳值、抽签、跳过规则、独占 claim | ✅ 不导入 `astrbot` |
| `clonetts_tts.py` | 火山引擎 v3 流式合成的 HTTP 与解析 | ✅ mock `aiohttp` |
| `main.py` | 钩子、配置读取、日志、与 AstrBot 的交互 | 依赖 AstrBot |

纯函数层刻意不导入 `astrbot`，这样判定逻辑可以脱离框架跑测试（`tests/`）。

## 检测：三条信号

| 信号 | 来源 | 说明 |
| --- | --- | --- |
| **A** 残留 `Record` | `event.get_messages()` | STT 关闭或失败时才成立 |
| **B** 平台原始消息 | OneBot：`raw_message.message` 里有 `type == "record"`；QQ 官方：`raw_message.attachments` 里 `content_type` 以 `voice` / `audio` / `silk` 开头（或音频文件名） | 只看"本条消息自己"，被引用的语音不算 |
| **C** 临时音频后缀 | `event._temporary_local_files` | 预处理的兜底依据（图片也会登记，故按后缀过滤） |

合并规则（`detection.detect_voice_input`）：

1. 能拿到平台原始消息（信号 B 有结论）→ **以 B 为准**，A 作为补充；
   此时忽略 C，所以"文字引用一条语音"不会被误判。
2. 拿不到原始消息 → A 命中即为语音；否则看 C 里是否有音频后缀。

`raw_voice_signal()` 返回 `True` / `False` / `None`：`None` 表示"这个平台的结构我们不会判断"，
调用方退回到 A + C。

QQ 官方只读**顶层** `attachments`：被引用的语音在 `msg_elements` 里，不计入本条消息。

## 钩子与时序

两个钩子的 `priority` 都是 **100**：

| 钩子 | 做什么 |
| --- | --- |
| `on_llm_request` | 计算并写入 `event.set_extra("voice_input", bool)`，供其它插件在请求 LLM 前读取 |
| `on_decorating_result` | 再写一次（命令类结果不走 `on_llm_request`），然后按概率决定要不要把回复换成语音 |

AstrBot 里**数值大的 handler 先执行**。所以：

- 想读 `voice_input` 的插件，`priority` 要 **< 100**；
- 想做回复装饰、又不想被本插件抢先的插件，`priority` 要 **> 100**（但要自己处理"链里已有 `Record`"）。

每个事件只打一条 `[voice_input]` info 日志（内部标记 `_voice_input_announced`）。

## 强制语音回复的决策顺序

`on_decorating_result` 里依次判断：

1. `voice_reply_probability <= 0` → 完全不介入（不转换、不降级）。
2. 没有结果 / 空链 → 返回。
3. 流式结果（`STREAMING_RESULT` / `STREAMING_FINISH`）→ 跳过并 warning 一次。
4. 链里已有 `Record` → 不重复转换。
5. 组装判定参数交给 `reply_policy.should_convert()`：必须是 LLM 结果、全是 `Plain`、
   有可读文本、未超过 `voice_reply_max_chars`、抽签命中。
6. 通过 → 合成音频，把整条链换成 `Record.fromFileSystem(path, text="")`。
7. 没通过 → 如果装了 clonetts，把 `result.result_content_type` 降级为 `GENERAL_RESULT`，
   让别的 TTS 插件不要再合成一次。

**抽签**在事件上是缓存的（`_voice_reply_roll`）：`probability >= 1.0` 直接视为 1.0，
否则 `random.random()` 只取一次。这样 agent 多轮调用不会出现"前半段语音、后半段文字"。

## 独占：为什么要三件套

见 [配置与共存](configuration.md#和-astrbot_plugin_clonetts-一起用)。
实现上的三个点缺一不可：

1. **钩子顺序**：本插件 priority 100，clonetts v3.0.4 是默认 0，所以本插件先决定。
2. **`Record.text = ""`**：clonetts 用 `hasattr(component, "text")` 收集文本，空串让它走
   "文本为空，跳过"分支；写 `None` 会在 `"".join([None])` 抛异常。
3. **没转成时降级 `GENERAL_RESULT`**：让 `result.is_llm_result()` 为 False，
   clonetts 与框架 TTS 都不会接手。

这依赖 clonetts 的具体实现，实测版本 **v3.0.4**；对方换实现后需要重新验证。

## TTS 合成路径

```
_force_voice_reply
  └─ _synthesize_voice
       ├─ _provider_audio        # context.get_using_tts_provider_async → provider.get_audio(text)
       └─ _clonetts_audio        # 框架没有 / 失败时：读 clonetts 配置 → 火山 v3 直连
```

- **框架 TTS**：`get_using_tts_provider_async(umo)` 的前置见 [配置与共存](configuration.md)。
  失败会打 `[voice_reply] 框架 TTS 合成失败，尝试火山回退`。
- **火山回退**：`clonetts_tts.config_path()` 定位 clonetts 的配置，`load_config()` 读
  `api_key` / `voice_type`，`synthesize()` 用 `aiohttp` 调 v3 流式接口，把音频写进
  `get_astrbot_temp_path()`。
- 两路都失败 → 保留文字，warning 一次（`_warned_missing_tts`）。

合成出的文件用 `event.track_temporary_local_file(path)` 登记，交给 AstrBot 事后清理。

## 火山回退的 `await` 坑（2.0.0 已修）

```python
# 错：先对 coroutine 调 .splitlines()，必然 AttributeError
lines = await response.read().splitlines()
# 对：先 await 拿到 bytes，再 splitlines
lines = (await response.read()).splitlines()
```

这个 bug 会让火山回退**必然失败**并静默退回文字。已修复，并在 `tests/test_clonetts_tts.py`
里用 mock 流补了回归测试。

## 为什么不往系统提示词里加"请用语音回复"

试过。执行主体是模型：可能不调工具、调了但失败，长上下文下遵循率还会下降，结果是概率性的。
回复已生成、尚未投递时再替换，才是确定性的。决策记录见
[ADR 0002](adr/0002-forced-voice-reply-hook.md)。

## 平台与版本约束

- `_temporary_local_files` 是 AstrBot **>= 4.27.3** 才有的属性；缺失时插件会 warning 一次，
  判定退化为 A + B。
- 只有 `qq_official` 做过真机验证；`aiocqhttp`（OneBot v11 / NapCat / LLOneBot）保留了代码路径
  但未实测；其它平台退化为"临时音频后缀"判定。
- 流式输出下不转换（与框架 TTS 一致）。

## 已知实现层面的取舍

| 取舍 | 影响 |
| --- | --- |
| `Record.text` 写空串 | 某些平台语音发送失败时会拿它做文字回退，此时回退文案为空 |
| 独占时降级结果类型 | 这条消息不再走框架 TTS，也不再走"仅 LLM 结果"的分段回复 |
| 只处理全 `Plain` 链 | 带图片 / @ 等组件的回复保持文字，不丢内容 |
| 转换后整条链只剩 `Record` | 由本插件转换时，图片等组件本来就不会出现（第 5 步已要求全 `Plain`） |

## 相关

- [配置与共存](configuration.md)
- [自定义回复策略](custom-policy.md)
- [ADR 0002](adr/0002-forced-voice-reply-hook.md)
