# Person 人物档案设计

## 1. 设计结论

Person 不使用固定的 16 个 Domain 槽位，也不复制 Domain 的 `name`、`keywords`
等说明。

系统采用两套彼此独立的结构：

1. `step2_domain_taxonomy_v3.py`：负责内容分类、生成引导和领域覆盖统计。
2. Person：只保存人物真正拥有的状态，每条事实占一行。

V3 taxonomy 是分类标签，不是人物数据的嵌套容器。

人物状态是一张平铺的记录表。每条记录包含 `domain`、`subcategory`、`field`、`mutable` 和 `value`。Person 不再分 `core` 和 `initial_state`。

---

## 2. Person 整体结构

```yaml
person_id: P001
round_id: v0
states: []
```

- `round_id`：该档案所属轮次。初始人物档案为 `v0`。
- `states`：人物当前拥有的全部状态记录。
- `mutable`：这一行事实是否允许在 Benchmark 中变化。

Person 中没有 Exposure，也不保存完整 Domain 模板。

---

## 3. Taxonomy 的使用方式

`domain` 和 `subcategory` 是记录上的分类字段，用来说明这条事实属于哪一类。

规则：

- `domain` 使用 `DOMAIN_DEFINITIONS` 里的中文名称，不使用英文代码。
- `subcategory` 必须来自对应 Domain 的 `SUBCATEGORY_DEFINITIONS`。
- Domain 的 `name`、`keywords`、`extract`、`scope` 和 `exclude` 在运行时从 V3 taxonomy 查询，不复制进 Person。
- 同一组 `domain + subcategory + field` 只能出现一次。
- `mutable` 属于这一行，不挂在整个子类上。

---

## 4. 状态组织方式

一条事实写一行，字段名显式放在 `field` 上：

```yaml
states:
  - domain: 身份与基础信息
    subcategory: 姓名称谓
    field: legal_name
    mutable: false
    value: 林晓
  - domain: 身份与基础信息
    subcategory: 姓名称谓
    field: nickname
    mutable: false
    value: 小晓
  - domain: 身份与基础信息
    subcategory: 居住地址
    field: address
    mutable: true
    value: 苏州工业园区
```

只创建人物实际拥有的记录，不建立空槽位。

---

## 5. mutable：是否可变

`mutable: false` 保存 Benchmark 运行期间禁止修改的信息：

```yaml
states:
  - domain: 身份与基础信息
    subcategory: 姓名称谓
    field: legal_name
    mutable: false
    value: 林晓
  - domain: 身份与基础信息
    subcategory: 出生信息
    field: birth_date
    mutable: false
    value: 1997-05-18
  - domain: 身份与基础信息
    subcategory: 出生信息
    field: birthplace
    mutable: false
    value: 青岛
```

`mutable: true` 保存故事开始时实际成立、之后可以变化的状态：

```yaml
states:
  - domain: 身份与基础信息
    subcategory: 居住地址
    field: address
    mutable: true
    value: 苏州工业园区
  - domain: 职业与工作
    subcategory: 职业状态与规划
    field: employment_status
    mutable: true
    value: employed
```

规则：

- `mutable: false` 的信息创建后只读。
- 不保存可计算值，例如年龄可以由出生日期计算。
- 职业、住址、婚姻、资产、性格和偏好标记为 `mutable: true`。
- “属于身份与基础信息”不代表必须不可变；领域与是否可变是两回事。

---

## 6. 稀疏状态

状态只保存这个人物实际存在的信息，不创建空 Domain，也不填充大量 `null`。

规则：

- `domain` 必须是 V3 的 Domain。
- `subcategory` 必须是该 Domain 下的 Subcategory。
- 新增人物状态时，追加一行，并写明 `field`、`mutable` 和 `value`。
- 没有相关信息就不创建对应记录。
- `null` 只表示明确没有，不能表示未知。
- 初始版本创建后，`mutable: false` 的值保持不变。
- `mutable: true` 的后续变化写入目标状态的新版本，不覆盖初始值。
- V3 的 16 个 Domain 都可以被使用，但一个人物不需要覆盖全部 Domain。

---

## 7. 最小完整示例

```yaml
person_id: P001
round_id: v0

states:
  - domain: 身份与基础信息
    subcategory: 姓名称谓
    field: legal_name
    mutable: false
    value: 林晓
  - domain: 身份与基础信息
    subcategory: 姓名称谓
    field: nickname
    mutable: false
    value: 小晓
  - domain: 身份与基础信息
    subcategory: 出生信息
    field: birth_date
    mutable: false
    value: 1997-05-18
  - domain: 身份与基础信息
    subcategory: 出生信息
    field: birthplace
    mutable: false
    value: 青岛
  - domain: 身份与基础信息
    subcategory: 性别
    field: gender
    mutable: false
    value: 女
  - domain: 身份与基础信息
    subcategory: 国籍归属
    field: nationality
    mutable: false
    value: 中国
  - domain: 身份与基础信息
    subcategory: 居住地址
    field: address
    mutable: true
    value: 苏州工业园区
```

核心关系：

```text
V3 taxonomy → 说明一条信息属于什么内容
round_id    → 说明这份档案属于哪一轮
mutable     → 说明这一行信息是否允许变化
states      → 说明人物当前拥有哪些状态记录
```
