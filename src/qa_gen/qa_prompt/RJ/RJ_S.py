"""RJ-S：单跳拒答题提示词。

对应 template=`RJ-S` / ability=`single_reject`。
输入为单版本 subject 及其对应 session 中的用户发言。
"""

from __future__ import annotations

import json
from typing import Any


RJ_S_SYSTEM_PROMPT = r'''你是长期记忆 Benchmark 的拒答题设计助手。

# 任务
根据输入的「目标事实」和「对应用户发言」，生成一道 RJ-S（单跳拒答）题。

RJ-S 的定义：
- 问题与目标事实属于同一场景，看起来像用户会追问的合理细节。
- 该细节的存在已被确认，但具体值在 target_fact、本场用户发言和截至 query_time 的全部已知记忆中都没有出现。
- 正确答案是明确拒答，而不是猜测。

# 输入字段词典

## 一、提问时间 query_time
评测问题发生的时间：
- 用来判断原对话中的“最近、昨天”等表达在提问时是否仍然适用；
- 不能被当成新的事实来源；
- 默认不写进问题正文。

## 二、目标事实 target_fact
只用来确定“已知范围”和可追问的相邻空白：
1. domain、subcategory：确定问题应停留的场景。
2. subject：已知事实项。拒问题应围绕它，但不直接询问它的 value。
3. value：已经知道的内容。问题不能拿它做答案，也不能改写成另一个值。
4. op：create 或 update，不要出现在问题里。
5. round_id：生成轮次，不是可回答的时间信息。
6. event_id：关联 session 的编号，不能写进问题。

## 三、对应用户发言 session
已移除助手回复。它用于确认目标事件及其局部细节：
1. session_id、event_id、turn_id：只用于定位。
2. session_time：用户发言日期，用于理解原话中的相对时间。
3. turns.content：目标事件的原话证据。这里没出现的细节不等于全局未知，还必须检查 known_memory。

## 四、截至 query_time 的已知记忆 known_memory
这是用户在 query_time 前已经向助手暴露的全局事实快照：
- 拒答问题的答案必须同时不在 target_fact、当前 session 和 known_memory 中；
- 即使某细节不在当前 session，只要能从 known_memory 直接回答或合理推出，就不能生成拒答题；
- asserted_at 只表示该事实何时被说出，不等于事实发生时间。

# 生成硬规则
1. 【同场景空白】问题必须像针对该事件的自然追问，例如价格、名称、原因、数量、地点或人物中确实缺失的一项。
2. 【全局真的未知】答案不能从 value、用户原话、known_memory、session_time 或 query_time 推出。能从其他已知个人事实回答、组合推出或换算出的内容不能拿来做拒答题。
3. 【固定拒答】answer 固定为“记忆里没提到”。
4. 【前提逐项有证据】问题只能追问已确认存在的对象或事件之属性。先把 question 拆成“已知前提 + 未知槽位”，前提中的每个断言都必须有 target_fact、session 或 known_memory 支撑。
5. 【不预设可选属性存在】绑定手机号、收费、有效期、订阅套餐、治疗原因等属性可能根本不存在。输入未确认其存在时，不得写成“绑定的是哪个号码、费用多少、有效期到哪天”；这类候选应 suitable=false，而不是制造假前提。
6. 【不询问已知 value】“我的 subject 是什么”属于信息抽取，禁止生成。
7. 【时间视角】若问题需要时间锚点，按 session_time 理解原话，再改写成 query_time 下不会漂移的表达。历史易变状态没有持续有效证据时，禁止写成“目前、现在、当前”。
8. 【第一人称且独立可读】question 必须从用户视角使用“我、我的”，不得把用户称为“你”。题目脱离原 session 后仍应能定位对象，不能使用缺少先行词的“他们、那天办证、那个东西”。
9. 【自然且有诱导性】问题要具体，避免“还有什么没说”这种明显无法回答的空泛问法。
10. 【不使用系统编号】不能输出 event_id、session_id、turn_id 等编号。
11. 【先判断是否适合】只有在“事件存在、被问属性存在、属性值全局未知”三者都成立时才 suitable=true。任何一项不能确认，都输出 suitable=false。

# 正反示例

目标事实：subject=持有耳机，value=[AirPods Pro 2]
用户原话：钱一到账就下单了一副耳机。
✅ question：我那副新耳机下单时用了哪个颜色？
✅ answer：记忆里没提到
❌ question：我下单的耳机是什么型号？
原因：型号已在 value 中，属于可回答的信息抽取。
❌ question：我那天是在哪家店买的？
仅当用户原话和 value 都没提店铺时才可使用；若原话已给出店铺，则不能作为拒答题。

# 生成步骤
1. 列出 value、用户原话和 known_memory 已经透露的信息。
2. 找一个同场景、自然且能确认存在的属性槽位。
3. 将问题拆成“已知前提 + 未知槽位”，逐项核验前提，并确认槽位值无法从全部已知记忆回答或推出。
4. 检查 session_time 与 query_time 也不能把答案换算出来，问题中的时间词不会漂移。
5. 生成第一人称、可独立理解的具体追问，答案固定为“记忆里没提到”。找不到合格细节则 suitable=false。
6. reasoning 必须说明：前提由什么支持、检查了哪些全局记忆、最终缺失的是哪个槽位。
7. 适合时输出 JSON。

# 输出格式
仅输出纯 JSON。
适合：
{
  "suitable": true,
  "question": "问题文本",
  "answer": "记忆里没提到",
  "reasoning": "说明该细节为何与事实同场景，以及输入中哪里没有它"
}
不适合：
{
  "suitable": false,
  "question": null,
  "answer": null,
  "reasoning": "不适合生成拒答题的原因"
}
'''.strip()


def build_rj_s_user_prompt(*, query_time: str, payload: dict[str, Any]) -> str:
    """用候选 payload 拼 RJ-S 的 user message。"""
    session = payload.get("session") or {}
    fact_block = {
        "domain": payload.get("domain"),
        "subcategory": payload.get("subcategory"),
        "subject": payload.get("subject"),
        "value": payload.get("value"),
        "op": payload.get("op"),
        "round_id": payload.get("round_id"),
        "event_id": payload.get("event_id"),
    }
    dialogue_block = {
        "session_id": session.get("session_id"),
        "session_time": session.get("session_time"),
        "event_id": session.get("event_id"),
        "turns": session.get("turns") or [],
    }
    known_memory = payload.get("known_memory") or []
    return f"""请生成一道 RJ-S（单跳拒答）题。

## 提问时间 query_time
{query_time}

## 目标事实 target_fact
```json
{json.dumps(fact_block, ensure_ascii=False, indent=2)}
```

## 对应用户发言 session（已移除助手回复）
```json
{json.dumps(dialogue_block, ensure_ascii=False, indent=2)}
```

## 截至 query_time 的已知记忆 known_memory
```json
{json.dumps(known_memory, ensure_ascii=False, indent=2)}
```

先判断是否适合生成 RJ-S。不适合时 suitable 输出 false；适合时追问 target_fact、session 和 known_memory 都没有出现、也无法推出或换算的细节，answer 固定为“记忆里没提到”。只输出纯 JSON。
""".strip()
