<div align="center">

<img src="logo.png" alt="astrbot_plugin_voice_input" width="128" height="128" />

# 语音输入识别（astrbot_plugin_voice_input）

**检测用户发来的是不是语音；如果是语音，可以让机器人也用语音回复。**

[![简体中文](https://img.shields.io/badge/文档-简体中文-blue)](README.md)
[![English](https://img.shields.io/badge/docs-English-blue)](README.en.md)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.27.3-blue)](https://astrbot.app)
[![version](https://img.shields.io/badge/version-2.0.1-blue)](metadata.yaml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**简体中文** ｜ [English](README.en.md) ｜ [变更记录](CHANGELOG.md)

</div>

---

## 它能做什么

装上之后，你基本只需要动一处：把 `voice_reply_probability` 从 `0.0` 改成 `1.0`。
下面两个功能分开看。

### 功能 1：检测用户输入的是否是语音

自动生效，不需要配置。AstrBot 在预处理阶段会把语音转成文字，插件把这层信息捡回来，
任何插件都能读：

```python
event.get_extra("voice_input")  # True = 语音，False = 文字
```

| 相关配置 | 说明 |
| --- | --- |
| `verbose_log` | 打开后把每条消息的判定细节写进 debug 日志，排查时用；默认 `false` |

> 检测本身不依赖 STT。但 AI 要**听懂**你说了什么，仍需配一个语音识别模型（见「快速上手」第 2 步）。

### 功能 2：是语音时，控制机器人回复语音的概率

| 配置项 | 默认 | 效果 |
| --- | --- | --- |
| `voice_reply_probability` | `0.0` | `0.0` = 关闭；`1.0` = 每条语音消息都回语音；`0.5` = 一半。**只对语音消息生效**，文字消息永远不转 |
| `voice_reply_max_chars` | `300` | 回复文本超过这个字数就不转语音；`0` = 不限制。太长时 TTS 又慢又贵 |

**有三个全局开关会直接卡住这个功能**（都不在本插件的配置页里）：

| 全局开关 | 位置 | 必须设成 |
| --- | --- | --- |
| **语音回复** + **默认文本转语音模型** | 配置文件 → AI → 语音回复 | **开**，并选一个 TTS 模型。不开时本插件拿不到框架 TTS（只装了 clonetts 的话走它的火山回退） |
| **TTS 触发概率** | 配置文件 → AI → TTS 触发概率 | **`0`**。否则框架 TTS 会把**文字消息**也转成语音 |
| **流式输出** | 配置文件 → AI → 流式输出（在「其他」分组） | **关**。流式下框架 TTS 与本插件都不转换 |

### 💡 为什么这样设计

方便发语音的时候，通常也方便听语音 —— 发语音的人，大概率也愿意收到语音回复。
所以这件事交给插件判断：检测到语音输入，就按概率把回复换成语音，而不是指望模型自己想起来调 TTS 工具。

---

## 快速上手

约 10 分钟。两条路线选一条：**路线 A 复制提示词给机器人**，或**路线 B 自己点**。

### 路线 A（懒人）：把这段发给机器人

前提：WebUI 里给 Agent 打开了沙盒 / 插件安装权限。

```text
帮我安装并配置 AstrBot 插件「语音输入识别」（astrbot_plugin_voice_input），
目标是：我发语音时你用语音回复，我发文字时你用文字回复。

1. 安装并启用插件，然后读一下插件目录里的 AGENTS.md。
2. 检查 STT（语音识别）能不能用：不能用就告诉我怎么配（推荐 MiMo ASR）。
3. 检查 TTS 能不能用：没有就先用免费的 Edge TTS（缺 edge-tts 库要先装）。
4. 确认这三个全局开关：配置文件 → AI → 语音回复 = 开且选了默认模型；
   TTS 触发概率 = 0；流式输出 = 关。
5. 把插件配置 voice_reply_probability 设为 1.0，voice_reply_max_chars 保持 300。
6. 用一段话告诉我：你改了什么、还有哪一步需要我手动做、我发语音后应该看到什么日志。
```

机器人会读 [`AGENTS.md`](AGENTS.md)，把每个配置项的效果用一段话讲清楚；它改不了的地方会告诉你缺哪一步。

### 路线 B（手动）：四步前置链

> 顺序不能反：Agent 权限 → STT → TTS → 本插件。前 3 步都有跳过条件，配过就别重复配。

#### 第 1 步：给机器人 Agent 权限

WebUI 首页 / 系统设置里打开 Agent、沙盒与插件安装权限。

- 之前开过 → **跳过**。

#### 第 2 步：让 STT 能听懂语音

1. 模型提供商 → **语音转文字** → 新增 **MiMo STT(API)**：

   | 字段 | 值 |
   | --- | --- |
   | API Key | `sk-` 开头（按量计费）或 `tp-` 开头（Token Plan） |
   | API Base | `https://api.xiaomimimo.com/v1`（`tp-` Key 用 `https://token-plan-cn.xiaomimimo.com/v1`） |
   | 模型 | `mimo-v2.5-asr` |

2. 配置文件 → AI → **语音识别**：打开 → **默认语音转文本模型**选它。

- 之前配过，或问机器人"你能听懂我发的语音吗"、它说可以 → **跳过**。
- MiMo 平台也提供 TTS（`mimo-v2.5-tts` / 音色 `mimo_default`），本步只用到它的 ASR。

#### 第 3 步：让 TTS 能发出语音

1. 模型提供商 → **文字转语音** → 新增 → **Edge TTS**。
   - 免费、无需 API Key；默认音色 `zh-CN-XiaoxiaoNeural`。
   - 缺库时：「数据与日志 → 日志」右上角 **安装 pip 库** 填 `edge-tts`；或在容器里
     `pip install edge-tts` 后重启。
2. 配置文件 → AI → **语音回复**：打开 → **默认文本转语音模型**选 Edge TTS。
3. 同一页：**TTS 触发概率改成 `0`**，**流式输出关掉**。

- 之前配过，或问机器人"你能发语音吗"、它说可以 → **跳过**；但仍要确认
  **触发概率 = 0**、**流式输出 = 关**。
- 想要更好的音色：换 **阿里云百炼 TTS(API)**，模型用 **Cosy 系列**（如 `cosyvoice-v1`）。
  **Qwen 系列在 AstrBot 上直接跑不通（官方未适配）**。

#### 第 4 步：打开本插件的开关

WebUI → 插件 → `语音输入识别` → 插件配置：

| 配置项 | 值 |
| --- | --- |
| `voice_reply_probability` | `1.0` |
| `voice_reply_max_chars` | `300`（默认） |

保存并重载插件。

#### 验证

- 发一条**语音** → 收到语音；发一条**文字** → 收到文字。
- 启动日志里应有一行：

  ```
  [voice_reply] 强制语音回复：概率 1.00；文本上限：300 字
  ```

---

## 四种典型配置

| 我想要 | 语音回复 enable | TTS 触发概率 | `voice_reply_probability` |
| --- | --- | --- | --- |
| 只检测，不改回复 | 关（或开但触发概率 0） | `0` | `0.0`（默认） |
| **只有语音消息回语音**（推荐） | 开 + 选默认模型 | `0` | `1.0` |
| 所有回复都语音 | 开 + 选默认模型 | `1.0` | 任意 |
| 克隆音色 | 关 / 开皆可 | — | `1.0` + 装 `astrbot_plugin_clonetts` |

第四种会复用克隆插件的音色；两个插件同开时，语音消息由本插件独占，避免同一句合成两次。
细节见 [配置与共存](docs/configuration.md#和-astrbot_plugin_clonetts-一起用)。

---

## 排错

| 现象 | 先看这里 |
| --- | --- |
| 日志没有 `[voice_input]` 行 | 确认 AstrBot >= 4.27.3、插件已启用 |
| 判定永远为文字 | 打开 `verbose_log`；若三个检测信号都空，多半是平台在预处理前就没把语音交给 AstrBot |
| 发语音却回文字，日志有 `没有可用的 TTS` | 「语音回复」没开 / 没选默认模型；或没装 clonetts。见第 3 步 |
| 日志有 `流式输出下不会转换语音` | 配置文件 → AI → 流式输出 关掉 |
| **文字**消息也被转成语音 | TTS 触发概率不是 0 |
| 长回复不转语音 | 超过 `voice_reply_max_chars`（默认 300），调大或设 0 |
| 收到两条语音 / 被合成两次 | 确认 `astrbot_plugin_clonetts` 是 v3.0.4，且本插件 priority 仍是 100 |
| 百炼 TTS 不出声 | 选了 Qwen 系列（在 AstrBot 上跑不通）；换成 **Cosy 系列** |
| 想看到三个信号的具体取值 | `verbose_log` 打开，日志级别调到 DEBUG |

更完整的配置解释在 [配置与共存](docs/configuration.md)，实现层的原因在
[实现细节](docs/internals.md)。

---

## 工作原理（速览）

AstrBot 预处理会把语音转成文字、原地替换掉 `Record`，等插件拿到消息时语音痕迹已经没了。
本插件用三条信号把它找回来：消息链里残留的 `Record`、平台原始消息里的语音段、
预处理登记的临时音频文件；能拿到平台原始消息时以它为准（所以"文字引用一条语音"不会被误判）。

打开开关后，在回复生成、尚未投递时（`on_decorating_result`）按概率把纯文本回复换成一条语音；
同一事件只抽签一次，agent 多轮不会出现"前半段语音、后半段文字"。合成优先用你配置的框架 TTS，
没有时回退到 `astrbot_plugin_clonetts` 的火山配置，都失败就保留文字。

展开版：[实现细节](docs/internals.md) ｜ 决策记录：[ADR 0002](docs/adr/0002-forced-voice-reply-hook.md)

---

## 兼容性

| 项 | 说明 |
| --- | --- |
| AstrBot | **>= 4.27.3**（检测依赖该版本引入的 `_temporary_local_files`） |
| 平台 | **只有 `qq_official`（QQ 官方机器人）实测通过**；`aiocqhttp`（OneBot v11 / NapCat / LLOneBot）保留了代码路径但未实测；其它平台退化为"临时音频文件后缀"判定，同样未测试 |
| STT | 检测**不需要**开启；但 AI 要读懂语音内容仍需 STT |

实测环境与真机验证记录见 [开发与发布](docs/development.md#实测环境复现基线)。

### 已知限制

1. 流式输出下不会转换语音（框架 TTS 同样跳过）。
2. 命令 / `yield` 类结果、带图片等非纯文本的消息链保持文字，不会转换。
3. 回复超过 `voice_reply_max_chars` 不转换。
4. 为了让概率型 TTS 插件干净跳过，转换后 `Record.text` 是空串；某些平台语音发送失败时拿它做文字回退，
   这时回退文案为空。
5. 回退到火山 v3 需要 `astrbot_plugin_clonetts` 配置里有 `api_key` / `voice_type`；都没有时只回文字。
6. 插件本身不产生音频。能不能真的发出语音，取决于框架 TTS 提供商或 clonetts 的火山配置。

---

## 从 1.0.x 升级到 2.0.0

2.0.0 **移除了** `inject_prompt` / `prompt_text`：让模型"自己决定要不要调 TTS 工具"的思路被实测否定。

| 1.0.x 的配置 | 2.0.0 怎么做 |
| --- | --- |
| `inject_prompt: true` | 改成 `voice_reply_probability: 1.0`。效果从"靠模型自觉"变成插件确定性转换 |
| `inject_prompt: false`（默认） | 不用改，默认就是 `0.0` |
| `prompt_text: ...` | 删除。软提示路径已移除 |
| 依赖 `examples/02_clone_tts_prompt` 的注入 | 换成主插件开关；该示例保留为对照 |

旧配置文件里残留的 `inject_prompt` / `prompt_text` 会被忽略，不会报错，可以手动删掉。

---

## 完整配置项

本插件在 WebUI「插件配置」里只有三项：

| 配置项 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `voice_reply_probability` | float | `0.0` | 语音消息回语音的概率。`0.0` 关闭；`1.0` 每条都回；中间值按概率。只对语音输入生效 |
| `voice_reply_max_chars` | int | `300` | 回复超过这个字数不转语音；`0` = 不限制 |
| `verbose_log` | bool | `false` | 把判定细节（各信号、抽签结果）打进 debug 日志 |

数值有防御：概率钳到 `0.0–1.0`（误填 `80` 会 warning 并按 `1.0` 处理），字数上限的负数按 `0`（不限制）处理。

会影响它的 AstrBot 全局项（不在本插件里，见上文「功能 2」与「四种典型配置」）：

| 位置 | 配置项 | 建议 |
| --- | --- | --- |
| 配置文件 → AI | `provider_tts_settings.enable`（语音回复） | 开 |
| 配置文件 → AI | `provider_tts_settings.provider_id`（默认文本转语音模型） | 选一个 |
| 配置文件 → AI | `provider_tts_settings.trigger_probability`（TTS 触发概率） | `0` |
| 配置文件 → AI | `provider_settings.streaming_response`（流式输出） | 关 |
| 配置文件 → AI | `provider_stt_settings.enable` / `provider_id`（语音识别） | 开 + 选一个（否则 AI 读不懂语音） |

---

## 更多文档

- [文档索引](docs/README.md)
- [配置与共存](docs/configuration.md) —— TTS 选型、四种组合、与 clonetts 的场景矩阵
- [实现细节](docs/internals.md) —— 三信号、hook 时序、独占、火山回退
- [自定义回复策略](docs/custom-policy.md) —— 想自己写时看
- [开发与发布](docs/development.md)
- [AGENTS.md](AGENTS.md) —— 给 AI 的配置说明与回报模板
- [术语表](GLOSSARY.md) ｜ [ADR](docs/adr/) ｜ [变更记录](CHANGELOG.md)

示例目录：[`examples/01_builtin_tts`](examples/01_builtin_tts/)（配置教学）、
[`examples/02_clone_tts_prompt`](examples/02_clone_tts_prompt/)（可运行示例）。

---

## 许可

[MIT](LICENSE) © 2026 Lin-Ruipeng
