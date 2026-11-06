# 变更记录

本项目的所有重要变更都记录在这里。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [2.0.0] - 2026-11-06

插件定位从「只检测输入模态」扩展为「检测 + 一个可选的确定性回复策略」。

### Added

- 配置项 `voice_reply_probability`（float，`0.0`–`1.0`，默认 `0.0`）：语音消息的回复在投递前被换成语音。
  `1.0` = 每条语音消息都回语音，`0.0` = 关闭，中间值按概率抽签；**只对语音输入生效**。
- 配置项 `voice_reply_max_chars`（int，默认 `300`，`0` = 不限制）：回复文本超过上限就不转换，WebUI 可直接改。
- `on_decorating_result` 里的确定性转换：纯文本链整体换成一条 `Record`；同一事件只抽签一次并缓存在事件上，
  agent 多轮不会出现「前半段语音、后半段文字」。
- TTS 双路：框架 TTS provider 优先，没有或失败时复用 `astrbot_plugin_clonetts` 的
  `api_key` / `voice_type` 直连火山引擎 v3（`clonetts_tts.py`）；失败一律保留文字。
- 与 `astrbot_plugin_clonetts` 共存时的独占：priority 100 先执行、转换后 `Record.text=""`
  让对方以「文本为空」跳过、没抽中时把 `result_content_type` 降级为 `GENERAL_RESULT`，
  阻止它与内置 TTS 再合成一次（详见 [ADR 0002](docs/adr/0002-forced-voice-reply-hook.md)）。
- 纯函数层 `reply_policy.py`（概率钳值、抽签、跳过规则、独占 claim / block），可脱机单测。
- 火山流式响应解析与 mock aiohttp 的回归测试。
- 文档：真机验证结论（qq_official）、实测环境（AstrBot 4.29.4 + clonetts v3.0.4）、
  2.0.0 迁移表、与 clonetts 的分工场景矩阵。

### Changed

- README / README.en.md 的平台声明改为：**只有 `qq_official` 实测通过**；`aiocqhttp` 代码保留但未实测。
- ADR 0001「只暴露输入模态」标记为 Superseded，由 ADR 0002 取代。
- `GLOSSARY.md` 新增「强制语音回复」「抽签」「独占」「TTS 回退」，`inject_prompt` 标为已移除。

### Removed

- **破坏性变更**：移除 `inject_prompt` / `prompt_text`。软提示依赖模型自己调 TTS 工具，实测遵循率不稳定。
  迁移：`inject_prompt: true` → `voice_reply_probability: 1.0`；默认不配置即为 `0.0`，行为与 1.0.x 一致。
  旧配置文件里残留的键会被忽略，不会报错。

### Fixed

- 火山回退的 `await` 优先级 bug：`await response.read().splitlines()` 会先取 `.splitlines()` 再 await，
  导致合成**必然失败**并静默退回文字。改为先 `await` 再切行，并补了 mock 流的回归测试。
- 真机确认 `qq_official` 下「文字消息引用一条语音」已判为文字输入（`raw_signal=False`），
  不再被引用链里的音频干扰。

## [1.0.1] - 2026-11-06

### Added

- QQ 官方机器人（`qq_official`）的原始消息识别：读**顶层** `attachments`，
  `content_type` 以 `voice` / `audio` / `silk` 开头或文件名是音频时判为语音；
  被引用的语音在 `msg_elements` 里，不计入本条消息。
- `qq_official` 的回归测试，包含「文字消息引用语音」用例。

### Changed

- 调试日志改为打印 `raw_signal` 的真实取值（`True` / `False` / `None`），
  不再用「原始消息对象是否存在」冒充判断结果。
- README 的兼容性与已知限制同步。

### Fixed

- `qq_official` 下「文字消息引用一条语音」被误判为语音输入。

## [1.0.0] - 2026-11-06

首个发布版本：只判断输入模态，把结论交给其它插件。

### Added

- 事件标志 `voice_input`（`event.get_extra("voice_input")`，恒为 `True` / `False`），
  在 `on_llm_request` 与 `on_decorating_result`（priority=100）两处写入。
- `detection.py`：不导入 `astrbot` 的纯函数判定层，合并三条信号
  （残留 `Record`、平台原始消息段、事件登记的临时音频文件）。
- `inject_prompt` / `prompt_text`：可选的软提示，默认关闭，默认文案不点名任何 TTS 插件。
- `verbose_log`：把三条信号的取值打到 debug 日志。
- 中英双语 README、`examples/01_builtin_tts`、`examples/02_clone_tts_prompt`、`GLOSSARY.md`、
  `docs/adr/0001`。
- 纯函数测试 + 发布元数据一致性检查、`ruff` / `pytest` 配置、GitHub Actions。

### Changed

- 首个提交名为 `astrbot_plugin_voice_gate`（检测命中后往系统提示词注入语音回复指令）；
  同一天内重构为「只检测」并改名为 `astrbot_plugin_voice_input`，仍记作 1.0.0。
- 元数据唯一来源改为 `metadata.yaml`，移除 v3.5.19 起已废弃的 `@register`。
- `astrbot_version` 收紧到 `>=4.27.3`：判定依赖该版本引入的 `_temporary_local_files`。

### Removed

- 从未生效的 `enable` / `debug_log` 配置项。
- 写到 `/tmp` 的文件日志，改用插件自己的 `self.logger`。

### Fixed

- 信号 B（OneBot v11 原始消息段）：OneBot 下「文字消息引用一条语音」不再被误判。

[Unreleased]: https://github.com/Lin-Ruipeng/astrbot_plugin_voice_input/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/Lin-Ruipeng/astrbot_plugin_voice_input/releases/tag/v2.0.0
[1.0.1]: https://github.com/Lin-Ruipeng/astrbot_plugin_voice_input/commit/a9b9b2b
[1.0.0]: https://github.com/Lin-Ruipeng/astrbot_plugin_voice_input/commit/d75bb62
