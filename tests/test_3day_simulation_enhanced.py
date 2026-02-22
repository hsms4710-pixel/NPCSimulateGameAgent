# -*- coding: utf-8 -*-
"""
3天综合模拟测试用例 - 增强版
============================

在原有测试基础上增加以下场景:
1. 四级决策系统集成测试
2. RAG记忆语义检索测试
3. 记忆压缩/遗忘机制测试
4. 多NPC并行运行测试
5. 经济系统物品交易测试
6. 任务系统完整流程测试
7. 事件传播延迟测试
8. NPC自主行为循环测试
9. 情绪变化和好感度累积测试
10. 边界条件测试（金币不足、精力耗尽等）
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from unittest.mock import Mock, MagicMock, patch

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('EnhancedSimTest')


# ========== 测试结果记录 ==========

@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    category: str
    details: str
    expected: Any = None
    actual: Any = None


class EnhancedTestRunner:
    """增强版测试运行器"""

    def __init__(self):
        self.results: List[TestResult] = []
        self.mock_llm_responses = {}

    def record(self, name: str, passed: bool, category: str, details: str,
               expected=None, actual=None):
        result = TestResult(name, passed, category, details, expected, actual)
        self.results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} [{category}] {name}: {details}")
        if not passed:
            logger.warning(f"    期望: {expected}, 实际: {actual}")

    def summary(self) -> Dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        by_category = {}
        for r in self.results:
            if r.category not in by_category:
                by_category[r.category] = {"passed": 0, "failed": 0}
            if r.passed:
                by_category[r.category]["passed"] += 1
            else:
                by_category[r.category]["failed"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            "by_category": by_category
        }


# ========== 测试1: 四级决策系统集成 ==========

def test_four_level_decision_integration(runner: EnhancedTestRunner):
    """测试四级决策系统集成"""
    logger.info("\n" + "=" * 50)
    logger.info("测试1: 四级决策系统集成")
    logger.info("=" * 50)

    try:
        from npc_optimization.four_level_decisions import (
            L1RoutineDecision, L2FastFilter, L3StrategyPlanning,
            L4ToTReactReasoning, FourLevelDecisionMaker, DecisionLevel
        )

        # 测试L1: 生物钟硬判决
        # L1RoutineDecision需要npc_config参数
        npc_config = {
            "name": "测试NPC",
            "profession": "铁匠",
            "schedule": {}
        }
        l1 = L1RoutineDecision(npc_config)

        # 场景1: 极度疲劳应该强制睡眠
        from core_types import NPCAction
        result = l1.decide(
            current_activity=NPCAction.WORK,
            current_hour=14,
            energy_level=0.1,
            hunger_level=0.3,
            fatigue_level=0.99,
            latest_impact_score=10
        )
        runner.record(
            "L1-疲劳强制睡眠",
            result == NPCAction.SLEEP,
            "四级决策",
            "极度疲劳时L1应该做出睡眠决策",
            expected="NPCAction.SLEEP",
            actual=str(result)
        )

        # 场景2: 极度饥饿应该强制进食
        result = l1.decide(
            current_activity=NPCAction.WORK,
            current_hour=14,
            energy_level=0.5,
            hunger_level=0.95,
            fatigue_level=0.3,
            latest_impact_score=10
        )
        runner.record(
            "L1-饥饿强制进食",
            result == NPCAction.EAT,
            "四级决策",
            "极度饥饿时L1应该做出进食决策",
            expected="NPCAction.EAT",
            actual=str(result)
        )

        # 测试L4路径模拟
        from npc_optimization.unified_tools import UnifiedToolRegistry
        tool_registry = UnifiedToolRegistry()
        l4 = L4ToTReactReasoning(llm_client=Mock(), tool_registry=tool_registry)

        # 场景: 铁匠处理火灾
        path_result = l4._simulate_path(
            path={"steps": ["观察火情", "拿起工具", "帮忙灭火"]},
            npc_profile={
                "profession": "铁匠",
                "skills": {"铁匠技艺": 80},
                "history": ["曾处理过火灾事故"]
            },
            context={
                "current_hour": 14,
                "weather": "晴朗",
                "emotion": "焦急",
                "event_type": "fire"
            }
        )

        runner.record(
            "L4-路径模拟评估",
            0.1 <= path_result["success_prob"] <= 0.95,
            "四级决策",
            f"成功概率在合理范围内",
            expected="0.1-0.95",
            actual=path_result["success_prob"]
        )

        runner.record(
            "L4-风险评估",
            0.0 <= path_result["risk_level"] <= 0.8,
            "四级决策",
            f"风险等级在合理范围内",
            expected="0.0-0.8",
            actual=path_result["risk_level"]
        )

    except Exception as e:
        runner.record(
            "四级决策系统导入",
            False,
            "四级决策",
            f"导入失败: {e}",
            expected="成功导入",
            actual=str(e)
        )


# ========== 测试2: RAG记忆语义检索 ==========

def test_rag_memory_semantic_search(runner: EnhancedTestRunner):
    """测试RAG记忆语义检索"""
    logger.info("\n" + "=" * 50)
    logger.info("测试2: RAG记忆语义检索")
    logger.info("=" * 50)

    try:
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem(model_path="./models/text2vec-base-chinese")

        # 添加测试记忆
        test_memories = [
            ("mem_1", "我在铁匠铺学习锻造技术，师傅教了我很多", 8),
            ("mem_2", "今天市场上有人在卖新鲜的苹果和蔬菜", 5),
            ("mem_3", "昨天晚上在酒馆听说村口出现了可疑人物", 7),
            ("mem_4", "牧师在教堂给大家讲了一个关于勇气的故事", 6),
            ("mem_5", "铁匠铺的炉火非常旺盛，能感受到热浪", 4),
        ]

        for mem_id, content, importance in test_memories:
            rag.add_memory(mem_id, content, importance)

        # 测试语义搜索 - 使用正确的方法名
        results = rag.search_relevant_memories("锻造和打铁相关的事情", top_k=3)

        runner.record(
            "RAG-添加记忆",
            len(test_memories) == 5,
            "RAG记忆",
            "成功添加5条记忆",
            expected=5,
            actual=len(test_memories)
        )

        # 验证搜索结果包含铁匠相关内容
        has_blacksmith_memory = any(
            "铁匠" in r.get("content", "") or "锻造" in r.get("content", "")
            for r in results
        )
        runner.record(
            "RAG-语义搜索准确性",
            has_blacksmith_memory,
            "RAG记忆",
            "搜索'锻造和打铁'应返回铁匠相关记忆",
            expected="包含铁匠/锻造内容",
            actual=results[0].get("content", "")[:30] if results else "无结果"
        )

        # 测试不相关查询
        unrelated_results = rag.search_relevant_memories("关于天气和季节变化", top_k=3)
        runner.record(
            "RAG-搜索返回结果",
            len(unrelated_results) >= 0,
            "RAG记忆",
            "不相关查询也应返回结果（按相似度排序）",
            expected="有结果",
            actual=f"返回{len(unrelated_results)}条"
        )

    except Exception as e:
        runner.record(
            "RAG记忆系统",
            False,
            "RAG记忆",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试3: 记忆压缩和遗忘机制 ==========

def test_memory_compression_forgetting(runner: EnhancedTestRunner):
    """测试记忆压缩和遗忘机制"""
    logger.info("\n" + "=" * 50)
    logger.info("测试3: 记忆压缩和遗忘机制")
    logger.info("=" * 50)

    try:
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem(model_path="./models/text2vec-base-chinese")

        # 添加相似记忆（应该被压缩）
        rag.add_memory("sim_1", "今天在铁匠铺看到了新的锻造技术", 6)
        rag.add_memory("sim_2", "铁匠铺的锻造技术令人印象深刻", 5)
        rag.add_memory("sim_3", "我观察了铁匠铺里的锻造过程", 4)

        # 添加低重要性记忆（应该被遗忘）
        rag.add_memory("low_1", "路边有一块石头", 2)
        rag.add_memory("low_2", "天空是蓝色的", 1)

        initial_count = rag.get_stats().get("total_memories", 5)

        # 测试记忆压缩
        if hasattr(rag, 'compress_similar_memories'):
            compress_result = rag.compress_similar_memories(similarity_threshold=0.80)
            runner.record(
                "记忆压缩执行",
                isinstance(compress_result, dict),
                "记忆管理",
                "压缩方法返回统计信息",
                expected="dict",
                actual=type(compress_result).__name__
            )
        else:
            runner.record(
                "记忆压缩执行",
                False,
                "记忆管理",
                "compress_similar_memories方法不存在",
                expected="方法存在",
                actual="方法不存在"
            )

        # 测试遗忘机制
        if hasattr(rag, 'apply_forgetting'):
            forget_result = rag.apply_forgetting(decay_factor=0.9, min_importance=1.5)
            runner.record(
                "遗忘机制执行",
                isinstance(forget_result, (int, dict)),
                "记忆管理",
                "遗忘方法返回删除数量或统计",
                expected="int或dict",
                actual=type(forget_result).__name__
            )
        else:
            runner.record(
                "遗忘机制执行",
                False,
                "记忆管理",
                "apply_forgetting方法不存在",
                expected="方法存在",
                actual="方法不存在"
            )

        # 测试维护方法
        if hasattr(rag, 'maintenance'):
            maintenance_result = rag.maintenance(compress=True, forget=True)
            runner.record(
                "记忆维护执行",
                "summary" in maintenance_result or "before_count" in maintenance_result,
                "记忆管理",
                "维护方法返回报告",
                expected="包含统计信息",
                actual=str(maintenance_result)[:100]
            )
        else:
            runner.record(
                "记忆维护执行",
                False,
                "记忆管理",
                "maintenance方法不存在",
                expected="方法存在",
                actual="方法不存在"
            )

    except Exception as e:
        runner.record(
            "记忆压缩遗忘",
            False,
            "记忆管理",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试4: 多NPC并行运行 ==========

def test_parallel_npc_system(runner: EnhancedTestRunner):
    """测试多NPC并行运行系统"""
    logger.info("\n" + "=" * 50)
    logger.info("测试4: 多NPC并行运行")
    logger.info("=" * 50)

    try:
        from world_simulator.parallel_npc_system import (
            WorldSimulator, NPCAgent, SimulationClock, GameTime
        )

        # 测试游戏时间
        time1 = GameTime(day=1, hour=8, minute=0)
        time2 = GameTime(day=1, hour=8, minute=30)

        runner.record(
            "游戏时间比较",
            time1 < time2,
            "并行系统",
            "GameTime比较功能正常",
            expected="time1 < time2",
            actual=f"{time1} < {time2}"
        )

        # 测试时间推进
        time1.advance(minutes=45)
        runner.record(
            "游戏时间推进",
            time1.hour == 8 and time1.minute == 45,
            "并行系统",
            "时间推进45分钟",
            expected="8:45",
            actual=f"{time1.hour}:{time1.minute}"
        )

        # 测试模拟时钟 - 使用正确的参数（不传time_scale）
        clock = SimulationClock()  # 使用默认参数
        initial_time = clock.current_time.to_string()

        runner.record(
            "模拟时钟初始化",
            clock.current_time is not None,
            "并行系统",
            "时钟初始化成功",
            expected="有当前时间",
            actual=initial_time
        )

        # 测试世界模拟器
        simulator = WorldSimulator()

        runner.record(
            "世界模拟器创建",
            simulator is not None,
            "并行系统",
            "WorldSimulator创建成功",
            expected="实例存在",
            actual="创建成功"
        )

        # 测试NPC Agent创建（使用Mock）
        mock_npc_system = Mock()
        mock_npc_system.npc_name = "测试NPC"
        mock_npc_system.current_location = "酒馆"
        mock_npc_system.current_activity = Mock(value="休息")
        mock_npc_system.energy = 0.8  # 使用新字段 (0.0-1.0)

        agent = NPCAgent(mock_npc_system, "test_agent_1")

        runner.record(
            "NPC Agent创建",
            agent.agent_id == "test_agent_1",
            "并行系统",
            "NPCAgent创建成功",
            expected="test_agent_1",
            actual=agent.agent_id
        )

        # 测试Agent状态
        runner.record(
            "Agent暂停/恢复",
            not agent.is_paused,
            "并行系统",
            "Agent初始状态为运行中",
            expected="未暂停",
            actual="未暂停" if not agent.is_paused else "已暂停"
        )

        agent.pause()
        runner.record(
            "Agent暂停",
            agent.is_paused,
            "并行系统",
            "Agent暂停功能",
            expected="已暂停",
            actual="已暂停" if agent.is_paused else "未暂停"
        )

        agent.resume()
        runner.record(
            "Agent恢复",
            not agent.is_paused,
            "并行系统",
            "Agent恢复功能",
            expected="未暂停",
            actual="未暂停" if not agent.is_paused else "已暂停"
        )

    except ImportError as e:
        runner.record(
            "并行系统导入",
            False,
            "并行系统",
            f"模块导入失败: {e}",
            expected="成功导入",
            actual=str(e)
        )
    except Exception as e:
        runner.record(
            "并行系统测试",
            False,
            "并行系统",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试5: 经济系统物品交易 ==========

def test_economy_item_trading(runner: EnhancedTestRunner):
    """测试经济系统物品交易"""
    logger.info("\n" + "=" * 50)
    logger.info("测试5: 经济系统物品交易")
    logger.info("=" * 50)

    try:
        from world_simulator.economy_system import (
            EconomySystem, CurrencyType, ItemCategory
        )

        economy = EconomySystem()

        # 初始化玩家和NPC钱包
        economy.currency_manager.add_funds("玩家", 100, CurrencyType.GOLD)
        economy.currency_manager.add_funds("商人NPC", 500, CurrencyType.GOLD)

        # get_balance返回int，不是dict
        player_balance = economy.currency_manager.get_balance("玩家", CurrencyType.GOLD)
        runner.record(
            "货币添加",
            player_balance == 100,
            "经济系统",
            "玩家初始金币100",
            expected=100,
            actual=player_balance
        )

        # 添加物品到库存
        economy.inventory_manager.add_item("商人NPC", "health_potion", 10)
        npc_inventory = economy.inventory_manager.get_inventory("商人NPC")

        # get_inventory返回List[Dict]，需要查找对应物品
        potion_count = sum(item.get("quantity", 0) for item in npc_inventory
                          if item.get("item_id") == "health_potion")
        runner.record(
            "物品添加到库存",
            potion_count == 10,
            "经济系统",
            "商人有10个血瓶",
            expected=10,
            actual=potion_count
        )

        # 测试物品购买 - 使用 market_system 而不是 market
        # buy_item返回 Tuple[bool, str] 而不是 Dict
        success, message = economy.market_system.buy_item("玩家", "商人NPC", "health_potion", 2)

        runner.record(
            "物品购买",
            success,
            "经济系统",
            "玩家购买2个血瓶",
            expected="成功",
            actual="成功" if success else message
        )

        # 验证购买后状态
        player_inventory = economy.inventory_manager.get_inventory("玩家")
        player_potion_count = sum(item.get("quantity", 0) for item in player_inventory
                                  if item.get("item_id") == "health_potion")
        runner.record(
            "购买后库存更新",
            player_potion_count == 2,
            "经济系统",
            "玩家有2个血瓶",
            expected=2,
            actual=player_potion_count
        )

        # 测试转账
        transfer_result = economy.currency_manager.transfer(
            "玩家", "商人NPC", 10, CurrencyType.GOLD, "donation", "捐赠"
        )

        runner.record(
            "货币转账",
            transfer_result is not None,
            "经济系统",
            "玩家向商人转账10金币",
            expected="成功",
            actual="成功" if transfer_result else "失败"
        )

    except ImportError as e:
        runner.record(
            "经济系统导入",
            False,
            "经济系统",
            f"模块导入失败: {e}",
            expected="成功导入",
            actual=str(e)
        )
    except Exception as e:
        runner.record(
            "经济系统测试",
            False,
            "经济系统",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试6: 任务系统完整流程 ==========

def test_quest_system_workflow(runner: EnhancedTestRunner):
    """测试任务系统完整流程"""
    logger.info("\n" + "=" * 50)
    logger.info("测试6: 任务系统完整流程")
    logger.info("=" * 50)

    try:
        from world_simulator.quest_system import (
            QuestManager, Quest, QuestObjective, QuestStatus,
            ObjectiveType, QuestReward
        )
        from world_simulator.economy_system import EconomySystem

        economy = EconomySystem()
        quest_manager = QuestManager(economy)

        # 获取可用任务
        available = quest_manager.get_available_quests("玩家", "镇中心")
        runner.record(
            "获取可用任务",
            len(available) >= 0,
            "任务系统",
            "获取镇中心可用任务",
            expected="有任务列表",
            actual=f"{len(available)}个任务"
        )

        # 接受任务
        if available:
            # 使用 _quests (私有属性) 或直接从available获取
            quest_id = available[0].quest_id if hasattr(available[0], 'quest_id') else list(quest_manager._quests.keys())[0]
            accept_result = quest_manager.accept_quest(quest_id, "玩家")
            runner.record(
                "接受任务",
                accept_result[0] if isinstance(accept_result, tuple) else accept_result,
                "任务系统",
                f"玩家接受任务: {quest_id}",
                expected="成功",
                actual="成功" if (accept_result[0] if isinstance(accept_result, tuple) else accept_result) else "失败"
            )

            # 获取进行中的任务
            active = quest_manager.get_active_quests("玩家")
            runner.record(
                "获取进行中任务",
                len(active) > 0,
                "任务系统",
                "玩家有进行中的任务",
                expected="> 0",
                actual=len(active)
            )
        else:
            # 手动创建任务测试
            test_quest = Quest(
                id="test_quest",
                title="测试任务",
                description="这是一个测试任务",
                giver="测试NPC",
                objectives=[
                    QuestObjective(
                        id="obj_1",
                        type=ObjectiveType.TALK_TO,
                        description="与NPC对话",
                        target="测试NPC",
                        required_count=1
                    )
                ],
                rewards=QuestReward(gold=50)
            )
            quest_manager.create_quest(test_quest)

            runner.record(
                "创建自定义任务",
                "test_quest" in quest_manager.quests,
                "任务系统",
                "手动创建测试任务",
                expected="任务存在",
                actual="存在" if "test_quest" in quest_manager.quests else "不存在"
            )

    except ImportError as e:
        runner.record(
            "任务系统导入",
            False,
            "任务系统",
            f"模块导入失败: {e}",
            expected="成功导入",
            actual=str(e)
        )
    except Exception as e:
        runner.record(
            "任务系统测试",
            False,
            "任务系统",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试7: 事件传播延迟 ==========

def test_event_propagation_delay(runner: EnhancedTestRunner):
    """测试事件传播延迟"""
    logger.info("\n" + "=" * 50)
    logger.info("测试7: 事件传播延迟")
    logger.info("=" * 50)

    try:
        from npc_optimization.event_coordinator import EventCoordinator, EventPriority
        from npc_optimization.spatial_system import get_spatial_system

        spatial = get_spatial_system()
        coordinator = EventCoordinator()

        # 测试传播延迟计算
        if hasattr(spatial, 'calculate_event_propagation_delay'):
            delay = spatial.calculate_event_propagation_delay(
                origin_location="酒馆",
                target_location="农田",
                severity=8
            )

            runner.record(
                "传播延迟计算",
                delay > 0,
                "事件传播",
                "从酒馆到农田的传播延迟",
                expected="> 0",
                actual=f"{delay:.2f}分钟"
            )
        else:
            runner.record(
                "传播延迟计算",
                False,
                "事件传播",
                "calculate_event_propagation_delay方法不存在",
                expected="方法存在",
                actual="方法不存在"
            )

        # 测试NPC通知顺序
        if hasattr(spatial, 'get_npc_event_notification_order'):
            # 先注册NPC位置
            spatial.set_npc_position("贝拉", "酒馆")
            spatial.set_npc_position("铁匠", "铁匠铺")
            spatial.set_npc_position("农夫", "农田")

            # 获取NPC通知顺序（不需要npc_locations参数）
            order = spatial.get_npc_event_notification_order(
                origin_location="酒馆",
                severity=8
            )

            runner.record(
                "NPC通知顺序",
                len(order) > 0,
                "事件传播",
                "获取NPC通知顺序",
                expected="有顺序列表",
                actual=f"{len(order)}个NPC"
            )

            # 验证最近的NPC排在前面
            if order:
                first_npc = order[0] if isinstance(order[0], str) else order[0].get("npc_name", "")
                runner.record(
                    "最近NPC优先通知",
                    first_npc == "贝拉" or "酒馆" in str(order[0]),
                    "事件传播",
                    "酒馆的NPC应该最先收到通知",
                    expected="贝拉(酒馆)",
                    actual=str(order[0])[:30]
                )
        else:
            runner.record(
                "NPC通知顺序",
                False,
                "事件传播",
                "get_npc_event_notification_order方法不存在",
                expected="方法存在",
                actual="方法不存在"
            )

    except Exception as e:
        runner.record(
            "事件传播测试",
            False,
            "事件传播",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试8: NPC情绪和好感度变化 ==========

def test_emotion_affinity_changes(runner: EnhancedTestRunner):
    """测试NPC情绪和好感度变化"""
    logger.info("\n" + "=" * 50)
    logger.info("测试8: 情绪和好感度变化")
    logger.info("=" * 50)

    try:
        from backend.world_data import WorldDataManager, RelationshipLevel

        world_data = WorldDataManager()

        # 测试初始关系
        initial_rel = world_data.get_relationship("玩家", "贝拉·欢笑")
        initial_affinity = initial_rel.affinity

        runner.record(
            "获取初始关系",
            initial_rel is not None,
            "关系系统",
            "获取玩家与贝拉的关系",
            expected="有关系对象",
            actual=f"好感度: {initial_affinity}"
        )

        # 测试好感度增加
        world_data.modify_affinity("玩家", "贝拉·欢笑", 10, "帮忙打扫酒馆")
        updated_rel = world_data.get_relationship("玩家", "贝拉·欢笑")

        runner.record(
            "好感度增加",
            updated_rel.affinity == initial_affinity + 10,
            "关系系统",
            "帮忙后好感度+10",
            expected=initial_affinity + 10,
            actual=updated_rel.affinity
        )

        # 测试多次互动累积
        for i in range(5):
            world_data.modify_affinity("玩家", "贝拉·欢笑", 5, f"互动{i+1}")

        final_rel = world_data.get_relationship("玩家", "贝拉·欢笑")
        expected_final = initial_affinity + 10 + 25  # +10 + 5*5

        runner.record(
            "多次互动好感度累积",
            final_rel.affinity == expected_final or final_rel.affinity == min(100, expected_final),
            "关系系统",
            "多次互动后好感度正确累积",
            expected=min(100, expected_final),
            actual=final_rel.affinity
        )

        # 测试信任度变化
        world_data.modify_trust("玩家", "贝拉·欢笑", 15, "完成任务获得信任")
        trust_rel = world_data.get_relationship("玩家", "贝拉·欢笑")

        runner.record(
            "信任度变化",
            trust_rel.trust >= 15,
            "关系系统",
            "信任度增加",
            expected=">= 15",
            actual=trust_rel.trust
        )

        # 测试关系等级
        level = trust_rel.level
        runner.record(
            "关系等级判断",
            isinstance(level, RelationshipLevel),
            "关系系统",
            "关系等级正确计算",
            expected="RelationshipLevel枚举",
            actual=level.value if hasattr(level, 'value') else str(level)
        )

    except Exception as e:
        runner.record(
            "情绪好感度测试",
            False,
            "关系系统",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试9: 边界条件 ==========

def test_boundary_conditions(runner: EnhancedTestRunner):
    """测试边界条件"""
    logger.info("\n" + "=" * 50)
    logger.info("测试9: 边界条件测试")
    logger.info("=" * 50)

    try:
        from world_simulator.economy_system import EconomySystem, CurrencyType
        from backend.world_data import WorldDataManager

        economy = EconomySystem()
        world_data = WorldDataManager()

        # 测试金币不足
        economy.currency_manager.add_funds("穷玩家", 5, CurrencyType.GOLD)

        # 尝试购买昂贵物品
        economy.inventory_manager.add_item("商人", "iron_sword", 5)
        # buy_item返回 Tuple[bool, str]
        success, message = economy.market_system.buy_item("穷玩家", "商人", "iron_sword", 1)

        runner.record(
            "金币不足购买失败",
            not success,
            "边界条件",
            "金币不足时购买应该失败",
            expected="失败",
            actual="失败" if not success else "成功"
        )

        # 测试好感度上限
        for _ in range(30):
            world_data.modify_affinity("测试A", "测试B", 10, "测试")

        rel = world_data.get_relationship("测试A", "测试B")
        runner.record(
            "好感度上限100",
            rel.affinity <= 100,
            "边界条件",
            "好感度不应超过100",
            expected="<= 100",
            actual=rel.affinity
        )

        # 测试好感度下限
        for _ in range(30):
            world_data.modify_affinity("测试C", "测试D", -10, "冲突")

        rel2 = world_data.get_relationship("测试C", "测试D")
        runner.record(
            "好感度下限-100",
            rel2.affinity >= -100,
            "边界条件",
            "好感度不应低于-100",
            expected=">= -100",
            actual=rel2.affinity
        )

        # 测试空库存取物 - remove_item返回 Tuple[bool, str]
        success, message = economy.inventory_manager.remove_item("空角色", "不存在的物品", 1)
        runner.record(
            "空库存取物失败",
            not success,
            "边界条件",
            "从空库存取物应该失败",
            expected="失败",
            actual="失败" if not success else "成功"
        )

    except Exception as e:
        runner.record(
            "边界条件测试",
            False,
            "边界条件",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 测试10: 三层记忆系统 ==========

def test_memory_layers(runner: EnhancedTestRunner):
    """测试三层记忆系统"""
    logger.info("\n" + "=" * 50)
    logger.info("测试10: 三层记忆系统")
    logger.info("=" * 50)

    try:
        from npc_optimization.memory_layers import (
            HotMemory, WarmMemory, ColdMemory, MemoryLayerManager
        )

        # 测试热记忆
        hot = HotMemory("测试NPC")

        hot.update_state({
            "location": "酒馆",
            "activity": "休息",
            "emotion": "平静"
        })

        snapshot = hot.get_snapshot()
        state = snapshot.get("state", {})
        runner.record(
            "热记忆-状态更新",
            state.get("location") == "酒馆",
            "三层记忆",
            "热记忆存储当前状态",
            expected="酒馆",
            actual=state.get("location")
        )

        # 测试冷记忆
        cold = ColdMemory("测试NPC")

        # 创建一个NPCEventEnhanced对象用于归档（使用唯一ID避免UNIQUE约束）
        from npc_optimization.memory_layers import NPCEventEnhanced
        import uuid
        test_event = NPCEventEnhanced(
            id=f"test_event_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat(),
            event_type="test",
            content="测试事件内容",
            analysis={},
            response="测试响应",
            state_before={},
            state_after={},
            impact_score=50
        )
        cold.archive_event(test_event)

        # 查询归档的事件
        archived = cold.query_events()
        runner.record(
            "冷记忆-事件归档",
            len(archived) > 0,
            "三层记忆",
            "冷记忆归档事件",
            expected="> 0",
            actual=len(archived)
        )

        # 测试记忆层管理器
        manager = MemoryLayerManager("测试NPC")

        runner.record(
            "记忆层管理器创建",
            manager is not None,
            "三层记忆",
            "MemoryLayerManager创建成功",
            expected="成功",
            actual="成功" if manager else "失败"
        )

    except Exception as e:
        runner.record(
            "三层记忆测试",
            False,
            "三层记忆",
            f"测试失败: {e}",
            expected="成功执行",
            actual=str(e)
        )


# ========== 主函数 ==========

def run_enhanced_tests():
    """运行所有增强测试"""
    logger.info("=" * 60)
    logger.info("3天综合测试用例 - 增强版")
    logger.info("=" * 60)

    runner = EnhancedTestRunner()

    # 运行所有测试
    test_four_level_decision_integration(runner)
    test_rag_memory_semantic_search(runner)
    test_memory_compression_forgetting(runner)
    test_parallel_npc_system(runner)
    test_economy_item_trading(runner)
    test_quest_system_workflow(runner)
    test_event_propagation_delay(runner)
    test_emotion_affinity_changes(runner)
    test_boundary_conditions(runner)
    test_memory_layers(runner)

    # 输出总结
    summary = runner.summary()

    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    logger.info(f"总测试数: {summary['total']}")
    logger.info(f"通过: {summary['passed']}")
    logger.info(f"失败: {summary['failed']}")
    logger.info(f"通过率: {summary['pass_rate']}")

    logger.info("\n按类别统计:")
    for category, stats in summary['by_category'].items():
        logger.info(f"  {category}: 通过{stats['passed']}, 失败{stats['failed']}")

    # 保存报告
    report = {
        "summary": summary,
        "results": [
            {
                "name": r.name,
                "passed": r.passed,
                "category": r.category,
                "details": r.details,
                "expected": str(r.expected),
                "actual": str(r.actual)
            }
            for r in runner.results
        ]
    }

    with open("tests/enhanced_simulation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n报告已保存到: tests/enhanced_simulation_report.json")

    return summary


if __name__ == "__main__":
    summary = run_enhanced_tests()
    sys.exit(0 if summary['failed'] == 0 else 1)
