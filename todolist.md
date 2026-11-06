# 待办事项

> 排名不分先后

- [] Bug fix
- [] WebUI重整，分为Dashboard与WebChat
- [x] 宣布项目公开
- [] 基于MyGO框架的GUI
- [] 对于发行版进行软件包打包（GUI）之后
- [] .desktop文件（同样在GUI之后）
- [] Live2D 支持（v1 不做，GUI 之后）
- [] 记忆系统和角色系统
- [x] 迁移config至data
- [] 全新的备份系统
- [] WebUI设置界面，分开简单设置和高级设置
- [p] 项目标准化（CI 已随 v0.4.5 落地；文档重整余下部分在 v1.x）
- [] 许可证合规（NOTICE + 第三方许可清单、发行物附 COPYING、WebUI 关于页源码链接）
- [] 文档重整
- [x] git中取消跟踪docs/archive
- [x] 全面取消多配置地点，配置完全归于data/config/*.toml（.env也迁移）
- [] 密码和api key 加密
- [] v1.0.0后续版本如果有破坏性更新，需支持老版本向新版本迁移（用户同意后）
- [] memory-lite和sqlite
- [] 给予用户更多可设置项
- [] 插件系统（参考Astrbot,由于我们使用cmcb但别人不一定，而且不一定所有人都愿意用cmcb,因此需要提供兼容层）→ **v1.1**（v1.0 不做，草案在 `docs/process/v1.1-plugin-system.md`）
- [] autorun自动任务
- [] 消息平台连接（做的话先做OneBot v11）
- [] 多模态、全模态模型支持
- [] 决策模型支持（自主回复 / 自主操作门控；不做主模型兜底，密集消息攒批）
- [] v1.x：借鉴 SurfCore（Mieksido/surfcore，v1.0 之后到 v2 之前，不进 v1.0 核心决策）
- [] v1.x：主管理员账户（人格化管理员提示注入）
- [] v1.x 评估：生活化主动联系（状态/日程/关系 → 行为候选；v1.0 的主动联系只走 autorun + 决策模型）
- [] v1.x：群聊全量历史持久化 + 工具查询
- [] v1.x 候选：回复拆多条（模型分段）、情绪/状态记忆
- [] v1.x：插件 LLM/结果钩子扩到 AstrBot 全量（on_waiting、工具前后、agent 开始/结束、消息发送后等）
- [] v1.x：知识库 rerank（成本敏感，v1 只留接口默认关）
- [] v1.1：文档站（VitePress）+ 域名
- [] v1.1：aarch64 / 交叉编译、deb / AppImage / Windows 打包
- [p] 制作图标与更改项目定义
- [x] 开发流程文档（从创建分支到更新版本）
- [] 制作宣传视频
- [] 统一连接路径&接入点
- [] LLM连接与提供商完全重构
- [] LLM fallback 按 D9 收敛（删竞速、免费优先、关双层重试、空输出重试）
- [] 知识库分组
- [] 日志优化（可读性与检索）
- [] 加强路径守卫测试（只白名单 `paths.py`；覆盖 f-string / 字符串拼接；扫描 templates 与脚本）
- [] 知识库二期
- [] 知识库-lite（不依赖 embedding 的纯关键词版；方案未定，v1 不做）
- [] 从zip导入skills
- [x] 切换项目许可证为AGPL
- [x] 增加只在develop发布的alpha-渠道
- [] 彩蛋
- [p] 模块开关&工具开关
- [] 取消models.dev获取元信息，直接从提供商获取（以及参考astrbot）
- [] 买域名，将文档站提上议程
- [x] 将项目名正式修改为Aris Project(与Project AIRI作出区别),并将项目移入Github组织
- [x] 定v1大版本开发代号为"跨越"("Cross")


---

## 备注（2026-10-28 定）

> 上方条目保持原样，这里只记阶段划分与已定决策。

### 两阶段
- **阶段一 beta-v0.4.3 → 正式 v0.4.4（地基版）**：路径与配置收口、CLI 事实入口、模块开关、退休机制退役、工程小件。不承诺旧数据 / 旧配置兼容。
- **阶段二 alpha-v0.4.6 → 正式 v1.0.0**：项目标准化、备份系统、WebUI 重整与设置页、统一连接路径、LLM 提供商重构、memory / 角色、打包与 GUI、公开。

> 阶段一（v0.4.4）已完成；阶段二进行中，施工入口见 `docs/process/v1.0.0-prep.md` 与 `docs/process/v1/`。

### v0.4.4 范围（W1–W6）
1. **W1 统一数据目录**：新增 `paths.py`；解析顺序 `ARIS_DATA_DIR` > 开发树 `./data` > 安装 `~/.project-aris`（2026-11-06 起安装态改为 `~/.aris-project`，见下文「安装态数据目录」）；清除硬编码；加守卫测试；`aris info` 打印解析结果。
2. **W2 配置收口**：`data/config/` 为运行时权威，模板随包（`src/aris/seed/config/`）首次幂等播种；**`.env` 不搬家，改为 TOML 并入 `data/config/`**（不再保留 `.env`；拆 `settings.toml` + `secrets.toml`，后者 0600；加载器改为「先读 TOML，再把 key 字段 setdefault 进 `os.environ`」以保住 provider 的 `api_key_env` 链路）；删除 `.env.example`，变量清单由 `aris config env` 只读展示；**不做自动迁移**（v1.0 前不承诺兼容）；同批改 `README.md` 快速开始——去掉 `cp`，目标形态是 `uv sync && uv run aris serve` 一条命令。
3. **W3 CLI 事实入口**：`aris info` / `aris config path|list|show|validate`（只读，不写配置）/ `aris modules list|status|enable|disable`；模块开关 7 个（store / knowledge / mcp / behavior / webui / character / voice），`modules.toml` 统一，`knowledge.toml.enabled` 并入；关闭时日志报错、不退出程序。
4. **W4 架构原则落地**：`serve` 只做组装与启动，**任何模块不得 import serve**；`get_runtime` 等运行时对象移到 `behavior/runtime.py`；加守卫测试。
5. **W5 LLM 退休机制退役**：`fetch` 只把同步后消失的模型写入 `data/state/llm-list-missing.json`，`aris llm missing list` 与 WebUI 只读查看。
6. **W6 工程小件**：AGPL-3.0-or-later、alpha 渠道（占号）、`git rm -r --cached docs/archive`、`docs/dev-flow.md`（人类文档）、`CLAUDE.md -> AGENTS.md` 软链。

### 已消歧
- 模块开关按模块粒度；工具开关 v1.0 再做（`ToolSpec.enabled` / `owner` 地基已存在）。
- 用户主动关闭的模块被依赖时：**记 error 日志、跳过依赖方，不退出程序**；`required` 只保留 `store.db`。
- CLI 不负责配置写入（查看 / 校验即可，编辑交给编辑器）。
- alpha tag 形如 `alpha-vX.Y.Z`，只在 develop，**占用数字线**。
- 旧配置 / 旧 `.env` 的迁移与兼容性：v1.0+ 再做。
- `.env` 的去向是**转成 TOML 并入 `data/config/`**，不是原样搬进 `data/`；拆分方案已定：`settings.toml`（启动参数）+ `secrets.toml`（密钥，0600）。
- 图标、CI、项目标准化、彩蛋、备份、公开：v1.0 或之后。

### 仓库形态（2026-10-29 定）
- **单仓多构建单元**：`src/aris/` 后端；`gui/` 桌面 / 前端（独立 `package.json` 与 lock）；`docs/` 文档站（VitePress，独立 lock）；`packaging/` 发行配方。GUI、文档站都不拆仓库。
- **构建隔离**：普通 `uv sync` 不装 Node、不构建 GUI；仅发版时设 `ARIS_BUILD_GUI=1`，通过构建钩子把 `gui/dist` 打进发行物（参照 AstrBot 的 dashboard）。
- **发行包**：包名 `ariscore`，两个命令 `arisp`（后端）/ `arisp-gui`（桌面壳，依赖后端）；
  `arisp` 入口显式注入 `ARIS_DATA_DIR`。同仓、同 CI、共用 `__version__`。
  安装布局与首启流程见 `v1.0.0-prep.md` §4.15 与 `docs/process/v1/S13-packaging.md`。
- **何时升级 workspace**：GUI 拆成多个 JS 包、或后端确需拆 `core` / `store` 时，改用 uv workspace / pnpm workspace，仍是单仓，不拆多仓。
- **仓库体积**：大资产（图标源文件、宣传视频、截图）走 release 附件，不进 git；`docs/archive` 按计划取消跟踪。

### 安装态数据目录（2026-11-06 定）
- **包安装**用 `~/.aris-project`；**源码树**用项目根下的 `data/`。
- 解析顺序 `ARIS_DATA_DIR` > 开发树 `./data` > `~/.aris-project`；不做 XDG、不上 Flatpak
  （参考：AstrBot 桌面包用 `~/.astrbot`）。
- **本项目不上 Flatpak**（开发者 2026-10-30 明确），所以 XDG 的沙箱优势不成立，主要看备份与习惯。
- 决定后只需改 `paths.py` 一处 + `tests/test_paths.py` + 施工文档。

### v0.4.4 施工进度（已发布）
- W1–W6 已完成，`v0.4.4` 于 2026-10-30 发布（施工文档已归档）。
- 技术债（建议项，本阶段未做）：`cli.py` 拆包；模块开关测试的总线快照隔离（3.5）。

## v0.4.5 标准化（v1.0 开发正式启动前必须完成）

> 目标：让项目看起来与维护方式符合「标准开源项目」。CI/CD 与 i18n 不在本阶段（v1 期间做）。

### A. 提交记录（head / body / footer）
- [x] 规则写清：AGENTS.md §8、docs/dev-flow.md §4（footer：Refs / Closes / BREAKING CHANGE / Co-authored-by）
- [x] commit-msg hook 增加 footer token 白名单校验（仅在有 footer 时校验，避免误伤）
- [x] 新提交按规则带 footer（有可关联 issue/PR 时；没有可关联内容不硬凑）

### B. 文档
- [x] changelogs（README + 0.4.4 + unreleased）
- [ ] CONTRIBUTING.md / SECURITY.md **保留 0 字节占位**，v1 P7 按「面向人类、不引用 AI 文档」重写正文
- [ ] 用户文档体系：docs/zh（与 docs/en）→ **v1.1 随文档站一起做**
- [x] README 升级：简介、快速开始、许可证与徽章（v0.4.5）；截图与文档索引 → v1.1
- [x] forAiDoc 清理：skills-backup、discuss-2026-09-28.md、Project-Aris.drawy、PLUGIN、DOCS-SITE、
      SECURITY-AND-REFACTOR-PLAN、referenceDocumentation、v0.4.4 施工文档 → `docs/archive/`（本机保留、不再跟踪）
- [x] 0.4.5.1：归档 `V1.0-PLAN.md`，同步 AGENTS §10 / §12；`WEB-SEARCH` / `EMBEDDING` /
      `TUI-问题修复` 的重写 / 归档要求写进 `docs/process/v1.0.0-prep.md` §10.1

### C. 项目结构
- [x] datadir.py 并入 paths.py（数据目录只有一处来源）
- [x] 顶层基础设施收进 `src/aris/infra/`：paths / settings（原 config）/ toml（原 cfgtoml）/ modules / logging / branding
- [ ] tests/ 按模块分组或加 README；测试支持代码收口到 tests/support → **v1 P7**
- [x] docs/ 目录边界：`forAiDoc`（AI 契约）/ `process`（阶段过程）/ `archive`（本机存档，不随仓库）；
      用户/开发文档语言结构随 v1 文档站一起规范（docs/zh、docs/en）
- [x] oldWish 迁出主仓库：独立仓库在 `data/temp/oldWish`（带历史），主仓库与 fork 已删除该分支

### D. CI/CD（v1 期间）
- [x] CI：PR 与 develop / main 推送跑 ruff / mypy / pytest；发版 PR 加真库 + embedding；alpha tag 跑 smoke（v0.4.5）
- [x] 0.4.5.1：修 `check` 的 PG 探针假失败；`integration` 用 `ARIS_PG_SOURCE=project` 强制便携 PG
- [ ] 打包（wheel + 可选 GUI）后加构建 / release 产物步骤
- [ ] CD：tag 触发构建与发布（等发行包形态稳定）

### E. i18n（v1 期间）
- [ ] 用户可见文案集中到常量 / 资源（先做后端，不引框架）→ **v1 P7**
- [ ] 至少支持中 / 英；后续再评估其它语言 → **v1 P7**

### v0.4.5 施工进度（已发布）

- 2026-11-01 发布 `v0.4.5`（tag `v0.4.5`）：W1 变更记录、W2 CI 分档、W3 发版脚本、W4 文档与合规。
- 发版时 `main` 上还没有 workflow，首次 release PR 走了 bypass 合并（bootstrap）；此后按正常 auto-merge。
- 遗留：`check` 的 PG 探针假失败、`integration` 选中系统 PG 缺 pgvector——均在 0.4.5.1 修复。
- 本版不做：`session_cooldown_days`（代码里尚无消费方，留到 v1 会话落地）、GitHub Release、打包、文档站、i18n。

### v0.4.5.1 收尾（2026-11-03）

- [x] 修 `check`：`test_probe_runnable_real_binary` 的跳过条件移到用例内（模块级 `skipif` 早于 fixture）
- [x] 修 `integration`：新增 `ARIS_PG_SOURCE=auto|project|system`，CI 设 `project` 强制走 `data/pg`
- [x] `docs/dev-flow.md`：修正 fork PR workflow bootstrap 的错误陈述；`gh` 命令改为网页优先
- [x] `PROGRESS.md`：刷新到 0.4.5 / 0.4.5.1
- [x] `todolist.md`：结算 v0.4.5（文档体系与 i18n 移交 v1.x）
- [x] `V1.0-PLAN.md` 归档，AGENTS §10 / §12 同步
- [ ] 发版：`bash scripts/release.sh 0.4.5.1` → 归档 `[0.4.5]`、封 `[0.4.5.1]` → PR → tag

- v1.0 决策收敛（2026-11-03）：记忆系统对外名 APEMS、插件推迟 v1.1、决策模型去掉 `main_llm`、
  记忆晋升与共享额度、配置档 `serve`/`webui` 不随档等，详见 `docs/process/v1.0.0-prep.md`。
