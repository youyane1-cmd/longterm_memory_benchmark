# QACandidate.payload 三种放法

`QACandidate` 外壳字段（`candidate_id` / `ability` / `template` / `query_time`）所有题型共用；**差异只在 `payload`**。

原则：

- **一道题 = 一个 `QACandidate`**，不要用「多个 candidate 组成元组」表示一题。
- 复杂结构进 `payload`；拼 prompt 时把需要的片段整段塞进去即可。

---

## 1. 单跳 / 单版本（当前信息抽取）

一个 subject、一个 value、一场 session、一条对齐后的 extract。

```python
payload = {
    "domain": "财务与资产",
    "subcategory": "消费支出",
    "subject": "大额设备支出",
    "value": ["AirPods Pro 2"],
    "op": "create",
    "round_id": "v1",
    "event_id": "v1-EV003",
    "session": { ... },   # 该 event 对应整场对话
    "extract": { ... },   # 该 session 的抽取；evidence 只保留本 subject
}
```

适用：单跳信息抽取、以及其它「只盯一个当前事实」的题。

说明：这是下面「多版本」在 `len(versions)==1` 时的平铺写法，读起来更直接。

---

## 2. 同一 subject 多版本（知识更新）

还是一个 candidate，版本进列表；每版自带当时的 session / extract（没有 event 的可为 `null`）。

```python
payload = {
    "domain": "身份与基础信息",
    "subcategory": "居住地址",
    "subject": "现居地",
    "versions": [
        {
            "version": 0,
            "round_id": "v0",
            "op": "initial",
            "value": ["苏州工业园区"],
            "event_id": None,
            "session": None,
            "extract": None,
        },
        {
            "version": 1,
            "round_id": "v3",
            "op": "update",
            "value": ["苏州高新区"],
            "event_id": "v3-EV005",
            "session": { ... },
            "extract": { ... },
        },
    ],
    # 可选便捷字段，方便组 gold / 干扰
    "current_value": ["苏州高新区"],
    "stale_value": ["苏州工业园区"],
}
```

适用：知识更新（问当前值、问旧值、多版本干扰等）。

与写法 1 的关系：写法 1 ≈ 只有一条的 `versions` 再把字段摊到顶层。若希望全库格式统一，单跳也可以只写 `versions: [一条]`，少一套平铺字段。

---

## 3. 多 subject 组合（多跳 IE / 跨事实推理）

一道题要拼多个不同 subject（或多次跳），用 `hops` 列表；每一跳的内部形状可与写法 1 相同，也可以是写法 2 的一条链。

```python
payload = {
    "hops": [
        {
            "domain": "...",
            "subcategory": "...",
            "subject": "现居地",
            "value": ["苏州高新区"],
            "event_id": "v3-EV005",
            "session": { ... },
            "extract": { ... },
        },
        {
            "domain": "...",
            "subcategory": "...",
            "subject": "父母居住地",
            "value": ["青岛"],
            "event_id": "v2-EV001",
            "session": { ... },
            "extract": { ... },
        },
    ],
    "relation": "compare_distance",  # 可选：这道题要做什么组合
}
```

若某一跳本身是更新链，该 hop 里用 `versions` 即可：

```python
"hops": [
    {"subject": "现居地", "versions": [ ... ]},
    {"subject": "通勤方式", "value": ["地铁"], "session": { ... }, "extract": { ... }},
]
```

适用：多跳信息抽取、跨事实开放域、部分时间题（多事件排序）等。

---

## 对照

| 放法 | 核心键 | 典型题型 |
|------|--------|----------|
| 1 单跳平铺 | `subject` + `value` + `session` + `extract` | 单跳 IE |
| 2 多版本 | `subject` + `versions[]` | 知识更新 |
| 3 多跳组合 | `hops[]`（元素同 1 或 2） | 多跳 IE / 组合推理 |

| 不要这样做 | 原因 |
|------------|------|
| 一题拆成多个 `QACandidate` 再组成元组 | `question_id` / gold / 校验边界混乱 |
| 把多 session 硬塞进外壳字段 | 外壳应保持稀薄，复杂结构进 `payload` |

---

## 拼 prompt

三种写法都一样：`build_messages` 读 `candidate.payload`，把 `session` / `extract` / `versions` / `hops` 需要的部分格式化进 user message；不必先改成 Python tuple。
