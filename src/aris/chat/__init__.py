"""chat 模块 —— 文字对话。

对外暴露：
- ChatSession：多轮对话会话（内存历史 + 流式 + 对话日志落盘）
- ChatTUI：全屏终端交互界面（TUI）
- 指令相关：COMMAND_HELP、parse_command

人设不再从这里转引：M2 起人设按 `cid` 从 `data/characters/` 取，
经总线 `character.system_prompt(cid)` 拿（不再直引 character 模块常量）。
"""

from .session import ChatSession
from .tui import ChatTUI
from .commands import COMMAND_HELP, parse_command

__all__ = [
    "ChatSession",
    "ChatTUI",
    "COMMAND_HELP",
    "parse_command",
]
