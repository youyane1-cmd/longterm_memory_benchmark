"""对话生成侧提示词的统一导入入口。"""

from .profile.step_0_0_profile import PROFILE_SUMMARY_SYSTEM_PROMPT
from .target_state_plan.step_1_0_target_state import (
    ROUND_PLAN_SYSTEM_PROMPT,
    ROUND_PLAN_USER_PROMPT,
)
from .time_event_graph.step_2_0_time_event_graph import (
    EVENT_GRAPH_SYSTEM_PROMPT,
    EVENT_GRAPH_USER_PROMPT_TEMPLATE,
    build_event_graph_user_prompt,
)
from .dialogue.step_3_0_dialogue import (
    build_assistant_system_prompt,
    build_user_system_prompt,
)
from .dialogue.step_3_1_dialogue_extract import (
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_USER_PROMPT,
)
from .dialogue.step_3_2_dialogue_summary import (
    SUMMARY_SYSTEM_PROMPT,
    SUMMARY_USER_PROMPT,
)

__all__ = [
    "PROFILE_SUMMARY_SYSTEM_PROMPT",
    "ROUND_PLAN_SYSTEM_PROMPT",
    "ROUND_PLAN_USER_PROMPT",
    "EVENT_GRAPH_SYSTEM_PROMPT",
    "EVENT_GRAPH_USER_PROMPT_TEMPLATE",
    "build_event_graph_user_prompt",
    "build_assistant_system_prompt",
    "build_user_system_prompt",
    "EXTRACT_SYSTEM_PROMPT",
    "EXTRACT_USER_PROMPT",
    "SUMMARY_SYSTEM_PROMPT",
    "SUMMARY_USER_PROMPT",
]
