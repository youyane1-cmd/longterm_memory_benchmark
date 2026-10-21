# 长期记忆 Benchmark：故事时间线编排总框架

> 本文只讲一件事：**人物的故事怎样一章接一章地连续发展下去。**
>
> 不涉及对话生成、出题、Evidence 等细节。

---

## 1. 先说结论

你原来的理解是：

```text
每章：遍历领域池 → 选几个领域 → 构造几个 Thread → 选一个主 Thread → 编排时间线
```

这样做的问题是：每一章都像重新开局，上一章的故事无法自然延续，所以会感觉“跨不了章节”。

正确的做法是：

```text
只在最开始用领域池建几条故事
之后每一章都在这几条故事上“接着往下写”
```

跨章节靠的是：**每条故事都有一张“进度卡”，写完一章就更新这张卡，下一章从卡上记录的位置继续写。**

---

## 2. Thread 就是一张“故事进度卡”

可以把 Thread 想成一部连续剧里的一条剧情线，比如“小林的公司”“小林的钱”“小林的车”。

每条剧情线有一张进度卡，上面只记四件事：

```text
1. 这条故事讲什么
2. 已经演到哪一步了
3. 还有什么悬念没解决
4. 下一步可能怎么发展
```

例如：

```text
【进度卡：小林的公司】
讲什么：小林所在创业公司的经营状况
演到哪：公司正在找融资，但不顺利
悬念：融资能不能成功？
下一步可能：融资成功 / 裁员 / 破产
```

这张卡不是时间表，也不是剧本，只是“故事目前停在哪里”的记录。

---

## 3. “持久化”是什么意思

“持久化”的意思很简单：

> **这些进度卡保存在一个文件里，一章写完不会删掉，下一章直接拿来用。**

每一章都做三件事：

```text
章节开始：打开保存的进度卡
章节中间：根据进度卡决定本章让哪几条故事往前走一步
章节结束：把新的进度写回进度卡
```

原文中的“推进游标”，就是指“把进度卡上的‘演到哪’往后改”。

“不能每章重建”，就是指：**下一章不能扔掉这些卡，重新从领域池编新故事。**

---

## 4. 一个跨四章的例子

人物：小林，创业公司产品经理。

### 第 0 步：初始化（只做一次）

从领域池中挑几个适合小林的领域，各建一张进度卡：

```text
【公司】演到：公司正常经营，但现金流有点紧
【钱】  演到：收入稳定，有一些存款
【车】  演到：没车，一直在考虑买车
```

以后不会再这样整体从领域池开始挑。

### 第 1 章（1～2 月）

读取三张卡，选择本章主线：**车**。

本章发生：

```text
1 月 10 日  比较几款车型
1 月 25 日  买了一辆特斯拉
2 月 1 日   开始开车上班
```

章节结束，更新进度卡：

```text
【公司】演到：现金流紧张（本章没推进，原样保留）
【钱】  演到：买车花掉部分存款，每月多了车贷
【车】  演到：已经有车，开车上班
```

### 第 2 章（3～4 月）

读取上一章留下的卡。

“公司”这张卡上的悬念“现金流紧张”已经放了一章，适合推进，所以本章主线是：**公司**。

本章发生：

```text
3 月 5 日   融资谈判失败
4 月 2 日   公司宣布破产
4 月 2 日   小林收入中断
```

主线又影响了“钱”这张卡，所以“钱”跟着变化。

章节结束，更新：

```text
【公司】演到：公司已破产；新悬念：接下来去哪工作？
【钱】  演到：收入中断，还有车贷；新悬念：钱够用吗？
【车】  演到：仍然有车（本章没推进）
```

### 第 3 章（5～6 月）

读取卡片后发现：“钱”的压力最迫切，所以本章主线是：**钱**。

本章发生：

```text
5 月 8 日   重新做预算
5 月 20 日  决定卖车
6 月 3 日   把车卖给同事老周
6 月 4 日   改坐地铁
```

章节结束，更新：

```text
【公司】演到：已破产，还没开始找工作（本章暂停）
【钱】  演到：卖车后压力缓解
【车】  演到：车已卖出，这条故事结束
```

### 第 4 章（7～8 月）

读取卡片后发现：“公司”这张卡已经暂停了一章，悬念“接下来去哪工作”仍未解决，所以本章主线重新回到它。

本章发生：

```text
7 月 3 日   开始投简历
8 月 15 日  拿到新公司的录用通知
```

### 从这个例子可以看出

```text
“公司”故事：第 0 章建立 → 第 2 章推进 → 第 3 章暂停 → 第 4 章继续
“车”故事：  第 0 章建立 → 第 1 章买车 → 第 3 章卖车 → 结束
```

故事之所以能跨越章节，是因为每一章都从上一章写回的进度卡开始，而不是重新编一套。

---

## 5. 如果每章重建，会出什么问题

假设第 3 章不读取进度卡，而是重新从领域池挑领域、编故事：

```text
可能挑中“旅游”“健身”“恋爱”
然后编出：小林去三亚旅游、办健身卡、开始约会
```

这时就会出现：

- 公司破产后“接下来去哪工作”这个悬念没人管了；
- 刚刚收入中断，却突然去高消费旅游，不合逻辑；
- 车贷、卖车这条自然后果消失了；
- 每章之间看起来都是彼此无关的小故事。

这就是“跨不了章节”的原因。

---

## 6. 每章的编排流程

```text
1. 打开进度卡
   读取每条故事演到哪、还有什么悬念。

2. 列出本章候选
   主要看已有卡片中值得推进的故事；
   同时检查是否满足第 7 节的新领域触发条件，满足则补一张新卡。

3. 每条候选故事只提出“下一步”
   例如“公司：融资失败后破产”，而不是写完整后续人生。

4. 选一条主线
   本章重点推进它。

5. 看主线会影响哪些其他故事
   例如公司破产 → 收入中断，所以“钱”也要跟着变。
   没有被影响的故事可以本章暂停。

6. 把本章事件按先后顺序放进日历
   例如必须先破产，再收入中断，再卖车。

7. 章节结束，把新进度写回进度卡
   记录：演到哪、哪些悬念解决了、新出现了什么悬念。
```

然后进入下一章，重复这个过程。

---

## 7. 故事轮换的具体算法

本节回答：从程序角度，旧故事怎样**一定会结束**，新故事怎样**一定会出现**。

核心靠三个机制：

```text
机制 A：故事模板有有限阶段，每个阶段有最长停留章数 → 旧故事一定会走到结局
机制 B：长期没推进的故事自动休眠、再自动关闭       → 被冷落的故事会退场
机制 C：每章按固定规则计算“本章要开几张新卡”，
        再按打分加权抽样选哪个领域              → 新故事一定会进来
```

LLM 不参与“开不开、关不关、选哪个领域”的决定，这些全部由程序完成。LLM 只负责填具体内容（对象叫什么、养什么猫、具体日期）。

### 7.1 数据一：故事模板库（代替“领域池”）

领域池不再是一串领域名，而是一组**故事模板**。每个模板就是一个有限状态机：

```yaml
template_id: romance_new
domain: relationship

entry_condition:              # 程序判断能否开这张卡
  - state.relationship.status == "single"
  - 22 <= state.age <= 45

phases:                       # 按顺序推进，最后一个阶段是结局
  - {id: meet,     min_ch: 1, max_ch: 1, background_only: true}
  - {id: dating,   min_ch: 1, max_ch: 2}
  - {id: together, min_ch: 2, max_ch: 4}
  - {id: outcome,  terminal: true, branches: [breakup, engaged]}

state_writes:                 # 进入某阶段时写入的属性
  together: {relationship.status: "dating"}
  breakup:  {relationship.status: "single"}
  engaged:  {relationship.status: "engaged"}

hooks:                        # 进入某阶段后，可能带出其他领域
  together: [{domain: family, weight: 0.6}]      # 见家长
  breakup:  [{domain: travel, weight: 0.5}]      # 散心旅行

on_close_spawn:               # 结局后自动接续的新模板
  engaged: [wedding_plan]

cooldown_after_close: 4       # 关闭后 4 章内不再开同一模板
persona_prior: 0.6            # 该人物设定下，这类故事的基础可能性
```

再举两个模板的简写：

```yaml
template_id: job_loss
domain: career
phases:
  - {id: crisis,     min_ch: 1, max_ch: 2}
  - {id: collapse,   min_ch: 1, max_ch: 1}
  - {id: unemployed, min_ch: 1, max_ch: 2}
  - {id: job_search, min_ch: 1, max_ch: 2}
  - {id: outcome,    terminal: true, branches: [new_job]}
hooks:
  unemployed: [{domain: pet, weight: 0.5}, {domain: study, weight: 0.6}]
on_close_spawn:
  new_job: [new_job_adaptation]

template_id: adopt_pet
domain: pet
entry_condition: [state.housing.pet_allowed == true]
phases:
  - {id: consider, min_ch: 1, max_ch: 1, background_only: true}
  - {id: adopt,    min_ch: 1, max_ch: 1}
  - {id: routine,  min_ch: 1, max_ch: 3}
  - {id: outcome,  terminal: true, branches: [settled]}
```

**机制 A 就体现在 `max_ch` 上**：一张卡在某阶段停留达到 `max_ch`，下一章必须推进。因此每个故事的最长寿命是各阶段 `max_ch` 之和，不会无限演下去。

### 7.2 数据二：进度卡（Thread 记录）

```yaml
thread_id: T-07
template_id: romance_new
domain: relationship
status: active            # active / dormant / closed
phase: dating
chapters_in_phase: 1      # 在当前阶段已停留几章
created_ch: 4
last_advanced_ch: 5       # 最后一次推进是在第几章
```

### 7.3 数据三：钩子队列和季节表

事件提交后，把模板中声明的 `hooks` 放进人物的钩子队列：

```yaml
hooks:
  - {domain: pet,   weight: 0.5, source: EV-038, expire_ch: 5}
  - {domain: study, weight: 0.6, source: EV-038, expire_ch: 5}
```

季节钩子由一张固定表每章自动加入：

```yaml
season_hooks:
  "01-02": [{domain: family, weight: 0.8}]   # 春节
  "07-08": [{domain: travel, weight: 0.5}]   # 暑期
  "11-12": [{domain: health, weight: 0.4}]   # 年底体检
```

### 7.4 全局参数

```yaml
ACTIVE_MIN: 3            # 活跃故事下限
ACTIVE_MAX: 5            # 活跃故事上限
NEW_MAX_PER_CH: 1        # 每章最多新开几张卡（低于下限时可到 2）
FORCE_NEW_AFTER: 2       # 连续 2 章没开新卡，本章必须开
STRONG_HOOK: 0.6         # 钩子权重达到该值，可以触发开新卡
DORMANT_AFTER: 2         # 连续 2 章没推进 → 休眠
CLOSE_AFTER_DORMANT: 3   # 休眠 3 章仍未被唤醒 → 关闭
HOOK_TTL: 3              # 钩子 3 章后过期
MAX_MAIN_STREAK: 2       # 同一张卡最多连续 2 章当主线
```

### 7.5 每章开头依次执行的五个函数

```python
def plan_chapter_threads(person, ch, rng):
    add_season_hooks(person, ch)
    update_lifecycle(person, ch)          # 机制 B：休眠、关闭、唤醒
    n = decide_new_count(person, ch)      # 机制 C：本章开几张新卡
    open_new_threads(person, ch, n, rng)  # 机制 C：开哪几张
    return pick_roles(person, ch)         # 选主线、必须推进的卡
```

**函数 1：更新生命周期**

```python
def update_lifecycle(person, ch):
    for t in person.threads:
        if t.status == "closed":
            continue
        idle = ch - t.last_advanced_ch

        if t.phase_is_terminal_and_done():
            close(t, ch)                               # 正常结局
        elif t.status == "active" and idle >= DORMANT_AFTER and not t.overdue():
            t.status = "dormant"                       # 被冷落，先休眠
        elif t.status == "dormant":
            if has_hook(person, t.domain):
                t.status = "active"                    # 有相关钩子，唤醒
            elif idle >= DORMANT_AFTER + CLOSE_AFTER_DORMANT:
                close(t, ch)                           # 静默退场，属性保持最后的值

def close(t, ch):
    t.status = "closed"
    for tpl in t.template.on_close_spawn.get(t.outcome, []):
        create_thread(tpl, ch, as_successor=True)      # 接续故事，不占新卡名额
```

**函数 2：决定本章开几张新卡**

```python
def decide_new_count(person, ch):
    active = person.count(status="active")

    if active < ACTIVE_MIN:
        return min(ACTIVE_MIN - active, 2)             # 有空位，必须补
    if ch - person.last_new_ch >= FORCE_NEW_AFTER:
        if active >= ACTIVE_MAX:
            retire_lowest_priority(person)             # 满了就先让一张卡休眠
        return 1                                       # 太久没新故事，强制开
    if active < ACTIVE_MAX and max_hook_weight(person) >= STRONG_HOOK:
        return 1                                       # 有强钩子，顺势开
    return 0
```

**函数 3：选开哪个模板**

```python
def open_new_threads(person, ch, n, rng):
    cands = []
    for tpl in TEMPLATES:
        if not tpl.entry_condition(person.state):   continue  # 与当前状态冲突
        if tpl.domain in person.active_domains():   continue  # 同领域已有活跃卡
        if in_cooldown(tpl, person, ch):            continue  # 刚结束过

        score = (0.35 * hook_score(person, tpl.domain)        # 有事件或季节引出
               + 0.25 * freshness(person, tpl.domain, ch)     # 很久没出现
               + 0.25 * coverage_gap(person, tpl)             # 能补素材缺口
               + 0.15 * tpl.persona_prior)                    # 符合人设
        cands.append((tpl, score))

    for tpl in weighted_sample(cands, n, temperature=0.5, rng=rng):
        t = create_thread(tpl, ch)                     # 从第一个阶段开始
        consume_hook(person, tpl.domain)
        person.last_new_ch = ch

def freshness(person, domain, ch):
    last = person.last_seen_ch(domain)                 # 从未出现过返回 None
    return 1.0 if last is None else min(1.0, (ch - last) / 6)
```

使用加权抽样而不是取最高分，是为了避免每个人物都走同一套故事；随机数种子由 `person_id + ch` 决定，保证可复现。

**函数 4：选主线和必须推进的卡**

```python
def pick_roles(person, ch):
    active = person.threads_with(status="active")

    must_advance = [t for t in active if t.chapters_in_phase >= t.phase.max_ch]

    main_cands = [t for t in active
                  if not t.phase.background_only
                  and not t.main_streak_reached(MAX_MAIN_STREAK)]
    main = max(main_cands, key=lambda t:
               0.4 * t.chapters_in_phase / t.phase.max_ch   # 越接近超时越优先
             + 0.3 * min(1.0, (ch - t.last_advanced_ch) / 3)  # 越久没推进越优先
             + 0.3 * coverage_gap(person, t.template))

    new_cards = [t for t in active if t.created_ch == ch]    # 新卡本章只做背景小事件
    return main, must_advance, new_cards
```

**函数 5：章节结束时写回**

```python
def commit_chapter(person, ch, committed_events):
    for ev in committed_events:
        t = ev.thread
        if ev.advances_phase:
            t.phase = t.next_phase(ev.branch)
            t.chapters_in_phase = 0
            t.last_advanced_ch = ch
            push_hooks(person, t.template.hooks.get(t.phase), expire=ch + HOOK_TTL)
    for t in person.threads_with(status="active"):
        t.chapters_in_phase += 1
    drop_expired_hooks(person, ch)
```

### 7.6 模拟运行：八章中的故事轮换

初始：`工作(job_loss)`、`钱(budget)`、`车(buy_car)` 三张卡。

```text
C1  1-2 月
    季节钩子 family 0.8 ≥ 0.6 → 开 1 张：家庭(spring_festival)，本章只做背景
    主线：车（买车）
    活跃：工作、钱、车、家庭

C2  3-4 月
    主线：工作（融资失败 → 破产），带出钩子 pet 0.5、study 0.6
    家庭上章之后没推进
    活跃：工作、钱、车、家庭

C3  5-6 月
    家庭已 2 章未推进 → 休眠
    距上次开新卡 2 章 → 强制开 1 张
      抽样候选：study 0.61、pet 0.55、travel 0.20（刚破产，旅行分低）
      抽中：宠物(adopt_pet)，背景：考虑领养一只猫
    主线：钱（卖车）；车进入结局 sold → 关闭
    活跃：工作、钱、宠物        休眠：家庭        关闭：车

C4  7-8 月
    活跃 3 条 = 下限；卖车时老周说要给他介绍对象，带出钩子 relationship 0.7
    0.7 ≥ 0.6 → 开 1 张：恋爱(romance_new)，背景：和对方加了微信
    工作在 unemployed 阶段已达 max_ch → 必须推进：开始找工作
    主线：工作；宠物：正式领养
    活跃：工作、钱、宠物、恋爱

C5  9-10 月
    主线：恋爱（开始约会）
    工作进入结局 new_job → 关闭，自动接续：新工作适应(new_job_adaptation)
    钱 2 章未推进 → 休眠
    活跃：新工作、宠物、恋爱        休眠：家庭、钱

C6  11-12 月
    距上次开新卡 2 章 → 强制开；季节钩子 health 0.4
      抽中：健康(annual_checkup)，背景：体检发现血脂偏高
    家庭自 C1 起 5 章未推进，且没有 family 钩子 → 静默关闭（春节故事结束）
    主线：恋爱（确定关系 together），章末带出钩子 family 0.6
    活跃：新工作、宠物、恋爱、健康    休眠：钱        关闭：车、工作、家庭

C7  次年 1-2 月
    季节钩子 family 0.8 + 恋爱钩子 family 0.6 → 开 1 张新家庭卡(meet_parents)
    主线：恋爱（带对象回家过年）；新家庭卡作为关联线
    活跃：新工作、宠物、恋爱、健康、家庭    休眠：钱

C8  3-4 月
    钱自 C3 起 5 章未推进且无钩子 → 静默关闭
    活跃 5 条 = 上限，不开新卡
    恋爱在 together 阶段已达 max_ch → 必须推进，进入结局 engaged
    关闭恋爱，自动接续：婚礼筹备(wedding_plan)
```

轮换效果：

```text
C1–C3：工作、钱、车、家庭
C4–C6：工作 → 新工作，宠物、恋爱、健康陆续加入；车、旧家庭卡先后退场
C7–C8：因恋爱开出新的家庭故事；钱退场；恋爱结束并接续婚礼筹备
```

这个过程没有依赖“LLM 觉得该换故事了”，每一步开卡、关卡、选主线都能从上面的函数和参数中算出来。

---

## 8. 领域池、进度卡、时间线的关系

```text
领域池：故事的来源，开头用来建卡，之后每章检查是否需要补新卡
进度卡：每条故事目前停在哪里，跨章节一直保存
时间线：所有故事实际发生的事件，按日期排在同一条日历上
```

一句话概括：

> **开头用领域池建立几张故事进度卡；之后每章打开进度卡，选一条故事推进，顺带更新受影响的故事，写完后把新进度存回去，下一章接着写。**

