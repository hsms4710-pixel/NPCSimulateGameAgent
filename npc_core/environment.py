"""
NPC 环境感知和需求管理系统

包含:
- EnvironmentPerception: 环境感知系统
- NeedSystem: 需求管理系统
"""

import random
from datetime import datetime
from typing import Dict, List, Any

from core_types import NPCAction
from .data_models import NeedState


class EnvironmentPerception:
    """环境感知系统"""

    def __init__(self, world_clock):
        self.world_clock = world_clock
        self.current_weather = "clear"
        self.current_location = "home"
        self.nearby_entities = []
        self.last_updated = datetime.now()

    def update_perception(self):
        """更新环境感知"""
        self.current_weather = self._get_current_weather()
        self.nearby_entities = self._scan_nearby_entities()
        self.last_updated = datetime.now()

    def _get_current_weather(self) -> str:
        """获取当前天气（简化版）"""
        # 基于月份和随机性生成天气
        month = self.world_clock.current_time.month
        hour = self.world_clock.current_time.hour

        # 冬季天气
        if month in [12, 1, 2]:
            weather_options = ["snow", "clear", "cloudy", "storm"]
            weights = [0.3, 0.3, 0.3, 0.1]
        # 春季天气
        elif month in [3, 4, 5]:
            weather_options = ["rain", "clear", "cloudy", "storm"]
            weights = [0.2, 0.4, 0.3, 0.1]
        # 夏季天气
        elif month in [6, 7, 8]:
            weather_options = ["clear", "rain", "storm", "cloudy"]
            weights = [0.5, 0.2, 0.1, 0.2]
        # 秋季天气
        else:
            weather_options = ["clear", "rain", "cloudy", "fog"]
            weights = [0.4, 0.2, 0.3, 0.1]

        # 夜间调整
        if hour < 6 or hour > 22:
            weights = [w * 0.7 for w in weights]  # 夜间天气更稳定

        return random.choices(weather_options, weights=weights)[0]

    def _scan_nearby_entities(self) -> List[Dict[str, Any]]:
        """扫描附近实体（简化版）"""
        # 这里可以扩展为更复杂的实体检测逻辑
        # 目前返回一些示例实体
        entities = []

        # 基于时间添加一些实体
        hour = self.world_clock.current_time.hour
        if 6 <= hour <= 9:  # 早晨
            entities.append({"type": "person", "name": "村民", "distance": 10})
        elif 18 <= hour <= 22:  # 晚上
            entities.append({"type": "person", "name": "守卫", "distance": 20})

        # 随机添加一些环境实体
        if random.random() < 0.1:  # 10%概率
            entities.append({"type": "animal", "name": "野兔", "distance": random.randint(5, 50)})

        return entities

    def assess_safety(self) -> float:
        """评估当前环境安全性 0-1"""
        safety_score = 1.0

        # 天气影响
        if self.current_weather in ['storm', 'heavy_rain', 'snow']:
            safety_score *= 0.7

        # 时间影响
        hour = self.world_clock.current_time.hour
        if 0 <= hour <= 5:
            safety_score *= 0.8  # 深夜不太安全

        # 附近实体影响
        for entity in self.nearby_entities:
            if entity.get('type') == 'threat':
                safety_score *= 0.5

        return max(0.0, min(1.0, safety_score))


class NeedSystem:
    """需求管理系统"""

    def __init__(self):
        self.needs = NeedState()

    def update_needs(self, time_passed_minutes: float, current_activity: NPCAction):
        """根据时间和活动更新需求"""
        # 时间流逝导致的需求增加
        base_rate = time_passed_minutes / 60.0  # 转换为小时

        # 基础需求增长
        self.needs.hunger = min(1.0, self.needs.hunger + base_rate * 0.15)  # 每小时增加15%
        self.needs.fatigue = min(1.0, self.needs.fatigue + base_rate * 0.12)  # 每小时增加12%
        self.needs.social = min(1.0, self.needs.social + base_rate * 0.08)  # 每小时增加8%
        self.needs.security = min(1.0, self.needs.security + base_rate * 0.05)  # 每小时增加5%

        # 活动对需求的影响
        if current_activity == NPCAction.EAT:
            self.needs.hunger = max(0.0, self.needs.hunger - base_rate * 0.8)  # 吃饭减少饥饿
        elif current_activity == NPCAction.SLEEP:
            self.needs.fatigue = max(0.0, self.needs.fatigue - base_rate * 0.6)  # 睡觉减少疲劳
            self.needs.hunger = min(1.0, self.needs.hunger + base_rate * 0.05)  # 睡觉时会饿
        elif current_activity == NPCAction.SOCIALIZE:
            self.needs.social = max(0.0, self.needs.social - base_rate * 0.4)  # 社交减少社交需求
        elif current_activity == NPCAction.WORK:
            self.needs.fatigue = min(1.0, self.needs.fatigue + base_rate * 0.2)  # 工作增加疲劳
            self.needs.achievement = max(0.0, self.needs.achievement - base_rate * 0.1)  # 工作满足成就需求
        elif current_activity == NPCAction.REST:
            self.needs.fatigue = max(0.0, self.needs.fatigue - base_rate * 0.3)  # 休息减少疲劳

        self.needs.last_updated = datetime.now()

    def get_most_urgent_need(self) -> tuple:
        """获取最紧急的需求"""
        need_levels = {
            'hunger': self.needs.hunger,
            'fatigue': self.needs.fatigue,
            'social': self.needs.social,
            'security': self.needs.security,
            'achievement': self.needs.achievement
        }
        return max(need_levels.items(), key=lambda x: x[1])

    def get_need_satisfaction_level(self) -> float:
        """获取整体需求满足度 0-1"""
        total_needs = (self.needs.hunger + self.needs.fatigue +
                      self.needs.social + self.needs.security + self.needs.achievement)
        return 1.0 - (total_needs / 5.0)  # 平均值取反
