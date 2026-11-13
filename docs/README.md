# 文档索引

想快速用起来，先看根目录的 [README](../README.md)；下面是给"想搞明白 / 想改"的人看的。

| 文档 | 适合谁 | 内容 |
| --- | --- | --- |
| [安装与配置](install.md) | 替用户装插件的 AI 助手、第一次配置的人 | 安装方式、三个配置项、全局前置（STT / TTS / TTS 触发概率 / 流式输出）、TTS 提供商选型、推荐配置与四种典型配置、验证步骤、向用户汇报模板 |
| [配置与共存](configuration.md) | 配不通、想换 TTS、和 clonetts 一起用 | STT/TTS 解析规则、框架 TTS 的自动转换条件、与 clonetts 的场景矩阵、失败降级、字数上限与钳值——讲"为什么必须这样设" |
| [实现细节](internals.md) | 想读懂代码、排查"为什么没转语音" | 三检测信号、hook 时序、抽签与跳过规则、独占三件套、火山回退 |
| [自定义回复策略](custom-policy.md) | 想自己写 `on_decorating_result` | 完整可拷代码、priority 规则、与主插件同开时的行为 |
| [开发与发布](development.md) | 改这个仓库的人 | 测试覆盖、发布检查清单、实测环境、真机验证记录 |
| [AGENTS.md](../AGENTS.md) | 机器人 / AI 助手 | 入口：定位、文档地图、维护约定；安装配置指向 [install.md](install.md) |
| [ADR](adr/) | 想知道"为什么这么设计" | 0001 只暴露输入模态（已被取代）、0002 强制语音回复下沉到主插件 |
| [GLOSSARY](../GLOSSARY.md) | 统一用词 | 输入模态、强制语音回复、抽签、独占、TTS 回退等术语 |

## 快速导航

- 我要**发语音、机器人回语音** → [README 快速上手](../README.md#快速上手)，需要逐项检查时用 [安装与配置](install.md)
- 我**配了 TTS 但插件说没有可用 TTS** → [配置与共存](configuration.md#astrbot-的-tts--stt-解析规则)
- 我**文字消息也被转成语音了** → 把「TTS 触发概率」设 0，见 [四种典型配置](install.md#四种典型配置)
- 我**装了 clonetts，怕重复合成** → [和 astrbot_plugin_clonetts 一起用](configuration.md#和-astrbot_plugin_clonetts-一起用)
- 我想**自己搞一套回复策略** → [自定义回复策略](custom-policy.md)
