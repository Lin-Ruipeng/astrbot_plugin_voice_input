# AGENTS.md — 给 AI 助手的说明书

> 两个读者：
> 1. **替用户安装 / 配置本插件的机器人或 AI 助手**（AstrBot 的 Agent、QQ 机器人等）——
>    读「插件做什么」「配置项」「全局前置」「向用户汇报」四节就能动手。
> 2. **在本仓库里改代码 / 写文档的 agent** —— 直接跳到最后一节。

---

## 插件做什么

`astrbot_plugin_voice_input`（语音输入识别）做两件事：

1. **检测用户这条消息是不是语音发来的。** 结论写在 `event.get_extra("voice_input")`
   （`True` / `False`），装完即生效，不需要配置。
2. **如果用户发的是语音，按概率把机器人的文字回复换成语音。**
   默认关闭；核心开关是 `voice_reply_probability`。

设计动机：方便发语音的时候通常也方便听语音，所以发语音的人大概率愿意收到语音回复。
把"要不要回语音"交给插件判断，而不是指望模型自己想起来调 TTS 工具。

---

## 配置项（WebUI → 插件 → 插件配置）

| 配置项 | 类型 | 默认 | 作用 |
| --- | --- | --- | --- |
| `voice_reply_probability` | float `0.0`–`1.0` | `0.0` | 语音消息回语音的概率。`0.0` = 关闭；`1.0` = 每条语音消息都回语音；`0.5` = 一半。文字消息永远不转 |
| `voice_reply_max_chars` | int | `300` | 回复文本超过这个字数就不转语音；`0` = 不限制。太长时 TTS 又慢又贵 |
| `verbose_log` | bool | `false` | 把检测信号与抽签结果打到 debug 日志，排查时打开 |

数值都做了防御：概率超出 `0–1` 会 warning 并按边界处理；字数负数按 `0`（不限制）。

---

## 全局前置（不满足时插件拿不到 STT / TTS）

这几项在 AstrBot 的「配置文件 → AI」里，不属于本插件，但直接决定它能不能工作：

| 前置 | 位置 | 要求 |
| --- | --- | --- |
| **STT（语音识别）** | 模型提供商 → 语音转文字；配置文件 → AI → **语音识别** | 打开，并选**默认语音转文本模型**。推荐 MiMo STT(API)：`API Base` `https://api.xiaomimimo.com/v1`、模型 `mimo-v2.5-asr`。不配 STT 也能检测语音，但 AI 读不懂你说了什么 |
| **TTS（语音合成）** | 模型提供商 → 文字转语音；配置文件 → AI → **语音回复** | 打开，并选**默认文本转语音模型**。免费起点：**Edge TTS**（默认音色 `zh-CN-XiaoxiaoNeural`，需 `edge-tts` 库）。只装 clonetts 时它会走火山回退 |
| **TTS 触发概率** | 配置文件 → AI → **TTS 触发概率** | 必须设 **0**。否则 AstrBot 内置 TTS 会把**文字消息**也转成语音，和本插件的"只有语音回语音"冲突 |
| **流式输出** | 配置文件 → AI → **流式输出**（在「其他」分组） | 必须**关**。流式下内置 TTS 与本插件都不转换 |

关键事实（AstrBot 源码行为，v4.27.3 起一致）：

- 本插件用 `context.get_using_tts_provider_async()` 取 TTS。它在
  `provider_tts_settings.enable == false` 或 `provider_id` 为空时**直接返回 None** ——
  所以"配了提供商但没开语音回复"等于没配。STT 同理。
- 内置 TTS 只在 `语音回复=开`、`随机数 <= TTS 触发概率`、非流式时自动转换，
  且只处理纯文本组件。

### TTS 提供商怎么选

| 选择 | 说明 |
| --- | --- |
| **Edge TTS**（先用这个） | 免费、无需 API Key。缺 `edge-tts` 库时，在「数据与日志 → 日志」右上角 **安装 pip 库** 填 `edge-tts`，或在容器里 `pip install edge-tts` 后重启 |
| **阿里云百炼 TTS(API)**（音色更好） | 模型必须用 **Cosy 系列**（如 `cosyvoice-v1`，默认音色 `loongstella`）。**Qwen 系列在 AstrBot 上直接跑不通（官方未适配）** |
| **MiMo TTS** | MiMo 平台同时提供 STT 与 TTS：`mimo-v2.5-tts` / `mimo_default`。本仓库实测主要用它的 ASR，TTS 也可用 |
| **astrbot_plugin_clonetts** | 想用克隆音色时安装。本插件检测到它会**独占语音消息**（避免同一句合成两次），并在没有框架 TTS 时复用它的火山凭据 |

---

## 推荐配置（语音进 → 语音出，文字进 → 文字出）

| 设置 | 值 |
| --- | --- |
| 语音识别 | 开 + 选 MiMo ASR（或你已有的 STT） |
| 语音回复 | 开 + 选 Edge TTS（或百炼 Cosy） |
| TTS 触发概率 | `0` |
| 流式输出 | 关 |
| `voice_reply_probability` | `1.0` |
| `voice_reply_max_chars` | `300`（默认） |

### 四种典型配置

| 我想要 | 语音回复 enable | TTS 触发概率 | `voice_reply_probability` |
| --- | --- | --- | --- |
| 只检测，不改回复 | 关（或开但触发概率 0） | `0` | `0.0` |
| **只有语音消息回语音** | 开 + 选默认模型 | `0` | `1.0` |
| 所有回复都语音 | 开 + 选默认模型 | `1.0` | 任意 |
| 克隆音色 | 关 / 开皆可 | — | `1.0` + 装 clonetts |

---

## 装好之后怎么验证

1. 启动日志里应有一行：`[voice_reply] 强制语音回复：概率 1.00；文本上限：300 字`。
2. 发一条**语音**：应收到一条语音，日志有 `[voice_input] 本轮消息判定为语音输入`。
3. 发一条**文字**：应收到文字，日志有 `[voice_input] 本轮消息判定为文字输入`。
4. 看不到语音时按顺序查：
   - 日志有 `[voice_reply] 没有可用的 TTS` → 语音回复没开 / 没选默认模型（或没装 clonetts）；
   - 日志有 `[voice_reply] 流式输出下不会转换语音` → 去关流式输出；
   - 回复太长 → 调大 `voice_reply_max_chars` 或缩短回复；
   - 平台只有 `qq_official` 做过真机验证；其它平台可能发不出语音。

---

## 向用户汇报的模板

配置完成后，用一段人话回复，别贴日志原文：

```
已完成：
- 安装了 astrbot_plugin_voice_input 并启用
- STT：<用了哪个 / 之前就有>
- TTS：<用了哪个 / 之前就有>
- 已确认：语音回复=开、TTS 触发概率=0、流式输出=关
- 插件：voice_reply_probability=1.0、voice_reply_max_chars=300

还需要你手动做：
- <没有就写"无">

怎么自测：
- 发一条语音，应该收到语音；发一条文字，应该收到文字。
- 启动日志里应有 "[voice_reply] 强制语音回复：概率 1.00；文本上限：300 字"

可调项：
- voice_reply_probability：0~1，改成 0 就只检测不回语音
- voice_reply_max_chars：超过这个字数不转语音，0 = 不限制
```

如果某一步你改不了（比如 WebUI 的模型提供商需要用户自己点），就明确说"这一步需要你手动做"，
并给出菜单路径，不要把失败吞掉。

---

## 给仓库维护 agent

- **纯函数层** `detection.py` / `reply_policy.py` 刻意不导入 `astrbot`，改判定或抽签逻辑先补
  `tests/`，保证能脱机单测。
- **不要**让默认能力依赖某个 TTS 插件的工具名（`tests/test_metadata.py` 会拦）。
- 提交前：`ruff check . && ruff format --check .`、`pytest`。
- 版本号三处同步：`metadata.yaml`、`pyproject.toml`、两份 README 的 badge。
- 文档约定：`README.md` / `README.en.md` 只面向使用者；实现原理、配置矩阵、开发与发布在
  `docs/`；决策记录在 `docs/adr/`；术语以 `GLOSSARY.md` 为准。
