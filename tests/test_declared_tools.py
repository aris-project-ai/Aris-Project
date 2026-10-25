"""`.ai_tools` 声明契约与探询收编的回归用例。

覆盖（docs/forAiDoc/BEHAVIOR-REWORK.md 第 1 节）：
- 探询按 `.ai_tools` 后缀收编，spec 字段（owner / needs_context）落到注册表；
- 单提供方失败（抛错 / 返回 None / 畸形 spec）不连坐，错误进 declaration_failures；
- enabled=False 的声明照常登记但模型不可见；
- 运行时装配把声明收进运行的注册表；重名注册记 warning 后后注册者胜。
"""

from __future__ import annotations

from typing import Any

from aris.behavior.registry import ToolRegistry, register_declared_tools
from aris.core.tools import ToolSpec


def _spec(
    name: str = "echo",
    *,
    enabled: bool = True,
    owner: str = "fake_mod",
    **extra: Any,
) -> ToolSpec:
    """构造一条最小可用的声明（fn 原样回显参数）。"""

    def _fn(**kwargs: Any) -> Any:
        return kwargs

    return ToolSpec(
        name=name,
        description=f"{name}：测试用回显工具",
        parameters={"type": "object", "properties": {}},
        fn=_fn,
        owner=owner,
        enabled=enabled,
        **extra,
    )


def test_collects_declared_specs(monkeypatch) -> None:
    """后缀匹配 + 字段收编：owner / needs_context / enabled 全部落表。"""
    providers: dict[str, Any] = {
        "fake_mod.ai_tools": lambda: [_spec("echo")],
        "knowledge.ai_tools": lambda: [],  # 空声明 = 合法，不算失败
    }
    monkeypatch.setattr(
        "aris.behavior.registry.services",
        lambda: ["knowledge.ai_tools", "fake_mod.ai_tools", "http.request"],
    )
    monkeypatch.setattr(
        "aris.behavior.registry.call",
        lambda name, *a, **k: providers[name](),
    )

    registry = ToolRegistry()
    register_declared_tools(registry)

    names = [t.definition.name for t in registry.items()]
    assert "echo" in names
    echo = next(t for t in registry.items() if t.definition.name == "echo")
    assert echo.owner == "fake_mod"
    assert registry.declaration_failures == []


def test_provider_failures_are_isolated(monkeypatch) -> None:
    """一个提供方抛错不影响下一家；返回 None / 畸形类型同样记失败。"""

    def _boom() -> list[ToolSpec]:
        raise RuntimeError("provider exploded")

    providers: dict[str, Any] = {
        "boom.ai_tools": _boom,
        "empty.ai_tools": lambda: [],
        "junk.ai_tools": lambda: "不是列表",
        "good.ai_tools": lambda: [_spec("good_tool")],
    }
    monkeypatch.setattr(
        "aris.behavior.registry.services",
        lambda: list(providers),
    )
    monkeypatch.setattr(
        "aris.behavior.registry.call",
        lambda name, *a, **k: providers[name](),
    )

    registry = ToolRegistry()
    register_declared_tools(registry)

    failed = {provider for provider, _ in registry.declaration_failures}
    assert failed == {"boom.ai_tools", "junk.ai_tools"}
    assert "good_tool" in [t.definition.name for t in registry.items()]


def test_empty_declaration_is_not_a_failure(monkeypatch) -> None:
    """空列表 = 该模块没有工具，合法状态，不算探询失败。"""
    monkeypatch.setattr(
        "aris.behavior.registry.services",
        lambda: ["empty.ai_tools"],
    )
    monkeypatch.setattr("aris.behavior.registry.call", lambda *a, **k: [])

    registry = ToolRegistry()
    register_declared_tools(registry)

    assert registry.items() == []
    assert registry.declaration_failures == []


def test_malformed_spec_recorded(monkeypatch) -> None:
    """畸形声明只记失败，其余 spec 照常收编。"""

    def fake_provider() -> list[ToolSpec]:
        return [
            _spec("ok_tool"),
            _spec(""),  # 空 name = 畸形声明
        ]

    monkeypatch.setattr(
        "aris.behavior.registry.services",
        lambda: ["broken.ai_tools"],
    )
    monkeypatch.setattr("aris.behavior.registry.call", lambda *a, **k: fake_provider())

    registry = ToolRegistry()
    register_declared_tools(registry)

    assert "ok_tool" in [t.definition.name for t in registry.items()]
    assert any("name" in error for _, error in registry.declaration_failures)


def test_disabled_spec_hidden_from_model() -> None:
    """enabled=False：照常登记（CLI 可枚举），definitions() 过滤掉。"""
    registry = ToolRegistry()
    registry.register_spec(_spec("hidden", enabled=False))
    registry.register_spec(_spec("shown"))

    assert [d.name for d in registry.definitions()] == ["shown"]
    assert [t.definition.name for t in registry.items()] == ["hidden", "shown"]


def test_duplicate_registration_wins_last() -> None:
    """重名注册：warning 后后注册者胜（owner 跟随后者）。"""
    registry = ToolRegistry()
    registry.register_spec(_spec("dup", owner="behavior"))
    registry.register_spec(_spec("dup", owner="fake_mod"))

    dup = next(t for t in registry.items() if t.definition.name == "dup")
    assert dup.owner == "fake_mod"
    assert len(registry.items()) == 1


def test_runtime_collects_declared_tools(monkeypatch) -> None:
    """BehaviorRuntime 装配顺序：内置 → 声明探询，fake 声明进运行注册表。"""
    from aris.behavior.runtime import BehaviorRuntime

    specs = [_spec("fake_echo")]
    monkeypatch.setattr(
        "aris.behavior.registry.services",
        lambda: ["fake_mod.ai_tools"],
    )
    monkeypatch.setattr(
        "aris.behavior.registry.call",
        lambda name, *a, **k: specs if name == "fake_mod.ai_tools" else None,
    )

    runtime = BehaviorRuntime(_FakeEngine())
    names = {t.definition.name for t in runtime.registry.items()}
    assert "fake_echo" in names
    # skill 激活工具与内置工具不受影响
    assert "activate_skill" in names


class _FakeEngine:
    """最省事的假引擎：BehaviorRuntime 只存引用，不真正调用。"""
