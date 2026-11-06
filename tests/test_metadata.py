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


def test_plugin_name_matches_directory(metadata: dict[str, Any]) -> None:
    assert metadata["name"] == ROOT.name


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
    assert set(schema) == {"inject_prompt", "prompt_text", "verbose_log"}
    for key, item in schema.items():
        assert item.get("type"), f"{key} 必须声明 type"
        assert "default" in item, f"{key} 必须有默认值"
    assert schema["inject_prompt"]["default"] is False


def test_default_prompt_is_not_vendor_specific() -> None:
    """默认文案不能点名某个 TTS 插件的工具名（发布前的 review 结论）。"""

    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    assert "clone_tts" not in schema["prompt_text"]["default"]

    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "clone_tts" not in main_source


def test_main_does_not_use_deprecated_register() -> None:
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from astrbot.api.star import register" not in main_source
    assert "@register(" not in main_source


def test_main_exposes_documented_extra_key() -> None:
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'VOICE_INPUT_KEY = "voice_input"' in main_source
