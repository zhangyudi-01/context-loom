# Context Loom handoff

## 阶段边界

当前技能完整执行测试领域前置分析：AI 分析资料，脚本初始化和校验产物。
不在该阶段打分复杂度、创建 CLI Baseline 会话、执行 fork 或生成测试点。
复杂度路由属于后续 Runtime 阶段，不能为了分批方便拆碎 RSU。

迁移保留 `preanalysis/v1` 和既有 Markdown 契约；领域参考中的
`rsu-test-point-generation` 指原项目的消费协议，不要求用户安装或调用旧项目技能。
Context Loom 的实际消费入口是 `loom-test-points` / `context-loom setup-testing`。

## 消费协议

生产端先运行本技能的 `validate_preanalysis.py`，新建目录必须要求 canonical layout。
消费端从模块根目录及其直接子目录定位唯一 manifest，按 artifact 和 resource role
解析真实路径，不把固定文件名或 `SRC-MOD` 写死成跨项目假设。

| 前置分析内容 | Context Loom 工作流位置 |
|---|---|
| 全局上下文、当前模块需求、Context Pack | 三类共享 `sources` |
| 当前完整 RSU 行、原文与父级条件、来源定位 | 对应 task 的 `payload` |
| 当前 RSU 的来源原文不在三类固定来源中 | 当前任务的聚焦动态来源 |
| 必要 Q、FC、DC、直接声明的附件来源 | `contexts` 和 task `context_refs` |
| 其他 RSU 仅作语义支持 | 当前任务动态上下文，不自动变成额外执行任务 |
| manifest、覆盖表、卡片来源证据 | 交接与追溯，不是每任务递归全文输入 |

只有 `captured` 且相关问题无未决、数据闭包不 blocked 的 RSU 可执行。
引用无法解析、来源原文不匹配、路径越过项目边界或多个 manifest 时拒绝交接。
不要用缺失卡片的链接代替实际内容；不要默认加载整个资料库。

现有 `setup-testing` 仍将结果放在用户指定的项目外隔离目录，不复制原资料，
不重建 RSU，不声称选定 RSU 等于完整模块覆盖。可在后续阶段明确授权后执行：

```text
context-loom setup-testing --module <module-root> --output <new-isolated-workflow-dir> --rsu RSU-001 RSU-002
context-loom doctor <new-isolated-workflow-dir> --offline
```

上述准备和检查不调用模型；`context-loom run` 会调用模型，不能因本次只请求前置分析而自动启动。
