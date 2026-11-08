# 开发与发布

面向改这个仓库的人。使用者请回 [README](../README.md)。

## 环境

```bash
pip install pytest pyyaml packaging ruff
```

- Python `>= 3.10`（`pyproject.toml`）
- **不需要安装 AstrBot**：纯函数层（`detection.py` / `reply_policy.py`）不导入框架，
  `clonetts_tts.py` 的测试用 mock 替掉 `aiohttp`

## 常用命令

```bash
ruff check . && ruff format --check .   # lint + 格式（CI 同款）
pytest                                  # 全部单测
```

CI（`.github/workflows/ci.yml`）在 Python 3.10 / 3.12 上跑 pytest，并用固定版本 ruff 检查。

## 测试覆盖

| 文件 | 覆盖 |
| --- | --- |
| `tests/test_detection.py` | 三信号合并、OneBot / QQ 官方原始消息、CQ 码字符串、音频后缀、引用语音不误判 |
| `tests/test_reply_policy.py` | 概率钳值、字数钳值、抽签、跳过规则、独占 claim / block |
| `tests/test_clonetts_tts.py` | 火山 v3 流式响应解析、`await` 优先级回归、失败路径 |
| `tests/test_metadata.py` | 发布元数据一致性（见下） |

`tests/test_metadata.py` 锁住了几件容易回归的事：

- `metadata.yaml` 的必填字段、纯语义化版本号、`repo` 指向 GitHub、`astrbot_version` 范围；
- `_conf_schema.json` 恰好是三个键，且都有 `type` / `default` / `description`；
- 旧配置项 `inject_prompt` / `prompt_text` 不再出现；
- `main.py` 读取了 schema 里的每个键、不使用废弃的 `@register`、不写死别的插件的工具名。

## 目录结构

```
.
├── main.py                 # 钩子、配置、日志
├── detection.py            # 纯函数：三信号判定
├── reply_policy.py         # 纯函数：概率 / 抽签 / 跳过 / 独占
├── clonetts_tts.py         # 火山 v3 合成（回退路径）
├── _conf_schema.json       # 插件配置（WebUI 渲染）
├── metadata.yaml           # 插件市场元数据
├── AGENTS.md               # 给"装插件/调配置"的机器人看
├── GLOSSARY.md             # 领域术语
├── README.md / README.en.md
├── docs/
│   ├── README.md           # 文档索引
│   ├── configuration.md    # 配置、TTS 选型、与 clonetts 共存
│   ├── internals.md        # 实现细节
│   ├── development.md      # 本文件
│   ├── custom-policy.md    # 自己写回复策略
│   └── adr/                # 决策记录
├── examples/
│   ├── 01_builtin_tts/     # 教学（无可执行插件）
│   └── 02_clone_tts_prompt/# 可运行示例
└── tests/
```

## 发布检查清单

1. **版本号三处一致**：`metadata.yaml`、`pyproject.toml`、`README.md` / `README.en.md` 的 badge。
2. **CHANGELOG**：`## [x.y.z] - YYYY-MM-DD`，按 Keep a Changelog 分类。
3. **配置项**：新增 / 删除 `_conf_schema.json` 的键时，同步 `main.py` 的读取与 `AGENTS.md` 的配置表；
   `tests/test_metadata.py` 会拦"schema 有但 main 没读"。
4. **文档链接**：README / docs / examples 里的相对链接都要能打开。
5. `ruff check . && ruff format --check .`、`pytest` 全绿。

## 实测环境（复现基线）

| 项 | 值 |
| --- | --- |
| 平台 | `qq_official` |
| AstrBot | 4.29.4（仓库 pyproject；安装元数据 4.28.2） |
| 音色克隆 | `astrbot_plugin_clonetts` **v3.0.4** |
| STT | `mimo_stt_api`（`mimo-v2.5-asr`） |
| 系统 | Debian 13 / Python 3.12 / Docker 容器 |
| 本插件 | 2.0.0 |

## 真机验证结论（2026-11-06，qq_official）

测试环境同上表；容器里**没有配置框架 TTS 提供商**，语音走 clonetts 的火山回退。

| 场景 | 结果 |
| --- | --- |
| 发送语音（`voice_reply_probability: 1.0`） | ✅ 收到一条语音 |
| 发送纯文字 | ✅ 文字回复，不转语音 |
| 文字消息**引用**一条语音 | ✅ 判为文字输入（`raw_signal=False`，临时文件里虽有被引用的音频） |
| 与 `astrbot_plugin_clonetts` v3.0.4 同开 | ✅ 日志显示已独占，未出现重复合成 |

这次实测修掉了一个 `await` 优先级 bug：`await response.read().splitlines()` 等价于
`await (response.read().splitlines())`，会先取 `.splitlines()` 再 await，导致火山回退
**必然失败**并静默退回文字。已修复并补了 mock 流的回归测试。

## 文档约定

- `README.md` / `README.en.md` **只面向使用者**：两个功能、快速上手、配置、排错。
- `docs/` 放实现、配置矩阵、开发与发布；`docs/adr/` 放决策记录。
- `AGENTS.md` 放"给 AI 看的"安装 / 配置说明与回报模板。
- 术语以 `GLOSSARY.md` 为准；新增概念先更新术语表。
