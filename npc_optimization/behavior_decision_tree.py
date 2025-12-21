"""
行为决策树
使用硬编码规则处理日常行为，减少LLM调用
所有规则从人物卡（NPC配置）读取，确保可自定义
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

# 从主系统导入NPCAction，确保一致性
try:
    from npc_system import NPCAction
except ImportError:
    # 如果无法导入，定义本地枚举（备用）
    from enum import Enum
    class NPCAction(Enum):
        WORK = "工作"
        REST = "休息"
        SLEEP = "睡觉"
        EAT = "吃饭"
        SOCIALIZE = "社交"
        OBSERVE = "观察"
        HELP_OTHERS = "帮助他人"
        THINK = "思考"
        PRAY = "祈祷"
        LEARN = "学习"
        CREATE = "创造"
        TRAVEL = "移动"


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
        self.work_hours = self._parse_work_hours(npc_config.get("work_hours", ""))
        self.sleep_time = self._parse_sleep_time()
        self.meal_times = self._parse_meal_times()
        self.habits = npc_config.get("daily_schedule", {}).get("habits", [])
    
    def _parse_work_hours(self, work_hours_str: str) -> tuple:
        """解析工作时间（从人物卡读取）"""
        if not work_hours_str:
            return (9, 18)  # 默认9-18点
        
        # 解析格式："早上6点-晚上7点" 或 "6:00-19:00"
        import re
        # 尝试提取时间
        times = re.findall(r'(\d{1,2})', work_hours_str)
        if len(times) >= 2:
            start = int(times[0])
            end = int(times[1])
            return (start, end)
        
        return (9, 18)  # 默认值
    
    def _parse_sleep_time(self) -> tuple:
        """解析睡觉时间（从人物卡读取）"""
        # 从daily_schedule读取，如果没有则使用默认
        sleep_config = self.daily_schedule.get("sleep_time", "22:00-6:00")
        
        import re
        times = re.findall(r'(\d{1,2})', sleep_config)
        if len(times) >= 2:
            start = int(times[0])
            end = int(times[1])
            return (start, end)
        
        return (22, 6)  # 默认22:00-6:00
    
    def _parse_meal_times(self) -> List[tuple]:
        """解析吃饭时间（从人物卡读取）"""
        meal_config = self.daily_schedule.get("meal_times", ["7:00-8:00", "12:00-13:00", "18:00-19:00"])
        
        meal_times = []
        import re
        for meal in meal_config:
            times = re.findall(r'(\d{1,2})', meal)
            if len(times) >= 2:
                start = int(times[0])
                end = int(times[1])
                meal_times.append((start, end))
        
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
        # 1. 检查是否有紧急任务（优先级>=90），需要LLM决策
        if current_task and current_task.get("priority", 0) >= 90:
            return None  # 紧急任务需要LLM决策
        
        # 2. 睡觉时间判断（从人物卡读取）
        sleep_start, sleep_end = self.sleep_time
        if self._is_sleep_time(current_hour, sleep_start, sleep_end):
            if energy_level < 30 or needs.get("fatigue", 0) > 0.8:
                return NPCAction.SLEEP
        
        # 3. 吃饭时间判断（从人物卡读取）
        for meal_start, meal_end in self.meal_times:
            if meal_start <= current_hour < meal_end:
                if needs.get("hunger", 0) > 0.5:  # 饥饿度超过50%
                    return NPCAction.EAT
        
        # 4. 工作时间判断（从人物卡读取）
        work_start, work_end = self.work_hours
        if work_start <= current_hour < work_end:
            # 如果没有紧急任务，且能量足够，则工作
            if not current_task or current_task.get("priority", 0) < 80:
                if energy_level > 30:
                    return NPCAction.WORK
        
        # 5. 根据需求判断
        # 极度疲劳 -> 休息或睡觉
        if needs.get("fatigue", 0) > 0.8:
            if current_hour >= sleep_start or current_hour < sleep_end:
                return NPCAction.SLEEP
            else:
                return NPCAction.REST
        
        # 能量过低 -> 休息
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
        
        # 解析习惯时间
        import re
        times = re.findall(r'(\d{1,2})', habit_time)
        if len(times) >= 1:
            habit_hour = int(times[0])
            if current_hour == habit_hour:
                # 映射习惯动作到NPCAction
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
        # 如果有规则决策结果，不需要LLM
        routine_action = self.decide_routine_behavior(
            current_hour, energy_level, needs, current_task
        )
        
        return routine_action is None

