# 状态驱动的长期交互记忆 Benchmark

**State-Driven Long-Term Interactive Memory Benchmark — 面向可控人物生长与可追溯证据。**

面向**单用户—AI 个性化助手**场景，从一个很小的人物种子出发，让同一位用户在数月乃至更长时间里持续与 AI 助手交互。人物的居住、工作、资产、关系、偏好和生活习惯由状态规划驱动，并随时间事件逐步变化；每一次变化都落实到自然对话，并保留可定位到具体 turn 的证据。最终既能恢复人物在任意版本的结构化画像，也能从状态链和对话证据中统一生成长期记忆问题。

## 为什么需要状态驱动的长期交互数据

[LongMemEval](https://arxiv.org/abs/2410.10813) 系统地测试了信息抽取、多会话推理、时间推理、知识更新和拒答，并为问题提供证据 session。它的用户—助手历史是围绕目标问题和证据陈述合成、人工编辑，再混入 filler session 得到的，适合测试一个 memory system 能否从很长的历史中找到正确证据。但它的构造重点是**问题—证据测试实例**，不是让同一个人的世界状态按时间持续生长。

[LoCoMo](https://arxiv.org/abs/2402.17753) 更接近长期社会对话：两个带 persona 的 LLM agent 根据时间事件图跨 session 交谈，再由人工校订长期一致性。它擅长产生很长、很自然的人际对话，但事件图主要控制“发生什么”，没有用显式的状态差量约束“人物在每一章结束时必须变成什么”，因此较难精确控制属性更新、领域覆盖和最终人物画像。

这个项目试图补上两者之间的空缺：

- 每条人物世界线对应一位用户与 AI 个性化助手的持续交互，而不是多个社会角色之间的聊天。
- 数据不是围绕预先写好的题目反向拼接；先让人物世界线生长，全部完成后再统一出题。
- 每轮先规定人物应该发生哪些状态变化，再让模型寻找合理事件和自然表达方式。
- 状态、事件、会话、原话证据和问题使用同一条可追溯链路。
- 人物可以继续增长；在 `v13` 出题后，仍然可以追加 `v14`、`v15`，并得到新的当前画像。

这里的“单用户”是任务场景，而不是数据集只能包含一个人物。扩展 Benchmark 时，可以生成 P002、P003 等彼此独立的人物世界线；每条世界线仍分别模拟一位用户与其 AI 助手的长期关系。仓库中的 P001 是当前用于验证完整生成与出题闭环的参考样例。

## 系统架构

![状态驱动的长期交互记忆 Benchmark 系统架构](docs/architecture.svg)

每轮先从 16 个领域中确定 1 条主线和 4 条副线，规划 10 条 `create` / `update` 状态变化，再把变化编排为带日期的事件。对话由两个信息不对称的角色生成：User Agent 拥有人物摘要、历史事件、本次事件与状态变化，以及最近 10 条滚动摘要；Assistant Agent 不知道事件图和目标状态，只根据当前日期和已经发生的对话正常回应。对话原话必须覆盖目标状态，才能连同事实、事件和 turn 级证据一起提交。

状态链、事件图和人物画像按版本累积；同一人物的 sessions、extracts 和 summaries 只追加、不重写。问答流水线不参与人物生长，只读取指定版本的冻结快照，因此可以先在任意版本出题，再继续把世界线增长到后续版本。

## 设计要点

### 状态规划驱动人物生长

人物信息组织为：

```text
domain → subcategory → subject → versions[]
```

当前实现包含 16 个生活领域。每轮选取 1 条主线和 4 条副线，规划 10 条状态变化：

- `create` 新增事实；
- `update` 替换已有值；
- 集合型 `update` 可以增加或移除其中一项；
- 清空值表示某个已有状态结束。

旧值不会被覆盖删除，而是保留为历史版本。因此系统既能回答“现在是什么”，也能回答“以前是什么、什么时候变了”。

### Domain 从生成源头贯穿到出题材料

`domain / subcategory / subject` 从状态规划开始，继续进入目标变化、事件 `goal_state`、对话事实抽取和 QA candidate，而不是在出题时重新猜测。这让领域覆盖可规划、数据分布可统计，问题也能继承来源领域。

当前生成链路已经保留这些标签；仓库现有的最终问题 JSONL 尚未把 domain 序列化到 `QuestionRecord.meta`。

### 信息不对称的 User–Assistant 对话

- **User Agent** 扮演人物，看到人物摘要、历史事件、本次事件与状态变化，以及最近 10 条滚动摘要。
- **Assistant Agent** 只知道当前日期和已经发生的对话，看不到事件图与目标状态。

因此状态变化要通过求助、分享、吐槽或回忆等自然动机逐步暴露，而不是由双方照着同一份剧情脚本复述。

### 通过证据验证后才提交

每个事件生成一段 12 turns 的对话，再抽取用户事实、事件、滚动摘要和对应状态变化的 turn 级原话。原话未覆盖目标状态时，只重做当前对话；验证通过后才追加 session、extract 和 summary。

### 画像与问题都从状态链计算

每条状态链的最后一个版本组成指定轮次的人物画像。画像不是重新概括全部聊天得到的模糊摘要，而是可计算、可比较、可追溯的结构化快照。

对话流水线负责让人物生长；QA 流水线只读取某个冻结版本的状态链、会话和证据。题型不会反向控制人物生成。

## 从初始人物画像到最终人物画像

![P001 从 v0 到 v13 的人物成长时间轴](docs/person_data_card_timeline.svg)

P001 最初只有 9 条基础事实。经过 13 轮生长，最终形成 79 个当前状态、139 个状态版本、107 个时间事件、107 段对话和 130 条 turn 级证据，并据此生成 182 道单跳与多跳问题。

房租、手机、薪资、住房和联系方式等事实可以多次变化。每个版本都能继续追溯到事件、会话、具体 turn 和原始文本，使 Benchmark 同时具备当前画像、知识更新、时间推理和证据核验能力。

## 快速开始

安装项目：

```bash
pip install -e .
```

模型、接口地址和密钥默认读取 `AZURE_OPENAI_MODEL`、`OPENAI_BASE_URL`、`OPENAI_API_KEY`。

```bash
# 查看可选领域
ltm list-domains

# 从 v0 开始，持续生成到 v13
ltm dialogue --to-round 13

# 从 v13 冻结快照生成单跳问题
ltm qa --planning-round v13 --hop single --limit 40

# 生成多跳问题
ltm qa --planning-round v13 --hop multi --model deepseek-v4-pro --limit 40
```

也可以直接调用：

```py
from longterm_memory_benchmark import run_dialogue, run_qa
```

`ltm` 对应 `cli.py` 中的 `main`，也可以使用 `python -m longterm_memory_benchmark`。`--planning-round 13` 会自动转换为 `v13`。

## 生成结果

### 对话与人物材料

`run_dialogue` 按版本迭代，每轮依次处理人物画像、目标状态、时间窗口、事件图、对话、事实抽取与摘要。

- `{person}_v{n}_profile_data.json`：该轮最终人物画像；
- `{person}_v{n}_planning_state.json`：截至该轮的全部状态链；
- `{person}_v{n}_target_state.json`：本轮必须实现的状态变化；
- `{person}_v{n}_time_event_graph.json`：截至该轮的完整事件图；
- `{person}_dialogue_sessions.json`：该人物的全部会话；
- `{person}_dialogue_extracts.jsonl`：事实、事件和 turn 证据；
- `{person}_dialogue_summaries.jsonl`：全部滚动摘要。

### Benchmark 问题

`run_qa` 读取指定轮次的冻结材料，生成带标准答案、推理过程和证据引用的问题。每完成一条就写入 `{person}_{hop}_questions.jsonl`，同一个 `question_id` 只保留最新结果。

- `information_extraction`：单跳事实读取；多跳聚合同一状态链的历史版本；
- `open_domain`：人物记忆与外部常识结合；
- `temporal`：依据 session 时间解释相对时间；
- `reject`：目标信息在记忆中不存在时拒答；
- `knowledge_update`：从多个历史版本中确定当前值。

当前多跳默认生成 `information_extraction` 和 `knowledge_update`。`query_time` 是提问时的“现在”；`session_time` 是历史对话发生的日期。

## 项目结构

```text
longterm_memory_benchmark/
├── cli.py                          # dialogue、qa、list-domains
├── run_dialogue.py                 # 人物与对话生成入口
├── run_qa.py                       # Benchmark 问题生成入口
├── llm_client.py                   # OpenAI 兼容接口
├── src/
│   ├── dialogue_gen/
│   │   ├── step0_0_0_person_profile.py
│   │   ├── step1_0_0_target_state.py
│   │   ├── step1_1_0_time_plan.py
│   │   ├── step2_0_0_time_event_graph.py
│   │   ├── step3_0_0_dialogue_generate.py
│   │   ├── step3_1_0_dialogue_extract.py
│   │   ├── step3_2_0_dialogue_summary.py
│   │   ├── step3_3_0_dialogue_orchestrate.py
│   │   └── dialogue_prompt/                     # 画像、状态、事件与对话提示词
│   ├── qa_gen/
│   │   ├── base.py                              # 题型生成基类
│   │   ├── materials.py                         # 加载出题原料
│   │   ├── models.py                            # 候选、证据与问题记录
│   │   ├── step1_0_gen_basic_qa.py              # 信息抽取（IE）
│   │   ├── step1_1_gen_open_qa.py               # 开放域（OD）
│   │   ├── step1_2_gen_temporal_qa.py           # 时间推理（TR）
│   │   ├── step1_3_gen_reject_qa.py             # 拒答（RJ）
│   │   ├── step1_4_gen_knowledge_update_qa.py   # 知识更新（KU）
│   │   └── qa_prompt/                           # IE、OD、TR、RJ、KU 提示词
│   └── utils/
├── data/
│   ├── persons/                    # 初始人物画像
│   ├── output/                     # 状态、事件、会话与证据
│   └── qa/                         # 问题 JSONL
└── docs/                           # 架构图与人物数据卡片
```

## 当前实现边界

- 一轮覆盖一个月，并规划 10 条状态变化。
- 一段会话固定为 12 turns；状态覆盖失败最多重新生成 3 次。
- Domain 已贯穿状态、事件、抽取和 QA candidate，最终问题记录尚未序列化该字段。
- 多跳开放域、时间推理和拒答尚未实现。

## 参考

- [LoCoMo: Evaluating Very Long-Term Conversational Memory of LLM Agents](https://arxiv.org/abs/2402.17753)
- [LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory](https://arxiv.org/abs/2410.10813)
