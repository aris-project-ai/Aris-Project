# Project Aris

## 简述

Project Aris 是一个拟人 AI，参考 Neuro-sama：目标不是做助手，而是一个长期存在、会自己长大的「人」。

项目始于 2026-07，在 AI 辅助下开发。

## 大致实现

* Aris
  * 记忆系统
    * 工具
      * Embedding Model（本地部署，文本转向量）
      * 数据库（PostgreSQL + pgvector，兼顾 GraphRAG）
    * 分层：热记忆常驻、冷记忆归档
    * 内容：事件、对话总结、两周记；权重随时间衰减，被用到才涨
  * 语音系统
    * TTS（Edge TTS 起步，Azure TTS 备选）
    * STT（未定）
  * 人格系统
    * 提示词工程起步
    * 世界观 / 人际关系 / 成长轨迹
  * 行为
    * 函数调用
    * 联网搜索
    * Skills
    * MCP 服务器
    * 插件
  * 交互
    * 语音为主，文字为辅
    * 接入外部平台（Matrix / Discord 等）
    * TUI 只用于调试，WebUI 只用于运维
  * WebUI 管理后台
    * 审计、提供商与模型、技能、配置、日志、知识库
