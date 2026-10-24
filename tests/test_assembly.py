"""v1.0 M1：进程级运行时上收（组装根装配一次，会话注入共享）。

覆盖：
- 运行时幂等（`get_runtime()` 重复调用同一份；`reset_runtime()` 后重建）；
- 组装后实例级总线服务就绪（`tools.execute` / `loop.run` / `skills.menu`），
  而「模型存在 loop 上」的旧服务 `loop.set_model` 已移除；
- 两段会话共享同一份 registry / skills，不互相覆盖（M1 的验收点）；
- 模型 id 按调用传、不落 loop 实例；`tools_enabled=False` 请求不带工具定义。
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

from aris.behavior import AgentLoop, BehaviorRuntime, ToolRegistry
from aris.behavior.runtime import TOOLS_SYSTEM_HINT
from aris.chat import ChatSession
from aris.core import bus, has_service
from aris.core.llm.message import Message, MessageRole
from aris.serve import assemble, get_runtime, peek_runtime, reset_runtime


class _StubEngine:
    """够用的假引擎：记录每次请求，回一段纯文本增量（不碰网络）。"""

    def __init__(self) -> None:
        self.requests: list = []

    def stream_deltas(self, request) -> Iterator[SimpleNamespace]:
        self.requests.append(request)
        yield SimpleNamespace(
            stall=False,
            content="ok",
            reasoning="",
            finish_reason="stop",
            tool_calls=[],
            model_id=request.model_id,
            degraded=False,
            race_possible=False,
        )


def _service(name: str):
    """取服务实现本体（`call()` 是直接调用服务，`services()` 只给名字）。"""
    return bus._services[name]


def _echo_registry() -> ToolRegistry:
    """含一个 echo 工具的空注册表（验证请求真的带/不带工具定义）。"""
    registry = ToolRegistry()
    registry.register(
        "echo",
        description="原样返回 text 参数",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        fn=lambda **kw: kw["text"],
    )
    return registry


def test_runtime_is_process_singleton() -> None:
    """组装根持有的运行时幂等；reset 后重建的是新对象。"""
    assemble()
    first = get_runtime()
    assert get_runtime() is first
    assert peek_runtime() is first

    reset_runtime()
    assert peek_runtime() is None
    try:
        assert get_runtime() is not first
    finally:
        reset_runtime()
        assemble()  # 给后续用例留一份装配好的运行时


def test_assembly_registers_instance_services() -> None:
    """组装后单槽服务指向那一份运行时；旧的 loop.set_model 不再存在。"""
    assemble()
    runtime = get_runtime()
    for name in ("tools.execute", "loop.run", "skills.menu"):
        assert has_service(name), name
    assert not has_service("loop.set_model"), "模型已改为按调用传，不该再有 loop.set_model"
    assert _service("tools.execute").__self__ is runtime.registry
    assert _service("loop.run").__self__ is runtime.loop
    assert _service("skills.menu").__self__ is runtime.skills


def test_two_sessions_share_one_runtime() -> None:
    """开第二段会话不会把 registry / skills 服务顶掉（M1 验收点）。"""
    assemble()
    runtime = get_runtime()
    model = runtime.engine.providers.resolve_default_model()
    names = ("tools.execute", "loop.run", "skills.menu")
    before = {name: _service(name) for name in names}

    a = ChatSession(runtime=runtime, model_id=model)
    b = ChatSession(runtime=runtime, model_id=model, tools_enabled=False)

    assert {name: _service(name) for name in names} == before, "单槽服务被第二个会话顶掉了"
    assert a.registry is b.registry is runtime.registry
    assert a.runtime is b.runtime is runtime
    # 人设 + 工具提示/技能菜单只在工具启用时拼（--no-tools 用原始人设）
    assert TOOLS_SYSTEM_HINT in a.history[0].content
    assert TOOLS_SYSTEM_HINT not in b.history[0].content


def test_loop_model_id_is_per_call() -> None:
    """模型按调用传：同一个 loop 依次用不同模型，不存实例状态。"""
    engine = _StubEngine()
    loop = AgentLoop(engine, registry=_echo_registry())
    messages = [Message(role=MessageRole.USER, content="hi")]

    list(loop.iter_events(messages, model_id="a"))
    list(loop.iter_events(messages, model_id="b", tools_enabled=False))

    assert [request.model_id for request in engine.requests] == ["a", "b"]
    assert len(engine.requests[0].tools) == 1
    assert engine.requests[1].tools == []


def test_runtime_without_tools_keeps_raw_prompt() -> None:
    """with_tools=False 的运行时：空注册表、不装技能、system prompt 不加工。"""
    runtime = BehaviorRuntime(_StubEngine(), with_tools=False)
    assert runtime.skills is None
    assert runtime.tool_count() == 0
    assert runtime.system_prompt("人设") == "人设"


def test_behavior_step_reports_runtime() -> None:
    """serve 的 behavior 步骤：探针报运行时状态，启动动作幂等装配。"""
    from aris.serve.conf import ServeConfig
    from aris.serve.steps import _probe_behavior, _start_behavior, build_steps

    steps = {step.name: step for step in build_steps(ServeConfig())}
    assert steps["behavior"].start is not None
    assemble()
    assert "运行时已装配" in _probe_behavior()
    assert "工具已就绪" in _start_behavior()
