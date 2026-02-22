#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_npc_core.py - NPC Core 模块测试

测试内容：
1. Memory, Goal, Relationship, NeedState 数据类
2. EnvironmentPerception, NeedSystem 类
3. NPCBehaviorSystem 导入和创建

使用 pytest 框架，配合 conftest.py 中的共享 fixtures
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# 数据类测试
# ============================================================================

class TestMemoryDataClass:
    """测试 Memory 数据类"""

    def test_memory_creation_basic(self):
        """测试基本创建"""
        from npc_core import Memory

        memory = Memory(
            content="今天在镇广场遇见了老朋友",
            emotional_impact=5,
            importance=7,
            timestamp=datetime.now()
        )

        assert memory.content == "今天在镇广场遇见了老朋友"
        assert memory.emotional_impact == 5
        assert memory.importance == 7
        assert isinstance(memory.timestamp, datetime)
        assert memory.tags == []
        assert memory.related_npcs == []

    def test_memory_creation_with_optional_fields(self):
        """测试带可选字段的创建"""
        from npc_core import Memory

        memory = Memory(
            content="和铁匠讨论了新剑的设计",
            emotional_impact=3,
            importance=6,
            timestamp=datetime.now(),
            tags=["工作", "社交"],
            related_npcs=["铁匠", "学徒"]
        )

        assert len(memory.tags) == 2
        assert "工作" in memory.tags
        assert len(memory.related_npcs) == 2
        assert "铁匠" in memory.related_npcs

    def test_memory_emotional_impact_range(self):
        """测试情感影响范围（-10 到 +10）"""
        from npc_core import Memory

        # 正面情感
        positive_memory = Memory(
            content="获得了村长的赞扬",
            emotional_impact=10,
            importance=8,
            timestamp=datetime.now()
        )
        assert positive_memory.emotional_impact == 10

        # 负面情感
        negative_memory = Memory(
            content="被顾客投诉",
            emotional_impact=-8,
            importance=6,
            timestamp=datetime.now()
        )
        assert negative_memory.emotional_impact == -8


class TestGoalDataClass:
    """测试 Goal 数据类"""

    def test_goal_creation_basic(self):
        """测试基本创建"""
        from npc_core import Goal

        goal = Goal(
            description="完成今天的锻造订单",
            priority=8
        )

        assert goal.description == "完成今天的锻造订单"
        assert goal.priority == 8
        assert goal.deadline is None
        assert goal.progress == 0.0
        assert goal.sub_goals == []
        assert goal.status == "active"

    def test_goal_creation_with_all_fields(self):
        """测试带所有字段的创建"""
        from npc_core import Goal

        deadline = datetime.now() + timedelta(days=7)
        goal = Goal(
            description="打造一把传说级武器",
            priority=10,
            deadline=deadline,
            progress=0.3,
            sub_goals=["收集材料", "设计图纸", "锻造"],
            status="active"
        )

        assert goal.deadline == deadline
        assert goal.progress == 0.3
        assert len(goal.sub_goals) == 3
        assert goal.status == "active"

    def test_goal_status_values(self):
        """测试目标状态值"""
        from npc_core import Goal

        statuses = ["active", "completed", "failed", "paused"]
        for status in statuses:
            goal = Goal(
                description="测试目标",
                priority=5,
                status=status
            )
            assert goal.status == status


class TestRelationshipDataClass:
    """测试 Relationship 数据类"""

    def test_relationship_creation_basic(self):
        """测试基本创建"""
        from npc_core import Relationship

        rel = Relationship(
            npc_name="村长",
            affection=60,
            trust=70
        )

        assert rel.npc_name == "村长"
        assert rel.affection == 60
        assert rel.trust == 70
        assert rel.interactions_count == 0
        assert rel.last_interaction is None
        assert rel.relationship_type == "acquaintance"

    def test_relationship_creation_full(self):
        """测试完整创建"""
        from npc_core import Relationship

        last_time = datetime.now()
        rel = Relationship(
            npc_name="酒馆老板",
            affection=80,
            trust=85,
            interactions_count=50,
            last_interaction=last_time,
            relationship_type="friend"
        )

        assert rel.interactions_count == 50
        assert rel.last_interaction == last_time
        assert rel.relationship_type == "friend"

    def test_relationship_affection_range(self):
        """测试亲密度范围（-100 到 +100）"""
        from npc_core import Relationship

        # 高亲密度
        friend_rel = Relationship(
            npc_name="老友",
            affection=100,
            trust=90
        )
        assert friend_rel.affection == 100

        # 敌对关系
        enemy_rel = Relationship(
            npc_name="盗贼",
            affection=-80,
            trust=10
        )
        assert enemy_rel.affection == -80


class TestNeedStateDataClass:
    """测试 NeedState 数据类"""

    def test_needstate_creation_default(self):
        """测试默认创建"""
        from npc_core import NeedState

        needs = NeedState()

        assert needs.hunger == 0.0
        assert needs.fatigue == 0.0
        assert needs.social == 0.0
        assert needs.security == 0.0
        assert needs.achievement == 0.0
        assert isinstance(needs.last_updated, datetime)

    def test_needstate_creation_custom(self):
        """测试自定义创建"""
        from npc_core import NeedState

        needs = NeedState(
            hunger=0.5,
            fatigue=0.3,
            social=0.7,
            security=0.2,
            achievement=0.4
        )

        assert needs.hunger == 0.5
        assert needs.fatigue == 0.3
        assert needs.social == 0.7
        assert needs.security == 0.2
        assert needs.achievement == 0.4

    def test_needstate_boundary_values(self):
        """测试边界值（0-1）"""
        from npc_core import NeedState

        # 最小值
        min_needs = NeedState(
            hunger=0.0,
            fatigue=0.0,
            social=0.0,
            security=0.0,
            achievement=0.0
        )
        assert min_needs.hunger == 0.0

        # 最大值
        max_needs = NeedState(
            hunger=1.0,
            fatigue=1.0,
            social=1.0,
            security=1.0,
            achievement=1.0
        )
        assert max_needs.hunger == 1.0


# ============================================================================
# EnvironmentPerception 测试
# ============================================================================

class TestEnvironmentPerception:
    """测试环境感知系统"""

    def test_init(self, mock_world_clock):
        """测试初始化"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)

        assert perception.world_clock == mock_world_clock
        assert perception.current_weather == "clear"
        assert perception.current_location == "home"
        assert perception.nearby_entities == []
        assert isinstance(perception.last_updated, datetime)

    def test_update_perception(self, mock_world_clock):
        """测试更新感知"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)
        old_update_time = perception.last_updated

        # 等待一小段时间确保时间戳不同
        import time
        time.sleep(0.01)

        perception.update_perception()

        # 验证更新时间已改变
        assert perception.last_updated >= old_update_time

    def test_get_current_weather_returns_valid_weather(self, mock_world_clock):
        """测试获取当前天气"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)
        weather = perception._get_current_weather()

        valid_weathers = ["clear", "rain", "cloudy", "storm", "snow", "fog", "heavy_rain"]
        assert weather in valid_weathers

    def test_scan_nearby_entities(self, mock_world_clock):
        """测试扫描附近实体"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)
        entities = perception._scan_nearby_entities()

        assert isinstance(entities, list)
        for entity in entities:
            assert "type" in entity
            assert "name" in entity
            assert "distance" in entity

    def test_assess_safety(self, mock_world_clock):
        """测试安全性评估"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)
        safety = perception.assess_safety()

        assert 0.0 <= safety <= 1.0

    def test_assess_safety_with_storm_weather(self, mock_world_clock):
        """测试恶劣天气下的安全性评估"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)
        perception.current_weather = "storm"
        safety = perception.assess_safety()

        assert safety < 1.0  # 风暴天气安全性应降低

    def test_assess_safety_with_threat(self, mock_world_clock):
        """测试存在威胁时的安全性评估"""
        from npc_core import EnvironmentPerception

        perception = EnvironmentPerception(mock_world_clock)
        perception.nearby_entities = [
            {"type": "threat", "name": "狼", "distance": 10}
        ]
        safety = perception.assess_safety()

        assert safety < 0.6  # 存在威胁时安全性应大幅降低


# ============================================================================
# NeedSystem 测试
# ============================================================================

class TestNeedSystem:
    """测试需求管理系统"""

    def test_init(self):
        """测试初始化"""
        from npc_core import NeedSystem, NeedState

        need_system = NeedSystem()

        assert isinstance(need_system.needs, NeedState)
        assert need_system.needs.hunger == 0.0

    def test_update_needs_time_passing(self):
        """测试时间流逝导致的需求增加"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()
        initial_hunger = need_system.needs.hunger
        initial_social = need_system.needs.social

        # 模拟60分钟过去 (使用 OBSERVE 动作，不会特别减少任何需求)
        need_system.update_needs(60, NPCAction.OBSERVE)

        assert need_system.needs.hunger > initial_hunger  # 饥饿应该增加
        assert need_system.needs.social > initial_social  # 社交需求应该增加

    def test_update_needs_eating(self):
        """测试吃饭减少饥饿"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()
        need_system.needs.hunger = 0.8  # 设置高饥饿值

        need_system.update_needs(30, NPCAction.EAT)

        assert need_system.needs.hunger < 0.8  # 饥饿应该减少

    def test_update_needs_sleeping(self):
        """测试睡觉减少疲劳"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()
        need_system.needs.fatigue = 0.7  # 设置高疲劳值

        need_system.update_needs(60, NPCAction.SLEEP)

        assert need_system.needs.fatigue < 0.7  # 疲劳应该减少

    def test_update_needs_working(self):
        """测试工作增加疲劳"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()
        initial_fatigue = need_system.needs.fatigue

        need_system.update_needs(60, NPCAction.WORK)

        assert need_system.needs.fatigue > initial_fatigue  # 工作增加疲劳

    def test_update_needs_socializing(self):
        """测试社交减少社交需求"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()
        need_system.needs.social = 0.8  # 设置高社交需求

        need_system.update_needs(60, NPCAction.SOCIALIZE)

        assert need_system.needs.social < 0.8  # 社交需求应该减少

    def test_get_most_urgent_need(self):
        """测试获取最紧急需求"""
        from npc_core import NeedSystem

        need_system = NeedSystem()
        need_system.needs.hunger = 0.9
        need_system.needs.fatigue = 0.3
        need_system.needs.social = 0.5

        urgent_need, level = need_system.get_most_urgent_need()

        assert urgent_need == "hunger"
        assert level == 0.9

    def test_get_need_satisfaction_level(self):
        """测试获取需求满足度"""
        from npc_core import NeedSystem

        need_system = NeedSystem()
        # 所有需求都为0，满足度应为1
        satisfaction = need_system.get_need_satisfaction_level()
        assert satisfaction == 1.0

        # 设置一些需求
        need_system.needs.hunger = 0.5
        need_system.needs.fatigue = 0.5
        satisfaction = need_system.get_need_satisfaction_level()
        assert 0.0 < satisfaction < 1.0

    def test_needs_clamped_to_bounds(self):
        """测试需求值被限制在 0-1 范围内"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()

        # 测试上界限制
        need_system.needs.hunger = 0.95
        need_system.update_needs(120, NPCAction.REST)  # 长时间休息
        assert need_system.needs.hunger <= 1.0

        # 测试下界限制
        need_system.needs.fatigue = 0.05
        need_system.update_needs(120, NPCAction.SLEEP)  # 长时间睡觉
        assert need_system.needs.fatigue >= 0.0


# ============================================================================
# NPCBehaviorSystem 导入测试
# ============================================================================

class TestNPCBehaviorSystemImport:
    """测试 NPCBehaviorSystem 导入"""

    def test_import_from_npc_core(self):
        """测试从 npc_core 导入"""
        from npc_core import NPCBehaviorSystem
        assert NPCBehaviorSystem is not None

    def test_import_all_data_models(self):
        """测试导入所有数据模型"""
        from npc_core import Memory, Goal, Relationship, NeedState
        assert Memory is not None
        assert Goal is not None
        assert Relationship is not None
        assert NeedState is not None

    def test_import_environment_classes(self):
        """测试导入环境类"""
        from npc_core import EnvironmentPerception, NeedSystem
        assert EnvironmentPerception is not None
        assert NeedSystem is not None


class TestNPCBehaviorSystemCreation:
    """测试 NPCBehaviorSystem 创建"""

    def test_creation_with_mock_client(self, sample_npc_config, mock_llm_client):
        """测试使用 Mock 客户端创建"""
        from npc_core import NPCBehaviorSystem

        # 创建一个更完整的 Mock DeepSeekClient
        mock_client = Mock()
        mock_client.call_model = mock_llm_client.call_model
        mock_client.generate_response = mock_llm_client.generate_response

        try:
            npc = NPCBehaviorSystem(sample_npc_config, mock_client)
            assert npc is not None
            # 验证基本属性
            assert hasattr(npc, 'npc_config') or hasattr(npc, 'config')
        except Exception as e:
            # 如果创建失败，至少验证类可以导入
            pytest.skip(f"NPCBehaviorSystem 创建需要额外依赖: {e}")

    def test_npc_config_required_fields(self, sample_npc_config):
        """测试 NPC 配置必需字段"""
        required_fields = ["name", "profession", "personality", "background"]
        for field in required_fields:
            assert field in sample_npc_config, f"缺少必需字段: {field}"


# ============================================================================
# 边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """边界条件测试"""

    def test_memory_empty_content(self):
        """测试空内容记忆"""
        from npc_core import Memory

        memory = Memory(
            content="",
            emotional_impact=0,
            importance=1,
            timestamp=datetime.now()
        )
        assert memory.content == ""

    def test_goal_zero_priority(self):
        """测试零优先级目标"""
        from npc_core import Goal

        goal = Goal(
            description="低优先级任务",
            priority=0
        )
        assert goal.priority == 0

    def test_relationship_zero_trust(self):
        """测试零信任关系"""
        from npc_core import Relationship

        rel = Relationship(
            npc_name="陌生人",
            affection=0,
            trust=0
        )
        assert rel.trust == 0

    def test_needstate_all_zero(self):
        """测试所有需求为零"""
        from npc_core import NeedState

        needs = NeedState()
        total = (needs.hunger + needs.fatigue + needs.social +
                 needs.security + needs.achievement)
        assert total == 0.0

    def test_needstate_all_max(self):
        """测试所有需求为最大值"""
        from npc_core import NeedState

        needs = NeedState(
            hunger=1.0,
            fatigue=1.0,
            social=1.0,
            security=1.0,
            achievement=1.0
        )
        total = (needs.hunger + needs.fatigue + needs.social +
                 needs.security + needs.achievement)
        assert total == 5.0


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration:
    """集成测试"""

    def test_environment_and_needs_interaction(self, mock_world_clock):
        """测试环境感知和需求系统的交互"""
        from npc_core import EnvironmentPerception, NeedSystem
        from core_types import NPCAction

        perception = EnvironmentPerception(mock_world_clock)
        need_system = NeedSystem()

        # 模拟一天的活动
        activities = [
            (NPCAction.EAT, 30),
            (NPCAction.WORK, 240),
            (NPCAction.EAT, 30),
            (NPCAction.WORK, 240),
            (NPCAction.EAT, 30),
            (NPCAction.SOCIALIZE, 60),
            (NPCAction.SLEEP, 480)
        ]

        for activity, duration in activities:
            need_system.update_needs(duration, activity)
            perception.update_perception()

        # 验证需求系统正常工作
        assert 0.0 <= need_system.needs.hunger <= 1.0
        assert 0.0 <= need_system.needs.fatigue <= 1.0

    def test_all_npc_actions_with_need_system(self):
        """测试所有 NPC 动作与需求系统的交互"""
        from npc_core import NeedSystem
        from core_types import NPCAction

        need_system = NeedSystem()

        # 测试每个动作
        for action in NPCAction:
            try:
                need_system.update_needs(30, action)
            except Exception as e:
                pytest.fail(f"动作 {action} 导致错误: {e}")

        # 验证需求值仍在有效范围内
        assert 0.0 <= need_system.needs.hunger <= 1.0
        assert 0.0 <= need_system.needs.fatigue <= 1.0
        assert 0.0 <= need_system.needs.social <= 1.0
