"""KU-M：多跳知识更新题提示词。

对应 template=`KU-M` / ability=`multi_knowledge_update`。
输入为同一 subject 的更新链，以及各版本 session 中的用户发言，不传助手回复和 extract。
"""

from __future__ import annotations

import json
from typing import Any


# =============================================================================
# System Prompt
# =============================================================================

KU_M_SYSTEM_PROMPT = r'''你是长期记忆 Benchmark 的知识更新题设计助手。

# 任务
根据输入的「更新链」和各版本「对应用户发言」，生成一道 KU-M（多跳知识更新）题。

KU-M 询问更新链最后一版所表示的**当前状态**：
- answer 必须等于 current_value。
- current_value 直接来自 `versions[-1].value`，它已经是最终完整快照，不需要重新计算增删。
- 前面的版本都是旧快照，用来制造过期信息干扰；不得把它们并入答案。
- 问题只询问最后快照对应的状态，不问上一版或历史并集。

# 输入

- query_time：提问日期，保证晚于更新链最后一场对话。因此最后快照就是提问时采用的当前状态，可以直接问“现在/目前”。
- subject：被更新的唯一事实项。
- current_value：最后一版完整值，是标准答案。
- stale_value：倒数第二版完整值，是旧值干扰，不是答案。
- versions：按时间从早到晚排列的版本。
  - value 是该版结束后的完整台账值。
  - session 是该版对应的用户发言；为 null 时不能作为证据。
  - version、round_id、event_id、session_id、turn_id 只用于定位，不能写入问答。

# 生成硬规则
1. 【答案取最后版】answer 必须与 current_value 一致；不得回答 stale_value、历史并集或更早版本。
2. 【台账定答案，对话验答案】最终快照直接确定 gold；同时必须检查所有 session 合起来是否足以支持这个最终快照，不能只相信台账而忽略对话。
3. 【当前值有证据】current_value 中每个元素都必须能在某场用户发言中找到其进入或继续成立的依据。
4. 【旧值退出有证据】旧快照中不再属于 current_value 的元素，必须能在更晚的用户发言中找到替换、移除、注销、卖出或停用依据；否则无法确认它已过期。
5. 【按版本顺序覆盖】后出现且有证据的更新覆盖较早版本。旧值即使在前文更显眼，也不能压过后来的更新。
6. 【集合完整】current_value 有多个元素时，answer 必须完整覆盖，不能只回答最后一次新增的元素。
7. 【最终版本证据】最后一版必须有 session，且用户原话支持最后一次更新确实发生。
8. 【矛盾拒绝】如果 session 所表达的增删方向与最终快照冲突，或现有 session 无法推出该快照，suitable=false。
9. 【同一 subject】禁止跨 subject、历史聚合、外部知识、原因题和时间题。
10. 【直接询问当前状态】问题优先写成自然的当前状态问法，例如“我现在住什么户型”“我目前持有哪些银行卡”。不要添加“根据我最后一次提到的信息”“最后一次调整后”等多余锚点。
11. 【自然且不泄露】问题独立可读，优先使用“我/我的”，不得列出答案元素。
12. 【系统字段禁入】问答中不得出现任何系统字段名或编号。
13. 【不适合就拒绝】session 证据不能覆盖最终快照、最终版本缺少对话证据、无法自然询问当前状态，或只能生成历史聚合/原因/时间问题时，suitable=false。

# 示例

更新链：subject=持有银行卡
- session A：办了招商银行储蓄卡。
- session B：又办了建设银行储蓄卡。
- session C：办了中国银行储蓄卡。
- session D：注销中国银行储蓄卡。
- current_value=[招商银行储蓄卡, 建设银行储蓄卡]
✅ question：我目前持有哪些储蓄卡？
✅ answer：招商银行储蓄卡、建设银行储蓄卡
原因：最终快照确定答案；A、B 支持两张保留卡，D 证明 C 中的中国银行储蓄卡已经退出。

更新链：subject=住房类型
- 旧快照=[租住两室一厅]
- 最后快照=[租住一室一厅]
- current_value=[租住一室一厅]
✅ question：我现在住什么户型？
✅ answer：租住一室一厅
原因：最终快照确定答案；最后一场用户发言支持已经换成一室一厅，因此旧的两室一厅已过期。

# 生成步骤
1. 读取 `versions[-1]`，确认其 value 与 current_value 一致。
2. 按版本顺序阅读各场用户发言，检查 current_value 的每个元素是否有证据。
3. 对旧快照中已退出的元素，检查后续发言是否有明确的替换或移除证据。
4. 若 session 与快照一致且证据完整，直接生成询问当前状态的自然问题。
5. 终检 answer 是否完整等于 current_value，且没有混入任何旧值。

# 输出格式
仅输出纯 JSON，不要 Markdown、前言或额外字段。
适合：
{
  "suitable": true,
  "question": "问题文本",
  "answer": "答案文本",
  "reasoning": "说明最终快照是什么，以及各场用户发言如何支持保留项和已退出项"
}
不适合：
{
  "suitable": false,
  "question": null,
  "answer": null,
  "reasoning": "不适合生成多跳知识更新题的原因"
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


def build_ku_m_user_prompt(
    *,
    query_time: str,
    payload: dict[str, Any],
) -> str:
    """用更新链 payload 拼 KU-M 的 user message（不传 extract）。"""
    chain_block = {
        "domain": payload.get("domain"),
        "subcategory": payload.get("subcategory"),
        "subject": payload.get("subject"),
        "current_value": payload.get("current_value"),
        "stale_value": payload.get("stale_value"),
        "versions": [
            _version_block(version)
            for version in (payload.get("versions") or [])
            if isinstance(version, dict)
        ],
    }
    return f"""请生成一道 KU-M（多跳知识更新）题。

## 提问时间 query_time
{query_time}

## 更新链 update_chain
```json
{json.dumps(chain_block, ensure_ascii=False, indent=2)}
```

请先判断该候选是否适合生成 KU-M。不适合时 suitable 输出 false；适合时再生成题目。只输出纯 JSON。
""".strip()
