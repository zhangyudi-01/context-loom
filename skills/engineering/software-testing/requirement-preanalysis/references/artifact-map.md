# Artifact Map

本文件固定前置分析产物的职责边界。不要让同一信息在多个文件中以不同结论重复维护。

新建前置分析产物统一放在 `<module-root>/preanalysis/`，后续测试点默认放在同级 `<module-root>/test-points/`。不得把前置分析文件与后续方案、用例平铺混放在模块根目录；既有平铺目录只作为兼容布局读取，迁移必须由用户明确提出。

## 默认产物

| 文件或目录 | 唯一职责 | 必须包含 | 禁止包含 |
|---|---|---|---|
| `preanalysis-manifest.json` | 连接前置分析生产端与测试点消费端 | `preanalysis/v1`、模块根目录、六类产物路径、三类固定资源角色、测试点输出目录 | 绝对路径、业务内容、聊天状态、可执行命令 |
| `00-module-requirement-pack.md` | 保存当前模块需求原文 | 当前模块完整原文、原型或附件引用 | AI 总结、澄清答案、测试点 |
| `01-context-pack.md` | 保存模块逻辑与上下文基线 | 全文背景、模块定位、能力、详细主链路、边界、资料优先级、固定/动态输入 | 改写后的需求原文、正式测试点或测试步骤 |
| `02-sentence-test-point-map.md` | 保存来源原文到 `RSU-ID` 的无损映射 | 资源入口、原文结构与拆分决策表、RSU 表、来源覆盖表、后续输入契约 | ATP/STP 种子、复杂度、验证步骤、人工结论伪装成原文 |
| `03-clarification-questions.md` | 保存普通问题、人工答案和回填结果 | 已确认表、待确认表、回填规则 | 签字审批流程、需求原文替代品、测试用例 |
| `context-cards/README.md` | 保存 Context Card 索引与规则 | Card ID、链接、主题、覆盖范围 | 复制完整模块逻辑 |
| `context-cards/FC-xxx-*.md` | 保存可复用的局部复杂上下文 | 引用入口、定位、关联来源、已确认内容、当前边界 | 每个 RSU 的重复卡片、未经确认的推断、正式步骤 |
| `data-closures/README.md`（可选） | 保存数据库相关模块的数据闭包索引 | DC-ID、状态、关联 RSU、来源资源和可点击卡片 | 无数据库模块的空索引、整库 ER 图 |
| `data-closures/DC-xxx-*.md`（可选） | 保存最小可复用业务数据路径 | 表角色、连接/过滤、基数、数据 Profile、查询口径、准备和清理结构 | 按 TP 复制的图、环境密码、无依据外键、正式用例 SQL |
| `README.md` | 保存当前目录的执行入口 | 文件职责、快速索引、分析流程、四项固定输入、阶段约束 | 大段业务细节、非默认评估流程 |

## 信息归属

| 信息类型 | 主保存位置 | 其他文件如何引用 |
|---|---|---|
| 产物路径和固定资源角色 | `preanalysis-manifest.json` | 下游按逻辑角色解析，不猜目录名或文件名 |
| 当前模块需求原文 | `00-module-requirement-pack.md` | map 使用 `SRC-MOD + 来源定位` |
| 模块背景、作用、能力和详细逻辑 | `01-context-pack.md` | README/map 使用 `CTX` |
| 来源原文结构、语义角色与拆分决定 | `02-sentence-test-point-map.md` | 决策表使用来源范围和 `RSU-ID`，不直接生成测试点 |
| 来源原文单元 | `02-sentence-test-point-map.md` | Q/FC 使用 `RSU-ID` |
| 人工确认和范围结论 | `03-clarification-questions.md` | Context Pack/FC 回填结论，保留 `Q-ID` 追溯 |
| 功能链路、既有契约、验证位置 | Context Card | map 使用 `FC-ID`，Context Pack 保留模块级结论 |
| 数据表关系、连接/过滤、数据状态和准备/清理结构 | Data Closure Card（适用时） | map 的 RSU 使用 `DC-ID`，测试点单独记录 `data_closure_refs` |
| 正式测试点 | 后续阶段产物 | 必须记录 `primary_rsu_id`、`source_rsu_ids`、`question_refs`、`context_refs`；数据库相关测试点还记录 `data_closure_refs` |

## 权威关系

按以下顺序处理冲突，但不要机械地用低层资料覆盖高层资料：

1. 当前模块需求原文。
2. 用户或业务人员对本次范围和实际链路的明确确认。
3. 当前需求全文与全局共享规则。
4. 经人工确认继续沿用的历史 PRD 条款。
5. 当前需求引用的附件、接口、数据库、配置和环境资料。
6. 仅供参考的历史资料。

人工确认可以解释范围和既有运行事实，但不能回写成来源文档原文。历史资料只有在确认沿用时才进入当前基线。

## 非默认产物

以下内容不属于本 Skill 的默认产物或必经步骤：

- `04-pilot-comparison-note.md` 等试点评估材料。
- AI 改写的原子需求、ATP/STP 种子。
- 复杂度评分或复杂度处理清单。
- `test-point-batch-*`。
- 正式测试点、测试方案、测试用例、执行步骤和 Excel。

用户明确要求某个独立评估附件时可以单独维护，但不得反向改变默认前置分析契约。

## 生命周期

```text
需求全文/全局上下文/模块需求/相关资料/人工讲解
  -> 模块逻辑 Context Pack
  -> 普通澄清问题与确认回填
  -> RSU 原文映射 + 来源覆盖
  -> Context Card 动态依赖
  -> 可选 Data Closure 数据依赖
  -> 强校验通过
  -> 后续逐 RSU 生成 0～N 个带闭包引用的测试点
  -> 全模块去重、覆盖、引用完整性和跨 RSU 检查
  -> 测试用例
```
