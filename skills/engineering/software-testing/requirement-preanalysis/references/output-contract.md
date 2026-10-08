# Fixed Output Contract

本文件是生成与审核的唯一格式基线。除标记为“可扩展”的位置外，不修改主章节名称、顺序和表头。

## 通用格式

- 文件编码使用 UTF-8。
- 每个文件只有一个一级标题。
- 标题、正文、表格和代码块之间保留一个空行。
- 表格空值写 `无`，不要留空。
- ID 固定为三位数字：`RSU-001`、`Q-001`、`FC-001`、`DC-001`。
- 默认资源角色使用 `SRC-GLOBAL`、`SRC-MOD`、`CTX`；既有项目可由 manifest 映射为其他合法且唯一的 `SRC-*`/`CTX` ID。问题索引仍使用 `Q-INDEX`。
- 路径使用相对 Markdown 链接，资源表中集中维护。
- 不创建同文件 ID 锚点或长文档深层标题链接。

## 目录布局

新建产物的目录契约固定为：

```text
<module-root>/
  preanalysis/
    preanalysis-manifest.json
    README.md
    00-module-requirement-pack.md
    01-context-pack.md
    02-sentence-test-point-map.md
    03-clarification-questions.md
    context-cards/
    data-closures/          # 仅数据库相关模块
  test-points/              # 后续阶段
```

`preanalysis/` 必须是模块根目录的直接子目录，使下游能自动发现其中唯一的 manifest。新建产物不得平铺在模块根目录。既有平铺/自定义路径仍可由 manifest 或旧格式兼容读取，但不属于新建输出契约；迁移时必须同步更新相对链接、manifest 和受影响的下游状态。

## preanalysis-manifest.json

manifest 是跨项目机器契约，schema 固定为 `preanalysis/v1`。新建 manifest 位于 `<module-root>/preanalysis/preanalysis-manifest.json`；所有路径相对 manifest 文件，禁止绝对路径；六类 artifact role 和三类 resource role 缺一不可，`module_root` 固定为 `..`，默认 `output.test_points_dir` 为 `../test-points` 且不能等于模块根目录。

```json
{
  "schema_version": "preanalysis/v1",
  "module_root": "..",
  "artifacts": {
    "readme": "README.md",
    "module_requirement": "00-module-requirement-pack.md",
    "context_pack": "01-context-pack.md",
    "rsu_map": "02-sentence-test-point-map.md",
    "clarifications": "03-clarification-questions.md",
    "context_card_index": "context-cards/README.md"
  },
  "resource_roles": {
    "global_context": "SRC-GLOBAL",
    "module_requirement": "SRC-MOD",
    "module_context": "CTX"
  },
  "output": {
    "test_points_dir": "../test-points"
  }
}
```

新建产物使用示例文件名。既有项目可以使用其他相对路径，但不能修改逻辑键名、schema 或下游表格契约。

## README.md

章节顺序固定：

```markdown
# <模块名>需求前置分析

## 当前目标
## 文件职责
## 快速索引
## 分析流程
## 后续测试点生成输入
## 后续追溯关系
## 约束
```

`文件职责` 表头固定：

```markdown
| 文件 | 职责 |
|---|---|
```

`后续测试点生成输入` 必须明确四项固定输入：

1. manifest `global_context` 角色对应资源全文。
2. manifest `module_requirement` 角色对应资源全文。
3. manifest `module_context` 角色对应的模块背景、能力、已确认详细逻辑和理解边界。
4. 当前 `RSU-ID` 完整映射行。

## 01-context-pack.md

章节顺序固定：

```markdown
# <模块名> Context Pack

## 目标
## 资源索引
## 当前阶段边界
### In Scope
### Out of Scope
## 资料优先级
## 模块在需求全文中的背景与定位
## 模块目标与能力
## 已确认的详细逻辑
### 主链路
### 逻辑说明
## 已确认的理解边界
## 领域契约边界
## 原文、上下文和验证信息的边界
## 后续测试点生成输入规则
### 固定输入
### 动态输入
## 当前缺口
```

`领域契约边界` 可以替换为更具体但必须以“边界”结尾的二级标题，例如“文件与传输契约边界”“接口与数据库契约边界”。只能有一个主契约边界章节；多个主题拆到 Context Card。

`资源索引` 表头固定：

```markdown
| 资源 ID | 可点击文件 | 用途 |
|---|---|---|
```

`原文、上下文和验证信息的边界` 表头固定：

```markdown
| 信息类型 | 保存位置 | 示例 |
|---|---|---|
```

`已确认的详细逻辑` 必须同时包含主链路和编号逻辑说明，并区分当前新增能力、沿用既有能力与明确排除范围。

## 02-sentence-test-point-map.md

章节顺序固定：

```markdown
# <模块名>原文需求单元映射

## 定位
## 引用入口
## 当前模块原文单元
[可扩展：一个或多个“已确认沿用的……原文单元”]
[可扩展：共享规则原文单元]
## 原文来源覆盖检查
## 后续使用规则
```

`引用入口` 表头固定：

```markdown
| 资源 ID | 可点击文件 | 定位用途 |
|---|---|---|
```

每个 RSU 表使用同一表头：

```markdown
| RSU-ID | 父级条件（原文） | 原文内容 | 来源 | 来源定位 | 相关上下文 | 相关问题 | 状态 |
|---|---|---|---|---|---|---|---|
```

`父级条件（原文）` 只保存当前 `原文内容` 所需的最小原文适用条件、触发、状态或范围。父级中的创建/生成、修改/删除、写入/发送、状态变化、页面进入/跳转、弹窗/提示、展示等可观察行为，必须完整出现在至少一个 RSU 的 `原文内容` 中；仅在父级条件列重复不算映射。父句与子项不可分割时，将父句和完整必要子项合并为一个 `composite-contract`；可以独立验证时，为父句和子项分别建立 RSU。

`当前模块原文单元` 下必须先维护“原文结构与拆分决策”表，再维护 RSU 表。该表是语义审查记录，不是测试项表，也不替代 RSU 表：

```markdown
| 来源范围 | 语义角色 | 拆分处理 | 对应 RSU | 判定理由 |
|---|---|---|---|---|
```

允许的语义角色：

- `visual-placeholder`：原型、图片、附件标记等没有文本行为的视觉或资料占位符。
- `structural-container`：只引出后续条款的父级组织文字，例如“查询条件包括：”。
- `field-fragment`：离开父级后不能独立理解的字段名、枚举项或结果字段。
- `independent-contract`：自身包含对象以及条件、动作、限制或可观察结果的完整条款。
- `composite-contract`：父规则与子项共同定义一个完整对象、列表或结果契约的来源范围。
- `unresolved`：现有资料不足以决定语义边界。

允许的拆分处理：

- `one-rsu`：该来源范围恰好对应一个完整 RSU；多个独立契约必须先拆为多个来源范围。
- `not-rsu`：该来源范围保留追溯，但不单独创建 RSU；字段碎片要填写吸收它的 RSU。
- `pending`：边界尚未确认，不创建可消费的独立 RSU。

角色与处理决定必须匹配：视觉占位符、结构容器和字段碎片只能是 `not-rsu`；独立契约和复合契约只能是 `one-rsu`；未决范围只能是 `pending`。`对应 RSU` 必须引用已存在的 RSU-ID；`one-rsu` 恰好引用一个，字段碎片必须引用吸收它的 RSU，纯容器、视觉占位符和未决范围写 `无`。

该表解决“测试项”和“RSU”粒度不同的问题。比如“查询条件包括：”是结构容器，不建立 RSU；“彩票年：下拉选择框，包含……默认为全部”是独立契约，可以建立 RSU。结果列表的排序、分页和完整字段集合若共同定义一个结果契约，应合并为一个 `composite-contract` RSU。后续测试点可以从该复合 RSU 派生多个测试意图，但不能反过来把字段碎片登记为独立 RSU，也不能把可验证父级行为降级成只存在于 `父级条件（原文）` 的上下文。

允许的 RSU 状态：

- `captured`
- `pending-context`
- `pending`

`原文来源覆盖检查` 表头固定：

```markdown
| 原文来源范围 | 处理结果 | 对应 RSU/问题 | 说明 |
|---|---|---|---|
```

`原文来源范围` 必须写成 `SRC-ID > 章节/规则/字段范围`，其中 `SRC-ID` 已在引用入口登记，后半段足以人工回查。即使同一文件一部分纳入、一部分排除，也要拆成多行，禁止仅用整文件名或“附件”概括。

允许的覆盖结果：

- `mapped`
- `indexed-only`
- `scope-excluded`
- `pending-context`
- `pending`
- `not-applicable`
- `not-rsu`

`not-rsu` 表示来源范围已审查但不单独生成 RSU；覆盖说明必须写明语义角色以及被哪个 RSU 吸收，纯结构容器和视觉占位符没有吸收对象时写 `无`。历史产物若尚未包含“原文结构与拆分决策”表，可以继续按旧格式校验并收到兼容性警告；新建或补充该章节的产物必须满足上述决策表契约。

拆分决策表和来源覆盖表必须以完全相同的 `SRC-ID > 语义范围` 逐项对账：`one-rsu -> mapped`、`not-rsu -> not-rsu`、`pending -> pending|pending-context`。两表的 RSU 引用必须一致；`pending` 覆盖行必须关联至少一个状态为 `pending` 或 `deferred` 的 `Q-ID`。覆盖表中的上述四类状态也必须存在对应拆分决策，只有 `indexed-only`、`scope-excluded`、`not-applicable` 可作为纯覆盖记录。

`后续使用规则` 必须重复四项固定输入和动态依赖解析原则。重复是执行契约，不视为冗余。

动态依赖解析必须区分“当前 RSU 直接语义输入”和“FC/DC 来源证据”：RSU `相关上下文` 直接列出的资源加载正文；FC/DC 卡片引用的来源资源只进入追溯证据索引并记录路径、用途和正文哈希，不自动展开全文。若测试点语义确实依赖来源原文，必须把聚焦资源 ID 直接写入相应 RSU，不能依赖下游递归扫描卡片或其他 RSU。

## 03-clarification-questions.md

章节顺序固定：

```markdown
# <模块名>问题确认清单

## 引用入口
## 已确认问题与结论
## 待确认问题
## 已确认的模块逻辑摘要
## 执行准备项
## 回填规则
```

“已确认的模块逻辑摘要”可以使用领域化标题，例如“已确认的系统链路”，但只能保存摘要；完整逻辑仍以 Context Pack 为准。

已确认表头固定：

```markdown
| Q-ID | 关联原文/上下文 | 状态 | 人工确认结论 | 回填结果 |
|---|---|---|---|---|
```

待确认表头固定：

```markdown
| Q-ID | 关联来源 | 状态 | 问题 | 未确认时的处理 |
|---|---|---|---|---|
```

允许的 Q 状态：

- `answered`
- `pending`
- `deferred`
- `out-of-scope`

已回答或排除的问题必须填写结论和回填结果。待确认问题必须说明未确认时如何处理，禁止自行补结论。

## context-cards/README.md

章节顺序固定：

```markdown
# Context Cards

## 卡片索引
## 使用规则
```

卡片索引表头固定：

```markdown
| Card ID | 类型 | 可点击文件 | 职责 |
|---|---|---|---|
```

无卡片时也保留表头，并在正文写明“当前无 Context Card”。

## FC-xxx-<主题>.md

核心章节顺序固定：

```markdown
# FC-xxx <主题>

## 引用入口
## 定位
## 关联来源
## <主题内容，可包含一个或多个二级章节>
## 当前边界
```

主题内容按卡片类型选择，不随意混用：

- 功能链路卡：`## 系统链路`、`## 链路理解`、必要分支。
- 契约卡：`## 契约来源边界`、`## 已确认契约`。
- 证据卡：`## 已确认的观察链路`、`## 各层信息的用途`。

`定位` 必须说明卡片保存什么、不是哪类产物。`当前边界` 必须列出不在本卡片展开的内容。

## data-closures/README.md（可选）

仅数据库相关模块创建。章节顺序固定：

```markdown
# Data Closures

## 闭包索引
## 状态定义
## 使用规则
```

闭包索引表头固定：

```markdown
| DC-ID | 业务数据闭包 | 可点击文件 | 状态 | 关联 RSU | 来源资源 |
|---|---|---|---|---|---|
```

允许状态为 `ready`、`test-point-ready`、`blocked`。启用后，map 和 Context Pack 必须同时登记 `DC-INDEX`，map 必须登记每张 `DC-ID` 卡；索引、卡片和 RSU 的关联必须一致。

## DC-xxx-<业务数据路径>.md（可选）

按最小可复用业务数据路径创建，不按整个模块堆叠整库关系，也不按每个测试点复制。章节顺序固定：

```markdown
# DC-xxx <业务数据路径>

## 引用入口
## 定位
## 关联范围
## 闭包目标
## 输入与输出
## 关系图
## 表角色
## 连接与过滤契约
## 数据状态与准备契约
## 查询与断言契约
## 清理与隔离
## 当前缺口
```

固定表头：

```text
资源 ID | 可点击文件 | 用途
方向 | 逻辑对象 | 物理载体/字段 | 约束 | 依据
Table ID | 物理表 | 职责 | 访问模式 | 主键/自然键 | 关键字段 | 数据所有权
Edge ID | From | To | Join Predicate | 基数 | 附加过滤 | 依据
Profile ID | 数据状态目标 | 准备策略 | 预期推导 | 清理策略
用途 | 查询入口 | 断言口径 | 空结果含义 | 依据
```

`关系图` 必须包含 Mermaid `flowchart`。图只用于导航；连接谓词、过滤、基数、表角色、数据状态、预期推导、准备和清理必须进入固定表格。`ready` 卡的“当前缺口”只能写 `- 无`，且不能残留未知/待确认数据契约；`blocked` 卡必须关联待确认 `Q-ID`，关联 RSU 不能为 `captured`。

DC 卡必须自包含测试点阶段需要的聚焦数据语义。`引用入口` 和各表中的 `依据` 用于证明结论来源；它们不会让下游自动复制整份 schema、SQL、代码或数据库设计。若卡片仍需读某个来源正文才能确定测试点语义，该卡不能以已闭合状态交付，或者必须把聚焦来源资源显式绑定到相应 RSU。

## 索引契约

所有主产物满足：

1. 顶部索引中的每个相对路径都能从当前文件位置解析。
2. map 中使用的 `SRC-*` 在 map 的引用入口中有唯一记录。
3. map 中使用的 `Q-ID` 在问题清单中有定义。
4. map 中使用的 `FC-ID` 有对应文件，并在 map 引用入口和 Context Card 索引中登记。
5. 启用数据闭包时，`DC-INDEX` 和每个 `DC-ID` 都有可点击文件；卡片引用的 schema/SQL/API/代码资源已在 map 登记并可打开。
6. 长文档定位使用章节、规则、表格或字段名称，不只写文件名。
7. 同文件 ID 只写普通文本；任何本地 Markdown 链接都不使用 `#fragment`，改用“文件链接 + 语义定位”。

## 完成门禁

以下任一情况存在时，不得报告完成：

- 必需章节、表格或文件缺失，或出现重复必需章节、重复固定表格、多个一级标题、空表格单元格。
- 存在 `{{PLACEHOLDER}}`。
- 存在失效本地链接。
- RSU/Q/FC/DC/SRC 引用未定义或重复，Context Card 未同时登记到 map 和卡片索引，或 Data Closure 的索引、状态、RSU/来源关系不闭合。
- 新建产物未位于 `<module-root>/preanalysis/`，或 manifest 不能从模块根目录的直接子目录发现。
- 拆分决策与来源覆盖的范围、状态、RSU 引用或待确认问题不一致。
- RSU 原文无法在可读来源中匹配且未记录 pending 原因。
- Context Pack 缺少模块背景、能力或详细逻辑。
- README、Context Pack 或 map 缺少四项固定输入。
- map 出现 ATP/STP 种子、复杂度、处理模式、测试步骤或正式测试点列。
- 生成了 `test-point-batch-*` 或正式用例产物。
