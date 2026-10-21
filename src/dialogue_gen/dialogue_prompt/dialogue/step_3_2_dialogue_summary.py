import json
SUMMARY_SYSTEM_PROMPT = """
你是对话摘要助手。
只总结本段对话产生的客观事实信息，禁止逐句摘抄。
【硬性约束】
1. 摘要必须简短凝练，删除大量心理感受、推导过程、情绪描写。保留关键实体、日期、事件、动作；只写客观发生的内容，不渲染感受。写成单段短句，不要长铺垫。
2. 【强制】摘要**不要记录任何备忘录相关信息**，所有涉及备忘录、备忘、笔记保存、复制内容到备忘录、新建备忘文档等内容全部剔除，不写入摘要。
""".strip()

SUMMARY_USER_PROMPT = """
为下面对话写 session_summary，**高度精简，只提取本段新发生的客观事实**，剔除心理感受、感想、推论。
只保留关键实体、时间、动作，压缩成简短一段话。对话包含 turn_id、speaker、content。
【强制规则】摘要里**完全不写任何备忘录相关内容**，所有备忘录、备忘、保存到笔记类描述全部删掉。
""".strip()

def build_summary_user_prompt(materials: dict) -> str:
    """把一段对话拼成摘要用的用户提示词。"""
    material_text = json.dumps(materials, ensure_ascii=False, indent=2)
    return f"{SUMMARY_USER_PROMPT}\n{material_text}"
