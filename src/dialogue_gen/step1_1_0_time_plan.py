"""世界时间线。按人物起始日期和轮次计算每一轮的一个月窗口。"""

import calendar
import re
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict

from ..utils import parse_date


class TimeWindow(BaseModel):
    """一轮事件可以发生的起止日期，两端都包含在内。"""

    model_config = ConfigDict(extra="forbid")

    round_id: str
    start: date
    end: date


class TimePlan:
    """维护人物的世界时间线。状态本身不保存日期。"""

    def __init__(self, start: date | str, months: int = 1) -> None:
        if months < 1:
            raise ValueError("每轮至少跨 1 个月")
        self.start = parse_date(start)
        self.months = months

    def node(self, round_id: str) -> date:
        """返回这一轮状态成立的时间节点。v0 是起始日期，之后每轮加一个月。"""
        return _add_months(self.start, _round_index(round_id) * self.months)

    def window(self, round_id: str) -> TimeWindow:
        """返回这一轮事件图使用的一个月范围。v0 只有时间节点，没有事件窗口。"""
        index = _round_index(round_id)
        if index < 1:
            raise ValueError("v0 是初始时间节点，没有一个月的事件窗口")
        start = self.node(f"v{index - 1}")
        if index > 1:
            start += timedelta(days=1)
        return TimeWindow(round_id=round_id, start=start, end=self.node(round_id))


def _round_index(round_id: str) -> int:
    match = re.fullmatch(r"v(\d+)", round_id)
    if match is None:
        raise ValueError(f"无效的版本编号：{round_id}")
    return int(match.group(1))


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


if __name__ == "__main__":
    time_plan = TimePlan(start="2025-01-01")
    print(time_plan.window("v1"))
"""round_id='v1' start=datetime.date(2025, 1, 1) end=datetime.date(2025, 2, 1)"""