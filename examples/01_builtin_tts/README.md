# 示例 1：配好 AstrBot 自带 TTS，做到「语音进 → 语音出」

> **这是一篇教学，不是可安装的插件。** 本目录只有这份 README。
> 想自己写回复策略（读 `voice_input`、自己调 TTS provider）的完整代码，见
> [`docs/custom-policy.md`](../../docs/custom-policy.md)。

## 目标

| 你发的内容 | 机器人回的内容 |
| --- | --- |
| 一条语音 | 一条**语音** |
| 一条文字 | **文字** |

默认情况下插件只做检测、不改回复；要让"语音消息回语音"，需要把 AstrBot 自带的 TTS 配通，
再打开插件里的 `voice_reply_probability`。

## 为什么这样设计

方便发语音的时候，通常也方便听语音 —— 发语音的人大概率愿意收到语音回复。
所以这件事交给插件判断：**检测到语音输入，就按概率把回复换成语音**，而不是指望模型自己想起来调 TTS 工具。

---

## 路线 A（懒人）：把这段发给机器人

前提：WebUI 里给 Agent 开了沙盒 / 插件安装权限，且机器人能读到插件目录里的 `AGENTS.md`。

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

机器人改不了模型提供商时，会明确告诉你缺哪一步；照它说的点两下即可。

---

## 路线 B（手动）：四步前置链

> 顺序不能反：Agent 权限 → STT → TTS → 本插件。
> 前 3 步都有"跳过条件"，别重复配。

### 第 1 步：给机器人 Agent 权限

WebUI 首页 / 系统设置里打开 Agent、沙盒与插件安装权限。

- 之前开过 → **跳过**。

### 第 2 步：让 STT 能听懂语音

不开 STT 也能检测语音，但 AI 读不懂你说了什么，回复会答非所问。

1. 模型提供商 → **语音转文字** → 新增 **MiMo STT(API)**：

   | 字段 | 值 |
   | --- | --- |
   | API Key | `sk-` 开头（按量计费）或 `tp-` 开头（Token Plan） |
   | API Base | `https://api.xiaomimimo.com/v1`（`tp-` Key 用 `https://token-plan-cn.xiaomimimo.com/v1`） |
   | 模型 | `mimo-v2.5-asr` |

2. 配置文件 → AI → **语音识别**：打开 → **默认语音转文本模型**选它。

- 之前配过，或直接问机器人"你能听懂我发的语音吗"、它说可以 → **跳过**。
- MiMo 平台同时也提供 TTS（`mimo-v2.5-tts` / `mimo_default`）；本步只用到它的 ASR。

### 第 3 步：让 TTS 能发出语音

1. 模型提供商 → **文字转语音** → 新增 → **Edge TTS**。
   - 免费、无需 API Key；默认音色 `zh-CN-XiaoxiaoNeural`。
   - 若日志提示缺少 `edge-tts` 库：WebUI「数据与日志 → 日志」右上角 **安装 pip 库** 填
     `edge-tts`；或在容器里 `pip install edge-tts` 后重启 AstrBot。
2. 配置文件 → AI → **语音回复**：打开 → **默认文本转语音模型**选 Edge TTS。
3. 同一页：**TTS 触发概率改成 `0`**，**流式输出关掉**。
   - 触发概率不设 0 的话，AstrBot 内置 TTS 会把**文字消息**也转成语音。
   - 流式输出下，内置 TTS 和本插件都不会转换。

- 之前配过，或问机器人"你能发语音吗"、它说可以 → **跳过**，
  但仍要确认**触发概率 = 0**、**流式输出 = 关**。

#### 想换更好的音色：阿里云百炼 TTS

模型提供商 → 文字转语音 → 新增 **阿里云百炼 TTS(API)**，填百炼控制台的 API Key，模型用
**Cosy 系列**（如 `cosyvoice-v1`，默认音色 `loongstella`）。

> **Qwen 系列在 AstrBot 上直接跑不通（官方未适配）**，不要选。

### 第 4 步：打开本插件的开关

WebUI → 插件 → `语音输入识别` → 插件配置：

| 配置项 | 值 |
| --- | --- |
| `voice_reply_probability` | `1.0` |
| `voice_reply_max_chars` | `300`（默认） |

保存并重载插件。

### 验证

- 发一条**语音** → 收到语音；发一条**文字** → 收到文字。
- 启动日志里应有一行：

  ```
  [voice_reply] 强制语音回复：概率 1.00；文本上限：300 字
  ```

---

## 常见坑

| 现象 | 原因 | 怎么办 |
| --- | --- | --- |
| 发语音还是回文字，日志有 `没有可用的 TTS` | 「语音回复」没开，或没选默认文本转语音模型 | 按第 3 步打开并选模型（`get_using_tts_provider_async` 此时返回 `None`） |
| 连**文字**消息也变成语音 | TTS 触发概率不是 0 | 把 **TTS 触发概率** 改成 `0` |
| 日志有 `流式输出下不会转换语音` | 流式输出开着 | 配置文件 → AI → 流式输出 关掉 |
| Edge TTS 报缺库 | AstrBot 未内置 `edge-tts` | 「数据与日志 → 日志 → 安装 pip 库」装 `edge-tts` |
| 长回复不转语音 | 超过 `voice_reply_max_chars`（默认 300） | 调大上限或设 0 |
| 百炼 TTS 不出声 | 选了 Qwen 系列 | 换成 **Cosy 系列**（Qwen 在 AstrBot 上跑不通） |
| 平台发不出语音 | 只有 `qq_official` 做过真机验证 | 见 [兼容性](../../README.md#兼容性) |

---

## 想自己写回复策略

主插件已经内置了"语音进 → 语音出"的确定性转换。如果你想自己读 `voice_input`、自己调 provider、
或者加自己的跳过规则，完整示例代码在：

- [`docs/custom-policy.md`](../../docs/custom-policy.md) —— 一份可直接拷成插件的 `Star` 实现
- [`docs/configuration.md`](../../docs/configuration.md) —— 与 clonetts 共存、场景矩阵、失败降级
- [`AGENTS.md`](../../AGENTS.md) —— 给 AI 看的配置说明与回报模板
