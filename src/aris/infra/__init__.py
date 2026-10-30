"""infra —— 项目基础设施（与业务无关、全项目共用）。

包含：
- paths：数据目录解析与 data/ 分层
- settings：启动级配置（settings.toml / secrets.toml）
- toml：模块级配置加载（data/config/<module>.toml）
- modules：模块开关（data/config/modules.toml）
- logging：日志初始化
- branding：对外显示名与仓库地址

本包不 import 任何业务模块；业务模块可以依赖本包，反过来不行。
"""
