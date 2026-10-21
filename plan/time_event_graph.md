# 时间事件图设计

## 1. 目标

时间事件图用于记录人物世界中按时间发生的事件。

系统每轮规划未来三个月的新事件，然后直接追加到已有事件列表中。历史事件不修改，
也不重新生成。

当前版本只设计：

- 事件发生时间；
- 事件内容；
- 事件绑定的目标状态。

暂不设计因果边、前置条件和复杂事件类型。

---

## 2. 规划输入

```yaml
planning_input:
  person_summary: 人物画像摘要
  time_range: 2020-01-03 至 2020-04-06
  target_states: 本轮 20 条状态的 field 和 value
```

- `person_summary`：来自最终目标状态，帮助模型理解人物整体情况。
- `time_range`：由 `TimePlan` 按人物起始日期和 `round_id` 算出。`v0` 是起始时间节点，之后每一轮加三个月。事件日期由模型决定，但必须落在这个范围内。
- `target_states`：本轮必须实现的状态。送给模型的是每条状态的 `change_id`、`field` 和 `value`。一条事件可以包含多条相关状态。

---

## 3. 时间事件图结构

```yaml
time_event_graph:
  person_id: P001

  events:
    - event_id: EV001
      time: 2026-01-15
      event: 林晓购买了一辆特斯拉 Model 3
      goal_state: [CH01]

    - event_id: EV002
      time: 2026-02-03
      event: 林晓周末和朋友去郊外聚餐
      goal_state: []
```

### 3.1 字段说明

- `person_id`：事件图所属人物。
- `events`：按世界时间排列的全部事件。
- `event_id`：事件唯一标识。
- `time`：事件发生的世界时间。
- `event`：事件的简洁描述。
- `goal_state`：该事件实现或推动的目标状态 `change_id`。

`goal_state` 使用数组：

- 一个事件可以绑定一个或多个目标状态；
- 多个事件也可以共同绑定同一个目标状态；
- 与目标状态无关的日常事件或噪声事件使用空数组 `[]`。

---

## 4. 每轮新增事件

事件规划器每轮只输出本轮新增的事件：

```yaml
new_events:
  - event_id: EV021
    time: 2026-07-08
    event: 林晓参加新公司的面试
    goal_state: [CH01]

  - event_id: EV022
    time: 2026-08-01
    event: 林晓正式入职新公司
    goal_state: [CH01]

  - event_id: EV023
    time: 2026-08-05
    event: 林晓开始乘坐地铁上下班
    goal_state: [CH02]

  - event_id: EV024
    time: 2026-08-20
    event: 林晓和朋友在家看了一场电影
    goal_state: []
```

生成完成后，将 `new_events` 追加到原来的 `events`，再按 `time` 排序。

---

## 5. 目标状态绑定规则

1. 本轮每个目标状态都必须至少被一个 Event 的 `goal_state` 引用。
2. Event 只引用目标状态的 `change_id`，不复制目标状态内容。
3. 实现同一个目标的多个 Event 可以重复引用同一个 `change_id`。
4. 没有状态目标的事件使用 `goal_state: []`。
5. 噪声事件允许存在，但不能影响已经确定的人物状态。
6. Event 的 `event` 后续可以作为对应状态版本的 `event_summary`。

---

## 6. 追加规则

1. 已有 Event 不修改、不删除。
2. 新 Event 的 `event_id` 不能与历史事件重复。
3. 新 Event 的时间由模型决定，并且必须位于 `TimePlan` 为本轮算出的三个月起止日期内。
4. 新 Event 不能与人物当前属性和历史事件冲突。
5. 追加完成后的 `events` 始终按 `time` 排列。

当前阶段不要求显式记录事件之间的因果关系。只要新事件在人物经历、时间和目标状态上
保持合理连续即可。
