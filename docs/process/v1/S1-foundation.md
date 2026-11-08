# S1 契约与地基

> 状态：可开工（§6 的问题已答；2026-11-07 方案 D 落定）
> 代码入口：`src/aris/infra/`（config_items / components / toml / settings / branding）、`src/aris/i18n/`、`src/aris/behavior/registry.py`、`src/aris/cli.py`
> 事实查看：`config.items`（总线服务）、`aris config list`、`aris components list`、`aris tools list`
> 上游契约：`docs/process/v1.0.0-prep.md` §3.3（配置项元数据）、§3.8（外部组件清单）、§4.13（工具开关）、§4.17（i18n）、§4.18（品牌）

## 1. 一句话

把**后面每个批次都要踩的四样地基**立起来：配置项元数据（设置页 / CLI / 文档共用一套事实）、
外部组件清单（PG / embedding 的版本与校验值集中一处）、i18n 基建（新文案一律走 `t()`）、
工具开关（`ToolSpec.enabled` 接到配置与 CLI）。
这一批**不做设置页、不做写回、不做前端**——那些在 S8。

## 2. 出口条件（DoD）

| # | 验收 | 命令 / 判据 |
|---|---|---|
| 1 | 模块启用与否，配置项**都能**被列出；键名唯一、默认值来自代码 | `config.items` 返回被关闭模块的项并标注；`as_dict()` 可 JSON 序列化 |
| 2 | 元数据与代码不漂移 | `tests/test_config_items.py` 全绿（覆盖 / 唯一 / 默认值） |
| 3 | 新文案都能走 `t()`，切换语言生效 | `ARIS_LANGUAGE=en aris info` 输出英文（`doctor` 自身行同理；模块探针行 S1 不翻）；缺 key 回退 `zh-CN` 并记 DEBUG |
| 4 | 工具开关能持久化并影响工具面 | `aris tools list` 显示启停；关掉的工具不出现在 `definitions()`，`tools.execute` 拒绝 |
| 5 | 品牌只在一处 | `grep -rn "Aris Project" src/ pyproject.toml` 只剩 `branding.py`（模板渲染点除外） |
| 6 | 外部组件版本只在一处 | `grep -rn "bekko-embedding" src/` 只剩 `infra/components.py`；`store/bootstrap.py` 里无版本 / 校验常量；`aris components list --json` 可解析 |
| 7 | 全检通过 | `bash scripts/check.sh` |
| 8 | 关闭模块的 import 不产生注册副作用 | `tests/test_import_isolation.py`：import `aris.store` / `aris.knowledge` / `aris.mcp` / `aris.webui` / `aris.character` / `aris.behavior` 后，`services()` 不含这些模块的服务；`knowledge` 迁移未登记 |

## 3. 任务

### T1 配置项元数据（Lead）

**新增** `src/aris/infra/config_items.py`：

- `Item(...)`：只写「额外语义」（`section` / `control` / `apply` / `required` / `auto_empty` /
  `secret` / `hidden` / `min` / `max` / `step` / `pattern` / `condition` / `options` / `collapsed`）；
- `config_file(filename, *, scope, exclude=())`：登记「配置类 ↔ toml 文件」，类定义处装饰；
- `iter_items()`：键名、类型、默认值、选项全部从注解与字段推导（`Annotated` 里的 `Item` 可选）；
- `ConfigItem.as_dict()`：给 `config.items` 总线服务 / 前端用（Path / Enum 转 JSON 安全值）；
- `load_all()`：按**固定清单** import 各配置模块，**不看模块开关**（要求 1 的前提）。
  只做 import，不跑 serve 步骤、不连库。
  - **清单放顶层 `src/aris/config_registry.py`**（2026-11-07 定）：`infra/config_items.py` 只留机制
    （`Item` / `@config_file` / 注册表 / `iter_items` / `CATEGORY_MAP`），不能反过来 import 业务模块
    （AGENTS §4）；也不能靠 `serve.assemble()`——它尊重模块开关，关掉的模块根本不会 import。
  - **注册改显式（2026-11-07 定，方案 D）**：可关模块的 `__init__.py` 只做定义 / re-export，
    **不** `provide()`、**不** import `migrations`；`provide()` 与迁移登记收进模块级 `register()`，
    由 `serve.assemble()` / `cli.main()` 按模块开关显式调用。`load_all()` 只 import
    `<module>/conf.py`，不会把关闭模块的服务 / 工具 / 迁移带进来。
    - 覆盖：`store` / `knowledge` / `mcp` / `webui` / `character` / `behavior`（`skills` 服务）。
      `core` 是常驻基础设施，不受模块开关控制，保持 import 即注册。
    - `serve/steps.py` 的 `REQUIRED_SERVICES` 仍从包 `__init__` 读；`serve.assemble()` 负责
      import 后调用 `register()`。
    - 代价：`tests/test_store.py::test_store_services_registered` 改成显式 `register()`；
      AGENTS §6 与 `docs/forAiDoc/CMCB.md` 的注册约定同步更新。
  - **剩余要求**：包 `__init__` 仍会拉重依赖（FastAPI / LLM engine / TUI），单进程全量 import
    实测约 +0.5~0.8s；S1 只要求不连库、不联网，不优化这部分耗时。
  - 防漂移：AST 测试扫 `@config_file(` 的宿主模块，必须都在 `CONFIG_MODULES` 里。
- **tab / section id（2026-11-07 定）**：一律**英文 slug**（`chat` / `models` / `memory` /
  `knowledge` / `storage` / `network` / `logs` / `ui`）；显示名走 i18n
  （`config.tab.<id>` / `config.section.<id>`），id 不随语言变。
- **label / desc 命名空间（2026-11-07 定）**：新增 `config` 命名空间；键用**扁平点号**
  （`config.chat.temperature.label` / `.desc`），不嵌套。
- **`condition` / `section_condition`（2026-11-07 定）**：S1 只落字段，先不接真实条件；
  等 S8 设置页真正需要成对显隐时再定义语义与测试。
- **`config.items` 总线服务（2026-11-07 定）**：S1 就 `provide`，S8 设置页只做消费；
  S1 的验收靠 `iter_items()` / `as_dict()` 与测试，不靠 CLI 子命令。

**配置类归位**：没有 `conf.py` 的模块先把配置 dataclass 抽到 `<module>/conf.py`
（已有：`store/conf.py`、`knowledge/conf.py`、`serve/conf.py`、`mcp/conf.py`），
给 `load_all()` 一个稳定的纯配置入口（包 `__init__` 仍会执行，但已无注册副作用）：

| 新文件 | 从哪搬 | 内容 |
|---|---|---|
| `chat/conf.py` | `chat/session.py` | `ChatConfig` |
| `behavior/conf.py` | `behavior/loop.py`、`behavior/search/base.py`、`behavior/tools/http_request.py` | `LoopConfig`、`SearchConfig`、`HttpRequestConfig` |
| `core/conf.py` | `core/audit.py`、`core/llm/notify.py` | `AuditConfig`、`NotifyConfig` |
| `webui/conf.py` | `webui/__init__.py` 的 `_resolve_bind` 内联类 | `WebUIConfig` |

> 搬完原模块 `from .conf import X` 即可；不保留同名再导出（避免两份）。

**登记表**（一个文件可挂多个类）：

| 文件 | 类 | scope |
|---|---|---|
| `chat.toml` | `ChatConfig`、`LoopConfig` | profile |
| `search.toml` | `SearchConfig`、`HttpRequestConfig` | profile |
| `audit.toml` | `AuditConfig` | profile |
| `notify.toml` | `NotifyConfig` | profile |
| `logging.toml` | `LoggingConfig`（`infra/logging.py`） | profile |
| `store.toml` | `StoreConfig` | profile |
| `knowledge.toml` | `KnowledgeConfig` | profile |
| `settings.toml` | `Settings`（**pydantic**，排除 `data_dir`） | profile |
| `serve.toml` | `ServeConfig` | global |
| `webui.toml` | `WebUIConfig` | global |
| `mcp.toml` | `McpConfig`（排除 `servers`） | global |

**表 / 数组字段**：`store.mirror`、`serve.skip`、`mcp.servers` 这类结构化配置不进通用设置页
（§3.3「通用设置页只覆盖扁平键值」）。`mcp.toml` 的 8 个超时 / 退避字段**登记 + `Item(hidden=True)`**
（2026-11-07 定）：CLI 可见，MCP 页复用同一份元数据，通用设置页不渲染。

**生效方式**：S1 没有任何模块提供 `reload()`，`apply` 一律 `restart`，不标 `hot`。

**CLI**：**不提供 `aris config items`**（2026-11-07 定）。全量元数据只经 `config.items`
总线服务给设置页；CLI 侧保留 `aris config path/list/show/validate`，精细编辑用
vim / nano / sed 直接改 TOML，不再加全量列表命令。

**测试**（`tests/test_config_items.py`）：

- 每个已登记文件都存在于 `src/aris/seed/config/`；
- 键名全局唯一（`chat.toml` / `search.toml` 各挂两个类，重点查撞名）；
- 每条都有 `type` / `default` / `control` / `apply`；
- `Annotated` 解析正确：`X | None` 标 `nullable`，`StrEnum` / `Literal` 出 `choices`；
- `load_all()` 在**没有数据库**时也能跑通；
- 模块开关全关时，`iter_items()` 仍返回全部条目；
- import 可关模块（`aris.store` / `knowledge` / `mcp` / `webui` / `character` / `behavior`）后，
  `services()` 不出现这些模块的服务，`knowledge` 迁移未登记（`tests/test_import_isolation.py`）。

### T2 i18n 基建（Lead）

- `src/aris/i18n/__init__.py`：`t(key, **params)`、`set_locale()` / `current_locale()` /
  `detect_locale()`、按命名空间懒加载、缺失 key 回退 `zh-CN` 并记 DEBUG；`zh-CN` 也没有时返回 key 本身。
- `src/aris/locales/{zh-CN,en}/{common,nav,settings,errors,cli,config}.json`；`config` 是新增命名空间，
  装配置项的 `config.<key>.label` / `.desc`、`config.tab.<id>` / `config.section.<id>`（T1 用）；
  键一律扁平点号，不嵌套。
- **语言来源（2026-11-07 定，不做 `--lang`）**：
  1. 进程环境 `ARIS_LANGUAGE`（临时覆盖；`[settings]` 键本来就映射成 `ARIS_<KEY>`）；
  2. `settings.toml` 的 `language = "auto" | "zh-CN" | "en"`（**随档**）；
  3. `auto` 按 POSIX 顺序读 `LC_ALL` → `LC_MESSAGES` → `LANG`，取第一个非空：`zh` 开头 → `zh-CN`，
     其它 → `en`；**全未设置也回退 `en`**。
- **S1 的 en 范围（2026-11-07 定）**：只做 **CLI**（`cli` 命名空间 + `aris info` / `doctor` 自身行）；
  WebUI 与配置项 `label` / `desc` 的 en 留到 S14，先留好命名空间与 `t()` 口子。
  zh-CN 的配置项文案在 T1 必须全填（缺 key 测试会红）。
- **`doctor` 改用 `print` 输出**（2026-11-07 定）：命令结果是用户可见输出，走 `t()`，去掉时间戳与级别；
  `loguru` 只留真正的诊断日志，日志消息**不翻**。模块探针行由 `serve/steps.py` 给出，S1 不翻。
- Jinja 注入全局 `t()` + `<html lang>` + `window.__ARIS_I18N__`（只注入当前页命名空间）→ **S2 外壳**。
- **不翻**：日志消息、LLM 工具描述、模块探针文案（§4.17 / §4.20）。

### T3 工具开关（可外包，Lead 复核）

- 种子 `src/aris/seed/config/tools.toml`（随档），**只记关闭项，缺失 = 全开**：

  ```toml
  [disabled]
  tools = ["web_search"]
  ```

- **不表达 owner**：按 owner（整个插件）开关属于插件系统（v1.1）；模块级整块关由 `modules.toml` 负责。
- `behavior/registry.py` 注册时按配置设 `enabled`；**关掉 = 移出模型工具面 + `tools.execute` 拒绝（记 warning）**。
- **从属显示**：`register_declared_tools` 探询 `<模块名>.ai_tools` 时，`spec.owner` 为空就用服务名前缀补；
  内置工具由 behavior 显式填 `behavior`。来源只读展示，**不进 `tools.toml`**。
- `aris tools list` 增加「状态（启用 / 关闭）」与「来源（builtin / knowledge / mcp / 插件）」两列；
  加 `--json`（WebUI 工具页要用，CLI ≥ WebUI）。
- `[disabled].tools` 里出现未注册的名字只记 warning、保留原值（插件 / 模块可能暂时关闭），不自动清理。
- 开关在装配（注册）时生效，S1 不提供热重载；改了 `tools.toml` 需重启。
- **不做**工具管理页（S2 外壳之后，页面在侧栏「工具」分组下）。

### T4 品牌尾巴（可外包）

- `src/aris/infra/branding.py` 是唯一来源（已有 `APP_NAME` / `GITHUB_URL`）；
- 清理：`*.egg-info` 残留、模板 / 文案里硬编码的项目名与仓库地址；
- **`pyproject.toml` 的 URL 是唯一例外**（2026-11-07 定）：PEP 621 不支持动态 `urls`，它读不了
  `branding.py`；在文件里加注释指向 `branding.py`，发版前人工对一次。
- 代码标识（`import aris`、命令 `aris`、`ARIS_` 前缀、`data/`）**不动**。

### T5 旧文档清理（2026-11-04 定：不在 S1）

文档仍在演进、文档站也还没做，集中清理**推迟到想起来 / 真要动它时**，见 `v1.0.0-prep.md` §10.1。
S1 不碰这块。

### T6 外部组件清单（Lead）

**新增** `src/aris/infra/components.py`：PG / pgvector / micromamba / embedding 模型的
来源、版本、校验值集中在这里（`v1.0.0-prep.md` §3.8 已定格式与范围）。

- **形状**：三种 frozen dataclass + 模块级元组，不硬塞一个结构——
  `Archive`（`base_url` + 按平台文件名 + 按平台 sha256）、
  `CondaPackage`（`id` / 精确 `version` / `channel`）、
  `Model`（`repo` / `revision` / `dimension` / `license`）。
- **缺校验就报错**：`require_sha()` 对空串 / 非 64 位十六进制直接抛 `ComponentsError`，
  不允许「跳过校验继续装」。
- **平台键归一**只在这一处：`sys.platform` + `platform.machine()` → `linux-64` / `linux-aarch64`
  （其它平台先明确报「未支持」，不做猜测映射）。
- **收编（同批，不拆开）**：
  - `store/bootstrap.py`：`MAMBA_VERSION` / `MAMBA_URL` / `MAMBA_SHA256` /
    `PG_VERSION` / `PGVECTOR_SPEC` / `CONDA_CHANNEL` 全部删除，改调清单；
    同时修掉 `MAMBA_URL` 的 arch 写死；
  - `store/embedding/local.py`：`DEFAULT_MODEL` / `BEKKO_A25M_DIM` 改为从清单取；
    加载时传 `revision`（**现在读 `refs/main`，是浮动的**，收编时一并修）；
  - `store/conf.py`：`local_model` 默认值改为 `BEKKO_A25M.repo`。
- **embedding 用 HF revision（commit）锁**，不跟 tag；缓存里只有别的 commit 时**不拿它顶替**
  （否则锁 revision 失效），没有就联网取钉住的那个。
- **用户镜像覆盖（2026-11-07 修订）**：**不新增 `components.toml`**；读现有
  `data/config/store.toml` 的 `[mirror]`，只接受 `url`：`"<id>"` = 镜像目录（自动拼官方文件名）、
  `"<id>.<platform>"` = 完整 URL 精确覆盖；`sha256` 永远取清单。镜像必须字节一致。
- **CLI**：`aris components list [--json]`，只读；`doctor` 增一行「清单主版本 vs `data/pgdata` 实际」，
  不一致只 warning（重建数据目录不自动做）。
- **不做**：下载逻辑（留在 `store/bootstrap.py`，这里只是事实）；uv（打包工具，归 S13）；
  STT / TTS / 本地推理运行时（v1 不预留空结构）。

## 4. 不做（明确划线）

- 设置页、元数据写回、`tomlkit`（S8）；
- 配置档目录与迁移（S4）；
- WebUI 外壳 / 样式管线（S2）；
- 插件 / 按 owner 的工具开关（v1.1）；
- 外部组件的下载方式改造（§7-29，S5）；
- 旧文档集中清理（§10.1，不绑阶段）。

## 5. 已知坑

- **注册靠显式 `register()`**：可关模块的 `__init__.py` 不 `provide()` / 不 import 迁移；
  `load_all()` 只 import `<module>/conf.py`，不能指望 `assemble()`——后者尊重模块开关，
  会把被关模块的配置项漏掉。
- **pydantic 的默认值不能受环境影响**：`Settings()` 会读环境变量，列默认值时要取**类字段默认值**，
  不能 `get_settings()`。
- **`WebUIConfig` 现在是内联类**：不抽出来就没法登记。
- **同一 toml 挂多个类**：`chat.toml`、`search.toml` 各有两个类，键名前缀相同，靠字段名区分；
  测试必须兜住未来撞名。
- **`apply=hot` 不能乱标**：模块在 import 时读配置，没有 `reload()` 的模块一律 `restart`。

## 6. 已确认（2026-11-04）

1. **`tools.toml` 结构**：`[disabled] tools = [...]`，**不写 owner**；整插件开关归插件系统（v1.1）。
2. **工具关掉的效果**：移出模型工具面 + `tools.execute` 拒绝（记 warning）。
3. **模块关闭时的 `config.items`**：仍列出并标注「模块已关闭」，因此走独立的 `load_all()`。
4. **旧文档清理**：不在 S1，改为「想起来再做」（§10.1）。
5. **外部组件清单**（2026-11-06）：`src/aris/infra/components.py`，**Python 常量**（不用 TOML），
   v1 只收 **PG + embedding**，排在 **S1**；用户镜像覆盖方向定「允许」但细节待议（§7-28）。
6. **i18n 不做 `--lang`**（2026-11-07）：语言来源 = 进程环境 `ARIS_LANGUAGE` > `settings.toml` 的
   `language` > `auto`；`auto` 按 POSIX 顺序读 `LC_ALL` → `LC_MESSAGES` → `LANG`，`zh` 开头 →
   `zh-CN`，其它（含全未设置）→ `en`。S1 的 en 只覆盖 CLI，WebUI / 配置项文案留 S14。
7. **`doctor` 输出改用 `print`**（2026-11-07）：用户可见结果走 `t()`，日志不翻；模块探针行 S1 不翻。
8. **`load_all()` 清单放顶层**（2026-11-07）：`src/aris/config_registry.py`，`infra` 只留机制；
   AST 测试防新 `conf.py` 漏登记。
9. **mcp 配置项**（2026-11-07）：8 个超时 / 退避字段登记 + `hidden`；表 / 数组字段
   （`store.mirror` / `serve.skip` / `mcp.servers`）不进通用设置页。
10. **S1 执行顺序**（2026-11-07）：T2 i18n → T1 配置项元数据 → T3 工具开关 → T4 品牌。
11. **注册改显式（2026-11-07，方案 D）**：可关模块 `__init__` 不 `provide()` / 不 import 迁移，
    收进模块级 `register()`，由 `serve.assemble()` / `cli.main()` 调用；`load_all()` 只 import
    `<module>/conf.py`。`core` 保持 import 即注册。AGENTS §6 / `docs/forAiDoc/CMCB.md` 同步。
