# skills-backup —— 迁移前的技能备份

> **用途声明（2026-09-28）**：本目录是 `src/aris/behavior/skills/` 里那三个技能的
> **迁移前备份**，按 `docs/developDoc/discuss-2026-09-28.md` D7/D13 设立。

## 为什么在这儿

- **D7 定案**：技能整体迁到 `data/skills/`——技能本质是外部内容；Aris 自己的核心能力
  直接做进 `behavior` 模块，不靠外部技能文件承载
- 包内现有的三个技能（`note` / `frontend-design` / `doc-coauthoring`）
  **只是技能机制的测试样本**，不是真实能力
- 用户要求：**先别删**，之后还要用它们测试 skills，**先备份到本目录**（放 src 外、
  不被 gitignore），迁移完、测试好之后**再删**

## 内容

| 目录 | 内容 |
|---|---|
| `note/` | `SKILL.md` + `tools.py`（唯一带工具的样本） |
| `frontend-design/` | `SKILL.md` + LICENSE |
| `doc-coauthoring/` | 仅 `SKILL.md` |

## 处置时机

1. `data/skills/` 迁移完成、SkillManager 指向新目录
2. 用这三个样本验证发现 / 菜单 / 激活 / 工具注册仍然正常
3. 验证通过后：**删除本目录**，并同步删掉 `src/aris/behavior/skills/` 下的原件
