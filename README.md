# 状态驱动的长期交互记忆 Benchmark

**State-Driven Long-Term Interactive Memory Benchmark — 面向可控人物生长与可追溯证据。**

从一个很小的人物种子出发，让同一位用户在数月乃至更长时间里持续与 AI 助手交互。人物的居住、工作、资产、关系、偏好和生活习惯由状态规划驱动，并随时间事件逐步变化；每一次变化都落实到自然对话，并保留可定位到具体 turn 的证据。最终既能恢复人物在任意版本的结构化画像，也能从状态链和对话证据中统一生成长期记忆问题。

## 为什么需要状态驱动的长期交互数据

[LongMemEval](https://arxiv.org/abs/2410.10813) 系统地测试了信息抽取、多会话推理、时间推理、知识更新和拒答，并为问题提供证据 session。它的用户—助手历史是围绕目标问题和证据陈述合成、人工编辑，再混入 filler session 得到的，适合测试一个 memory system 能否从很长的历史中找到正确证据。但它的构造重点是**问题—证据测试实例**，不是让同一个人的世界状态按时间持续生长。

[LoCoMo](https://arxiv.org/abs/2402.17753) 更接近长期社会对话：两个带 persona 的 LLM agent 根据时间事件图跨 session 交谈，再由人工校订长期一致性。它擅长产生很长、很自然的人际对话，但事件图主要控制“发生什么”，没有用显式的状态差量约束“人物在每一章结束时必须变成什么”，因此较难精确控制属性更新、领域覆盖和最终人物画像。

这个项目试图补上两者之间的空缺：

- 场景是持续的 **user–assistant 交互**，而不是两个社会角色之间的聊天。
- 数据不是围绕预先写好的题目反向拼接；先让人物世界线生长，全部完成后再统一出题。
- 每轮先规定人物应该发生哪些状态变化，再让模型寻找合理事件和自然表达方式。
- 状态、事件、会话、原话证据和问题使用同一条可追溯链路。
- 人物可以继续增长；在 `v13` 出题后，仍然可以追加 `v14`、`v15`，并得到新的当前画像。

## 设计要点

### 1. 状态规划，而不是直接续写对话

人物信息组织为：

```text
domain → subcategory → subject → versions[]
```

当前实现包含 16 个生活领域。每轮选取 1 条主线和 4 条副线，规划 10 条状态变化：

- `create`：新增以前不存在的事实；
- `update`：替换已有值；
- 集合型 `update`：可以增加或移除其中一项；
- 清空值：表达某个已有状态结束或不再成立。

旧值不会被覆盖删除，而是保留为历史版本。因此系统既能回答“现在是什么”，也能回答“以前是什么、什么时候变了、为什么变”。

### 2. Domain 从生成阶段开始携带

`domain / subcategory / subject` 不是出题时再由模型猜测。它们从状态规划开始，继续进入目标变化、事件 `goal_state`、对话事实抽取和 QA candidate。这样可以按领域分析覆盖率、控制数据分布，也可以让题目继承其来源领域。

当前生成链路已经保留这些标签；最终发布用的 `QuestionRecord` 还需要把 candidate 中的 domain 写入 `meta`，当前仓库里的问题 JSONL 尚未序列化这个字段。

### 3. 两个信息不对称的对话角色

- **User Agent** 扮演人物，看到人物摘要、已经发生的事件、本次需要暴露的事件和状态变化，以及最近 10 条滚动摘要。
- **Assistant Agent** 只知道当前日期和已经发生的对话，看不到事件图与目标状态，因而只能像普通助手一样回应和追问。

这种信息差让状态变化通过求助、分享、吐槽、回忆等自然动机逐步暴露，而不是由双方照着同一份剧情脚本念出来。

### 4. 对话必须通过状态覆盖验证

每个事件生成一段 12 turns 的对话。生成后抽取：

- 用户事实；
- 已发生事件；
- 对应状态变化的 turn 级原话证据；
- 本段滚动摘要。

如果原话没有覆盖目标状态，这段对话不会提交，而是按同一事件重新生成。通过后，session、extract 和 summary 才会追加到该人物的历史中。

### 5. 最终人物画像可以直接恢复

每条状态链的最后一个版本组成指定轮次的人物画像。因此人物画像不是重新概括全部聊天得到的一段模糊摘要，而是一个可计算、可比较、可追溯的结构化快照。

生成和出题是两条独立流水线：对话流水线负责让人物生长；QA 流水线读取某个冻结版本的状态链、会话和证据，再生成信息抽取、开放域、时间推理、拒答和知识更新问题。

## 系统架构

![状态驱动的长期交互记忆 Benchmark 系统架构](docs/architecture.svg)

每轮先从 16 个领域中确定 1 条主线和 4 条副线，规划 10 条 `create` / `update` 状态变化，再把变化编排为带日期的事件。对话由两个信息不对称的角色生成：User Agent 拥有人物摘要、历史事件、本次事件与状态变化，以及最近 10 条滚动摘要；Assistant Agent 不知道事件图和目标状态，只根据当前日期和已经发生的对话正常回应。对话原话必须覆盖目标状态，才能连同事实、事件和 turn 级证据一起提交。

状态链、事件图和人物画像按版本累积；同一人物的 sessions、extracts 和 summaries 只追加、不重写。问答流水线不参与人物生长，只读取指定版本的冻结快照，因此可以先在任意版本出题，再继续把世界线增长到后续版本。

## 从初始人物画像到最终人物画像

![P001 从 v0 到 v13 的人物成长时间轴](docs/person_data_card_timeline.svg)

P001 最初只有 9 条基础事实。经过 13 轮生长，最终形成 79 个当前状态、139 个状态版本、107 个时间事件、107 段对话和 130 条 turn 级证据，并据此生成 182 道单跳与多跳问题。

房租、手机、薪资、住房和联系方式等事实可以多次变化。每个版本都能继续追溯到事件、会话、具体 turn 和原始文本，使 Benchmark 同时具备当前画像、知识更新、时间推理和证据核验能力。

## 项目结构

```text
longterm_memory_benchmark/
├── pyproject.toml                  # 安装配置，注册命令 ltm
├── __main__.py                     # python -m longterm_memory_benchmark
├── cli.py                          # 命令行：dialogue、qa、list-domains
├── run_dialogue.py                 # 对话流水线入口
├── run_qa.py                       # 问答流水线入口
├── llm_client.py                   # OpenAI 兼容接口
├── src/
│   ├── api.py                      # 对外统一导入
│   ├── dialogue_gen/               # 对话生成
│   │   ├── step0_0_0_person_profile.py
│   │   ├── step1_0_0_target_state.py
│   │   ├── step1_1_0_time_plan.py
│   │   ├── step2_0_0_time_event_graph.py
│   │   ├── step3_0_0_dialogue_generate.py
│   │   ├── step3_1_0_dialogue_extract.py
│   │   ├── step3_2_0_dialogue_summary.py
│   │   ├── step3_3_0_dialogue_orchestrate.py
│   │   └── dialogue_prompt/        # 档案、目标、事件图、对话提示词
│   ├── qa_gen/                     # 问答生成
│   │   ├── materials.py            # 读取人物材料，组装单跳与更新链
│   │   ├── models.py               # 候选、题目、证据
│   │   ├── base.py                 # 生成器共用流程
│   │   ├── step1_0_gen_basic_qa.py             # 信息抽取
│   │   ├── step1_1_gen_open_qa.py              # 开放域
│   │   ├── step1_2_gen_temporal_qa.py          # 时间推理
│   │   ├── step1_3_gen_reject_qa.py            # 拒答
│   │   ├── step1_4_gen_knowledge_update_qa.py  # 知识更新
│   │   └── qa_prompt/              # IE、OD、TR、RJ、KU 提示词
│   └── utils/                      # JSON / YAML 读写
├── data/
│   ├── persons/                    # 人物种子与初始画像
│   ├── output/                     # 对话流水线产物
│   └── qa/                         # 问答 jsonl
└── extra_doc/                      # 早期服务端试验代码
```

## 对话流水线

`run_dialogue` 按版本迭代。每一轮先保存再载入，顺序是：

1. 人物档案
2. 目标状态与领域规划
3. 时间计划
4. 时间事件图
5. 按事件生成对话、抽取事实、写摘要

`data/output` 里的主要文件：

| 文件 | 内容 |
| --- | --- |
| `{person}_v{n}_profile_data.json` | 该轮结构化画像 |
| `{person}_v{n}_person_profile.txt` | 该轮人物摘要 |
| `{person}_v{n}_planning_state.json` | 规划状态 |
| `{person}_v{n}_target_state.json` | 目标状态 |
| `{person}_v{n}_time_event_graph.json` | 时间事件图 |
| `{person}_dialogue_sessions.json` | 全部对话 |
| `{person}_dialogue_extracts.jsonl` | 事实抽取 |
| `{person}_dialogue_summaries.jsonl` | 对话摘要 |

## 问答流水线

`run_qa` 只加载一次人物材料，再按题型生成。每完成一条就追加到 `{person}_{hop}_questions.jsonl`，同一个 `question_id` 只保留最新一行。

| 题型 | 模板 | 单跳 | 多跳 |
| --- | --- | --- | --- |
| `information_extraction` | IE-S / IE-M | 直接询问一个事实 | 询问同一事实项历史上出现过的全部值 |
| `open_domain` | OD-S | 个人前提加可核查的外部知识 | 未实现 |
| `temporal` | TR-S | 由对话时间换算出的事件时间 | 未实现 |
| `reject` | RJ-S | 提问时记忆中不存在该信息 | 未实现 |
| `knowledge_update` | KU-M | 无单跳形态 | 询问更新链最后的当前状态 |

`query_time` 是提问时的“现在”，问题里的相对时间以它为准。`session_time` 是历史对话发生的日期，原话里的相对时间以它为准。

## 命令行

在本目录执行一次 `pip install -e .`。之后可在任意目录运行。模型、接口地址和密钥默认读环境变量 `AZURE_OPENAI_MODEL`、`OPENAI_BASE_URL`、`OPENAI_API_KEY`。

```bash
ltm list-domains

ltm dialogue --to-round 13

ltm qa --planning-round v13 --hop single --limit 40

ltm qa --planning-round v13 --hop multi --model deepseek-v4-pro --limit 40
```

`ltm` 就是 `cli.py` 里的 `main`。不通过脚本时，用 `python -m longterm_memory_benchmark`，后面的子命令相同。

`--planning-round 13` 会写成 `v13`。单跳不指定 `--abilities` 时跑全部已注册题型。多跳不指定时只跑 `information_extraction` 和 `knowledge_update`。

Python 里也可以直接调用：

```python
from longterm_memory_benchmark import run_dialogue, run_qa
```

问答相关类型从 `longterm_memory_benchmark.src.api` 导入。
