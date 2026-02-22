"""
行为决策树
使用硬编码规则处理日常行为，减少LLM调用
所有规则从人物卡（NPC配置）读取，确保可自定义
"""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from core_types import NPCAction


def _parse_hour_range(time_str: str, default: tuple) -> tuple:
    """
    安全解析时间范围字符串，提取起止小时。

    支持格式：
      - "22:00-6:00"  → (22, 6)
      - "早上6点-晚上7点" → (6, 7)
      - "6-18"        → (6, 18)

    Args:
        time_str: 时间范围字符串
        default:  解析失败时的默认值

    Returns:
        (start_hour, end_hour) 整数元组
    """
    if not time_str:
        return default

    # 优先匹配 HH:MM 格式（避免将分钟数字误认为小时）
    hours = re.findall(r'(\d{1,2}):\d{2}', time_str)
    if len(hours) >= 2:
        return (int(hours[0]), int(hours[1]))

    # 次优：匹配带"点"或"时"的中文时间
    nums = re.findall(r'(\d{1,2})(?:点|时)', time_str)
    if len(nums) >= 2:
        return (int(nums[0]), int(nums[1]))

    # 降级：提取所有整数（如 "6-18"）
    nums = re.findall(r'\b(\d{1,2})\b', time_str)
    if len(nums) >= 2:
        return (int(nums[0]), int(nums[1]))

    return default


class BehaviorDecisionTree:
    """
    行为决策树
    从NPC配置（人物卡）读取作息习惯，使用规则决策日常行为
    """

    def __init__(self, npc_config: Dict[str, Any]):
        """
        初始化行为决策树

        Args:
            npc_config: NPC配置（人物卡），包含daily_schedule、work_hours等
        """
        self.config = npc_config
        self.daily_schedule = npc_config.get("daily_schedule", {})
        self.work_hours = _parse_hour_range(
            npc_config.get("work_hours", ""), default=(9, 18)
        )
        self.sleep_time = _parse_hour_range(
            self.daily_schedule.get("sleep_time", "22:00-6:00"), default=(22, 6)
        )
        self.meal_times = self._parse_meal_times()
        self.habits = self.daily_schedule.get("habits", [])

    def _parse_meal_times(self) -> List[tuple]:
        """解析吃饭时间（从人物卡读取）"""
        meal_config = self.daily_schedule.get(
            "meal_times", ["7:00-8:00", "12:00-13:00", "18:00-19:00"]
        )
        meal_times = []
        for meal in meal_config:
            parsed = _parse_hour_range(meal, default=None)
            if parsed is not None:
                meal_times.append(parsed)
        return meal_times if meal_times else [(7, 8), (12, 13), (18, 19)]

    def decide_routine_behavior(self,
                                current_hour: int,
                                energy_level: int,
                                needs: Dict[str, float],
                                current_task: Optional[Dict[str, Any]] = None) -> Optional[NPCAction]:
        """
        决策日常行为（不使用LLM）

        Args:
            current_hour: 当前小时（0-23）
            energy_level: 能量水平（0-100）
            needs: 需求字典 {"hunger": 0.0-1.0, "fatigue": 0.0-1.0, "social": 0.0-1.0}
            current_task: 当前任务（如果有）

        Returns:
            NPCAction 或 None（None表示需要LLM决策）
        """
        # *** 生存锁定逻辑（最高优先级）***
        if energy_level < 10 and needs.get("fatigue", 0) > 0.9:
            return NPCAction.SLEEP

        if needs.get("hunger", 0) > 0.95:
            return NPCAction.EAT

        # 1. 检查是否有紧急任务（优先级>=90），需要LLM决策
        if current_task and current_task.get("priority", 0) >= 90:
            return None

        # 2. 睡觉时间判断（从人物卡读取）
        sleep_start, sleep_end = self.sleep_time
        if self._is_sleep_time(current_hour, sleep_start, sleep_end):
            if energy_level < 30 or needs.get("fatigue", 0) > 0.8:
                return NPCAction.SLEEP

        # 3. 吃饭时间判断（从人物卡读取）
        for meal_start, meal_end in self.meal_times:
            if meal_start <= current_hour < meal_end:
                if needs.get("hunger", 0) > 0.5:
                    return NPCAction.EAT

        # 4. 工作时间判断（从人物卡读取）
        work_start, work_end = self.work_hours
        if work_start <= current_hour < work_end:
            if not current_task or current_task.get("priority", 0) < 80:
                if energy_level > 30:
                    return NPCAction.WORK

        # 5. 根据需求判断
        if needs.get("fatigue", 0) > 0.8:
            if self._is_sleep_time(current_hour, sleep_start, sleep_end):
                return NPCAction.SLEEP
            else:
                return NPCAction.REST

        if energy_level < 20:
            return NPCAction.REST

        # 6. 检查自定义习惯（从人物卡读取）
        for habit in self.habits:
            habit_action = self._check_habit(habit, current_hour)
            if habit_action:
                return habit_action

        # 7. 默认情况：需要LLM决策
        return None

    def _is_sleep_time(self, hour: int, sleep_start: int, sleep_end: int) -> bool:
        """判断是否在睡觉时间"""
        if sleep_start > sleep_end:  # 跨天（如22:00-6:00）
            return hour >= sleep_start or hour < sleep_end
        else:  # 同天（如0:00-8:00）
            return sleep_start <= hour < sleep_end

    def _check_habit(self, habit: Dict[str, Any], current_hour: int) -> Optional[NPCAction]:
        """检查自定义习惯（从人物卡读取）"""
        habit_time = habit.get("time", "")
        habit_action = habit.get("action", "")

        hours = re.findall(r'(\d{1,2})(?::\d{2}|点|时|$)', habit_time)
        if hours:
            habit_hour = int(hours[0])
            if current_hour == habit_hour:
                action_map = {
                    "祈祷": NPCAction.PRAY,
                    "思考": NPCAction.THINK,
                    "学习": NPCAction.LEARN,
                    "创造": NPCAction.CREATE,
                    "社交": NPCAction.SOCIALIZE,
                    "休息": NPCAction.REST
                }
                return action_map.get(habit_action)

        return None

    def should_use_llm(self,
                       current_hour: int,
                       energy_level: int,
                       needs: Dict[str, float],
                       current_task: Optional[Dict[str, Any]] = None) -> bool:
        """
        判断是否需要使用LLM决策

        Returns:
            True: 需要LLM决策
            False: 可以使用规则决策
        """
        return self.decide_routine_behavior(current_hour, energy_level, needs, current_task) is None
