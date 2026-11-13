# AGENTS.md — 给 AI 助手的入口

`astrbot_plugin_voice_input`（语音输入识别）是一个 AstrBot 插件，做两件事：

1. 判断本轮用户消息是不是**语音发来的**，结论写到 `event.get_extra("voice_input")`（`True` / `False`），
   装完即生效。
2. 打开 `voice_reply_probability` 后，按概率把**语音消息**的回复换成语音。默认 `0.0`（关闭），
   文字消息永远不转。

## 需要安装 / 配置

👉 **读 [docs/install.md](docs/install.md)。**

安装步骤、三个配置项与效果、四个全局前置（STT / TTS / TTS 触发概率 / 流式输出）、TTS 提供商选型、
推荐配置、装完怎么验证、以及**向用户汇报的模板**都在那一份里。按顺序做完再回复用户。

## 文档地图

| 想知道 | 去哪 |
| --- | --- |
| 怎么装、怎么配、怎么验证、怎么回报 | [docs/install.md](docs/install.md) |
| 某个开关**为什么**必须这样设（解析规则、框架 TTS 条件、与 clonetts 共存、失败降级） | [docs/configuration.md](docs/configuration.md) |
| 代码怎么实现（三检测信号、hook 时序、独占、火山回退） | [docs/internals.md](docs/internals.md) |
| 想自己写一套 `on_decorating_result` 回复策略 | [docs/custom-policy.md](docs/custom-policy.md) |
| 为什么这么设计 | [docs/adr/](docs/adr/) ｜ 术语口径 | [GLOSSARY.md](GLOSSARY.md) |

## 给仓库维护 agent

- **纯函数层** `detection.py` / `reply_policy.py` 刻意不导入 `astrbot`，改判定或抽签逻辑先补
  `tests/`，保证能脱机单测。
- **不要**让默认能力依赖某个 TTS 插件的工具名（`tests/test_metadata.py` 会拦）。
- **版本号三处一致**：`pyproject.toml`（[项目元数据](GLOSSARY.md)）、`metadata.yaml`
  （[发布元数据](GLOSSARY.md)）、`README.md` / `README.en.md` 的 version badge。
  `tests/test_metadata.py` 会拦任意一处漂移，不用靠人记。
- 提交前：`ruff check . && ruff format --check .`、`pytest`。
- 文档约定：`README.md` / `README.en.md` **只面向使用者且必须自足**（插件市场的安装页直接展示它，
  用户不会点转跳）；操作链在 `docs/install.md`；原理在 `docs/configuration.md`；决策在 `docs/adr/`；
  术语以 `GLOSSARY.md` 为准。改配置项时同步 `_conf_schema.json`、`main.py`、`docs/install.md`
  的配置表（`tests/test_metadata.py` 会拦 schema 与 `main.py` 不一致）。
