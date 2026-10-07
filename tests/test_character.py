"""v1.0 M2：角色载体（`data/characters/<cid>/`）。

覆盖：
- 两个角色目录并存、人设不串；
- 播种默认角色只发生一次（幂等），已有角色时不新建；
- `character.system_prompt` 的 `cid` 必填（防静默串号），未知 cid 报可操作错误；
- 三段只读占位文本不算内容，填了才拼进人设；
- `ChatSession` 按 cid 取人设；`system_prompt`（`--system`）仍是最高优先级。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import aris.character  # noqa: F401  确保 character.* 服务已注册
from aris.character import DEFAULT_NAME, TEXT_FILES, CharacterStore, carrier
from aris.character import prompt as character_prompt
from aris.chat import ChatSession
from aris.core import call


@pytest.fixture
def store(tmp_path, monkeypatch) -> CharacterStore:
    """把进程级角色仓库指向临时目录。"""
    store = CharacterStore(tmp_path / "characters")
    monkeypatch.setattr(carrier, "_store", store)
    return store


def _legacy_prompt() -> str:
    """v1.0 之前的系统提示词（逐字），用于验证播种文本没被改写。"""
    return (
        f"{character_prompt.DEFAULT_INTRO}\n"
        f"你的性格：{character_prompt.DEFAULT_PERSONALITY}\n"
        f"你的语气：{character_prompt.DEFAULT_TONE}\n"
        f"{character_prompt.DEFAULT_BOUNDARIES}"
    )


def test_two_characters_do_not_mix(store: CharacterStore) -> None:
    first = store.create(name="Aris", cid="aaa", fields={"intro": "甲的人设"})
    second = store.create(name="Bella", cid="bbb", fields={"intro": "乙的人设"})
    assert first.system_prompt().startswith("甲的人设")
    assert second.system_prompt().startswith("乙的人设")
    assert store.system_prompt("aaa") != store.system_prompt("bbb")
    assert [info.name for info in store.list()] == ["Aris", "Bella"]
    assert store.cids() == ["aaa", "bbb"]


def test_seed_default_is_idempotent(store: CharacterStore) -> None:
    cid = store.seed_default()
    assert store.seed_default() == cid
    assert store.cids() == [cid]
    assert store.load(cid).name == DEFAULT_NAME


def test_seed_default_keeps_existing(store: CharacterStore) -> None:
    store.create(name="Bella", cid="bbb")
    assert store.seed_default() == "bbb"
    assert store.cids() == ["bbb"]


def test_placeholder_files_only_join_prompt_when_filled(store: CharacterStore, tmp_path) -> None:
    store.create(cid="aaa")
    assert "# 世界观" not in store.system_prompt("aaa")
    path = tmp_path / "characters" / "aaa" / TEXT_FILES[0]
    path.write_text("她住在一间旧书店楼上。", "utf-8")
    prompt = store.system_prompt("aaa")
    assert "# 世界观" in prompt
    assert "旧书店" in prompt


def test_bus_services_and_required_cid(store: CharacterStore) -> None:
    with pytest.raises(TypeError):
        call("character.system_prompt")  # cid 必填：不给就报错，不静默取默认
    assert call("character.list") == []
    cid = call("character.resolve")
    assert call("character.resolve") == cid  # 幂等
    assert call("character.list")[0]["cid"] == cid
    assert call("character.system_prompt", cid) == _legacy_prompt()
    with pytest.raises(FileNotFoundError):
        call("character.system_prompt", "nope")
    with pytest.raises(FileNotFoundError):
        call("character.resolve", "nope")


class _StubEngine:
    """够用的假引擎：ChatSession 构造只用到提供方信息。"""

    def __init__(self) -> None:
        self.providers = SimpleNamespace(
            all_model_ids=lambda: ["m1"],
            resolve_default_model=lambda: "m1",
            default_model="m1",
        )


def test_session_takes_character_prompt(store: CharacterStore, tmp_path) -> None:
    store.create(name="Aris", cid="aaa")
    session = ChatSession(
        _StubEngine(), model_id="m1", cid="aaa", tools_enabled=False, data_dir=tmp_path
    )
    assert session.cid == "aaa"
    assert session.history[0].content == _legacy_prompt()


def test_session_system_prompt_overrides_character(store: CharacterStore, tmp_path) -> None:
    store.create(name="Aris", cid="aaa")
    session = ChatSession(
        _StubEngine(),
        model_id="m1",
        cid="aaa",
        system_prompt="临时人设",
        tools_enabled=False,
        data_dir=tmp_path,
    )
    assert session.history[0].content == "临时人设"


def test_session_seeds_default_character_when_empty(store: CharacterStore, tmp_path) -> None:
    session = ChatSession(_StubEngine(), model_id="m1", tools_enabled=False, data_dir=tmp_path)
    assert session.cid == store.cids()[0]
    assert "你是 Aris" in session.history[0].content
