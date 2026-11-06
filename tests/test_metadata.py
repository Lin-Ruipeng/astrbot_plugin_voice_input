"""发布前的一致性检查：metadata.yaml、_conf_schema.json、main.py。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from reply_policy import DEFAULT_MAX_CHARS

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FIELDS = ("name", "desc", "version", "author")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@pytest.fixture(scope="module")
def metadata() -> dict[str, Any]:
    data = yaml.safe_load((ROOT / "metadata.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_required_fields_are_non_empty_strings(metadata: dict[str, Any]) -> None:
    for field in REQUIRED_FIELDS:
        value = metadata.get(field)
        assert isinstance(value, str) and value.strip(), f"metadata.yaml 缺少 {field}"


def test_version_is_semver_without_prefix(metadata: dict[str, Any]) -> None:
    assert SEMVER_RE.match(metadata["version"]), "version 必须是纯语义化版本，不能带 v"


def test_plugin_name_follows_convention(metadata: dict[str, Any]) -> None:
    """插件名会被当成模块名与安装目录名，所以要符合 AstrBot 的命名惯例。

    这里**不**和检出目录名比较：`git clone` 到任意目录（或下载 GitHub 的
    zip 得到 ``xxx-main``）都会让那个断言假失败。
    """

    name = metadata["name"]
    assert re.fullmatch(r"astrbot_plugin_[a-z0-9_]+", name), name
    assert name.isidentifier(), name


def test_repo_points_at_github(metadata: dict[str, Any]) -> None:
    repo = metadata["repo"]
    # 插件市场与自动更新都依赖真实的 repo 地址
    assert repo.startswith("https://github.com/")


def test_astrbot_version_range_is_pep440(metadata: dict[str, Any]) -> None:
    spec = SpecifierSet(metadata["astrbot_version"])
    assert Version("4.29.4") in spec
    # 检测机制依赖 _temporary_local_files（>= 4.27.3），不能声称支持更早版本
    assert Version("4.27.2") not in spec


def test_conf_schema_is_minimal_and_typed() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    assert set(schema) == {
        "voice_reply_probability",
        "voice_reply_max_chars",
        "verbose_log",
    }
    for key, item in schema.items():
        assert item.get("type"), f"{key} 必须声明 type"
        assert "default" in item, f"{key} 必须有默认值"
        assert item.get("description"), f"{key} 必须有 description（WebUI 可见）"
    assert schema["voice_reply_probability"]["type"] == "float"
    assert schema["voice_reply_probability"]["default"] == 0.0
    assert schema["voice_reply_max_chars"]["type"] == "int"
    assert schema["voice_reply_max_chars"]["default"] == DEFAULT_MAX_CHARS


def test_legacy_inject_prompt_is_gone() -> None:
    """2.0.0 移除了软提示路径，旧配置项不能再出现（README 的迁移表除外）。"""

    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    assert "inject_prompt" not in schema
    assert "prompt_text" not in schema

    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "inject_prompt" not in main_source
    assert "prompt_text" not in main_source


def test_main_reads_every_config_key() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    for key in schema:
        assert key in main_source, f"配置项 {key} 没有被 main.py 读取"


def test_main_does_not_name_other_plugins_tools() -> None:
    """默认能力不能依赖某个 TTS 插件的工具名（发布前的 review 结论）。"""

    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "clone_tts" not in main_source
    assert "CloneTTSTool" not in main_source


def test_main_does_not_use_deprecated_register() -> None:
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from astrbot.api.star import register" not in main_source
    assert "@register(" not in main_source


def test_main_exposes_documented_extra_key() -> None:
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'VOICE_INPUT_KEY = "voice_input"' in main_source
