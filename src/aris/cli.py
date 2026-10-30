"""CLI 入口（argparse 子命令式）。

现有子命令：
- doctor：环境自检（Python 版本、C 扩展、配置目录）
- llm test：手动验证 LLM 连接（流式对话，用于调试 fallback）
- chat：文字对话（交互循环或单次问答，基于 core/llm）
后续按阶段新增：voice 等。
"""

import argparse
import os
import re
import sys
from pathlib import Path

from loguru import logger

from . import __version__
from .config import get_settings
from .core.llm.config import LLMModel
from .logging import setup_logging


def _cmd_doctor(args: argparse.Namespace) -> int:
    """环境自检：Python 版本、C 扩展可用性、配置与数据目录。"""
    ok = True

    logger.info(f"Aris {__version__}")
    logger.info(f"Python: {sys.version.split()[0]} (需要 >= 3.12)")

    try:
        from aris.csrc import demo_available

        if demo_available():
            logger.info("C 扩展: 已加载（demo.so 可用）")
        else:
            logger.warning("C 扩展: 未加载（未编译 demo.so，主功能不受影响）")
    except ImportError as e:  # 防御：csrc 模块本身异常时降级
        logger.warning(f"C 扩展: 模块异常（{e}），已降级")

    from . import paths

    seeded = paths.seed_config()
    if seeded:
        logger.info(f"配置: 首次播种 {', '.join(seeded)} → {paths.config_dir()}")
    else:
        logger.info(f"配置目录: {paths.config_dir()}")
    if not paths.secrets_file().exists():
        logger.warning("密钥: secrets.toml 缺失（需要 LLM key 时填 data/config/secrets.toml）")

    settings = get_settings()
    logger.info(f"数据目录: {settings.data_dir}")

    # data/ 分层（可迁移性 D14）：必须带的项缺了只提示——首次运行本来就没有
    from .paths import CARRIED_PATHS, missing_carried

    missing = missing_carried(settings.data_dir)
    if missing:
        logger.info(f"分层: 缺 {'、'.join(missing)}（启动时创建 / 首次运行生成）")
    else:
        logger.info(f"分层: {'、'.join(CARRIED_PATHS)} 齐备（换机可整体拷走）")

    # 模块状态：与 `aris serve` 共用同一份探针（不再各写一套自检）
    from .serve import probe_all

    outcomes = probe_all()
    for outcome in outcomes:
        (logger.success if outcome.status == "ok" else logger.warning)(outcome.line)
    failed_required = [o for o in outcomes if o.status == "failed" and o.step.level == "required"]
    if failed_required:
        logger.error(f"{len(failed_required)} 个必需项未就绪，按上面提示处理后重试")
        ok = False

    if ok:
        logger.success("环境自检通过")
    return 0 if ok else 1


def _provider_key_status(provider) -> str:
    """提供方密钥状态文本：[就位] / [缺 key]。"""
    if os.environ.get(provider.api_key_env):
        return f"{provider.api_key_env} [就位]"
    return f"{provider.api_key_env} [缺 key]"


def _format_context(n: int | None) -> str:
    """把 tokens 数格式化为可读文本（200K / 1M / -）。"""
    if not n:
        return "-"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def _cmd_llm_list(args: argparse.Namespace) -> int:
    """列出全部提供方 + 模型 + 密钥状态 + 元数据，默认模型标 [默认]。"""
    from aris.core.llm import load_providers
    from aris.core.llm.config import ProviderConfigError

    settings = get_settings()
    try:
        providers = load_providers(settings.llm_providers_file)
    except ProviderConfigError as e:
        logger.error(str(e))
        return 1
    default_model = providers.resolve_default_model()

    for provider in providers.ordered_providers():
        print(f"提供方: {provider.id} ({provider.name})")
        print(f"  地址: {provider.base_url}")
        print(f"  传输: {provider.transport} | 密钥: {_provider_key_status(provider)}")
        if not provider.models:
            print("  模型: （空）")
            continue
        print("  模型:")
        for m in provider.models:
            marker = "  [默认]" if m.id == default_model else ""
            caps = ", ".join(m.capabilities) if m.capabilities else "-"
            name_col = f"{m.id}{marker}".ljust(34)
            context = _format_context(m.context_length)
            print(f"    - {name_col}  capabilities: {caps:<20}  context: {context}")
    print(f"\n默认模型: {default_model}")
    return 0


def _cmd_llm_check(args: argparse.Namespace) -> int:
    """配置体检：重复 id / order 引用 / 缺 key / 默认模型，有问题非零退出。"""
    from aris.core import call
    from aris.core.llm import manage as _manage  # noqa: F401 —— 触发 llm.providers.* 注册
    from aris.core.llm.config import ProviderConfigError

    try:
        issues = call("llm.providers.check") or []
    except ProviderConfigError as e:
        logger.error(str(e))
        return 1
    if not issues:
        logger.success("LLM 配置体检通过")
        return 0
    for level, message in issues:
        (logger.error if level == "error" else logger.warning)(f"[{level}] {message}")
    err_count = sum(1 for level, _ in issues if level == "error")
    return 1 if err_count else 0


def _cmd_llm_test(args: argparse.Namespace) -> int:
    """手动验证 LLM 连接：流式对话一次，展示 fallback / 错误处理。"""
    from aris.core import call
    from aris.core.llm import LLMEngine, load_providers, plain_chat

    settings = get_settings()
    providers = load_providers(settings.llm_providers_file)
    LLMEngine(
        providers,
        timeout=settings.llm_fallback_timeout,
        first_token_stall=settings.llm_first_token_stall,
        error_message=settings.llm_error_message,
    )

    model_id = args.model or providers.resolve_default_model()
    request = plain_chat(
        model_id=model_id,
        text=args.message,
        system=args.system,
    )
    print("Aris: ", end="", flush=True)
    for delta in call("llm.stream", request):
        print(delta, end="", flush=True)
    print()
    return 0


# ---------------------------------------------------------------------------
# aris llm fetch / aris llm missing list
# ---------------------------------------------------------------------------


def _series_prefix(model_id: str) -> str:
    """模型系列前缀：取 id 第一个 - 前段（如 claude-3 → claude）。"""
    return model_id.split("-", 1)[0] if "-" in model_id else model_id


def _pick_fetch_provider(providers, provider_id: str | None):
    """选择 fetch 目标提供方：显式指定 / default_model 所在 / order 第一个。"""
    if provider_id:
        for p in providers.providers:
            if p.id == provider_id:
                return p
        logger.error(f"提供方不存在: {provider_id}")
        return None
    default = providers.resolve_default_model()
    if default:
        for p in providers.providers:
            if p.get_model(default):
                return p
    return providers.ordered_providers()[0]


def _run_candidate_picker(title: str, candidates: list[LLMModel]) -> set[str] | None:
    """按系列分组分页的勾选列表（prompt_toolkit）。

    按键：↑/↓ 或 j/k 移动，空格 勾选/取消，p/n 翻页，回车 确认，q/ESC 放弃。
    返回勾选的模型 id 集合；放弃返回 None。
    """
    from prompt_toolkit.application import Application
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout

    groups: dict[str, list[LLMModel]] = {}
    for c in candidates:
        groups.setdefault(_series_prefix(c.id), []).append(c)
    pages = [sorted(v, key=lambda m: m.id) for _, v in sorted(groups.items())]
    selected: set[str] = set()
    page, row = 0, 0
    result: set[str] | None = None

    def meta_line(m: LLMModel) -> str:
        ctx = f"{m.context_length // 1000}K" if m.context_length else "-"
        caps = ",".join(m.capabilities) if m.capabilities else "-"
        return f"{m.name}  [ctx {ctx}]  [{caps}]"

    def build_text() -> str:
        items = pages[page]
        lines = [
            f"# {title}",
            f"  页面 {page + 1}/{len(pages)}，系列 {_series_prefix(items[0].id)}，"
            f"已选 {len(selected)} 个",
            "",
        ]
        for i, m in enumerate(items):
            mark = "[x]" if m.id in selected else "[ ]"
            cursor = ">" if i == row else " "
            lines.append(f" {cursor}{mark} {m.id:<28} {meta_line(m)}")
        lines += [
            "",
            " ↑/↓ 或 j/k 移动   空格 勾选/取消   p/n 翻页   回车 确认   q/ESC 放弃",
        ]
        return "\n".join(lines)

    text_control = FormattedTextControl(HTML)

    def set_content() -> None:
        text_control.text = build_text()

    kb = KeyBindings()

    @kb.add("up", "k")
    def _(event):
        nonlocal row
        row = (row - 1) % len(pages[page])
        set_content()

    @kb.add("down", "j")
    def _(event):
        nonlocal row
        row = (row + 1) % len(pages[page])
        set_content()

    @kb.add(" ")
    def _(event):
        mid = pages[page][row].id
        selected.symmetric_difference_update({mid})
        set_content()

    @kb.add("p")
    def _(event):
        nonlocal page, row
        page = (page - 1) % len(pages)
        row = 0
        set_content()

    @kb.add("n")
    def _(event):
        nonlocal page, row
        page = (page + 1) % len(pages)
        row = 0
        set_content()

    @kb.add("enter")
    def _(event):
        nonlocal result
        result = selected
        event.app.exit()

    @kb.add("q", "c-q", "escape")
    def _(event):
        event.app.exit()

    set_content()
    app = Application(
        layout=Layout(HSplit([Window(text_control)])),
        key_bindings=kb,
        full_screen=True,
    )
    app.run()
    return result


def _cmd_llm_fetch(args: argparse.Namespace) -> int:
    """/models 同步：拉取 → 对比 → 勾选/对齐 → 写回（缺失模型记入只读记录）。

    默认 dry-run（只打印 diff 不落盘）；--write 才应用变更。
    """
    from aris.core.llm import load_providers
    from aris.core.llm.config import ProviderConfigError
    from aris.core.llm.errors import AuthError, LLMError
    from aris.core.llm.fetch import (
        apply_sync,
        fetch_provider_models,
        missing_file_path,
        modelsdev_load,
        plan_sync,
    )

    settings = get_settings()
    try:
        providers = load_providers(settings.llm_providers_file)
    except ProviderConfigError as e:
        logger.error(str(e))
        return 1

    provider = _pick_fetch_provider(providers, args.provider_id)
    if provider is None:
        return 1

    print(f"拉取 {provider.id} /models ...", flush=True)
    try:
        endpoint_ids = fetch_provider_models(provider)
    except (LLMError, AuthError) as e:
        logger.error(str(e))
        return 1
    print(f"  端点共 {len(endpoint_ids)} 个模型")

    modelsdev = modelsdev_load(settings.data_dir, refresh=args.refresh)
    plan = plan_sync(provider, endpoint_ids, modelsdev)

    # ---- 打印 diff ----
    d = plan.diff
    print(f"\n对比 {provider.id}（本地 {len(provider.models)} 个）:")
    print(f"  云有本地无（添加候选）: {len(d.added)} 个")
    for mid in d.added:
        print(f"    + {mid}")
    print(f"  两边都有（保留）: {len(d.kept)} 个")
    if d.missing:
        print(f"  本地有云无（→ 移除并记入缺失文件）: {len(d.missing)} 个")
        for mid in d.missing:
            print(f"    - {mid}")

    if not args.write:
        print("\n（dry-run，未写入任何文件；确认后加 --write 应用变更）")
        return 0

    # ---- 选择要添加的候选 ----
    selected: set[str] | None
    if args.add:
        wanted = set(args.add.split(","))
        selected = {c.id for c in plan.candidates if c.id in wanted}
        missing_wanted = wanted - {c.id for c in plan.candidates}
        if missing_wanted:
            logger.warning(f"--add 中不在端点/候选的模型: {sorted(missing_wanted)}")
    elif sys.stdin.isatty() and plan.candidates:
        picked = _run_candidate_picker(f"选择要添加的模型（{provider.id}）", plan.candidates)
        if picked is None:
            print("已放弃，未写入。")
            return 0
        selected = picked
    else:
        selected = {c.id for c in plan.candidates}

    if args.delete:
        selected -= set(args.delete.split(","))

    keep = set(args.keep.split(",")) if args.keep else set()

    # ---- 应用 ----
    recorded = apply_sync(
        plan,
        sorted(selected),
        cfg=providers,
        providers_path=settings.llm_providers_file,
        keep=sorted(keep),
    )
    print(f"\n已写入 {settings.llm_providers_file}")
    print(f"  新增: {sorted(selected)}")
    print(f"  移除(记入缺失): {sorted(set(d.missing) - keep)}")
    print(f"  保留(keep): {sorted(keep)}")
    print(f"  备份: {settings.llm_providers_file}.bak")
    print(f"  缺失记录: {missing_file_path()}（共 {len(recorded)} 条，只读查看）")
    return 0


def _cmd_llm_missing(args: argparse.Namespace) -> int:
    """缺失模型记录：只读列出同步后从端点消失的模型。"""
    from aris.core.llm.fetch import load_missing, missing_file_path

    entries = load_missing()
    path = missing_file_path()
    if not entries:
        print(f"缺失记录为空（{path}）。")
        return 0

    print(f"缺失模型共 {len(entries)} 个（{path}）：")
    for e in entries:
        print(f"  [{e.provider}] {e.model}  (自 {e.last_seen})")
    print("\n只读记录：无宽限期、不自动恢复；模型回到端点后重新同步即可加回。")
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    """启动 WebUI 管理后台（组装走 serve.assemble()，端口探测归 webui 模块）。"""
    from .serve import assemble
    from .webui import start_server

    assemble()
    try:
        start_server(host=args.host, port=args.port)
    except RuntimeError as exc:  # 端口冲突等：给出可读错误而不是栈
        logger.error(str(exc))
        return 1
    return 0


def _split_step_names(raw: str | None) -> list[str] | None:
    """把 `--only a,b` 拆成步骤名列表（去空、去重、保序）。"""
    if not raw:
        return None
    return list(dict.fromkeys(name.strip() for name in raw.split(",") if name.strip()))


def _cmd_serve(args: argparse.Namespace) -> int:
    """一键启动各模块（组装根 / 启动编排；前台运行，Ctrl-C 停止）。"""
    from .serve import serve

    try:
        return serve(
            only=_split_step_names(args.only),
            skip=_split_step_names(args.skip),
            dry_run=args.dry_run,
        )
    except ValueError as exc:  # 步骤名写错：直接报错，不猜用户意图
        logger.error(str(exc))
        return 2


def _cmd_chat(args: argparse.Namespace) -> int:
    """文字对话：有消息参数走单次问答，无参数进入交互循环。

    v1.0 M1：引擎 / 工具注册表 / agent loop 不再在这里自建，走组装根
    `serve.assemble()` 建好的**进程级运行时**（会话与它共享一份）。
    """
    from aris.behavior.runtime import get_runtime
    from aris.chat import ChatSession
    from aris.serve import assemble

    settings = get_settings()
    assemble()  # 幂等；顺带注册 character / skills 等模块级服务
    session = ChatSession(
        runtime=get_runtime(),
        model_id=args.model,  # None → 用 providers 的默认模型
        system_prompt=args.system,  # None 时使用 character 人设（提示词工程）
        data_dir=settings.data_dir,
        thinking=args.thinking,
        tools_enabled=not args.no_tools,
    )
    if args.message:
        print("Aris: ", end="", flush=True)
        for delta in session.ask(args.message):
            print(delta, end="", flush=True)
        print()
        return 0
    return session.repl()


def _db_env_summary(env) -> str:
    """数据库环境一行摘要（来源 / 可执行 / 数据目录 / 端口 / 角色 / 库名）。"""
    bin_dir = str(env.bin_dir) if env.bin_dir else "（未安装）"
    return (
        f"来源: {env.source} | 可执行: {bin_dir} | 数据目录: {env.pgdata} | "
        f"端口: {env.port} | 角色: {env.user} | 库: {env.dbname}"
    )


def _cmd_db(args: argparse.Namespace) -> int:
    """数据库环境管理：init / start / stop / status / psql。"""
    import subprocess

    from aris.store import BootstrapError, bootstrap_env, is_running, start, stop
    from aris.store.pgenv import detect

    env = detect()
    action = args.db_command

    if action == "init":
        try:
            env = bootstrap_env(env)
        except BootstrapError as e:
            logger.error(str(e))
            return 1
        print(_db_env_summary(env))
        return 0

    if action == "status":
        print(_db_env_summary(env))
        if not env.installed:
            logger.warning("PostgreSQL 未安装——运行 aris db init 自动获取便携实例")
            return 1
        running = is_running(env)
        print(f"运行状态: {'运行中' if running else '已停止'}")
        if running and not args.no_probe:
            try:
                from aris.store.db import health

                info = health(env)
            except Exception as e:  # 探活失败只提示，不改 status 的退出码语义  # noqa: BLE001
                logger.warning(f"连接失败: {e}")
            else:
                vector = info["vector_version"] or "未安装"
                print(f"服务端: PostgreSQL {info['server_version']} | pgvector: {vector}")
        return 0

    if not env.installed:
        logger.error("PostgreSQL 未安装，请先运行 aris db init")
        return 1

    if action == "start":
        from aris.store import align_user, choose_port

        env = choose_port(env)  # 端口被占则换一个可用端口（不写配置）
        started = start(env)
        try:
            env = align_user(env)  # 换机后角色名可能与宿主用户名不同，在线复核并写标记
        except BootstrapError as e:
            logger.warning(f"角色探测未完成：{e}")
        state = "已启动" if started else "已在运行"
        logger.info(f"数据库{state}（端口 {env.port}，角色 {env.user}）")
        return 0

    if action == "stop":
        logger.info("数据库已停止" if stop(env) else "数据库本就未运行")
        return 0

    if action == "migrate":
        from contextlib import closing

        from aris.store.db import connect
        from aris.store.migrate import MigrationError
        from aris.store.migrate import run as run_migrations

        if not is_running(env):
            logger.error("数据库未运行，先执行 aris db start")
            return 1
        try:
            with closing(connect(env)) as conn:
                done = run_migrations(conn)
        except MigrationError as e:
            logger.error(str(e))
            return 1
        done_sql = f"：{', '.join(done)}" if done else ""
        print(f"本次应用 {len(done)} 条迁移{done_sql}")
        return 0

    if action == "psql":
        return subprocess.call([str(env.tool("psql")), *args.psql_args], env=env.tool_env())

    logger.error(f"未知的 db 子命令: {action}")
    return 1


def _cmd_knowledge(args: argparse.Namespace) -> int:
    """知识库：add / list / remove / search / reindex。"""
    from aris.modules import module_enabled

    if not module_enabled("knowledge"):
        logger.error(
            "knowledge 模块已关闭（data/config/modules.toml）；"
            "先执行 `aris modules enable knowledge`"
        )
        return 1

    from aris.knowledge import KnowledgeError, get_service

    service = get_service()
    action = args.knowledge_command

    try:
        if action == "add":
            outcomes = service.ingest(args.paths)
            for item in outcomes:
                tail = f"  ({item['reason']})" if item["reason"] else ""
                print(f"{item['status']:>7}  {item['chunks']:>4} 块  {item['path']}{tail}")
            print(f"共处理 {len(outcomes)} 个文件")
            return 0

        if action == "list":
            sources = service.list_sources()
            if not sources:
                print("知识库为空（用 aris knowledge add <路径> 摄入）")
                return 0
            for item in sources:
                print(f"{item['chunks']:>4} 块  {item['bytes']:>9} B  {item['source_path']}")
            print(f"共 {len(sources)} 个文档")
            return 0

        if action == "remove":
            info = service.remove(args.path)
            if info["removed"]:
                print(f"已移除 {info['source_path']}（{info['chunks']} 块）")
            else:
                print(f"未找到活跃文档：{info['source_path']}")
            return 0

        if action == "search":
            result = service.search(args.query, limit=args.top_k)
            if not result["results"]:
                print("无结果")
                return 0
            for hit in result["results"]:
                heading = f" › {hit['heading_path']}" if hit["heading_path"] else ""
                print(
                    f"[{hit['id']}] {hit['source_path']}{heading}  distance={hit['distance']:.4f}"
                )
                print("    " + hit["content"][:200].replace("\n", " "))
            return 0

        if action == "reindex":
            print(f"索引已就绪：{service.ensure_index()}")
            return 0
    except KnowledgeError as e:
        logger.error(str(e))
        return 1

    logger.error(f"未知的 knowledge 子命令: {action}")
    return 1


def _cmd_store(args: argparse.Namespace) -> int:
    """store 模块调试命令：info（配置 + 自检）/ embed（编码文本）。"""
    from aris.modules import module_enabled

    if not module_enabled("store"):
        logger.error(
            "store 模块已关闭（data/config/modules.toml）；先执行 aris modules enable store"
        )
        return 1

    from aris.store.conf import get_store_config
    from aris.store.embedding import EmbeddingError, get_provider

    cfg = get_store_config()

    if args.store_command == "info":
        print(
            f"provider: {cfg.embedding_provider} | model: {cfg.local_model} | "
            f"batch: {cfg.batch_size} | truncate: {cfg.truncate_dim or '-'}"
        )
        provider = get_provider()
        print(f"维度: {provider.dimension}")
        try:
            vectors = provider.embed(["维度探针"])
        except EmbeddingError as e:
            logger.error(str(e))
            return 1
        print(f"自检: 通过（返回 {len(vectors[0])} 维向量）")
        return 0

    texts = list(args.text)
    if not texts and not sys.stdin.isatty():
        texts = [line for line in sys.stdin.read().splitlines() if line.strip()]
    if not texts:
        logger.error("没有可编码的文本：给参数，或从 stdin 逐行传入")
        return 1

    try:
        vectors = get_provider().embed(texts)
    except EmbeddingError as e:
        logger.error(str(e))
        return 1
    for text, vec in zip(texts, vectors, strict=True):
        preview = ", ".join(f"{v:+.4f}" for v in vec[:5])
        print(f"{len(vec)} 维 | {preview} ... | {text[:40]}")
    return 0


def _cmd_tools(args: argparse.Namespace) -> int:
    """tools 命令：list —— agent 工具面清单（registry 全量 + 声明探询失败）。"""
    from aris.behavior.runtime import get_runtime
    from aris.serve import assemble

    assemble()
    try:
        runtime = get_runtime()
    except Exception as exc:  # noqa: BLE001 —— 组装降级时给明确报错而非裸 traceback
        logger.error(f"behavior 运行时未装配：{exc}")
        return 1

    items = runtime.registry.items()
    visible = sum(1 for tool in items if tool.enabled)
    failures = runtime.registry.declaration_failures
    print(f"共 {len(items)} 个工具：模型可见 {visible}，声明探询失败 {len(failures)} 条")
    for tool in items:
        desc = tool.definition.description.replace("\n", " ")
        flag = "" if tool.enabled else "（模型不可见）"
        print(f"- {tool.definition.name} [{tool.owner or 'behavior'}]{flag}: {desc[:76]}")
    for provider, error in failures:
        print(f"! 声明未收编 {provider}: {error}")
    return 0


def _cmd_services(args: argparse.Namespace) -> int:
    """services 命令：list —— 打印全部已注册的 CMCB 总线服务（按模块分组排序）。"""
    from aris.core import services

    names = sorted(services())
    print(f"共 {len(names)} 个总线服务：")
    for name in names:
        prefix = name.split(".", 1)[0]
        print(f"- {prefix:<12} {name}")
    return 0


def _extract_psql_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """摘出 `aris db psql` 之后的参数（原样透传，不参与 argparse）。

    argparse 的 REMAINDER 遇到 `-c` 这类以短横线开头的参数会报
    "unrecognized arguments"，故在解析前手工切分。
    """
    if len(argv) >= 2 and argv[0] == "db" and argv[1] == "psql":
        rest = argv[2:]
        if rest and rest[0] == "--":  # 允许 aris db psql -- -c "..."
            rest = rest[1:]
        return argv[:2], rest
    return argv, []


def _cmd_info(args: argparse.Namespace) -> int:
    """版本 / 路径 / 模块开关等环境事实（只读；健康检查用 `aris doctor`）。"""
    from . import paths
    from .config import get_settings
    from .modules import MODULES, load_modules, resolve_modules

    env = os.environ.get("ARIS_DATA_DIR", "").strip()
    if env:
        source = f"ARIS_DATA_DIR={env}"
    elif paths._find_dev_root_via_cwd() is not None:
        source = f"开发树 {Path.cwd().resolve()}"
    elif paths._find_dev_root_via_file() is not None:
        source = "开发树（按包路径判定）"
    else:
        source = "安装（默认 ~/.project-aris）"

    settings = get_settings()
    state = resolve_modules(load_modules())
    enabled = sum(1 for ok in state.enabled.values() if ok)
    print(f"Aris {__version__}")
    print(f"Python: {sys.version.split()[0]}（需要 >= 3.12）")
    print(f"数据目录: {paths.data_root()}  [{source}]")
    print(f"配置目录: {paths.config_dir()}")
    print(f"状态目录: {paths.state_dir()}")
    print(f"日志目录: {paths.logs_dir()}")
    print(f"配置模板: {paths.SEED_CONFIG_DIR}")
    print(f"providers: {settings.llm_providers_file}")
    print(f"工作目录: {Path.cwd().resolve()}")
    print(f"模块: 启用 {enabled}/{len(MODULES)}（详情 `aris modules list`）")
    return 0


# TOML 里哪些键算密钥（只用于 `aris config show` 脱敏）
_SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|hmac)")


def _mask_toml(text: str) -> str:
    """把 TOML 文本里的密钥值替换为 ***（逐行处理，保留原排版与注释）。"""
    masked: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if _SECRET_KEY_RE.search(key):
                indent = line[: len(line) - len(line.lstrip())]
                masked.append(f'{indent}{key} = "***"')
                continue
        masked.append(line)
    return "\n".join(masked)


def _config_names() -> list[str]:
    """全部配置文件名（种子模板 ∪ 用户目录里的 *.toml）。"""
    from . import paths

    names = {p.name for p in paths.SEED_CONFIG_DIR.glob("*.toml")}
    names |= {p.name for p in paths.config_dir().glob("*.toml")}
    return sorted(names)


def _cmd_config(args: argparse.Namespace) -> int:
    """配置事实（只读）：path / list / show / validate / env，不写任何文件。"""
    from . import paths
    from .cfgtoml import config_path

    command = args.config_command

    if command == "path":
        print(f"配置目录: {paths.config_dir()}")
        for name in _config_names():
            user = paths.config_dir() / name
            if user.is_file():
                print(f"  {name:<22} 用户  {user}")
            else:
                seed = paths.seed_config_file(name)
                print(f"  {name:<22} 种子  {seed if seed is not None else '（缺失）'}")
        return 0

    if command == "list":
        for name in _config_names():
            user = paths.config_dir() / name
            resolved = config_path(name)
            source = "用户" if user.is_file() else "种子"
            has_file = resolved is not None and resolved.is_file()
            size = f"{resolved.stat().st_size}" if has_file and resolved is not None else "-"
            print(f"- {name:<22} {source}  {size:>6} B  {resolved or '（缺失）'}")
        return 0

    if command == "show":
        name = args.name if args.name.endswith(".toml") else f"{args.name}.toml"
        p = config_path(name)
        if p is None:
            logger.error(f"没有这个配置文件：{name}（可用 `aris config list` 查看）")
            return 1
        print(f"# {p}")
        print(_mask_toml(p.read_text(encoding="utf-8")).rstrip())
        return 0

    if command == "validate":
        import tomllib

        from .modules import MODULES, load_modules, resolve_modules

        errors: list[str] = []
        checked = 0
        for name in _config_names():
            for candidate in (paths.config_dir() / name, paths.seed_config_file(name)):
                if candidate is None or not candidate.is_file():
                    continue
                checked += 1
                try:
                    tomllib.loads(candidate.read_text(encoding="utf-8"))
                except (tomllib.TOMLDecodeError, OSError) as exc:
                    errors.append(f"{candidate}: {exc}")

        module_file = paths.config_dir() / "modules.toml"
        if module_file.is_file():
            try:
                table = tomllib.loads(module_file.read_text(encoding="utf-8")).get("modules")
            except (tomllib.TOMLDecodeError, OSError) as exc:
                errors.append(f"{module_file}: {exc}")
                table = None
            known = {spec.name for spec in MODULES}
            if table is None:
                errors.append(f"{module_file}: 缺少 [modules] 表")
            elif not isinstance(table, dict):
                errors.append(f"{module_file}: [modules] 不是表")
            else:
                errors.extend(
                    f"{module_file}: 未知模块开关 {name!r}" for name in sorted(set(table) - known)
                )
                errors.extend(
                    f"{module_file}: {name} 不是布尔值"
                    for name, value in table.items()
                    if not isinstance(value, bool)
                )
        state = resolve_modules(load_modules())
        errors.extend(
            f"模块 {name}: {reason}" for name, reason in state.reasons.items() if "依赖" in reason
        )

        if errors:
            for line in errors:
                logger.error(f"配置校验: {line}")
            print(f"配置校验：{checked} 个文件，{len(errors)} 个问题")
            return 1
        print(f"配置校验：{checked} 个文件全部通过（TOML 可解析、模块开关合法、依赖满足）")
        return 0

    if command == "env":
        from .config import get_settings

        for key, value in get_settings().model_dump().items():
            env_key = f"ARIS_{key.upper()}"
            shown = "***" if _SECRET_KEY_RE.search(key) else value
            print(f"{env_key}={shown}")
        print(f"\n配置文件: {paths.config_dir()}（优先）/ 种子 {paths.SEED_CONFIG_DIR}")
        print(f"密钥文件: {paths.secrets_file()}")
        return 0

    logger.error(f"未知的 config 子命令：{command}")
    return 2


def _cmd_modules(args: argparse.Namespace) -> int:
    """模块开关事实：list / status / enable / disable（写文件，下一次启动生效）。"""
    from .modules import (
        MODULES,
        load_modules,
        resolve_modules,
        set_module_enabled,
        switch_warning,
    )

    command = args.modules_command

    if command in {"enable", "disable"}:
        if not args.name:
            logger.error(f"用法：aris modules {command} <name>")
            return 2
        enabled = command == "enable"
        try:
            path = set_module_enabled(args.name, enabled)
        except ValueError as exc:
            logger.error(str(exc))
            return 2
        print(f"已写入 {path}：{args.name} = {str(enabled).lower()}")
        warning = switch_warning(args.name, enabled)
        if warning:
            print(f"注意：{warning}")
        print("下一次启动生效（不影响当前进程）。")
        return 0

    cfg = load_modules()
    state = resolve_modules(cfg)

    if command == "status":
        for spec in MODULES:
            if state.enabled.get(spec.name, False):
                print(f"- {spec.name:<10} 启用")
            else:
                print(f"- {spec.name:<10} 关闭  ← {state.reasons.get(spec.name, '')}")
        blocked = [n for n, r in state.reasons.items() if "依赖" in r]
        if blocked:
            print("\n依赖未满足（先启用依赖的模块）：")
            for name in blocked:
                print(f"  - {name}: {state.reasons[name]}")
        return 0

    print(f"模块开关（{len(MODULES)} 个；文件 data/config/modules.toml）")
    for spec in MODULES:
        raw = getattr(cfg, spec.name, True)
        enabled = state.enabled.get(spec.name, False)
        mark = "✓" if enabled else "✗"
        deps = ",".join(spec.depends_on) or "-"
        steps = ",".join(spec.steps) or "-"
        print(f"- {mark} {spec.name:<10} 用户={str(raw).lower():<5} 依赖={deps:<12} 步骤={steps}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(
        prog="aris", description="Aris —— 基于大语言模型、类似 Neuro-sama 的赛博生命体"
    )
    parser.add_argument("--version", action="version", version=f"Aris {__version__}")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="在控制台显示 INFO 级别日志（默认只显示 WARNING 及以上，日志全量写文件）",
    )
    sub = parser.add_subparsers(dest="command")

    p_doctor = sub.add_parser("doctor", help="环境自检")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_info = sub.add_parser("info", help="版本 / 路径 / 模块开关等环境事实（只读）")
    p_info.set_defaults(func=_cmd_info)

    p_config = sub.add_parser("config", help="配置事实（只读：path/list/show/validate/env）")
    p_config_sub = p_config.add_subparsers(dest="config_command")
    p_config_path = p_config_sub.add_parser(
        "path", help="打印配置目录与每个文件的来源（用户/种子）"
    )
    p_config_path.set_defaults(func=_cmd_config)
    p_config_list = p_config_sub.add_parser("list", help="列出全部配置文件与大小（只读）")
    p_config_list.set_defaults(func=_cmd_config)
    p_config_show = p_config_sub.add_parser("show", help="打印某个配置（密钥脱敏）")
    p_config_show.add_argument("name", help="文件名，如 settings / settings.toml / secrets")
    p_config_show.set_defaults(func=_cmd_config)
    p_config_validate = p_config_sub.add_parser("validate", help="校验全部 TOML 与模块开关")
    p_config_validate.set_defaults(func=_cmd_config)
    p_config_env = p_config_sub.add_parser("env", help="打印进程最终生效的 ARIS_* 设置")
    p_config_env.set_defaults(func=_cmd_config)
    p_config.set_defaults(func=_cmd_config, config_command="list")

    p_modules = sub.add_parser("modules", help="模块开关（list / status / enable / disable）")
    p_modules_sub = p_modules.add_subparsers(dest="modules_command")
    p_modules_list = p_modules_sub.add_parser("list", help="列出 7 个模块的开关与依赖")
    p_modules_list.set_defaults(func=_cmd_modules)
    p_modules_status = p_modules_sub.add_parser("status", help="按依赖解析后的实际启停与原因")
    p_modules_status.set_defaults(func=_cmd_modules)
    p_modules_enable = p_modules_sub.add_parser(
        "enable", help="启用模块（写 modules.toml，下次启动生效）"
    )
    p_modules_enable.add_argument(
        "name", help="模块名：store / knowledge / mcp / behavior / webui / character / voice"
    )
    p_modules_enable.set_defaults(func=_cmd_modules)
    p_modules_disable = p_modules_sub.add_parser(
        "disable", help="关闭模块（写 modules.toml，下次启动生效）"
    )
    p_modules_disable.add_argument("name", help="模块名（同上）")
    p_modules_disable.set_defaults(func=_cmd_modules)
    p_modules.set_defaults(func=_cmd_modules, modules_command="list")

    p_llm = sub.add_parser("llm", help="LLM 提供方与模型管理")
    p_llm_test = p_llm.add_subparsers(dest="llm_command")
    p_list = p_llm_test.add_parser("list", help="列出提供方与模型（含密钥状态/元数据）")
    p_list.set_defaults(func=_cmd_llm_list)
    p_check = p_llm_test.add_parser(
        "check", help="配置体检（重复 id / 缺 key / 默认模型），有问题非零退出"
    )
    p_check.set_defaults(func=_cmd_llm_check)
    p_test = p_llm_test.add_parser("test", help="手动验证 LLM 连接（流式）")
    p_test.add_argument(
        "--model",
        default=None,
        help="统一模型 id（默认取 data/config/providers.toml 的 default_model）",
    )
    p_test.add_argument("--message", default="用一句话介绍你自己。", help="要发送的用户消息")
    p_test.add_argument(
        "--system",
        default="你是 Aris，一个基于大语言模型、类似 Neuro-sama 的赛博生命体，说话简洁自然。",
        help="系统提示词",
    )
    p_test.set_defaults(func=_cmd_llm_test)

    p_fetch = p_llm_test.add_parser(
        "fetch", help="与 /models 端点同步模型列表（对比/勾选/写回/缺失记录）"
    )
    p_fetch.add_argument(
        "provider_id", nargs="?", default=None, help="目标提供方（默认取 default_model 所在）"
    )
    p_fetch.add_argument("--refresh", action="store_true", help="强制刷新 models.dev 缓存")
    p_fetch.add_argument(
        "--write", action="store_true", help="应用变更并写回（默认只打印 diff，不落盘）"
    )
    p_fetch.add_argument("--add", default=None, help="只添加指定模型（逗号分隔，跳过勾选）")
    p_fetch.add_argument(
        "--keep", default=None, help="保留这些模型不移除、不记缺失（逗号分隔，即使云端已消失）"
    )
    p_fetch.add_argument("--delete", default=None, help="从不添加候选的模型中排除（逗号分隔）")
    p_fetch.set_defaults(func=_cmd_llm_fetch)

    p_missing = p_llm_test.add_parser("missing", help="缺失模型记录（同步后从端点消失，只读）")
    p_missing_sub = p_missing.add_subparsers(dest="missing_command")
    p_missing_list = p_missing_sub.add_parser("list", help="列出缺失模型记录")
    p_missing_list.set_defaults(func=_cmd_llm_missing)

    p_retired = p_llm_test.add_parser("retired", help="[已退役] 旧命令别名，请改用 missing list")
    p_retired.set_defaults(func=_cmd_llm_missing)

    p_chat = sub.add_parser("chat", help="文字对话（交互循环或单次问答）")
    p_chat.add_argument("message", nargs="?", help="要发送的消息；不提供则进入交互对话循环")
    p_chat.add_argument(
        "--model",
        default=None,
        help="统一模型 id（默认取 data/config/providers.toml 的 default_model）",
    )
    p_chat.add_argument(
        "--system",
        default=None,
        help="自定义系统提示词（默认使用内置 Aris 人设）",
    )
    p_chat.add_argument(
        "--thinking",
        action="store_true",
        help="开启思考模式（默认关闭，关闭时首字响应更快）",
    )
    p_chat.add_argument(
        "--no-tools",
        action="store_true",
        help="禁用工具调用（默认开启内置工具）",
    )
    p_chat.set_defaults(func=_cmd_chat)

    p_web = sub.add_parser("web", help="启动 WebUI 管理后台")
    p_web.add_argument("--host", default=None, help="监听地址（默认 0.0.0.0）")
    p_web.add_argument("--port", default=None, type=int, help="监听端口（默认 9690）")
    p_web.set_defaults(func=_cmd_web)

    p_serve = sub.add_parser(
        "serve",
        help="一键启动各模块（组装根；前台运行，Ctrl-C 停止）",
        description="按序拉起各模块：PG 自启 + 迁移、embedding 后台预热、knowledge 建表、"
        "WebUI 并入；失败分级（required 仅 store.db）且降级必记日志。",
    )
    p_serve.add_argument("--only", default=None, help="只启动列出的步骤（逗号分隔）")
    p_serve.add_argument("--skip", default=None, help="跳过列出的步骤（逗号分隔）")
    p_serve.add_argument(
        "--dry-run", action="store_true", help="只跑探针并打印清单，不启动任何东西"
    )
    p_serve.set_defaults(func=_cmd_serve)

    p_db = sub.add_parser("db", help="数据库环境管理（便携 PostgreSQL + pgvector）")
    p_db_sub = p_db.add_subparsers(dest="db_command")
    p_db_init = p_db_sub.add_parser("init", help="获取/初始化数据库环境（幂等）")
    p_db_init.set_defaults(func=_cmd_db)
    p_db_start = p_db_sub.add_parser("start", help="启动数据库服务")
    p_db_start.set_defaults(func=_cmd_db)
    p_db_stop = p_db_sub.add_parser("stop", help="停止数据库服务")
    p_db_stop.set_defaults(func=_cmd_db)
    p_db_status = p_db_sub.add_parser("status", help="查看环境与运行状态")
    p_db_status.add_argument("--no-probe", action="store_true", help="跳过连接探活")
    p_db_status.set_defaults(func=_cmd_db)
    p_db_migrate = p_db_sub.add_parser("migrate", help="应用待执行的 schema 迁移")
    p_db_migrate.set_defaults(func=_cmd_db)
    p_db_psql = p_db_sub.add_parser("psql", help="进入 psql（后续参数原样透传）")
    p_db_psql.set_defaults(func=_cmd_db, psql_args=[])

    p_store = sub.add_parser("store", help="存储/向量基础设施（embedding 调试）")
    p_store_sub = p_store.add_subparsers(dest="store_command")
    p_store_info = p_store_sub.add_parser("info", help="打印 embedding 配置并做一次自检")
    p_store_info.set_defaults(func=_cmd_store)
    p_store_embed = p_store_sub.add_parser(
        "embed", help="编码文本并打印维度与向量片段（不给参数则从 stdin 逐行读）"
    )
    p_store_embed.add_argument("text", nargs="*", help="待编码文本")
    p_store_embed.set_defaults(func=_cmd_store)

    p_kb = sub.add_parser("knowledge", help="知识库（摄入 / 列举 / 移除 / 检索）")
    p_kb_sub = p_kb.add_subparsers(dest="knowledge_command")
    p_kb_add = p_kb_sub.add_parser("add", help="摄入文件或目录（递归；md / txt / html）")
    p_kb_add.add_argument("paths", nargs="+", help="文件或目录路径")
    p_kb_add.set_defaults(func=_cmd_knowledge)
    p_kb_list = p_kb_sub.add_parser("list", help="列出已摄入文档")
    p_kb_list.set_defaults(func=_cmd_knowledge)
    p_kb_remove = p_kb_sub.add_parser("remove", help="移除一个文档及其块（软删）")
    p_kb_remove.add_argument("path", help="文档路径")
    p_kb_remove.set_defaults(func=_cmd_knowledge)
    p_kb_search = p_kb_sub.add_parser("search", help="纯向量检索（带来源标识）")
    p_kb_search.add_argument("query", help="检索词")
    p_kb_search.add_argument("--top-k", type=int, default=None, help="返回条数（默认读配置）")
    p_kb_search.set_defaults(func=_cmd_knowledge)
    p_kb_reindex = p_kb_sub.add_parser("reindex", help="建 HNSW 索引（幂等）")
    p_kb_reindex.set_defaults(func=_cmd_knowledge)

    p_tools = sub.add_parser("tools", help="agent 工具面（列表 / 状态）")
    p_tools_sub = p_tools.add_subparsers(dest="tools_command")
    p_tools_list = p_tools_sub.add_parser("list", help="列出已登记的 agent 工具与声明探询失败条目")
    p_tools_list.set_defaults(func=_cmd_tools)

    p_services = sub.add_parser("services", help="CMCB 总线服务管理")
    p_services_sub = p_services.add_subparsers(dest="services_command")
    p_services_list = p_services_sub.add_parser("list", help="列出全部已注册的总线服务")
    p_services_list.set_defaults(func=_cmd_services)

    # `db psql` 之后的参数不参与 argparse（-c 这类选项会被误判），解析前先摘出
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parse_argv, psql_args = _extract_psql_passthrough(raw_argv)
    args = parser.parse_args(parse_argv)
    if psql_args:
        args.psql_args = psql_args
    settings = get_settings()
    # doctor / db / store / knowledge / serve / web 是环境与运维命令，始终显示 INFO
    # 级别——serve 的启动清单本身就是输出，web 的监听地址也要看得见
    ops_commands = ("doctor", "db", "store", "knowledge", "serve", "web", "tools", "services")
    console_level = "INFO" if (args.verbose or args.command in ops_commands) else None
    # chat 命令默认不向控制台输出日志——全屏 TUI 由 prompt_toolkit 接管终端，
    # loguru 直接写 stderr 会破坏渲染（spinner 残留、界面错位）；日志仍写文件。
    # --verbose 可强制开启，用于联调排查。
    console = not (args.command == "chat" and not args.verbose)
    setup_logging(
        settings.log_level,
        settings.data_dir,
        console=console,
        console_level=console_level,
    )

    if args.command is None:
        parser.print_help()
        return 0

    # 注册模块级总线服务（各模块在 import 时自注册；此处只挂轻量模块）
    # v0.4.4 W3：按 modules.toml 开关，关闭的模块不 import（注册即 import）
    import importlib

    from .modules import load_modules, resolve_modules

    _state = resolve_modules(load_modules())
    for _name, _import_path in _state.import_paths():
        if _name in {"store", "knowledge"}:
            importlib.import_module(_import_path)

    if args.command == "llm" and args.llm_command is None:
        p_llm.print_help()
        return 0

    if args.command == "db" and args.db_command is None:
        p_db.print_help()
        return 0

    if args.command == "store" and args.store_command is None:
        p_store.print_help()
        return 0

    if args.command == "knowledge" and args.knowledge_command is None:
        p_kb.print_help()
        return 0

    if args.command == "tools" and args.tools_command is None:
        p_tools.print_help()
        return 0

    if args.command == "services" and args.services_command is None:
        p_services.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
