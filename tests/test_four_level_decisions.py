#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_four_level_decisions.py - 四级决策系统测试

测试内容：
1. L1RoutineDecision 生物钟判决
2. L2FastFilter 快速过滤
3. L4ToTReactReasoning._simulate_path 新实现
4. 各种场景下的路径评估

使用 pytest 框架，配合 conftest.py 中的共享 fixtures
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import json

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# L1RoutineDecision 测试
# ============================================================================

class TestL1RoutineDecision:
    """测试 L1 决策层 - 生物钟硬判决"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        assert L1RoutineDecision is not None

    def test_init(self, sample_npc_config):
        """测试初始化"""
        from npc_optimization.four_level_decisions import L1RoutineDecision

        l1 = L1RoutineDecision(sample_npc_config)

        assert l1.config == sample_npc_config
        assert l1.current_activity is None
        assert l1.action_start_time is None

    def test_forced_sleep_high_fatigue(self, sample_npc_config):
        """测试高疲劳时强制睡眠"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        result = l1.decide(
            current_activity=NPCAction.WORK,
            current_hour=22,
            energy_level=0.2,
            hunger_level=0.3,
            fatigue_level=0.99,  # 超过阈值
            latest_impact_score=50
        )

        assert result == NPCAction.SLEEP

    def test_forced_eat_high_hunger(self, sample_npc_config):
        """测试高饥饿时强制进食"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        result = l1.decide(
            current_activity=NPCAction.WORK,
            current_hour=14,
            energy_level=0.5,
            hunger_level=0.95,  # 超过阈值
            fatigue_level=0.3,
            latest_impact_score=30
        )

        assert result == NPCAction.EAT

    def test_default_routine_no_current_activity(self, sample_npc_config):
        """测试无当前行为时返回默认作息"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        result = l1.decide(
            current_activity=None,
            current_hour=10,
            energy_level=0.8,
            hunger_level=0.3,
            fatigue_level=0.2,
            latest_impact_score=20
        )

        assert isinstance(result, NPCAction)

    def test_continue_current_activity_low_impact(self, sample_npc_config):
        """测试低冲击力时继续当前行为"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        result = l1.decide(
            current_activity=NPCAction.WORK,  # 惯性值 65
            current_hour=10,
            energy_level=0.8,
            hunger_level=0.3,
            fatigue_level=0.2,
            latest_impact_score=30  # 低于惯性值
        )

        assert result is None  # 继续 L1

    def test_l2_required_high_impact(self, sample_npc_config):
        """测试高冲击力时需要 L2"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        result = l1.decide(
            current_activity=NPCAction.REST,  # 惯性值 50
            current_hour=15,
            energy_level=0.7,
            hunger_level=0.3,
            fatigue_level=0.2,
            latest_impact_score=80  # 高于惯性值
        )

        assert result == "L2_REQUIRED"

    def test_get_default_routine_sleep_hours(self, sample_npc_config):
        """测试睡眠时间默认作息"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        # 测试深夜时间
        for hour in [23, 0, 1, 2, 3, 4, 5]:
            result = l1._get_default_routine(hour)
            assert result == NPCAction.SLEEP

    def test_get_default_routine_work_hours(self, sample_npc_config):
        """测试工作时间默认作息"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        # 测试上午工作时间
        for hour in [7, 8, 9, 10, 11]:
            result = l1._get_default_routine(hour)
            assert result == NPCAction.WORK

        # 测试下午工作时间
        for hour in [13, 14, 15, 16, 17]:
            result = l1._get_default_routine(hour)
            assert result == NPCAction.WORK

    def test_get_default_routine_eat_hours(self, sample_npc_config):
        """测试用餐时间默认作息"""
        from npc_optimization.four_level_decisions import L1RoutineDecision
        from core_types import NPCAction

        l1 = L1RoutineDecision(sample_npc_config)

        # 早餐
        assert l1._get_default_routine(6) == NPCAction.EAT
        # 午餐
        assert l1._get_default_routine(12) == NPCAction.EAT
        # 晚餐
        assert l1._get_default_routine(18) == NPCAction.EAT

    def test_assess_duration(self, sample_npc_config):
        """测试评估行为持续时间"""
        from npc_optimization.four_level_decisions import L1RoutineDecision

        l1 = L1RoutineDecision(sample_npc_config)

        start_time = datetime.now() - timedelta(minutes=45)
        current_time = datetime.now()

        duration = l1.assess_duration(start_time, current_time)

        assert 44.0 <= duration <= 46.0  # 大约45分钟

    def test_assess_duration_no_start_time(self, sample_npc_config):
        """测试无开始时间时的持续时间"""
        from npc_optimization.four_level_decisions import L1RoutineDecision

        l1 = L1RoutineDecision(sample_npc_config)

        duration = l1.assess_duration(None, datetime.now())

        assert duration == 0.0


# ============================================================================
# L2FastFilter 测试
# ============================================================================

class TestL2FastFilter:
    """测试 L2 决策层 - 快速过滤"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.four_level_decisions import L2FastFilter
        assert L2FastFilter is not None

    def test_init(self, mock_llm_client):
        """测试初始化"""
        from npc_optimization.four_level_decisions import L2FastFilter

        l2 = L2FastFilter(mock_llm_client)

        assert l2.llm_client == mock_llm_client

    def test_assess_event_importance_returns_tuple(self, mock_llm_client, sample_npc_config):
        """测试返回正确的元组格式"""
        from npc_optimization.four_level_decisions import L2FastFilter

        l2 = L2FastFilter(mock_llm_client)

        is_important, urgency = l2.assess_event_importance(
            event_content="铁匠铺着火了！",
            npc_personality=sample_npc_config
        )

        assert isinstance(is_important, bool)
        assert isinstance(urgency, float)
        assert 0.0 <= urgency <= 1.0

    def test_assess_event_importance_yes_response(self, sample_npc_config):
        """测试 YES 响应解析"""
        from npc_optimization.four_level_decisions import L2FastFilter

        mock_client = Mock()
        mock_client.call_model = Mock(return_value="YES, 紧急度: 8")

        l2 = L2FastFilter(mock_client)

        is_important, urgency = l2.assess_event_importance(
            event_content="紧急事件",
            npc_personality=sample_npc_config
        )

        assert is_important is True
        assert urgency == 0.8

    def test_assess_event_importance_no_response(self, sample_npc_config):
        """测试 NO 响应解析"""
        from npc_optimization.four_level_decisions import L2FastFilter

        mock_client = Mock()
        mock_client.call_model = Mock(return_value="NO, 紧急度: 2")

        l2 = L2FastFilter(mock_client)

        is_important, urgency = l2.assess_event_importance(
            event_content="普通事件",
            npc_personality=sample_npc_config
        )

        assert is_important is False
        assert urgency == 0.2

    def test_assess_event_importance_error_fallback(self, sample_npc_config):
        """测试错误时的默认返回"""
        from npc_optimization.four_level_decisions import L2FastFilter

        mock_client = Mock()
        mock_client.call_model = Mock(side_effect=Exception("API错误"))

        l2 = L2FastFilter(mock_client)

        is_important, urgency = l2.assess_event_importance(
            event_content="测试事件",
            npc_personality=sample_npc_config
        )

        # 错误时默认认为重要
        assert is_important is True
        assert urgency == 0.5


# ============================================================================
# L3StrategyPlanning 测试
# ============================================================================

class TestL3StrategyPlanning:
    """测试 L3 决策层 - 战略规划"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.four_level_decisions import L3StrategyPlanning
        assert L3StrategyPlanning is not None

    def test_generate_strategy_blueprint(self, mock_llm_client, sample_npc_config):
        """测试生成战略蓝图"""
        from npc_optimization.four_level_decisions import L3StrategyPlanning

        l3 = L3StrategyPlanning(mock_llm_client)

        blueprint = l3.generate_strategy_blueprint(
            event_content="铁匠铺着火了！",
            npc_profile=sample_npc_config,
            current_context={"primary_goal": "完成工作"}
        )

        assert "ultimate_goal" in blueprint
        assert "key_steps" in blueprint
        assert "predicted_risks" in blueprint
        assert "resource_needs" in blueprint

    def test_validate_blueprint(self, mock_llm_client):
        """测试蓝图验证"""
        from npc_optimization.four_level_decisions import L3StrategyPlanning

        l3 = L3StrategyPlanning(mock_llm_client)

        raw_blueprint = {
            "ultimate_goal": "救火",
            "key_steps": "单个步骤",  # 应该被转换为列表
            "predicted_risks": ["风险1"]
        }

        validated = l3._validate_blueprint(raw_blueprint)

        assert isinstance(validated["key_steps"], list)
        assert isinstance(validated["predicted_risks"], list)
        assert isinstance(validated["resource_needs"], list)

    def test_parse_text_blueprint(self, mock_llm_client):
        """测试文本格式蓝图解析"""
        from npc_optimization.four_level_decisions import L3StrategyPlanning

        l3 = L3StrategyPlanning(mock_llm_client)

        text_response = """
目标：救助火灾现场
步骤：
- 确认火势
- 呼叫帮助
- 灭火
风险：
- 可能受伤
资源：
- 需要水桶
"""

        blueprint = l3._parse_text_blueprint(text_response)

        assert blueprint["ultimate_goal"] != ""
        assert len(blueprint["key_steps"]) > 0

    def test_assess_complexity_from_content(self, mock_llm_client):
        """测试根据内容评估复杂度"""
        from npc_optimization.four_level_decisions import L3StrategyPlanning

        l3 = L3StrategyPlanning(mock_llm_client)

        # 简单任务
        simple_blueprint = {
            "key_steps": ["做一件事"],
            "predicted_risks": []
        }
        assert l3._assess_complexity_from_content(simple_blueprint) == "shallow"

        # 中等任务
        moderate_blueprint = {
            "key_steps": ["步骤1", "步骤2", "步骤3"],
            "predicted_risks": ["风险1"]
        }
        assert l3._assess_complexity_from_content(moderate_blueprint) == "moderate"

        # 复杂任务
        complex_blueprint = {
            "key_steps": ["步骤1", "步骤2", "步骤3", "步骤4"],
            "predicted_risks": ["风险1", "风险2", "风险3"]
        }
        assert l3._assess_complexity_from_content(complex_blueprint) == "deep"


# ============================================================================
# L4ToTReactReasoning 测试
# ============================================================================

class TestL4ToTReactReasoning:
    """测试 L4 决策层 - ToT 增强型 ReAct 推理"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.four_level_decisions import L4ToTReactReasoning
        assert L4ToTReactReasoning is not None

    def test_init(self, mock_llm_client, mock_tool_registry):
        """测试初始化"""
        from npc_optimization.four_level_decisions import L4ToTReactReasoning

        l4 = L4ToTReactReasoning(mock_llm_client, mock_tool_registry)

        assert l4.llm_client == mock_llm_client
        assert l4.tool_registry == mock_tool_registry
        assert l4.max_iterations == 5


class TestSimulatePath:
    """测试 _simulate_path 方法"""

    @pytest.fixture
    def l4_instance(self, mock_llm_client, mock_tool_registry):
        """创建 L4 实例"""
        from npc_optimization.four_level_decisions import L4ToTReactReasoning
        return L4ToTReactReasoning(mock_llm_client, mock_tool_registry)

    def test_simulate_path_basic(self, l4_instance, sample_npc_config, sample_npc_state):
        """测试基本路径模拟"""
        path = {
            "steps": ["观察情况", "采取行动"],
            "risk_level": "low"
        }

        result = l4_instance._simulate_path(path, sample_npc_config, sample_npc_state)

        assert "outcome" in result
        assert "success_prob" in result
        assert "risk_level" in result
        assert result["outcome"] in ["positive", "neutral", "negative"]
        assert 0.1 <= result["success_prob"] <= 0.95
        assert 0.0 <= result["risk_level"] <= 0.8

    def test_simulate_path_skill_match_bonus(self, l4_instance, sample_npc_config, sample_npc_state):
        """测试技能匹配加成"""
        # 铁匠处理火灾应该有加成
        path = {
            "steps": ["灭火", "救人"],
            "risk_level": "medium"
        }

        result = l4_instance._simulate_path(path, sample_npc_config, sample_npc_state)

        # 技能匹配应该提高成功率
        assert result["success_prob"] > 0.5

    def test_simulate_path_complexity_penalty(self, l4_instance, sample_npc_config, sample_npc_state):
        """测试复杂度惩罚"""
        # 简单路径
        simple_path = {"steps": ["行动"], "risk_level": "low"}

        # 复杂路径
        complex_path = {
            "steps": ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5"],
            "risk_level": "low"
        }

        simple_result = l4_instance._simulate_path(simple_path, sample_npc_config, sample_npc_state)
        complex_result = l4_instance._simulate_path(complex_path, sample_npc_config, sample_npc_state)

        # 复杂路径成功率应该更低
        assert simple_result["success_prob"] >= complex_result["success_prob"]

    def test_simulate_path_night_time_risk(self, l4_instance, sample_npc_config):
        """测试夜间风险增加"""
        path = {"steps": ["行动"], "risk_level": "low"}

        # 白天状态
        day_state = {"current_hour": 12, "weather": "晴"}

        # 夜间状态
        night_state = {"current_hour": 2, "weather": "晴"}

        day_result = l4_instance._simulate_path(path, sample_npc_config, day_state)
        night_result = l4_instance._simulate_path(path, sample_npc_config, night_state)

        # 夜间风险应该更高
        assert night_result["risk_level"] >= day_result["risk_level"]

    def test_simulate_path_bad_weather_risk(self, l4_instance, sample_npc_config):
        """测试恶劣天气风险增加"""
        path = {"steps": ["行动"], "risk_level": "low"}

        # 晴天
        clear_state = {"current_hour": 12, "weather": "晴"}

        # 暴风雨
        storm_state = {"current_hour": 12, "weather": "暴风雨"}

        clear_result = l4_instance._simulate_path(path, sample_npc_config, clear_state)
        storm_result = l4_instance._simulate_path(path, sample_npc_config, storm_state)

        # 暴风雨风险应该更高
        assert storm_result["risk_level"] > clear_result["risk_level"]

    def test_simulate_path_dangerous_event_risk(self, l4_instance, sample_npc_config):
        """测试危险事件风险增加"""
        path = {"steps": ["行动"], "risk_level": "low"}

        # 普通事件
        normal_state = {"current_hour": 12, "event_type": "普通"}

        # 火灾事件
        fire_state = {"current_hour": 12, "event_type": "火灾"}

        normal_result = l4_instance._simulate_path(path, sample_npc_config, normal_state)
        fire_result = l4_instance._simulate_path(path, sample_npc_config, fire_state)

        # 火灾事件风险应该更高
        assert fire_result["risk_level"] > normal_result["risk_level"]

    def test_simulate_path_positive_emotion_bonus(self, l4_instance, sample_npc_config):
        """测试正面情绪加成"""
        path = {"steps": ["行动"], "risk_level": "low"}

        # 自信情绪
        confident_state = {"current_hour": 12, "emotion": "自信", "weather": "晴"}

        # 焦虑情绪
        anxious_state = {"current_hour": 12, "emotion": "焦虑", "weather": "晴"}

        confident_result = l4_instance._simulate_path(path, sample_npc_config, confident_state)
        anxious_result = l4_instance._simulate_path(path, sample_npc_config, anxious_state)

        # 自信情绪成功率应该更高
        assert confident_result["success_prob"] > anxious_result["success_prob"]

    def test_simulate_path_history_bonus(self, l4_instance):
        """测试历史经验加成"""
        path = {"steps": ["帮助灭火"], "risk_level": "medium"}

        # 有成功灭火经验的 NPC
        experienced_npc = {
            "name": "铁匠",
            "profession": "铁匠",
            "skills": {"锻造": 85},
            "history": ["成功帮助灭火救了村民"]
        }

        # 无相关经验的 NPC
        inexperienced_npc = {
            "name": "新手",
            "profession": "农民",
            "skills": {"耕种": 50},
            "history": []
        }

        context = {"current_hour": 12, "weather": "晴"}

        exp_result = l4_instance._simulate_path(path, experienced_npc, context)
        inexp_result = l4_instance._simulate_path(path, inexperienced_npc, context)

        # 有经验的 NPC 成功率应该更高
        assert exp_result["success_prob"] >= inexp_result["success_prob"]

    def test_calculate_skill_match(self, l4_instance):
        """测试技能匹配计算"""
        path = {"steps": ["锻造武器", "修理装备"], "risk_level": "low"}

        npc_profile = {
            "profession": "铁匠",
            "skills": {"锻造": 85, "修理": 70}
        }

        bonus = l4_instance._calculate_skill_match(path, npc_profile)

        assert 0.0 <= bonus <= 0.3
        assert bonus > 0  # 铁匠锻造应该有匹配

    def test_assess_environment_risk(self, l4_instance):
        """测试环境风险评估"""
        # 安全环境
        safe_context = {
            "current_hour": 12,
            "weather": "晴",
            "event_type": "普通",
            "current_location": "村庄"
        }

        # 危险环境
        dangerous_context = {
            "current_hour": 2,
            "weather": "暴风雨",
            "event_type": "袭击",
            "current_location": "森林"
        }

        safe_risk = l4_instance._assess_environment_risk(safe_context)
        dangerous_risk = l4_instance._assess_environment_risk(dangerous_context)

        assert safe_risk < dangerous_risk
        assert 0.0 <= safe_risk <= 0.4
        assert 0.0 <= dangerous_risk <= 0.4

    def test_get_emotion_modifier(self, l4_instance):
        """测试情绪修正"""
        # 正面情绪
        positive_context = {"emotion": "自信", "mood": "良好"}
        positive_modifier = l4_instance._get_emotion_modifier(positive_context)
        assert positive_modifier > 0

        # 负面情绪
        negative_context = {"emotion": "恐惧", "mood": "紧张"}
        negative_modifier = l4_instance._get_emotion_modifier(negative_context)
        assert negative_modifier < 0

        # 确保在范围内
        assert -0.1 <= positive_modifier <= 0.1
        assert -0.1 <= negative_modifier <= 0.1


# ============================================================================
# FourLevelDecisionMaker 测试
# ============================================================================

class TestFourLevelDecisionMaker:
    """测试四级决策系统主控制器"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.four_level_decisions import FourLevelDecisionMaker
        assert FourLevelDecisionMaker is not None

    def test_init(self, sample_npc_config, mock_llm_client, mock_tool_registry):
        """测试初始化"""
        from npc_optimization.four_level_decisions import FourLevelDecisionMaker

        decision_maker = FourLevelDecisionMaker(
            npc_config=sample_npc_config,
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry
        )

        assert decision_maker.npc_config == sample_npc_config
        assert decision_maker.l1 is not None
        assert decision_maker.l2 is not None
        assert decision_maker.l3 is not None
        assert decision_maker.l4 is not None

    def test_make_decision_l1_routine(self, sample_npc_config, mock_llm_client, mock_tool_registry):
        """测试 L1 日常决策"""
        from npc_optimization.four_level_decisions import FourLevelDecisionMaker, DecisionLevel
        from core_types import NPCAction

        decision_maker = FourLevelDecisionMaker(
            npc_config=sample_npc_config,
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry
        )

        # 高疲劳应该触发 L1 强制睡眠
        state = {
            "current_activity": NPCAction.WORK,
            "current_hour": 23,
            "energy": 0.2,
            "hunger": 0.3,
            "fatigue": 0.99
        }

        result = decision_maker.make_decision(
            event=None,
            current_state=state,
            latest_impact_score=30
        )

        assert result["decision_level"] == DecisionLevel.L1_ROUTINE
        assert result["action"] == NPCAction.SLEEP

    def test_make_decision_no_event(self, sample_npc_config, mock_llm_client, mock_tool_registry):
        """测试无事件时的决策"""
        from npc_optimization.four_level_decisions import FourLevelDecisionMaker, DecisionLevel
        from core_types import NPCAction

        decision_maker = FourLevelDecisionMaker(
            npc_config=sample_npc_config,
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry
        )

        state = {
            "current_activity": None,
            "current_hour": 10,
            "energy": 0.8,
            "hunger": 0.3,
            "fatigue": 0.2
        }

        result = decision_maker.make_decision(
            event=None,
            current_state=state,
            latest_impact_score=0
        )

        assert result["decision_level"] == DecisionLevel.L1_ROUTINE
        assert isinstance(result["action"], NPCAction)

    def test_make_decision_l2_filter(self, sample_npc_config, mock_tool_registry):
        """测试 L2 过滤不重要事件"""
        from npc_optimization.four_level_decisions import FourLevelDecisionMaker, DecisionLevel
        from core_types import NPCAction

        # 创建返回 "NO" 的 mock client
        mock_client = Mock()
        mock_client.call_model = Mock(return_value="NO, 紧急度: 2")

        decision_maker = FourLevelDecisionMaker(
            npc_config=sample_npc_config,
            llm_client=mock_client,
            tool_registry=mock_tool_registry
        )

        state = {
            "current_activity": NPCAction.WORK,
            "current_hour": 10,
            "energy": 0.8,
            "hunger": 0.3,
            "fatigue": 0.2
        }

        event = {"content": "一只野兔跑过"}

        result = decision_maker.make_decision(
            event=event,
            current_state=state,
            latest_impact_score=60  # 超过工作惯性值
        )

        assert result["decision_level"] == DecisionLevel.L2_FILTER

    def test_get_decision_stats(self, sample_npc_config, mock_llm_client, mock_tool_registry):
        """测试获取决策统计"""
        from npc_optimization.four_level_decisions import FourLevelDecisionMaker

        decision_maker = FourLevelDecisionMaker(
            npc_config=sample_npc_config,
            llm_client=mock_llm_client,
            tool_registry=mock_tool_registry
        )

        stats = decision_maker.get_decision_stats()

        assert "l1_decisions" in stats
        assert "l2_decisions" in stats
        assert "l3_decisions" in stats
        assert "l4_decisions" in stats


# ============================================================================
# map_step_to_action 测试
# ============================================================================

class TestMapStepToAction:
    """测试步骤到动作的映射"""

    def test_import_function(self):
        """测试函数可以导入"""
        from npc_optimization.four_level_decisions import map_step_to_action
        assert map_step_to_action is not None

    def test_notify_actions(self):
        """测试通知类动作映射"""
        from npc_optimization.four_level_decisions import map_step_to_action
        from core_types import NPCAction

        notify_steps = ["通知村长", "告诉大家", "呼叫帮助", "传达消息"]
        for step in notify_steps:
            action = map_step_to_action(step)
            assert action == NPCAction.SOCIALIZE

    def test_help_actions(self):
        """测试帮助类动作映射"""
        from npc_optimization.four_level_decisions import map_step_to_action
        from core_types import NPCAction

        help_steps = ["帮助灭火", "救援受困者", "协助撤离"]
        for step in help_steps:
            action = map_step_to_action(step)
            assert action == NPCAction.HELP_OTHERS

    def test_observe_actions(self):
        """测试观察类动作映射"""
        from npc_optimization.four_level_decisions import map_step_to_action
        from core_types import NPCAction

        observe_steps = ["确认情况", "观察火势", "查看现场"]
        for step in observe_steps:
            action = map_step_to_action(step)
            assert action == NPCAction.OBSERVE

    def test_travel_actions(self):
        """测试移动类动作映射"""
        from npc_optimization.four_level_decisions import map_step_to_action
        from core_types import NPCAction

        travel_steps = ["前往现场", "赶到铁匠铺", "跑向村口"]
        for step in travel_steps:
            action = map_step_to_action(step)
            assert action == NPCAction.TRAVEL

    def test_default_action(self):
        """测试默认动作"""
        from npc_optimization.four_level_decisions import map_step_to_action
        from core_types import NPCAction

        result = map_step_to_action("未知的动作描述xyz")
        assert result == NPCAction.OBSERVE

    def test_npcaction_input(self):
        """测试 NPCAction 输入"""
        from npc_optimization.four_level_decisions import map_step_to_action
        from core_types import NPCAction

        result = map_step_to_action(NPCAction.WORK)
        assert result == NPCAction.WORK


# ============================================================================
# 枚举类测试
# ============================================================================

class TestEnums:
    """测试枚举类"""

    def test_decision_level_enum(self):
        """测试 DecisionLevel 枚举"""
        from npc_optimization.four_level_decisions import DecisionLevel

        assert DecisionLevel.L1_ROUTINE.value == 1
        assert DecisionLevel.L2_FILTER.value == 2
        assert DecisionLevel.L3_STRATEGY.value == 3
        assert DecisionLevel.L4_DEEP_REASONING.value == 4

    def test_impact_classification_enum(self):
        """测试 ImpactClassification 枚举"""
        from npc_optimization.four_level_decisions import ImpactClassification

        assert ImpactClassification.TRIVIAL.value == 0
        assert ImpactClassification.MINOR.value == 1
        assert ImpactClassification.MODERATE.value == 2
        assert ImpactClassification.SIGNIFICANT.value == 3
        assert ImpactClassification.CRITICAL.value == 4
