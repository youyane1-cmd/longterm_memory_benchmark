"""信息抽取（IE）提示词。"""

from .IE_M import IE_M_SYSTEM_PROMPT, build_ie_m_user_prompt
from .IE_S import IE_S_SYSTEM_PROMPT, build_ie_s_user_prompt

__all__ = [
    "IE_M_SYSTEM_PROMPT",
    "IE_S_SYSTEM_PROMPT",
    "build_ie_m_user_prompt",
    "build_ie_s_user_prompt",
]
