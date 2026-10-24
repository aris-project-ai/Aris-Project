"""文字对话会话（aris chat）。

维护多轮对话历史（内存），流式调用 LLM，并把每轮问答作为日志落盘到
`<data_dir>/logs/YYYY-MM-DD/chat.log`，便于日后回溯与记忆系统接入。

M1 上收后会话**不自建**引擎 / 工具注册表 / 技能管理器 / agent loop，
而是注入 `BehaviorRuntime`（默认取组装根 `serve` 持有的进程级那一份）——
原来每开一段对话都自建并 provide 一次，单槽总线服务会被互相顶掉。
"""

from __future__ import annotations

import datetime
import os
import select
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from aris.cfgtoml import load_config

from ..behavior import BehaviorRuntime, LoopEventType
from ..core import call, has_service
from ..core.llm import LLMEngine, Message, MessageRole
from .commands import (
    COMMAND_HELP,
    PROMPT_ARIS,
    PROMPT_USER,
    ParsedCommand,
    parse_command,
)

# 兜底人设：仅当 character 模块未注册（服务缺失）时使用，正常路径不会走到
_FALLBACK_SYSTEM_PROMPT = "你是 Aris，一个拟人 AI，说话简洁自然。"


def _resolve_cid(cid: str | None) -> str | None:
    """选定角色 cid：显式给的优先，否则问 character 模块要默认角色（未注册则 None）。"""
    if cid or not has_service("character.resolve"):
        return cid
    return call("character.resolve")


def _default_system_prompt(cid: str | None) -> str:
    """默认系统提示词：经 CMCB 取该角色的人设（`cid` 省略时取默认角色）。

    `character.system_prompt` 的 `cid` 必填（防静默串号），故先解析出 cid 再取。
    """
    if not has_service("character.system_prompt"):
        return _FALLBACK_SYSTEM_PROMPT
    resolved = cid or call("character.resolve")
    return call("character.system_prompt", resolved) or _FALLBACK_SYSTEM_PROMPT


@dataclass
class ChatConfig:
    """chat 模块可调参数（config/chat.toml）。"""

    # LLM 采样参数：None = 不传（由提供方决定默认值）
    temperature: float | None = None  # 采样温度，0=确定性，1=随机性较高
    top_p: float | None = None  # 核采样概率质量，0.9=从前 90% token 采样
    log_rotation_bytes: int = 10 * 1024 * 1024
    tool_result_preview_len: int = 60
    # 默认角色 cid（None = 自动：空目录播种默认角色，否则用最早创建的那个）
    character: str | None = None


_chat_config = load_config(ChatConfig(), "chat.toml")


@dataclass
class CommandResult:
    """指令执行结果：反馈文本 + UI 动作标记（退出 / 清屏）。"""

    text: str = ""
    quit: bool = False
    clear: bool = False


def _chat_log_path(log_dir: Path) -> Path:
    """取当日对话日志路径；文件超限时依次切新文件（.1 .2 ...）。"""
    base = log_dir / "chat.log"
    if base.exists() and base.stat().st_size >= _chat_config.log_rotation_bytes:
        index = 1
        while True:
            candidate = log_dir / f"chat.log.{index}"
            if not candidate.exists() or candidate.stat().st_size < _chat_config.log_rotation_bytes:
                return candidate
            index += 1
    return base


def _discard_pending_input() -> None:
    """丢弃终端里尚未被读取的已输入字符（typeahead）。

    Aris 流式回复期间用户可能提前输入了文字，这些字符会滞留在输入缓冲，
    若不清空会被当作下一轮的用户输入。仅对终端 stdin 有效。
    """
    if not sys.stdin.isatty():
        return
    while select.select([sys.stdin], [], [], 0)[0]:
        try:
            os.read(sys.stdin.fileno(), 65536)
        except (BlockingIOError, OSError):
            break


class ChatSession:
    """一段多轮对话：内存保存历史，流式收发消息，对话内容落盘日志。

    每次 ask() 会把用户消息与 Aris 回复追加进内存历史，并把该轮问答
    写入当日对话日志文件。
    """

    def __init__(
        self,
        engine: LLMEngine | None = None,
        *,
        runtime: BehaviorRuntime | None = None,
        model_id: str | None = None,
        cid: str | None = None,
        system_prompt: str | None = None,
        data_dir: Path | None = None,
        thinking: bool = False,
        tools_enabled: bool = True,
    ) -> None:
        """建一段会话。

        ``runtime``/``engine`` 可省：默认取组装根 `serve` 持有的**进程级运行时**
        （M1 上收，见 `behavior/runtime.py` 与 `serve/assembly.py`）。测试或需要
        独立运行时时显式传：给 ``engine`` 会用该引擎自建一份运行时（工具面按
        ``tools_enabled`` 决定），给 ``runtime`` 则直接复用。

        ``cid`` 是角色 id（M2）：缺省时按 `config/chat.toml` 的 ``character``、
        再退到 character 模块的默认角色；`system_prompt` 显式给了则不取人设。
        """
        if runtime is None:
            if engine is None:
                from ..serve import get_runtime  # 组装根；懒导入避免循环引用

                runtime = get_runtime()
            else:
                runtime = BehaviorRuntime(engine, with_tools=tools_enabled)
        elif engine is not None and engine is not runtime.engine:
            raise ValueError("engine 与 runtime 指向不同的 LLM 引擎，二者只能给一个")

        if data_dir is None:
            from ..config import get_settings

            data_dir = get_settings().data_dir
        if system_prompt is None:
            # 只在需要默认人设时才解析 / 播种角色（显式 --system 不碰角色目录）
            cid = _resolve_cid(cid or _chat_config.character)
            system_prompt = _default_system_prompt(cid)

        self.runtime = runtime
        self.cid = cid  # 角色 id（M2 起人设按 cid 取；M3 会话按 cid 分区）
        self.engine = runtime.engine
        self.registry = runtime.registry
        self.available_models = self.engine.providers.all_model_ids()
        self._default_model = self.engine.providers.resolve_default_model()
        self.model_id = model_id or self._default_model
        self.thinking = thinking  # 默认关闭思考模式（首字更快），--thinking 开启
        self.tools_enabled = tools_enabled
        # 系统提示词：人设（工具启用时再拼工具提示与技能菜单）
        self._system_prompt = (
            runtime.system_prompt(system_prompt) if tools_enabled else system_prompt
        )
        self.history: list[Message] = [
            Message(role=MessageRole.SYSTEM, content=self._system_prompt)
        ]
        # 降级恢复状态：降级后记住实际生效的模型，下一轮竞速回主模型
        self._degraded_model: str | None = None
        log_dir = data_dir / "logs" / datetime.date.today().isoformat()
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir = log_dir

    def new(self) -> str:
        """清空对话历史，开启新会话（保留系统提示词），返回反馈文本。"""
        self.history = [Message(role=MessageRole.SYSTEM, content=self._system_prompt)]
        return "已开启新会话，对话历史已清空。"

    def set_model(self, model_id: str) -> str:
        """切换模型；id 不在可用列表时返回错误文本，不切换。"""
        if model_id in self.available_models:
            # 模型是会话状态（不是 loop 的），改这里即可——ask() 每轮按调用传给 loop
            self.model_id = model_id
            self._degraded_model = None  # 手动切模型：退出降级模式
            return f"已切换模型：{model_id}"
        hint = "\n".join(f"  {mid}" for mid in self.available_models)
        return f"未知模型 {model_id}，可用模型：\n{hint}"

    def close(self) -> None:
        """释放会话占用的资源。幂等，可安全多次调用。

        当前会话无外部资源（浏览器方案已移除，联网搜索走 Tavily API），
        保留方法以兼容调用方（TUI / repl 的退出路径）。
        """

    def run_command(self, parsed: ParsedCommand) -> CommandResult:
        """执行一条已解析的对话指令，返回 UI 层需要的结果。"""
        if parsed.name in {"quit", "exit"}:
            return CommandResult(text="", quit=True)
        if parsed.name == "help":
            return CommandResult(text=COMMAND_HELP)
        if parsed.name == "new":
            return CommandResult(text=self.new())
        if parsed.name == "clear":
            return CommandResult(text="", clear=True)
        if parsed.name == "model":
            if parsed.arg:
                return CommandResult(text=self.set_model(parsed.arg))
            models = "\n".join(
                f"  {mid}{'  [默认]' if mid == self._default_model else ''}"
                for mid in self.available_models
            )
            return CommandResult(text=f"当前模型：{self.model_id}\n可用模型：\n{models}")
        return CommandResult(text=f"未知指令 /{parsed.name}，输入 /help 查看可用指令")

    def ask(
        self,
        text: str,
        should_stop: Callable[[], bool] | None = None,
        on_tool: Callable[[str, str], None] | None = None,
        on_stall: Callable[[str], None] | None = None,
        on_degraded: Callable[[str], None] | None = None,
    ) -> Iterator[str]:
        """发送一条用户消息，流式返回 Aris 回复。

        走 agent loop（LLM ↔ 工具）：文本增量逐段 yield，工具调用与结果
        经 on_tool 回调通知；首字占位经 on_stall、降级经 on_degraded 通知。
        回复完成后把该轮问答写入对话日志。
        若 should_stop 回调返回 True，则中断并回滚未完成的 user 消息。
        """
        self.history.append(Message(role=MessageRole.USER, content=text))
        interrupted = False
        reply = ""
        for event in call(
            "loop.run",
            list(self.history),
            model_id=self.model_id,
            tools_enabled=self.tools_enabled,
            thinking=self.thinking,
            should_stop=should_stop,
            race_model=self._degraded_model,
        ):
            if event.type == LoopEventType.DELTA:
                yield event.content
            elif event.type == LoopEventType.TOOL:
                if on_tool is not None:
                    on_tool(event.name, event.result)
            elif event.type == LoopEventType.STALL:
                if on_stall is not None:
                    on_stall(event.content)
            elif event.type == LoopEventType.INTERRUPTED:
                interrupted = True
                break
            elif event.type == LoopEventType.DONE:
                reply = event.content
                # 降级恢复状态：降级且可竞速 → 记住实际生效模型，下一轮竞速回主模型；
                # 本家赢回 / 正常回答 → 退出降级模式
                if event.degraded and event.race_possible:
                    self._degraded_model = event.model_id
                else:
                    self._degraded_model = None
                if event.degraded and on_degraded is not None:
                    on_degraded(event.model_id)
        if interrupted:
            if self.history and self.history[-1].role == MessageRole.USER:
                self.history.pop()  # 撤掉未完成轮次的用户消息
            return
        self.history.append(Message(role=MessageRole.ASSISTANT, content=reply))
        self._append_log(text, reply)

    def _append_log(self, user_text: str, reply: str) -> None:
        """把一轮问答按人类可读格式追加到当日对话日志。"""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        with _chat_log_path(self._log_dir).open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] 用户: {user_text}\n")
            f.write(f"[{ts}] Aris: {reply}\n")

    def repl(self) -> int:
        """进入交互式对话循环。

        终端环境走全屏 TUI（输出区在上、输入框在底部、ESC 两次中断、
        Ctrl-C 退出）；非终端（管道/重定向）回退简单 input() 循环。
        """
        if sys.stdin.isatty():
            from .tui import ChatTUI

            return ChatTUI(self).run()

        # 非终端回退：逐行问答，Ctrl-C 中断本次回复
        print("开始与 Aris 对话（输入 /help 查看可用指令，/quit 退出）")
        while True:
            _discard_pending_input()  # 清掉上一轮回复期间残留的输入
            try:
                user_text = input(PROMPT_USER).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_text:
                continue
            parsed = parse_command(user_text)
            if parsed is not None:
                result = self.run_command(parsed)
                if result.quit:
                    break
                if result.clear:
                    print("\n" * 3)  # 非终端没有界面可清，仅刷屏分隔
                if result.text:
                    print(result.text)
                continue
            print(PROMPT_ARIS, end="", flush=True)
            for delta in self.ask(
                user_text,
                on_tool=lambda name, result: print(
                    f"\n  [调用工具 {name} → {result[: _chat_config.tool_result_preview_len]}]\n",
                    end="",
                    flush=True,
                ),
                on_stall=lambda t: print(f"\n[{t}]\n", end="", flush=True),
                on_degraded=lambda m: print(f"\n[已降级到模型: {m}]\n", end="", flush=True),
            ):
                print(delta, end="", flush=True)
            print()
        self.close()  # 释放浏览器等会话资源
        return 0
