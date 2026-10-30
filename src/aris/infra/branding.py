"""项目对外品牌文案（唯一来源）。

只放**对外可见的名字**。代码标识（`import aris`、命令 `aris`、`ARIS_` 前缀、
数据目录 `data/`）不随品牌变化，改名只改这里。
"""

from __future__ import annotations

APP_NAME = "Aris Project"
"""显示名：WebUI 标题 / 侧栏 / FastAPI title。"""

GITHUB_URL = "https://github.com/kasamorin/Project-Aris"
"""仓库地址。迁入 GitHub 组织后改这一行，`pyproject.toml` 的 URL 同步。"""

__all__ = ["APP_NAME", "GITHUB_URL"]
