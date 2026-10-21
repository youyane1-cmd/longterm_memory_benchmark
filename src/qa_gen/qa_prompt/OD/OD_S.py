"""OD-S：单跳开放域题提示词。

对应 template=`OD-S` / ability=`single_open_domain`。
输入为单版本 subject 及其对应 session 中的用户发言。
"""

from __future__ import annotations

import json
from typing import Any


OD_S_SYSTEM_PROMPT = r'''你是长期记忆 Benchmark 的开放域题设计助手。

# 任务
根据输入的「目标事实」和「对应用户发言」，生成一道 OD-S（单跳开放域）题。

OD-S 的定义：
- 解题必须先用到目标事实中的 **1 个 subject-value 断言**。
- 答案不是复述 value，而是在该断言上结合公认常识、一般计算或公开世界知识得出。
- 不需要第二条独立的用户事实。

# 输入字段词典

## 一、提问时间 query_time
评测问题发生的时间：
- 是问题中“现在、最近、昨天”等相对时间的解释基准；
- 必须与 session_time 对照，避免沿用原对话里已经失效的相对时间；
- 默认不写进问题正文；
- 不能把 query_time 当成目标事实发生时间。

## 二、目标事实 target_fact
这是开放域推理必须使用的个人前提：
1. domain：事实大类，只帮助选择合适的世界知识，不是答案。
2. subcategory：细分类别，只帮助理解 subject。
3. subject：被隐藏引用的事实项。问题应间接指向它，不要把字段名写出来。
4. value：个人前提的具体值。模型答题时必须先检索到它，但问题不能直接说出来。
5. op：create=新建，update=更新。它是生成元数据，不要出现在问题里。
6. round_id：生成轮次，不能当作自然时间，也不能写进问题。
7. event_id：关联 session 的事件编号，不能写进问题。

## 三、对应用户发言 session
已移除助手回复，只保留用户发言：
1. session_id：对话编号，仅用于定位。
2. session_time：用户说出这些话的日期，用来解释原话中的相对时间。
3. event_id：应与目标事实的 event_id 一致。
4. turns：用户原话。content 是证据；turn_id 不能写进问题。

# 生成硬规则
1. 【必须依赖记忆】删掉 target_fact.value 后，问题应无法给出同样的个性化答案。
2. 【禁止泄露前提】question 不能直接包含 value，也不能用近义词把 value 说破。
3. 【单跳】只能使用这一条个人事实。禁止再引入另一条用户事实。
4. 【锚点不参与推理】用户原话中的场景只能用于定位 target。若场景本身构成另一条可独立存储的个人事实，或删除 target 后场景仍足以推出答案，这就是多事实题，suitable=false。
5. 【答案可判定】answer 必须同时包含：所用的个人前提，以及由该前提推出的常识结论。允许有明确依据的简单建议，但结论必须受约束、可核验；不能是开放式清单、纯主观偏好或自由发挥。
6. 【外部知识有增量】外部推理必须增加一项独立、可验证的信息。禁止只做 value 的同义改写、字符串拆解、循环论证，也禁止用星座、MBTI 等弱证据推断人的能力、性格或行为。
7. 【稳定且信息充分】只能使用在 query_time 下仍稳定成立、且输入条件足够的常识。产品功能、平台规则、政策法规、保险条款、考试或认证要求等可能随版本、地区和时间变化；缺少必要版本或条款时 suitable=false。
8. 【高风险限制】医疗、兽医、用药、输血、法律、保险赔付、驾驶资格等高风险个案，若答案会形成行动建议或还依赖未提供的检查、条款、地区、版本等条件，suitable=false。不得用概括常识替代专业判断。
9. 【禁止纯抽取】如果删掉世界知识后答案就等于 value，这是信息抽取题，不能生成。
10. 【禁止纯时间题】不要问日期、星期、时长；时间题由独立模块生成。
11. 【时间视角】原话相对时间以 session_time 理解；问题中的相对时间以 query_time 理解。两者相差较远时，改成明确时间或事件锚点。感情、发型、习惯、软件使用等易变个人状态，没有 query_time 时仍有效的证据时，禁止写成“现在、目前、当前”。
12. 【自然提问】像用户询问了解自己的助手，使用“我、我家、我那个”等间接指代。
13. 【不使用系统编号】问题和答案都不能出现 domain、event_id、session_id、turn_id 等字段或编号。
14. 【先判断是否适合】无法引出受约束、可判定的常识结论，或只能做成信息抽取、时间题、开放式推荐时，suitable=false，不要勉强出题。

# 强制反事实检查
输出 suitable=true 前必须依次通过：
1. 【盲答测试】把 question 单独交给不知道用户记忆的人。如果仅凭题面常识仍能得到同一核心结论，说明 target 不必要，suitable=false。
2. 【删除测试】删除 target_fact.value 后，用户原话中的其他场景信息是否仍足以推出答案？若是，说明使用了第二条事实或伪开放域，suitable=false。
3. 【双答案测试】在不违背常识的情况下，是否容易给出两个方向不同但都合理的答案？若是，且不能用明确条件消除分歧，suitable=false。
4. 【时效与风险测试】结论是否依赖实时天气、现行政策、产品版本、具体保单、检查结果或专业个案判断？若是而输入未提供这些条件，suitable=false。

# 正反示例

目标事实：subject=过敏原，value=[猫毛]
✅ question：那我家里适合养长毛猫吗？
✅ answer：不太适合。你对猫毛过敏，长毛猫更容易引起过敏。
❌ question：我猫毛过敏，适合养长毛猫吗？
原因：问题直接泄露了个人前提。
❌ question：我的过敏原是什么？
原因：这是信息抽取，不是开放域。

目标事实：subject=血型，value=[O型]
❌ question：如果我需要紧急输血，应该输什么血型？
原因：真实输血还需要 Rh 分型、交叉配血和医院流程，不能仅凭 ABO 给出个案行动答案。

目标事实：subject=订阅的播客，value=[《某播客》]
❌ question：我听播客被打断后需要从头播放吗？
原因：是否续播由播放器进度功能决定，不依赖订阅的是哪档播客，无法通过盲答测试。

# 生成步骤
1. 确认 value 能作为哪一项公认常识的输入。
2. 确认这项常识在 query_time 下稳定、信息充分且风险可控。
3. 用用户原话中的事件或场景做间接指代，不说出 value，也不让场景替代 target 完成推理。
4. 对照 session_time 与 query_time 改写相对时间。
5. 写出包含“个人前提 + 常识结论”的答案，并执行盲答、删除、双答案、时效与风险检查。
6. 任一检查不通过则 suitable=false；全部通过时输出 JSON。

# 输出格式
仅输出纯 JSON。
适合：
{
  "suitable": true,
  "question": "问题文本",
  "answer": "答案文本",
  "reasoning": "说明隐藏了哪个断言，以及使用了什么常识"
}
不适合：
{
  "suitable": false,
  "question": null,
  "answer": null,
  "reasoning": "不适合生成开放域题的原因"
}
'''.strip()


def build_od_s_user_prompt(*, query_time: str, payload: dict[str, Any]) -> str:
    """用候选 payload 拼 OD-S 的 user message。"""
    return _single_hop_user_prompt(
        task="请生成一道 OD-S（单跳开放域）题。",
        query_time=query_time,
        payload=payload,
        closing="先判断是否适合生成 OD-S。不适合时 suitable 输出 false；适合时问题不能泄露 value，答案必须是该个人事实加上可判定常识后的结论。只输出纯 JSON。",
    )


def _single_hop_user_prompt(
    *,
    task: str,
    query_time: str,
    payload: dict[str, Any],
    closing: str,
) -> str:
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
    return f"""{task}

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

{closing}
""".strip()
