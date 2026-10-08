# 从原始模块开始需求前置分析

`testing-requirement-preanalysis` 是 AI 会话执行的技能，不是要求用户编写工作流配置的 Runner。
Python 3.11+ 足以运行随技能携带的脚手架和校验器；此阶段不依赖安装 Context Loom Runtime。

## 本地调用

在待分析项目的会话中引用
`skills/engineering/software-testing/requirement-preanalysis/SKILL.md` 的实际绝对路径，
并提供项目根目录和模块目录。例如：

```text
请使用 Context Loom 的 testing-requirement-preanalysis 技能。
技能路径：D:\pythonProject\context-loom\skills\engineering\software-testing\requirement-preanalysis\SKILL.md
项目根目录：D:\pythonProject\context-loom\.local-tests\task-list-clean
目标模块：modules\MOD-02-03-计奖审核（增）\MOD-02-03-01-任务列表

读取 global 中相关资料及模块的 00-module-requirement-pack.md，
在模块下的 preanalysis 目录完成需求前置分析并运行强校验。
原始资料只读，不复制旧结果，不创建 snapshot-project，不继续生成测试点或用例。
遇到未确认事项记录 Q 和影响范围，不自行补业务答案。
```

安装后可按宿主支持的方式选择 `testing-requirement-preanalysis`，再发送相同的项目与模块要求。
技能安装方式沿用仓库 README；本地未推送的修改不会自动出现在远程安装版本里。

## 执行与结果

AI 自动解析技能目录，读取业务资料和领域规范，必要时初始化骨架，完成实际分析，
再运行 `scripts/validate_preanalysis.py`。不需要用户手工准备 `context-loom.json`。
脚手架逐字复制需求包；其原有相对附件链接可能因目录层级改变而失效，AI 需在生成副本中
按原始位置重定位链接目标，保留可见文字和原始文件不变，最后由链接校验确认。

```text
modules/<module>/
  00-module-requirement-pack.md       原始输入，保持不变
  preanalysis/
    preanalysis-manifest.json
    README.md
    00-module-requirement-pack.md     供后续使用的需求包
    01-context-pack.md
    02-sentence-test-point-map.md
    03-clarification-questions.md
    context-cards/
    data-closures/                    仅数据库相关能力
```

AI 交付时说明分析范围、来源、RSU 数量、未决问题及校验结果。
校验器不证明业务语义一定正确，仍须审查来源覆盖和语义完整性；存在 pending 的 RSU 不交给下游。

## 下游阶段

前置分析与 Runtime 执行分别负责领域理解和会话编排。后续的全局、模块需求和 Context Pack
作为共享 Baseline 来源，完整 RSU 行成为任务载荷，必要 Q/FC/DC 成为动态上下文。
当前 `loom-test-points` 仍是选定 RSU 的隔离试运行，不是整个模块生产流程；
`loom-testing-full` 是旧的快照式演示，不用于本页的原始项目布局。
