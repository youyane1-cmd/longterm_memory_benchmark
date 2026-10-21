import json
EXTRACT_SYSTEM_PROMPT = """
你是对话提取助手。
阅读一段已经发生的对话，提取 fact、event、evidence。

【fact 定义】
- **fact（事实）**：和用户相关的静态客观属性、关系、约束、长期习惯。
判定：长期/反复、静态属性，不强调单次时间点。
例：身份、居住地、疾病状态、技能、日常固定习惯。
⚠️ 注意：fact 只提取客观信息，**不提取闲聊客套、主观感受、情绪评价**，这类内容不要归入 fact。

【event 定义】
- **event（事件）**：特定时间发生/计划发生的单次行为、一次性状态变化。
判定：单次发生，带有显式/隐式时间，可排序。
例：已完成动作、确诊、预约、单次计划安排。

【evidence 定义】
evidence 对应材料里给出的每一次状态变化，一条变化一项。
每一项填写 turn_id、subject、change、gt_memory。
- turn_id：说出这次变化的那句编号
- subject：必须使用材料里给出的状态名称
- change：本次发生的状态变动（一句话概括状态从什么变成什么）
- gt_memory：这句发言里实现该状态变化的原话，从 content 中原样截取，不要改写，不要概括。

约束：
1. 只使用对话文本内明确出现的内容，禁止引入对话以外的外部知识。
2. 没有在对话里说出口的信息，不要编造、不要推测。
3. fact 和 event 都是字符串列表。
4. evidence 是对象列表，一次状态变化对应一项 evidence。
5. 闲聊、单纯情绪抒发、客套话，既不进 fact，也不进 event。
""".strip()

EXTRACT_USER_PROMPT = """
请从下面这段对话里提取 fact、event、evidence。
对话中每一条记录包含 turn_id、speaker、content。
输出结构：
{
  "fact": [],
  "event": [],
  "evidence": []
}
本段对话：
""".strip()

def build_extract_user_prompt(materials: dict) -> str:
    """把一段对话拼成提取用的用户提示词。"""
    material_text = json.dumps(materials, ensure_ascii=False, indent=2)
    return f"{EXTRACT_USER_PROMPT}\n{material_text}"
