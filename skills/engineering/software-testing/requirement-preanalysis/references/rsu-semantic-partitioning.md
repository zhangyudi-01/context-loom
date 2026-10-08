# RSU Semantic Partitioning

## Purpose

`RSU` is a Requirement Source Unit: one complete, source-faithful business contract that can be handed to the later test-point generation stage. It is not a Markdown line, a sentence fragment, a list item, or a test point.

The mapping stage has two separate outputs:

1. `原文结构与拆分决策` records how the source structure was interpreted.
2. The RSU table records only source ranges that are complete enough to consume as one requirement unit.

Do not add a `测试项` column to the RSU table. Test intent and test-point wording belong to the later test-point generation stage (Context Loom's current consumer is `loom-test-points`).

## Mandatory two-pass analysis

Never create RSUs directly by iterating over Markdown lines. First build a semantic inventory of the source block, then create the RSU rows from that inventory.

### Pass 1: classify source ranges

Classify each source range with one role:

| 语义角色 | Meaning | Normal RSU decision |
|---|---|---|
| `visual-placeholder` | Prototype title, image, attachment marker, or visual placeholder without textual behavior | `not-rsu` |
| `structural-container` | Lead-in text such as `查询条件包括：` or `包含以下信息：` that only groups following items | `not-rsu` |
| `field-fragment` | A field name, enum list, or list item that is not independently understandable without its parent | `not-rsu`, merge into a parent RSU |
| `independent-contract` | A range with its own subject, condition/action, constraint, or observable result | `one-rsu` |
| `composite-contract` | A parent rule and its children jointly define one object/result contract | `one-rsu`, include the complete child set |
| `unresolved` | The source boundary or semantic role cannot be decided from available material | `pending` |

The role describes the source range, not its importance. A `structural-container` may be required to understand child RSUs, but it is still not an RSU itself.

### Pass 2: apply semantic closure

An RSU should contain enough source text to answer all applicable questions below without relying on a sibling line:

- What object, field, result, or operation is governed?
- What condition, trigger, state, or scope applies?
- What behavior, limitation, enumeration, or result is required?
- Are the values and child items needed to understand that behavior included?

If a row fails this closure test, do not emit it as a standalone RSU. Move only the smallest exact parent condition needed for comprehension into `父级条件（原文）`, or merge the parent and child source ranges into one composite RSU. A parent action or observable result must not disappear from `原文内容` during this operation.

## Parent and child rules

- A source heading or numbering label such as `业务规则 1` belongs in `来源定位`, not in `父级条件（原文）`.
- `父级条件（原文）` contains only visible source wording that supplies applicability, trigger, state, or scope to the child. Prefer the smallest exact clause that is sufficient for comprehension. Use `无` when there is no textual parent condition.
- A child is independent when it has its own object/control plus behavior or constraint. For example, each of `彩票年` and `奖期编号` has an independent input contract and may be its own RSU.
- A child is a fragment when it only names a result field or enum member. For example, `任务 ID；` and `创建时间。` are not standalone RSUs.
- If a parent says that a result is a list and specifies sorting/pagination, while children only enumerate the fields in that list, create one `composite-contract` RSU containing the parent and all field children.
- If sibling children describe different state-dependent actions, each complete action rule may be its own RSU. The container `任务列表的行内操作：` remains `not-rsu`.
- Never split a complete contract merely because it contains a colon, semicolon, full stop, line break, or numbered child list.
- Never merge two different numbered rules merely to reduce the RSU count.

## Parent-behavior exposure gate

`父级条件（原文）` is contextual input, not a place to hide testable behavior. After drafting all rows, inspect every non-`无` parent cell independently from `原文内容`.

- Pure applicability, trigger, state, or scope wording may remain only in the parent cell, for example `校验通过后` or `任务状态为待核查时`.
- A parent that creates, changes, deletes, persists, sends, invokes, navigates, opens/closes, prompts, displays, or otherwise produces an independently observable result must be represented verbatim in at least one RSU's `原文内容`.
- If the parent behavior is a complete contract, create its own `independent-contract` decision and RSU. Child RSUs inherit only the smallest exact condition clause they need.
- If the parent and children jointly define one indivisible object/result contract, use one `composite-contract` RSU whose `原文内容` contains the complete parent and required child set in source order.
- It is invalid to copy the full behavioral parent into several child rows while leaving it absent from every `原文内容` cell. Repetition in `父级条件（原文）` does not count as source-unit coverage.

Example of an invalid hidden parent:

```text
父级条件（原文）: 校验通过后，系统生成计奖审核任务，任务状态为“待核查”，并进入任务详情页。
原文内容: 顶部展示：……
```

The parent contains task creation, initial-state assignment, and navigation. Correct it either by creating an RSU whose `原文内容` is the complete parent sentence and separate RSUs for independently verifiable detail-page rules, or by including the complete parent sentence and all inseparable children in one composite RSU. A child may then use only `校验通过后` as its parent condition.

## Source-faithful merging

When a composite RSU spans a parent and child list, preserve every visible source term and its order. It is acceptable to join line-separated source text with ordinary spaces for a table cell; do not summarize, normalize away list members, or replace the source with a test assertion. The source validator must still find the normalized cell content in the source file. It validates parent wording as well as `原文内容`, and rejects high-confidence observable behavior that exists only in parent cells.

The RSU table remains the existing fixed contract:

```markdown
| RSU-ID | 父级条件（原文） | 原文内容 | 来源 | 来源定位 | 相关上下文 | 相关问题 | 状态 |
```

The separate decision table is:

```markdown
| 来源范围 | 语义角色 | 拆分处理 | 对应 RSU | 判定理由 |
|---|---|---|---|---|
```

Use `one-rsu` only when the range is represented by exactly one RSU row. If a range contains several independent contracts, split it into several decision rows first. Use `not-rsu` for visual placeholders, containers, and fragments. Use `pending` only when the decision cannot be made without an unresolved source or context question.

The partition table and source coverage table use the same normalized `SRC-ID > semantic location` as a reconciliation key. Their decisions must map as `one-rsu -> mapped`, `not-rsu -> not-rsu`, and `pending -> pending|pending-context`; RSU references must match. A pending coverage row must reference at least one unresolved `Q-ID`.

## Canonical example

Given:

```text
1. 查询条件包括：
   1. 彩票年：下拉选择框，包含：全部、{当前年份}、{当前年份-1}；单选，默认为全部；
   2. 奖期编号：文本输入框，仅可输入数字，默认为空，支持模糊匹配；
   3. 任务状态：下拉选择框，包含：全部、待核查、进行中、已结束、已作废；单选，默认为全部。

2. 查询结果为符合条件的任务列表，按任务 ID 倒序排列，支持分页，包含以下信息：
   1. 任务 ID；
   2. 彩票年；
   3. 奖期编号；
   4. 任务状态，包括待核查、进行中、已结束、已作废；
   5. 创建时间。

3. 任务列表的行内操作：
   1. 待核查、进行中任务，提供【继续审核】和【作废】；
   2. 已结束任务，提供【查看】；
   3. 已作废任务，提供【查看原因】。
```

The semantic result is:

| Source range | Role | Decision | Reason |
|---|---|---|---|
| 业务规则 1 | `structural-container` | `not-rsu` | Only introduces the query-condition children |
| 业务规则 1.1 | `independent-contract` | `one-rsu` | Has a control, options, selection mode, and default |
| 业务规则 1.2 | `independent-contract` | `one-rsu` | Has an input restriction, default, and matching behavior |
| 业务规则 1.3 | `independent-contract` | `one-rsu` | Has a control, options, selection mode, and default |
| 业务规则 2、2.1～2.5 | `composite-contract` | `one-rsu` | Parent result behavior and all result fields form one list contract |
| 业务规则 3 | `structural-container` | `not-rsu` | Only introduces state-dependent row actions |
| 业务规则 3.1 | `independent-contract` | `one-rsu` | Has a state condition and two actions |
| 业务规则 3.2 | `independent-contract` | `one-rsu` | Has a state condition and an action |
| 业务规则 3.3 | `independent-contract` | `one-rsu` | Has a state condition and an action |

`原型` is `visual-placeholder` and is not an RSU. Record the visible marker itself as `not-rsu`. If unreadable visual details may contain behavior that changes the partition decision, record a separate `unresolved` source range with a question and `pending` coverage; do not create an RSU whose content is only `原型`.

## Test-point boundary

For the composite result RSU, the later generation stage may derive separate candidates for filtering result, task-ID descending order, pagination, and each observable result field when those are distinct test intents. That later decomposition does not justify splitting the source mapping into field-only RSUs.
