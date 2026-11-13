# 示例 1：配好框架 TTS，做到「语音进 → 语音出」

> **这是一篇教学，不是可安装的插件。** 本目录只有这份 README。
> 想自己写回复策略（读 `voice_input`、自己调 TTS provider）的完整代码，见
> [`docs/custom-policy.md`](../../docs/custom-policy.md)。

## 目标

| 你发的内容 | 机器人回的内容 |
| --- | --- |
| 一条语音 | 一条**语音** |
| 一条文字 | **文字** |

默认情况下插件只做检测、不改回复；要让"语音消息回语音"，需要把框架 TTS 配通，
再打开插件里的 `voice_reply_probability`。

## 为什么这样设计

方便发语音的时候，通常也方便听语音 —— 发语音的人大概率愿意收到语音回复。
所以这件事交给插件判断：**检测到语音输入，就按概率把回复换成语音**，而不是指望模型自己想起来调 TTS 工具。

---

## 怎么配

完整的路线 A / 路线 B 在 [README → 快速上手](../../README.md#快速上手)：

- **路线 A（懒人）**：把 README 里那段提示词直接发给机器人，它会读 [`AGENTS.md`](../../AGENTS.md) 自己配。
- **路线 B（手动）**：Agent 权限 → STT → TTS → 本插件；前 3 步都有跳过条件。

本页只把 TTS 这一段展开——它是“语音出”的关键。

### TTS：先用免费的 Edge TTS

1. 模型提供商 → **文字转语音** → 新增 → **Edge TTS**。
   - 免费、无需 API Key；默认音色 `zh-CN-XiaoxiaoNeural`。
   - 缺 `edge-tts` 库时：WebUI「数据与日志 → 日志」右上角 **安装 pip 库** 填 `edge-tts`；
     或容器里 `pip install edge-tts` 后重启。
2. 配置文件 → AI → **语音回复**：打开 → **默认文本转语音模型**选 Edge TTS。
3. 同一页：**TTS 触发概率改成 `0`**，**流式输出关掉**。
   - 触发概率不设 0，框架 TTS 会把**文字消息**也转成语音。
   - 流式输出下，框架 TTS 和本插件都不转换。
4. 插件配置把 `voice_reply_probability` 设为 `1.0`。

#### 想换更好的音色：阿里云百炼 TTS

模型提供商 → 文字转语音 → 新增 **阿里云百炼 TTS(API)**，填百炼控制台的 API Key，模型用
**Cosy 系列**（如 `cosyvoice-v1`，默认音色 `loongstella`）。

> **Qwen 系列在 AstrBot 上直接跑不通（官方未适配）**，不要选。

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
| 发语音还是回文字，日志有 `没有可用的 TTS` | 「语音回复」没开，或没选默认文本转语音模型 | 按上面的 TTS 步骤打开并选模型（`get_using_tts_provider_async` 此时返回 `None`） |
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
- [`AGENTS.md`](../../AGENTS.md) —— 给 AI 助手的入口（安装 / 配置指引见 [`docs/install.md`](../../docs/install.md)）
