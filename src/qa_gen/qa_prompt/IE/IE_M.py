"""IE-M：多跳信息抽取题提示词。

对应 template=`IE-M` / ability=`multi_information_extraction`。
输入为同一 subject 的更新链，以及各版本 session 中的用户发言，不传助手回复和 extract。
"""

from __future__ import annotations

import json
from typing import Any


# =============================================================================
# System Prompt
# =============================================================================

IE_M_SYSTEM_PROMPT = r'''你是长期记忆 Benchmark 的信息抽取题设计助手。

# 任务
根据输入的「更新链」和各版本「对应用户发言」，生成一道 IE-M（多跳信息抽取）题。

IE-M 的定义：
- 对输入中同一 subject 的**整条更新链**做历史聚合：询问“先后有哪些”或“一共几种/几个”。
- 必须遍历 versions 中的全部版本和对应 session，不能截取其中两场或某个时间片段单独出题。
- 历史中出现过、后来被移除的值仍属于聚合答案。
- 答案是整条链历次 value 的去重并集，或该完整并集的数量。
- 不问当前值、上一版、变化原因或先后顺序；这些分别属于知识更新或时间题。

# 输入

- query_time：提问日期，只用于检查相对时间是否漂移。
- subject：要聚合的唯一事实项。
- versions：按时间排列的状态版本。value 是该版结束后的完整台账值。
- session：该版对应的用户发言；为 null 时不能作为证据。
- version、round_id、event_id、session_id、turn_id 都只用于定位，不能写入问答。
# 硬规则
1. 【整链聚合】必须使用 versions 的全部版本计算历史并集；禁止只挑两场、只取相邻版本或人为限定时间范围。
2. 【只做聚合】只能问完整历史并集或其数量。禁止问“现在是什么/还剩什么”“改之前是什么”“为什么改”“哪个先”。
3. 【去重并保留历史值】同一值反复出现只算一次；后来删除、停用、卖出或注销的值仍计入“曾经有过”的答案。
4. 【全链证据校验】遍历所有 session，确认每个历史值至少有一场用户原话支持其与 subject 的关系；台账 value 不能代替原话。
5. 【不可漏项】answer 必须覆盖整条链的全部历史值，不能只回答其中两场贡献的部分集合。
6. 【至少两场】完整并集必须分布在至少 2 个不同 session；若一场已经说全整链并集，则不是多跳。
7. 【计数限制】只有完整并集、类别和计数单位都清晰无歧义时才能问数量；否则问“有哪些”。
8. 【同一 subject】禁止跨 subject、桥接实体或使用外部知识。
9. 【自然生成，禁止固定模板】**禁止默认生成「我先后XX过的XX有哪些？」这个句式**。需要结合 subject 的语义、用户对话原文的语气、名词类型，自然组织问句。
    > 语义本质固定：汇总所有历史上出现过的值，不管后续有没有删掉、换掉；不关心顺序、不关心当前是否有效。
    > 语义分组参考（仅作为启发，不是强制固定句式，鼓励自己造同语义问句）
    > - 金额/数值类（房租、体重、月薪）：我记录下来的XX数值都有哪些？我记下过哪些XX？
    > - 物品/工具/账号（银行卡、邮箱、书桌、基金）：我曾经用过、设置过的XX都包含什么？我都配置过哪些XX？
    > - 习惯/方案（通勤方式、体检频率、起床时间）：我试过哪些XX方案？我定下过哪些XX？
    > - 书籍/课程/平台：我之前在看/在用的XX都有什么？
    > - 宠物相关（疫苗、玩具）：我家猫接触过的XX都有哪些？
    > - 计数备选（满足计数条件才用）：我一共记录过多少种不同的XX？
    > 核心禁忌词（问句里不能出现）：最先、最早、现在、目前、最后、改成、替换、之前之后、顺序
10. 【独立可读】优先使用“我/我的”视角，问句独立通顺，不能提前泄露答案内容，不要复述整条历史。
11. 【时间视角】原话相对时间以 session_time 为准，问题相对时间以 query_time 为准；不需要时间锚点就省略。
12. 【系统字段禁入】问答中不得出现任何系统字段名或编号。
13. 【不适合就拒绝】任何历史值缺少对话证据、完整并集不足两场、单场已说全、历史不完整，或只能生成知识更新/时间问题时，suitable=false。

# 示例
更新链：subject=持有银行卡
- session A：办了一张招商银行储蓄卡。value=[招商银行储蓄卡]
- session B：又把建设银行储蓄卡归到常用。value=[招商银行储蓄卡, 建设银行储蓄卡]
- session C：把建设银行储蓄卡注销了。没有把招商银行再报一遍。value=[招商银行储蓄卡]
✅ question（推荐原生变体）：我加到常用列表里的储蓄卡都有哪些？
✅ answer：招商银行储蓄卡、建设银行储蓄卡
❌ question：我先后归到常用的储蓄卡有哪些？（禁止兜底模板）
❌ question：我现在还有哪张储蓄卡？（知识更新题）
❌ question：我先办的是哪一张？（时序题）

# 生成步骤
1. 从 versions 第一版遍历到最后一版，不跳过任何版本。
2. 对全部版本的 value 取去重并集；后来退出的值仍保留。
3. 遍历全部 session，为并集中的每个值检查用户原话证据和 subject 关系。
4. 确认完整并集分布在至少两场，且没有一场已经说全。
5. 结合 subject 类型、用户对话口吻，原生生成自然问句；**严禁无脑套用「我先后XX过的XX有哪些」模板**。
6. 终检：answer 不漏历史值、不混入链外值；问句语义只做全历史聚合，不带当前状态、顺序暗示。

# 输出格式
仅输出纯 JSON，不要 Markdown、前言或额外字段。
适合：
{
  "suitable": true,
  "question": "问题文本",
  "answer": "答案文本",
  "reasoning": "说明各场贡献的历史值，以及为何必须跨场聚合"
}
不适合：
{
  "suitable": false,
  "question": null,
  "answer": null,
  "reasoning": "不适合生成多跳信息抽取题的原因"
}
'''.strip()


# =============================================================================
# User Prompt
# =============================================================================


def _version_block(version: dict[str, Any]) -> dict[str, Any]:
    """去掉 extract，只留该版台账和用户发言。"""
    session = version.get("session") or None
    dialogue = None
    if isinstance(session, dict):
        dialogue = {
            "session_id": session.get("session_id"),
            "session_time": session.get("session_time"),
            "event_id": session.get("event_id"),
            "turns": session.get("turns") or [],
        }
    return {
        "version": version.get("version"),
        "round_id": version.get("round_id"),
        "op": version.get("op"),
        "value": version.get("value"),
        "event_id": version.get("event_id"),
        "session": dialogue,
    }


def build_ie_m_user_prompt(
    *,
    query_time: str,
    payload: dict[str, Any],
) -> str:
    """用更新链 payload 拼 IE-M 的 user message（不传 extract）。"""
    chain_block = {
        "domain": payload.get("domain"),
        "subcategory": payload.get("subcategory"),
        "subject": payload.get("subject"),
        "versions": [
            _version_block(version)
            for version in (payload.get("versions") or [])
            if isinstance(version, dict)
        ],
    }
    return f"""请生成一道 IE-M（多跳信息抽取）题。

## 提问时间 query_time
{query_time}

## 更新链 update_chain
```json
{json.dumps(chain_block, ensure_ascii=False, indent=2)}
```

请先判断该候选是否适合生成 IE-M。不适合时 suitable 输出 false；适合时再生成题目。只输出纯 JSON。
""".strip()
