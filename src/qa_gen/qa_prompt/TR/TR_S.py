"""TR-S：单跳时间题提示词。

对应 template=`TR-S` / ability=`single_temporal`。
输入为单版本 subject 及其对应 session 中的用户发言。
"""

from __future__ import annotations

import json
from typing import Any


TR_S_SYSTEM_PROMPT = r'''你是长期记忆 Benchmark 的时间题设计助手。

# 任务
根据输入的「目标事实」和「对应用户发言」，生成一道 TR-S（单跳时间）题。

TR-S 的定义：
- 用目标事实或用户原话中的事件作锚点，询问该事件的时间或该事件相对提问时刻的时间距离。
- 只需要一场 session 中的一件事即可回答，不需要联合另一条独立事实。
- 必须正确区分「原对话视角」和「提问视角」。

# 输入字段词典

## 一、提问时间 query_time
评测问题实际被提出的日期，也是生成后问题中所有指示性时间词的唯一解释基准：
- 问题中的“今天、昨天、前天、最近、目前、现在、多久前、到现在”等，都必须相对 query_time 理解；
- 它不是目标事件发生时间，不能直接拿它当答案；
- 即使答案问绝对日期、无需用 query_time 做减法，也必须用它检查问题措辞是否发生时间漂移；
- 原对话中的相对时间属于历史话语，绝不能不经转换地搬进生成后的问题。

## 二、目标事实 target_fact
用来选择被询问时间的事件，不直接提供时间答案：
1. domain、subcategory：帮助理解事件语境。
2. subject：事实项。用它和用户原话定位“哪一件事”。
3. value：事实值。可用于识别事件，但问题不要直接泄露完整 value。
4. op：create 或 update，不要写进问题。
5. round_id：生成轮次，不是自然时间，禁止拿它当答案。
6. event_id：关联 session 的编号，不能写进问题。

## 三、对应用户发言 session
已移除助手回复：
1. session_id：仅用于定位。
2. session_time：历史用户发言发生的日期，格式 YYYY-MM-DD。原话里的“昨天、前天、上周、这周、最近”只能相对它解释。
3. event_id：应与目标事实一致。
4. turns：用户原话。相对时间只从这些 content 中读取。

# 两个时间视角
1. 【先解历史话语】先以 session_time 为基准，把原话中的相对时间解析成 event_time。
   - “昨天”= session_time 前 1 天；
   - “前天”= session_time 前 2 天；
   - “上周”只能确定为前一个自然周，不能编造具体某天；
   - “前两天、最近、之前”可能只是模糊范围，除非上下文进一步限定，否则不能强行解析成唯一日期。
2. 【再生成问题】生成后的问题发生在 query_time。问题中的任何相对时间词都要重新相对 query_time 成立。
3. 当 session_time 与 query_time 不同，禁止把历史原话中的“昨天、前天、上周、最近、目前、刚刚、这两天”等直接复制到问题中。
4. 可采用两类合法问法：
   - 绝对时间：用“那次、当时、之前提到的”等非时间指示锚点询问事件日期；
   - 查询时点相对时间：询问“截至现在过去多久、距今多久”，并以 query_time 为终点计算答案。
5. 原话没有提供事件发生时间时，不能默认 event_time=session_time。禁止为了得到时间答案而改问“我在哪天提到/告诉你/记录了这件事”；只有 target_fact 的 subject 本身就是一次告知、发布或记录行为时，才可询问该行为时间。
6. 答案精度不能超过已知信息。只有年月就不能回答具体日期；不知道具体日期就不能计算精确天数；不知道星期信息时不能问星期几。

# 生成硬规则
1. 【答案必须是时间】answer 是日期、年月、年份或可唯一计算的时长，不能是事实值本身。
2. 【可计算】答案的每一个时间成分都必须能从 session_time、用户原话和必要时的 query_time 推出。
3. 【单跳】只使用这一场 session 和这一条事实，不比较其他事件。
4. 【锚点】问题要能定位到该事件，但不要复述整段原话。
5. 【时间视角安全】逐字检查 question：其中每个相对时间词必须相对 query_time 为真。不得让问题表面含义指向与 answer 不同的日期。
6. 【禁止系统字段】不能输出 round_id、event_id、session_id、turn_id。
7. 【事件时间优先】优先询问事件实际发生时间；不要为了凑题改问“提到这件事的日期”。只有 subject 本身就是记录、告知或确认行为时，才能询问该行为的时间。
8. 【只允许一条时间边】被问事件必须被一个明确时间表达直接修饰。若要先计算事件 A 的时间，再通过“前一天、次日、后来”计算事件 B 的时间，属于二级时间链，不是 TR-S，suitable=false。
9. 【指代基准唯一】“前一天、次日、此前、后来”等关系词必须有唯一且明确的先行事件；存在两个合理时间基准时 suitable=false。
10. 【不得膨胀事件语义】一次“听了、用了、去了、看见了”不能改写成“首次、开始、从此养成”，除非原话明确表达起始含义；“想、考虑、打算”不能改写成“决定或完成”；“听见、猜测、迹象”不能改写成“看见或确认”。
11. 【目标相关性】被问时间必须属于 target_fact 对应的核心事件，不能询问仅作为叙述背景的浏览、纠结、保存页面等偶发动作。
12. 【算术一致】reasoning 中的时间表达、偏移量、计算过程和 answer 必须完全一致；“前天”是前 2 天，并检查跨月、跨年和闰年。
13. 【必须像真实用户会问】question 应是用户可能向长期记忆助手提出的简短回忆问题。禁止为了套模板而使用“确认自己当前的状态、记录持有的资质、配置某项状态、是哪一天提到的”等数据库式或元数据式表达。
14. 【状态不是事件】单身、血型、籍贯、绩点、偏好、习惯等属性或状态本身通常没有发生日期。除非原话明确描述了与 target 高度相关、自然且值得回忆的真实事件，否则 suitable=false；不能制造“确认、填写、补录、保存该状态”的时间题。
15. 【时长问法也要自然】不能仅为了让 query_time 参与计算就问“截至现在过去多少天”。只有持有时长、任职时长、坚持习惯、保修期、纪念日等本来就适合衡量持续时间的事件，才询问距今时长；普通购物、祈福、吃饭、一次出行优先问绝对日期。
16. 【先判断是否适合】问法所需精度超出已知时间时，先换更粗的合法问法。若原话无法唯一确定自然且有意义的时间问题，suitable=false，不要编造。

# 正反示例

session_time：2023-01-13
query_time：2024-12-01
用户原话：前天把闲置手机卖了，钱一到就下单了耳机。
✅ question：我卖掉闲置手机是哪一天？
✅ answer：2023-01-11
❌ question：我前天卖手机是哪一天？
原因：问题里的“前天”以 query_time 为基准，表示 2024-11-29，不再表示原话中的 2023-01-11。
❌ question：截至现在，我卖掉闲置手机已经过去多少天？
原因：虽然可以计算，但真实用户通常不会追问一笔普通旧物交易距今的精确天数，属于为使用 query_time 而制造的算术题。

session_time：2023-01-13
query_time：2024-12-01
用户原话：最近过敏，医生让我先吃药。
❌ question：我最近过敏是什么时候？
原因一：问题里的“最近”会被理解为 query_time 附近，发生了时间漂移。
原因二：原话中的“最近”不能唯一确定事件日期，也不能用 session_time 冒充过敏发生时间。本候选应输出 suitable=false。

session_time：2023-05-13
query_time：2024-12-01
用户原话：昨天去寺庙待了半天，顺手给家里人祈了个福。
✅ question：我那次去寺庙祈福是哪一天？
✅ answer：2023-05-12
❌ question：我昨天去寺庙祈福是哪一天？
原因：生成后的“昨天”只能表示 query_time 的前一天，即 2024-11-30，与历史事件日期冲突。

目标事实：subject=当前感情状态，value=[单身]
用户原话：前几天整理资料时，把感情状态写成了单身。
❌ question：我是在哪个月确认自己当前的感情状态是单身的？
原因：“单身”是状态，不是有明确发生时间的事件；“整理、确认、保存状态”只是记录动作，这种问题不像真实用户的回忆需求，应 suitable=false。

session_time：2023-10-13
用户原话：昨天通勤时点开《科技早知道》听了一会儿。
❌ question：我是从哪一天开始听《科技早知道》的？
原因：一次收听不能证明这是首次或起始时间。

session_time：2023-01-13
用户原话：耳机前天到货；到货前一天卖掉旧手机，到账后下单。
❌ question：我是哪一天下单耳机的？
原因：答案需要先求到货时间，再沿“前一天”追到另一事件，是二级时间链，不属于 TR-S。

# 生成步骤
1. 从用户原话定位与 subject/value 对应的事件，不要把“提及事实”偷换成“发生事件”。
2. 先做自然性检查：target 是否真的包含一个用户可能询问时间的生活事件；若只是状态、属性或记录动作，直接 suitable=false。
3. 检查事件语义没有被强化，被问时间属于 target 的核心事件，并且一个时间表达直接修饰该事件。
4. 以 session_time 解释原话，求出 event_time，并列出可确定的时间精度。
5. 以 query_time 作为问题的当前时点，选择自然的绝对时间问法；只有事件本身适合衡量持续时长时才选择查询时点相对问法。
6. 给出与问法一致的答案；若问“距今多久”，必须显式使用 query_time 计算。
7. 做四项终检：
   - 真人提问检查：用户是否真有理由这样问，而不是为了从字段中凑出一道时间题；
   - 视角检查：只知道 query_time 的人阅读 question，是否仍会指向 answer 对应的时间；
   - 单跳检查：是否只经过一条“被问事件—时间表达”的时间边；
   - 算术检查：时间词、偏移量、推导结果和 answer 是否一致。
8. 无法唯一确定自然、合法的答案则 suitable=false；适合时输出 JSON。

# 输出格式
仅输出纯 JSON。
适合：
{
  "suitable": true,
  "question": "问题文本",
  "answer": "时间答案",
  "reasoning": "说明时间基准、换算过程和精度"
}
不适合：
{
  "suitable": false,
  "question": null,
  "answer": null,
  "reasoning": "不适合生成时间题的原因"
}
'''.strip()


def build_tr_s_user_prompt(*, query_time: str, payload: dict[str, Any]) -> str:
    """用候选 payload 拼 TR-S 的 user message。"""
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
    return f"""请生成一道 TR-S（单跳时间）题。

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

先判断是否适合生成 TR-S。不适合时 suitable 输出 false；适合时答案必须是可由 session_time、用户原话和 query_time 唯一换算的时间。只输出纯 JSON。
""".strip()
