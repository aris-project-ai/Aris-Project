# 配置体系（CONFIG.md）

> 状态：契约 | 代码入口：`src/aris/infra/`（`settings.py` / `toml.py` / `paths.py` / `modules.py`）
> 事实查看：`aris config path|list|show|validate|env`、`aris modules list|status`、`aris info`

## 一处来源

配置只有一处：**`data/config/`**（路径由 `src/aris/infra/paths.py` 决定，随 `ARIS_DATA_DIR` 变化）。
目录内文件缺失时回落到**随包种子模板** `src/aris/seed/config/`；首次启动把模板幂等播种到
`data/config/`（只补缺失、不覆盖用户改动，`secrets.toml` 播种时置 0600）。

| 文件 | 管什么 | 读取方式 |
|---|---|---|
| `settings.toml` | 启动级参数（`[settings]` 表，非密钥） | 键映射成 `ARIS_<KEY>` 后由 pydantic-settings 读（`config.py`） |
| `secrets.toml` | 密钥，键名**就是**环境变量名 | `setdefault` 进 `os.environ`（`config.py`） |
| `providers.toml` | LLM 提供方（base_url / key 环境变量名 / 超时 / transport / 模型） | `core/llm/config.py`；`ARIS_LLM_PROVIDERS_FILE` 可覆盖路径 |
| `<module>.toml` | 模块可调参数（chat / search / logging / audit / notify / serve / knowledge / store / webui / mcp） | `cfgtoml.load_config`（tomllib） |
| `modules.toml` | 模块开关（`[modules]`，7 个业务模块，缺键=true） | `modules.py`；serve 装配 / `aris modules` |

## 优先级

```
代码内 dataclass 默认值  <  随包种子模板  <  data/config/*.toml  <  进程环境变量
```

- 缺文件、缺键、解析失败：**静默用默认值**并记 warning，不抛异常。
- `data_dir` 不写进 TOML：只认进程环境变量 `ARIS_DATA_DIR`（否则鸡生蛋）。
- 提供方的 `api_key_env` 直读 `os.environ`，所以 `secrets.toml` 会被 setdefault 进环境变量；
  进程环境变量优先，可临时覆盖：`DEEPSEEK_API_KEY=... uv run aris serve`。
- **不再有 `.env`**（v0.4.4 起）：配置一律 TOML，密钥只进 `secrets.toml`。

## 模块级加载（`cfgtoml.py`）

```python
from dataclasses import dataclass

from aris.infra.toml import load_config


@dataclass
class SearchConfig:
    timeout_seconds: float = 15.0  # 代码内默认值兜底
    results_count: int = 5


_search_config = load_config(SearchConfig(), "search.toml")
```

- `config_path(filename)`：用户文件优先，缺失时退回种子模板，两者都没有返回 `None`。
- 覆盖规则：与 dataclass 字段**同名**的顶层键覆盖默认值；不做类型校验。
- 模块级单例在 import 时读，因此 `serve.assemble()` 先播种配置、再 import 各模块。

## 模块开关（modules.toml）

- `[modules]` 表，7 个业务模块：store / knowledge / mcp / behavior / webui / character / voice；缺键 = `true`。
- 关闭 = `serve.assemble()` **不 import** 该模块（模块服务在 import 时自注册，所以必须先读开关再 import）。
- `aris modules enable|disable` 只改 TOML 布尔值（保留注释），**下一次启动生效**，不动运行中的进程。
- 依赖关系：`knowledge → store`、`webui → store + knowledge`；依赖被关时依赖方级联关闭，
  serve 记 error 日志并把对应启动步骤标 skipped，**不退出程序**（required 仍只有启用 store 时的 `store.db`）。
- `knowledge.toml` 不再有 `enabled`（v0.4.4 W3 并入 modules.toml）。
- 只读事实：`aris modules list|status`、`aris config path|list|show|validate|env`、`aris info`

## 收口原则（2026-08-12 定案，2026-10 沿用）

- **枚举 → 代码内 `StrEnum`**（逻辑类型，不进配置）：`MessageRole` / `LoopEventType` /
  `TransportKind` / `ApiFormat` / `FinishReason` / `WebSearchResultType` / `AuditKind`。
- **实现细节 → 模块顶部常量**（无人会调）。
- **真正可调参数 → `data/config/<module>.toml`**；新增时先在模块加 dataclass 字段，
  再把默认模板放进 `src/aris/seed/config/`，不新增环境变量入口。
- **密钥永远只在 `data/config/secrets.toml`**；其他 toml 只写 key 的环境变量名。

## 新增配置的步骤

1. 模块加 `@dataclass` 字段（带默认值）+ `load_config(...)` 模块级单例。
2. `src/aris/seed/config/<module>.toml` 补键（可省，代码默认值兜底）。
3. 本文件登记该文件与字段含义。
4. 打包无需改动：`seed/config/*.toml` 已进 `package-data`。
