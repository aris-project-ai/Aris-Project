# S1 契约与地基

> 状态：规划中（§6 的四个问题已答，可直接开工）
> 代码入口：`src/aris/infra/`（config_items / components / toml / settings / branding）、`src/aris/i18n/`、`src/aris/behavior/registry.py`、`src/aris/cli.py`
> 事实查看：`aris config items`、`aris config list`、`aris components list`、`aris tools list`
> 上游契约：`docs/process/v1.0.0-prep.md` §3.3（配置项元数据）、§3.8（外部组件清单）、§4.13（工具开关）、§4.17（i18n）、§4.18（品牌）

## 1. 一句话

把**后面每个批次都要踩的四样地基**立起来：配置项元数据（设置页 / CLI / 文档共用一套事实）、
外部组件清单（PG / embedding 的版本与校验值集中一处）、i18n 基建（新文案一律走 `t()`）、
工具开关（`ToolSpec.enabled` 接到配置与 CLI）。
这一批**不做设置页、不做写回、不做前端**——那些在 S8。

## 2. 出口条件（DoD）

| # | 验收 | 命令 / 判据 |
|---|---|---|
| 1 | 模块启用与否，配置项**都能**被列出；键名唯一、默认值来自代码 | `aris config items` 含被关闭模块的项并标注；`--json` 可解析 |
| 2 | 元数据与代码不漂移 | `tests/test_config_items.py` 全绿（覆盖 / 唯一 / 默认值） |
| 3 | 新文案都能走 `t()`，切换语言生效 | `aris --lang en doctor` 输出英文；缺 key 回退 `zh-CN` 并记 DEBUG |
| 4 | 工具开关能持久化并影响工具面 | `aris tools list` 显示启停；关掉的工具不出现在 `definitions()`，`tools.execute` 拒绝 |
| 5 | 品牌只在一处 | `grep -rn "Aris Project" src/ pyproject.toml` 只剩 `branding.py`（模板渲染点除外） |
| 6 | 外部组件版本只在一处 | `grep -rn "bekko-embedding" src/` 只剩 `infra/components.py`；`store/bootstrap.py` 里无版本 / 校验常量；`aris components list --json` 可解析 |
| 7 | 全检通过 | `bash scripts/check.sh` |

## 3. 任务

### T1 配置项元数据（Lead）

**新增** `src/aris/infra/config_items.py`：

- `Item(...)`：只写「额外语义」（`section` / `control` / `apply` / `required` / `auto_empty` /
  `secret` / `hidden` / `min` / `max` / `step` / `pattern` / `condition` / `options` / `collapsed`）；
- `config_file(filename, *, scope, exclude=())`：登记「配置类 ↔ toml 文件」，类定义处装饰；
- `iter_items()`：键名、类型、默认值、选项全部从注解与字段推导（`Annotated` 里的 `Item` 可选）；
- `ConfigItem.as_dict()`：给 CLI `--json` 与前端用（Path / Enum 转 JSON 安全值）；
- `load_all()`：按**固定清单** import 各配置模块，**不看模块开关**（要求 1 的前提）。
  只做 import，不跑 serve 步骤、不连库；代价是各包 `__init__` 会执行一遍（当前无副作用，用测试兜住）。

**配置类归位**：没有 `conf.py` 的模块先把配置 dataclass 抽到 `<module>/conf.py`
（已有：`store/conf.py`、`knowledge/conf.py`、`serve/conf.py`、`mcp/conf.py`），
避免 `load_all()` 去 import 整个业务模块：

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

**CLI**：`aris config items [--json] [--category <file 主名>] [--changed]`，只读。
`--changed` 只比对「当前值 ≠ 代码默认值」，不读写。

**测试**（`tests/test_config_items.py`）：

- 每个已登记文件都存在于 `src/aris/seed/config/`；
- 键名全局唯一（`chat.toml` / `search.toml` 各挂两个类，重点查撞名）；
- 每条都有 `type` / `default` / `control` / `apply`；
- `Annotated` 解析正确：`X | None` 标 `nullable`，`StrEnum` / `Literal` 出 `choices`；
- `load_all()` 在**没有数据库**时也能跑通；
- 模块开关全关时，`iter_items()` 仍返回全部条目。

### T2 i18n 基建（可外包，Lead 复核）

- `src/aris/i18n/__init__.py`：`t(key, **params)`、`set_locale()` / `current_locale()`、
  按命名空间懒加载、缺失 key 回退 `zh-CN` 并记 DEBUG；
- `src/aris/locales/zh-CN/{common,nav,settings,errors,cli}.json` + `en/` 同名骨架；
- 配置项 `language = auto | zh-CN | en`（`settings.toml`，**随档**）；`auto` 读 `LANG`，匹配不到回退 `zh-CN`；
- Jinja 注入全局 `t()` + `<html lang>` + `window.__ARIS_I18N__`（只注入当前页命名空间）；
- CLI 支持 `--lang` 临时覆盖；
- **不翻**：日志消息、LLM 工具描述（§4.17 / §4.20）。

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
- `aris tools list` 增加「状态（启用 / 关闭）」与「来源（builtin / knowledge / mcp / 插件）」两列。
- **不做**工具管理页（S2 外壳之后，页面在侧栏「工具」分组下）。

### T4 品牌尾巴（可外包）

- `src/aris/infra/branding.py` 是唯一来源（已有 `APP_NAME` / `GITHUB_URL`）；
- 清理：`pyproject.toml` 的 URL、`*.egg-info` 残留、模板 / 文案里硬编码的项目名与仓库地址；
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

- **注册表靠 import 填充**：`load_all()` 必须显式 import，不能指望 `assemble()`——后者尊重模块开关，
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
3. **模块关闭时的 `config items`**：仍列出并标注「模块已关闭」，因此走独立的 `load_all()`。
4. **旧文档清理**：不在 S1，改为「想起来再做」（§10.1）。
5. **外部组件清单**（2026-11-06）：`src/aris/infra/components.py`，**Python 常量**（不用 TOML），
   v1 只收 **PG + embedding**，排在 **S1**；用户镜像覆盖方向定「允许」但细节待议（§7-28）。
