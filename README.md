# 长期记忆 Benchmark

从人物种子出发，按时间线生成可追溯的多轮对话，再据此生成带证据的问答。对话和问答是两条独立流水线：问答读取已经落盘的规划、会话和抽取结果，不在对话生成过程中出题。

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
