"""behavior 的进程级运行时：工具注册表 + 技能管理器 + agent loop。

一个进程只有一份，由组装根 `serve.assemble()` 建好并持有（v1.0 M1 上收）——
原来每个 `ChatSession` 构造时都自建一套并 `provide` 一次，而
`tools.execute` / `loop.run` / `skills.menu` 都是**单槽**总线服务，
多开一段对话就把前一份顶掉（多人格时 A 的技能面会被 B 覆盖）。

会话侧经**依赖注入**拿这一份（AGENTS.md §6：对象构造 / 装配不走总线）；
总线服务仍然注册，供其他模块经 `core.call` 使用。

多角色（D1/D2）注意：v1.0 一个进程共享这一份注册表与技能激活状态；
将来若要「各角色各自的工具面」，在这里按 cid 分表即可，会话侧不必再改。
"""

from __future__ import annotations

from pathlib import Path

from ..core.llm.engine import LLMEngine
from .loop import AgentLoop
from .registry import ToolRegistry, register_declared_tools
from .skills import SkillManager
from .tools import register_builtin_tools

# 工具可用时追加到系统提示词
TOOLS_SYSTEM_HINT = "当需要实时信息（如当前时间、资料搜索）时使用提供的工具，使用前简单说明一句。"


class BehaviorRuntime:
    """behavior 的进程级运行时（一份 registry + 一份 skills + 一个 agent loop）。"""

    def __init__(
        self,
        engine: LLMEngine,
        *,
        skills_dir: Path | None = None,
        with_tools: bool = True,
    ) -> None:
        """建一份运行时。

        ``with_tools=False`` 只建空注册表、不装载技能（`--no-tools` 与测试里
        要「请求不带任何工具定义」的会话用）；agent loop 仍要建，会话的
        `ask()` 靠它跑。

        工具装配顺序：内置 → 技能 → 业务模块声明（`.ai_tools` 契约探询）。
        声明探询要求 owner 模块已被 import——时序由组装根保证。
        """
        self.engine = engine
        self.registry = ToolRegistry()
        self.skills: SkillManager | None = None
        if with_tools:
            register_builtin_tools(self.registry)
            # 实例化即注册 skills.menu 服务与 activate_skill 工具
            self.skills = SkillManager(self.registry, skills_dir)
            # 各模块经 <模块名>.ai_tools 声明的 agent 工具探询收编；
            # 失败已在 registry 侧记 warning 并进 declaration_failures
            register_declared_tools(self.registry)
        self.loop = AgentLoop(engine, registry=self.registry)

    def tool_count(self) -> int:
        """当前登记的工具数（启动探针用）。

        统计**全部登记**（含 disabled / 不可见工具），探针数字只反映装配
        结果，不随模型可见性开关波动；模型可见数看 `definitions()`。
        """
        return len(self.registry.items())

    def system_prompt(self, base: str) -> str:
        """拼系统提示词：人设 + 工具提示 +（有技能时）技能菜单。

        不带工具的运行时直接返回人设文本。
        """
        if self.skills is None:
            return base
        parts = [base, TOOLS_SYSTEM_HINT]
        menu = self.skills.menu()
        if menu:
            parts.append(menu)
        return "\n\n".join(parts)


__all__ = ["TOOLS_SYSTEM_HINT", "BehaviorRuntime"]
