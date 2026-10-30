# 待办事项

> 排名不分先后

- [] Bug fix
- [] WebUI重整，分为Dashboard与WebChat
- [] 宣布项目公开
- [] 基于MyGO框架的GUI
- [] 对于发行版进行软件包打包（GUI）之后
- [] .desktop文件（同样在GUI之后）
- [] 记忆系统和角色系统
- [] 迁移config至data
- [] 全新的备份系统
- [] WebUI设置界面，分开简单设置和高级设置
- [] 项目标准化（文档重整与CI/CD）
- [] 文档重整
- [] git中取消跟踪docs/archive
- [] 全面取消多配置地点，配置完全归于data/config/*.toml（.env也迁移）
- [] 密码和api key 加密
- [] v1.0.0后续版本如果有破坏性更新，需支持老版本向新版本迁移（用户同意后）
- [] memory-lite和sqlite
- [] 给予用户更多可设置项
- [] 插件系统（参考Astrbot,由于我们使用cmcb但别人不一定，而且不一定所有人都愿意用cmcb,因此需要提供兼容层）
- [] autorun自动任务
- [] 消息平台连接（做的话先做OneBot v11）
- [] 多模态、全模态模型支持
- [] 制作图标与更改项目定义
- [] 开发流程文档（从创建分支到更新版本）
- [] 制作宣传视频
- [] 统一连接路径&接入点
- [] LLM连接与提供商完全重构
- [] 知识库二期
- [] 从zip导入skills
- [] 切换项目许可证为AGPL
- [] 增加只在develop发布的alpha-渠道
- [] 彩蛋
- [] 模块开关&工具开关
- [] 取消models.dev获取元信息，直接从提供商获取（以及参考astrbot）
- [] 买域名，将文档站提上议程
- [] 将项目名正式修改为Aris Project(与Project AIRI作出区别),并将项目移入Github组织
- [] 定v1大版本开发代号为"跨越"("Cross")


---

## 备注（2026-10-28 定）

> 上方条目保持原样，这里只记阶段划分与已定决策。

### 两阶段
- **阶段一 beta-v0.4.3 → 正式 v0.4.4（地基版）**：路径与配置收口、CLI 事实入口、模块开关、退休机制退役、工程小件。不承诺旧数据 / 旧配置兼容。
- **阶段二 alpha-v0.4.6 → 正式 v1.0.0**：项目标准化、备份系统、WebUI 重整与设置页、统一连接路径、LLM 提供商重构、memory / 角色、打包与 GUI、公开。

> 施工文档：`docs/process/v0.4.4.md`（规划完成，未开工）。

### v0.4.4 范围（W1–W6）
1. **W1 统一数据目录**：新增 `paths.py`；解析顺序 `ARIS_DATA_DIR` > 开发树 `./data` > 安装 `~/.project-aris`；清除硬编码；加守卫测试；`aris info` 打印解析结果。
2. **W2 配置收口**：`data/config/` 为运行时权威，模板随包（`src/aris/seed/config/`）首次幂等播种；**`.env` 不搬家，改为 TOML 并入 `data/config/`**（不再保留 `.env`；拆 `settings.toml` + `secrets.toml`，后者 0600；加载器改为「先读 TOML，再把 key 字段 setdefault 进 `os.environ`」以保住 provider 的 `api_key_env` 链路）；删除 `.env.example`，变量清单由 `aris config env` 只读展示；**不做自动迁移**（v1.0 前不承诺兼容）；同批改 `README.md` 快速开始——去掉 `cp`，目标形态是 `uv sync && uv run aris serve` 一条命令。
3. **W3 CLI 事实入口**：`aris info` / `aris config path|list|show|validate`（只读，不写配置）/ `aris modules list|status|enable|disable`；模块开关 7 个（store / knowledge / mcp / behavior / webui / character / voice），`modules.toml` 统一，`knowledge.toml.enabled` 并入；关闭时日志报错、不退出程序。
4. **W4 架构原则落地**：`serve` 只做组装与启动，**任何模块不得 import serve**；`get_runtime` 等运行时对象移到 `behavior/runtime.py`；加守卫测试。
5. **W5 LLM 退休机制退役**：`fetch` 只把同步后消失的模型写入 `data/state/llm-list-missing.json`，`aris llm missing list` 与 WebUI 只读查看。
6. **W6 工程小件**：AGPL-3.0-or-later、alpha 渠道（占号）、`git rm -r --cached docs/archive`、`docs/DEV-FLOW.md`（人类文档）、`CLAUDE.md -> AGENTS.md` 软链。

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
- **发行包**：未来发行包为 `aris`（后端）/ `aris-gui`（桌面壳，依赖 `aris`）；打包后的前端命令是 `paris` / `paris-gui`，入口显式注入 `ARIS_DATA_DIR`（见 `docs/process/v0.4.4.md` D2）。同仓、同 CI、共用 `__version__`。
- **何时升级 workspace**：GUI 拆成多个 JS 包、或后端确需拆 `core` / `store` 时，改用 uv workspace / pnpm workspace，仍是单仓，不拆多仓。
- **仓库体积**：大资产（图标源文件、宣传视频、截图）走 release 附件，不进 git；`docs/archive` 按计划取消跟踪。

### 安装态数据目录（2026-10-30 记录，待定）
- 现状用 `~/.project-aris`（W1 定的），**尚未决定**是否改 XDG（`~/.local/share/aris`）。
- 参考：AstrBot 桌面包用 `~/.astrbot`；AIRI 用 Electron 的 `app.getPath('userData')`（Linux 即 XDG config）。
- **本项目不上 Flatpak**（开发者 2026-10-30 明确），所以 XDG 的沙箱优势不成立，主要看备份与习惯。
- 决定后只需改 `paths.py` 一处 + `tests/test_paths.py` + 施工文档。

