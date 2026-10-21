# 目标状态规划设计

## 1. 目标

系统每轮编排人物三个月后已经确定的状态。`value` 只填该字段的值，不是待办，也不是可能会发生的事。不要加“已”“已经”来强调。

每轮规划只允许两种操作：

- `update`：延伸一条已有状态链。
- `create`：新增一条状态链。

保持不变的状态不输出。每轮最终目标都必须完成。

---

## 2. 整体流程

```text
读取人物状态和累计状态链
    ↓
补齐初始累计状态链
    ↓
随机确定 1 个主线和 2 个副线
    ↓
调用大模型：提供人物摘要、这 3 个领域的当前状态，以及每个领域的全部子类说明，生成未来三个月的变化
    ↓
校验后，本轮 plan 就是目标状态
    ↓
把这些变化追加进累计状态链，两份一起返回
```

领域从 V3 分类里随机确定，不调用大模型。主线不选 `身份与基础信息`、`纪念日` 和 `兴趣爱好`，副线可以是其余任意领域。主线是未来三个月故事的中心，两条副线是这个故事可以带动的领域。

大模型看到人物摘要、选中领域里每条状态链的最后一个版本，以及该领域全部子类的名称、核心问题、定义和示例。子类说明不是只有当前状态里出现过的那几类。本轮一共生成 20 条变化，不规定每个领域分到多少条。每条变化只给对应字段增加一个版本：修改已有字段时 `op` 为 `update`，新增字段时 `op` 为 `create`。已有状态链能推出明显不同的下一阶段时尽量 `update`，下一阶段不能还是同一个状态；写不出就 `create`，不要为了凑数量编造变化。同一条状态链本轮只增加一个版本。

`update` 的 `version` 等于该链最后一个版本加一。`create` 此前没有版本，`version` 等于本轮 `round_id` 的数字。新版本的 `round_id` 都是本轮编号，由当前累计状态的 `round_id` 加一得到，例如 `v0` 之后是 `v1`。`event_summary` 先留空，等事件图生成后再写入。

人物档案补入的字段仍然使用 `op: initial`，不会出现在本轮最终目标里。

---

## 2.1 初始累计状态链

输入是 `ProfileData` 和 `PlanningState`，输出仍是 `PlanningState`。

比较单位是 `Domain + Subcategory + 字段`：

- 三层都已存在：不修改该状态链。
- 人物状态多出的字段：追加一条新状态链。
- 新链的 `round_id` 与 `ProfileData.round_id` 相同，`version` 等于该版本号。`v0` 对应 `version: 0`。
- 新链的 `op` 为 `initial`，`mutable` 取人物状态中这一行的值。
- 人物状态已经是一行一个字段，补齐时按原行写入，不再拆分 `value`。

补齐结束后，用人物摘要文本更新 `person_summary`。

---

## 2.2 本轮累计更新

本轮规划在初始累计状态链已经写好之后进行。领域随机选出，不要求这三个领域事先已经出现在累计状态中。

校验规则：

- 随机选出 1 个主线和 2 个副线，互不重复。主线不能是 `身份与基础信息`、`纪念日` 或 `兴趣爱好`。
- 每条变化的领域必须是这 3 个领域之一，总数为 20 条，不按领域分配数量。
- 同一个 `Domain + Subcategory + 字段` 本轮只能出现一次。
- `update` 的字段必须已存在、`mutable` 为 `true`，且新值不同于当前值。
- `create` 的字段必须尚不存在，子类必须属于该领域的 V3 分类。新链的 `mutable` 由模型根据事实性质给出。
- 20 条变化里，能形成明显不同的下一阶段时尽量 `update`。`update` 不能还是上一阶段的同一个状态；写不出这种变化就用 `create`，不要为了增加 `update` 数量编造变化。

校验通过后才写入累计状态链。本轮最终目标状态就是这 20 条变化，不包含未改动状态链的最后版本，也不包含 `initial` 版本。

---

## 3. 用于目标状态规划的累计状态

规划器读取人物当前已有的全部状态链，而不是只读取上一轮结果。

```yaml
planning_state:
  person_id: P001
  person_summary: 林晓，产品经理，目前住在苏州，生活方式偏务实。
  round_id: v3

  states:
    - domain: 职业与工作
      subcategory: 职业状态与规划
      field: employment_status
      mutable: true
      versions:
        - version: 0
          round_id: v0
          op: initial
          value: employed
          event_summary: 人物初始状态为在职
        - version: 1
          round_id: v2
          op: update
          value: unemployed
          reason: 所在团队收缩，三个月内离职是说得通的
          event_summary: 所在公司裁员后失去工作

    - domain: 旅行与出行
      subcategory: 交通出行方式
      field: commute_mode
      mutable: true
      versions:
        - version: 0
          round_id: v0
          op: initial
          value: public_transit
          event_summary: 初始使用公共交通通勤
        - version: 1
          round_id: v1
          op: update
          value: drive_car
          reason: 工作地点变远，公共交通通勤时间过长，三个月内买车自己开车上班
          event_summary: 买车后开始自己开车上班

    - domain: 兴趣爱好
      subcategory: 户外活动
      field: outdoor_activity
      mutable: true
      versions:
        - version: 2
          round_id: v2
          op: create
          value: hiking
          reason: 近期缺少户外活动，朋友邀约后三个月内开始周末徒步
          event_summary: 在朋友邀请下开始周末徒步
```

### 3.1 字段说明

- `person_id`：人物唯一标识。
- `person_summary`：帮助模型快速理解人物，不作为结构化事实源。
- `round_id`：累计状态当前已经规划到的轮次。下一轮编号在此基础上加一。
- `states`：平铺的累计状态链。每条记录用 `domain`、`subcategory`、`field` 标识一个字段。
- `mutable`：该字段是否允许在后续轮次变化。`false` 表示创建后只读，`true` 表示可以更新。
- `versions`：按轮次追加的全部状态版本。
- `version`：状态链内部递增的版本号。
- `round_id`：该版本产生于哪一轮。
- `op`：该版本是初始值、新增值还是更新值。
- `value`：该版本的字段值。只写值本身，不写计划或待办，也不加“已”“已经”。
- `reason`：说明三个月内推进到这个值为什么合理。`update` 必须写明上一阶段，并同时依据人物摘要和该字段的当前状态链。`create` 依据人物摘要。不能编造材料里没有的原因。初始版本没有这个字段。
- `event_summary`：造成该版本的事件摘要，供下一轮规划参考。规划本轮变化时先留空。

每条状态链最后一个版本的 `value` 就是当前状态。

---

## 4. 给下游的最终目标状态

最终目标状态只包含本轮三个月必须完成的变化。
下游只接收 `target_state`，不接收规划过程中的候选状态。
一轮实际输出 20 条变化，下面只展示其中 3 条的结构。

```yaml
target_state:
  plan_id: TP-P001-v3
  person_id: P001
  person_summary: 林晓，产品经理，目前住在苏州，生活方式偏务实。
  round_id: v3
  horizon: 3_months

  changes:
    - change_id: CH01
      op: update
      domain: 职业与工作
      subcategory: 职业状态与规划
      field: employment_status
      value: employed
      reason: 裁员后的三个月内重新找到工作

    - change_id: CH02
      op: update
      domain: 旅行与出行
      subcategory: 交通出行方式
      field: commute_mode
      value: public_transit
      reason: 工作地点变远，公共交通通勤时间过长，三个月内买车自己开车上班

    - change_id: CH03
      op: create
      domain: 健康与医疗
      subcategory: 健康管理
      field: exercise_frequency
      value: 每周三次
      reason: 久坐办公后身体不适，三个月内开始规律运动
```

### 4.1 字段说明

- `plan_id`：本轮目标状态计划标识。
- `person_id`：目标人物。
- `person_summary`：人物摘要，取自累计状态里的 `person_summary`。
- `round_id`：本轮编号。
- `horizon`：固定为三个月。
- `changes`：本轮必须完成的全部状态变化。
- `change_id`：单条变化标识。
- `op`：只能是 `update` 或 `create`。
- `domain`、`subcategory`：状态所属的 V3 分类。
- `field`：状态字段名。
- `value`：本轮结束时该字段的值，只写值本身；`create` 时它也是状态链初始值。不能写成计划、准备、预留、开始、打算，也不要加“已”“已经”。
- `reason`：`update` 写明上一阶段，并结合人物摘要和当前状态链，说明下一阶段变成这个值为什么合理；`create` 依据人物摘要说明新事实为什么会出现。下游编排事件时以此为原因，不把它当成已经发生的事件。

---

## 5. 生成规则

1. 从 V3 领域中随机选择 3 个。主线排除 `身份与基础信息`、`纪念日` 和 `兴趣爱好`，副线不限。
2. 模型接收人物摘要、这 3 个领域里每条状态链的最后一个版本，以及每个领域的全部子类说明。最后一个版本是 `update` 的上一阶段。20 条变化如何分配由模型决定。`create` 按子类的核心问题选择，不要重复堆进当前状态里已经出现的少数子类。
3. `update` 只能用于已经有上一阶段的字段。`create` 只能用于还没有状态链的新字段。其余 domain 不能写状态链。
4. `update` 必须有明显的阶段变化，不能还是上一阶段的同一个状态。换一种说法、加修饰、把原值嵌进新句子，都算同一阶段。例如不能把“苏州工业园区”写成“仍居住在苏州工业园区”或“已稳定居住在苏州工业园区内的固定住址”，也不能从研究生变成本科。写不出另一个阶段就用 `create`。
5. `update` 继承已有分类，不重新分类，也不能修改 `mutable: false` 的字段。
6. `create` 的 Domain 必须是本轮选中的领域，Subcategory 必须属于该领域的 V3 分类。
7. `create.field` 不能与对应分类下的已有字段重复。
8. `create.value` 是状态初始值，不描述成“无 → 新值”。
9. `update` 的 `reason` 必须写明上一阶段，并结合人物摘要和该字段的当前状态链，说明下一阶段变成这个值为什么合理。`create` 的 `reason` 依据人物摘要。
10. 保持不变的状态不进入 `changes`。
11. 输出的所有 `changes` 都是本轮已经确定的最终状态。`value` 只填字段的值，不能写成尚未发生的安排，也不要用“已”“已经”包装旧值。

---

## 6. 下一轮如何继续

本轮规划结束时，变化已经追加到累计状态链，`event_summary` 仍为空。事件图生成后，再把对应事件摘要写回这些版本。

下一轮再次读取：

```text
人物摘要 + 全部状态链 + 每个版本的事件总结
```

然后重新随机选择 1 个主线和 2 个副线，继续规划未来三个月。状态历史只追加，不覆盖、不删除。
