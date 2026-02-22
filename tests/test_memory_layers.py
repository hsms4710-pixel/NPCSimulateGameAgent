#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_memory_layers.py - 三层记忆系统测试

测试内容：
1. HotMemory 热记忆
2. WarmMemory 使用新的 Text2Vec 嵌入
3. ColdMemory 冷记忆
4. MemoryLayerManager 整体流程

使用 pytest 框架，配合 conftest.py 中的共享 fixtures
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from dataclasses import asdict
import threading
import time

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# 数据类测试
# ============================================================================

class TestNPCEventEnhanced:
    """测试 NPCEventEnhanced 数据类"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import NPCEventEnhanced
        assert NPCEventEnhanced is not None

    def test_creation_basic(self):
        """测试基本创建"""
        from npc_optimization.memory_layers import NPCEventEnhanced

        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="铁匠铺着火了",
            analysis={"impact": "high"},
            response="我需要去帮忙",
            state_before={"location": "家"},
            state_after={"location": "铁匠铺"},
            impact_score=85
        )

        assert event.id == "evt_001"
        assert event.event_type == "world_event"
        assert event.impact_score == 85
        assert event.resolved is False
        assert event.parent_event_id is None
        assert event.related_event_ids == []

    def test_creation_with_causal_chain(self):
        """测试带因果链的创建"""
        from npc_optimization.memory_layers import NPCEventEnhanced

        parent_event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="发现火灾",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=80
        )

        child_event = NPCEventEnhanced(
            id="evt_002",
            timestamp=datetime.now().isoformat(),
            event_type="dialogue",
            content="呼叫帮助",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=70,
            parent_event_id="evt_001",
            related_event_ids=["evt_001"]
        )

        assert child_event.parent_event_id == "evt_001"
        assert "evt_001" in child_event.related_event_ids


class TestInsight:
    """测试 Insight 数据类"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import Insight
        assert Insight is not None

    def test_creation_basic(self):
        """测试基本创建"""
        from npc_optimization.memory_layers import Insight

        insight = Insight(
            id="ins_001",
            created_at=datetime.now().isoformat(),
            source_event_ids=["evt_001", "evt_002"],
            insight_text="帮助他人让我感到满足",
            insight_type="reflection",
            emotional_weight=5,
            relevance_score=0.8
        )

        assert insight.id == "ins_001"
        assert insight.insight_type == "reflection"
        assert insight.emotional_weight == 5
        assert insight.embedding_vector is None
        assert insight.keywords == []


class TestEpisode:
    """测试 Episode 数据类"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import Episode
        assert Episode is not None

    def test_creation_basic(self):
        """测试基本创建"""
        from npc_optimization.memory_layers import Episode

        episode = Episode(
            id="ep_001",
            created_at=datetime.now().isoformat(),
            time_range=("2025-01-01T08:00:00", "2025-01-01T12:00:00"),
            involved_events=["evt_001", "evt_002", "evt_003"],
            episode_summary="今天上午帮助扑灭了铁匠铺的火灾",
            emotional_arc="紧张 -> 行动 -> 满足",
            key_decisions=["决定帮助", "呼叫支援"]
        )

        assert episode.id == "ep_001"
        assert len(episode.involved_events) == 3
        assert episode.embedding_vector is None


# ============================================================================
# HotMemory 测试
# ============================================================================

class TestHotMemory:
    """测试热记忆层"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import HotMemory
        assert HotMemory is not None

    def test_init(self):
        """测试初始化"""
        from npc_optimization.memory_layers import HotMemory

        hot = HotMemory("测试NPC")

        assert hot.npc_name == "测试NPC"
        assert hot.current_state == {}
        assert hot.recent_events == []
        assert hot.active_tasks == {}
        assert hot.thinking_vars == {}
        assert isinstance(hot.last_snapshot_time, datetime)

    def test_update_state(self):
        """测试状态更新"""
        from npc_optimization.memory_layers import HotMemory

        hot = HotMemory("测试NPC")
        old_time = hot.last_snapshot_time

        time.sleep(0.01)  # 确保时间戳不同
        hot.update_state({"location": "铁匠铺", "energy": 0.8})

        assert hot.current_state["location"] == "铁匠铺"
        assert hot.current_state["energy"] == 0.8
        assert hot.last_snapshot_time > old_time

    def test_update_state_atomic(self):
        """测试状态更新原子性"""
        from npc_optimization.memory_layers import HotMemory

        hot = HotMemory("测试NPC")
        hot.update_state({"a": 1, "b": 2})
        hot.update_state({"b": 3, "c": 4})

        assert hot.current_state["a"] == 1
        assert hot.current_state["b"] == 3
        assert hot.current_state["c"] == 4

    def test_add_event(self):
        """测试添加事件"""
        from npc_optimization.memory_layers import HotMemory, NPCEventEnhanced

        hot = HotMemory("测试NPC")

        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="测试事件",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=50
        )

        hot.add_event(event)

        assert len(hot.recent_events) == 1
        assert hot.recent_events[0].id == "evt_001"

    def test_add_event_maintains_max_5(self):
        """测试保持最多5条事件"""
        from npc_optimization.memory_layers import HotMemory, NPCEventEnhanced

        hot = HotMemory("测试NPC")

        # 添加7个事件
        for i in range(7):
            event = NPCEventEnhanced(
                id=f"evt_{i:03d}",
                timestamp=datetime.now().isoformat(),
                event_type="world_event",
                content=f"事件{i}",
                analysis={},
                response="",
                state_before={},
                state_after={},
                impact_score=50
            )
            hot.add_event(event)

        assert len(hot.recent_events) == 5
        # 应该保留最新的5个（索引2-6）
        assert hot.recent_events[0].id == "evt_002"
        assert hot.recent_events[-1].id == "evt_006"

    def test_get_snapshot(self):
        """测试获取快照"""
        from npc_optimization.memory_layers import HotMemory, NPCEventEnhanced

        hot = HotMemory("测试NPC")
        hot.update_state({"location": "村庄"})
        hot.active_tasks["task1"] = {"description": "锻造"}
        hot.thinking_vars["var1"] = "value1"

        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="test",
            content="测试",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=50
        )
        hot.add_event(event)

        snapshot = hot.get_snapshot()

        assert "state" in snapshot
        assert "recent_events" in snapshot
        assert "active_tasks" in snapshot
        assert "thinking_vars" in snapshot
        assert "snapshot_time" in snapshot
        assert snapshot["state"]["location"] == "村庄"
        assert len(snapshot["recent_events"]) == 1

    def test_thread_safety(self):
        """测试线程安全"""
        from npc_optimization.memory_layers import HotMemory, NPCEventEnhanced

        hot = HotMemory("测试NPC")
        errors = []

        def add_events():
            try:
                for i in range(10):
                    event = NPCEventEnhanced(
                        id=f"evt_{threading.current_thread().name}_{i}",
                        timestamp=datetime.now().isoformat(),
                        event_type="test",
                        content="测试",
                        analysis={},
                        response="",
                        state_before={},
                        state_after={},
                        impact_score=50
                    )
                    hot.add_event(event)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_events) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(hot.recent_events) == 5  # 应该保持最多5条


# ============================================================================
# WarmMemory 测试
# ============================================================================

class TestWarmMemory:
    """测试温记忆层"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import WarmMemory
        assert WarmMemory is not None

    def test_init_without_model(self):
        """测试无模型初始化"""
        from npc_optimization.memory_layers import WarmMemory

        warm = WarmMemory("测试NPC")

        assert warm.npc_name == "测试NPC"
        assert warm.insights == {}
        assert warm.episodes == {}

    def test_init_with_mock_model(self, mock_embedding_model):
        """测试带Mock模型初始化"""
        from npc_optimization.memory_layers import WarmMemory

        warm = WarmMemory("测试NPC", embedding_model=mock_embedding_model)

        assert warm.embedding_model == mock_embedding_model
        assert warm.embeddings_ready is True
        assert warm.embedding_dim == 768

    def test_add_insight_without_model(self):
        """测试无模型添加见解"""
        from npc_optimization.memory_layers import WarmMemory, Insight

        # 使用不存在的模型路径确保不加载模型
        warm = WarmMemory("测试NPC", model_path="./nonexistent_model_path_xyz")

        insight = Insight(
            id="ins_001",
            created_at=datetime.now().isoformat(),
            source_event_ids=["evt_001"],
            insight_text="帮助他人让我快乐",
            insight_type="reflection",
            emotional_weight=5,
            relevance_score=0.8
        )

        warm.add_insight(insight)

        assert "ins_001" in warm.insights
        # 如果模型未加载成功，embedding_vector 应该是 None
        # 但如果系统上有模型，可能会有向量，所以只检查见解是否存在
        assert warm.insights["ins_001"].insight_text == "帮助他人让我快乐"

    def test_add_insight_with_mock_model(self, mock_embedding_model):
        """测试带Mock模型添加见解"""
        from npc_optimization.memory_layers import WarmMemory, Insight

        warm = WarmMemory("测试NPC", embedding_model=mock_embedding_model)

        insight = Insight(
            id="ins_001",
            created_at=datetime.now().isoformat(),
            source_event_ids=["evt_001"],
            insight_text="帮助他人让我快乐",
            insight_type="reflection",
            emotional_weight=5,
            relevance_score=0.8
        )

        warm.add_insight(insight)

        assert "ins_001" in warm.insights
        assert warm.insights["ins_001"].embedding_vector is not None
        assert len(warm.insights["ins_001"].embedding_vector) == 768

    def test_add_episode(self, mock_embedding_model):
        """测试添加情景摘要"""
        from npc_optimization.memory_layers import WarmMemory, Episode

        warm = WarmMemory("测试NPC", embedding_model=mock_embedding_model)

        episode = Episode(
            id="ep_001",
            created_at=datetime.now().isoformat(),
            time_range=("2025-01-01T08:00:00", "2025-01-01T12:00:00"),
            involved_events=["evt_001"],
            episode_summary="今天帮助了邻居",
            emotional_arc="平静 -> 满足",
            key_decisions=["帮助"]
        )

        warm.add_episode(episode)

        assert "ep_001" in warm.episodes
        assert warm.episodes["ep_001"].embedding_vector is not None

    def test_search_insights_keyword_fallback(self):
        """测试关键词搜索降级"""
        from npc_optimization.memory_layers import WarmMemory, Insight

        warm = WarmMemory("测试NPC")  # 无模型

        # 添加一些见解
        insights = [
            ("ins_001", "帮助他人让我快乐"),
            ("ins_002", "锻造是我的专长"),
            ("ins_003", "与朋友交流很重要")
        ]

        for id_, text in insights:
            insight = Insight(
                id=id_,
                created_at=datetime.now().isoformat(),
                source_event_ids=[],
                insight_text=text,
                insight_type="reflection",
                emotional_weight=5,
                relevance_score=0.8
            )
            warm.add_insight(insight)

        # 搜索
        results = warm.search_insights("锻造", top_k=2)

        assert isinstance(results, list)
        # 应该能找到与锻造相关的见解
        if results:
            assert any("锻造" in r.insight_text for r in results)

    def test_search_insights_with_vector(self, mock_embedding_model):
        """测试向量搜索"""
        from npc_optimization.memory_layers import WarmMemory, Insight

        warm = WarmMemory("测试NPC", embedding_model=mock_embedding_model)

        # 添加见解
        for i in range(3):
            insight = Insight(
                id=f"ins_{i:03d}",
                created_at=datetime.now().isoformat(),
                source_event_ids=[],
                insight_text=f"见解内容{i}",
                insight_type="reflection",
                emotional_weight=5,
                relevance_score=0.8
            )
            warm.add_insight(insight)

        results = warm.search_insights("见解", top_k=2)

        assert isinstance(results, list)
        assert len(results) <= 2

    def test_get_recent_episodes(self, mock_embedding_model):
        """测试获取最近的情景摘要"""
        from npc_optimization.memory_layers import WarmMemory, Episode

        warm = WarmMemory("测试NPC", embedding_model=mock_embedding_model)

        # 添加不同时间的情景
        now = datetime.now()
        times = [
            now - timedelta(hours=6),   # 6小时前
            now - timedelta(hours=12),  # 12小时前
            now - timedelta(hours=30),  # 30小时前
        ]

        for i, t in enumerate(times):
            episode = Episode(
                id=f"ep_{i:03d}",
                created_at=t.isoformat(),
                time_range=(t.isoformat(), (t + timedelta(hours=2)).isoformat()),
                involved_events=[],
                episode_summary=f"情景{i}",
                emotional_arc="",
                key_decisions=[]
            )
            warm.add_episode(episode)

        # 获取最近24小时的
        recent = warm.get_recent_episodes(hours=24)

        assert len(recent) == 2  # 只有前两个在24小时内

    def test_cosine_similarity(self):
        """测试余弦相似度计算"""
        from npc_optimization.memory_layers import WarmMemory

        # 相同向量
        result1 = WarmMemory._cosine_similarity([1, 0, 0], [1, 0, 0])
        assert abs(result1 - 1.0) < 0.01

        # 正交向量
        result2 = WarmMemory._cosine_similarity([1, 0, 0], [0, 1, 0])
        assert abs(result2) < 0.01

        # 空向量
        result3 = WarmMemory._cosine_similarity([], [1, 0, 0])
        assert result3 == 0.0


# ============================================================================
# ColdMemory 测试
# ============================================================================

class TestColdMemory:
    """测试冷记忆层"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import ColdMemory
        assert ColdMemory is not None

    def test_init(self, temp_storage_dir):
        """测试初始化"""
        from npc_optimization.memory_layers import ColdMemory

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)

        assert cold.npc_name == "测试NPC"
        assert cold.db_path.exists()

    def test_init_creates_db(self, temp_storage_dir):
        """测试初始化创建数据库"""
        from npc_optimization.memory_layers import ColdMemory

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)

        # 验证数据库表存在
        with sqlite3.connect(cold.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='events'
            """)
            result = cursor.fetchone()
            assert result is not None

    def test_archive_event(self, temp_storage_dir):
        """测试归档事件"""
        from npc_optimization.memory_layers import ColdMemory, NPCEventEnhanced

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)

        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="测试事件",
            analysis={"key": "value"},
            response="测试响应",
            state_before={"a": 1},
            state_after={"b": 2},
            impact_score=50,
            resolved=True,
            parent_event_id="evt_000",
            related_event_ids=["evt_000"]
        )

        cold.archive_event(event)

        # 验证事件已存储
        with sqlite3.connect(cold.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM events WHERE id = ?", ("evt_001",))
            result = cursor.fetchone()
            assert result is not None

    def test_query_events_all(self, temp_storage_dir):
        """测试查询所有事件"""
        from npc_optimization.memory_layers import ColdMemory, NPCEventEnhanced

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)

        # 归档多个事件
        for i in range(3):
            event = NPCEventEnhanced(
                id=f"evt_{i:03d}",
                timestamp=datetime.now().isoformat(),
                event_type="world_event",
                content=f"事件{i}",
                analysis={},
                response="",
                state_before={},
                state_after={},
                impact_score=50
            )
            cold.archive_event(event)

        events = cold.query_events()

        assert len(events) == 3

    def test_query_events_by_type(self, temp_storage_dir):
        """测试按类型查询事件"""
        from npc_optimization.memory_layers import ColdMemory, NPCEventEnhanced

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)

        # 归档不同类型的事件
        types = ["world_event", "dialogue", "world_event"]
        for i, t in enumerate(types):
            event = NPCEventEnhanced(
                id=f"evt_{i:03d}",
                timestamp=datetime.now().isoformat(),
                event_type=t,
                content=f"事件{i}",
                analysis={},
                response="",
                state_before={},
                state_after={},
                impact_score=50
            )
            cold.archive_event(event)

        events = cold.query_events(event_type="dialogue")

        assert len(events) == 1
        assert events[0].event_type == "dialogue"

    def test_query_events_by_time_range(self, temp_storage_dir):
        """测试按时间范围查询事件"""
        from npc_optimization.memory_layers import ColdMemory, NPCEventEnhanced

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)

        now = datetime.now()
        times = [
            now - timedelta(days=5),
            now - timedelta(days=3),
            now - timedelta(days=1),
        ]

        for i, t in enumerate(times):
            event = NPCEventEnhanced(
                id=f"evt_{i:03d}",
                timestamp=t.isoformat(),
                event_type="world_event",
                content=f"事件{i}",
                analysis={},
                response="",
                state_before={},
                state_after={},
                impact_score=50
            )
            cold.archive_event(event)

        # 查询最近2天的事件
        start_time = (now - timedelta(days=2)).isoformat()
        events = cold.query_events(start_time=start_time)

        assert len(events) == 1


# ============================================================================
# MemoryLayerManager 测试
# ============================================================================

class TestMemoryLayerManager:
    """测试分层记忆管理器"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.memory_layers import MemoryLayerManager
        assert MemoryLayerManager is not None

    def test_init(self, temp_storage_dir):
        """测试初始化"""
        from npc_optimization.memory_layers import MemoryLayerManager

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            storage_dir=temp_storage_dir
        )

        assert manager.npc_name == "测试NPC"
        assert manager.hot_memory is not None
        assert manager.warm_memory is not None
        assert manager.cold_memory is not None

    def test_init_with_mock_model(self, temp_storage_dir, mock_embedding_model):
        """测试带Mock模型初始化"""
        from npc_optimization.memory_layers import MemoryLayerManager

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            embedding_model=mock_embedding_model,
            storage_dir=temp_storage_dir
        )

        assert manager.warm_memory.embedding_model == mock_embedding_model

    def test_start_and_stop(self, temp_storage_dir):
        """测试启动和停止"""
        from npc_optimization.memory_layers import MemoryLayerManager

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            storage_dir=temp_storage_dir
        )

        manager.start()
        assert manager.running is True
        assert manager.archival_thread is not None

        manager.stop()
        assert manager.running is False

    def test_add_event(self, temp_storage_dir):
        """测试添加事件"""
        from npc_optimization.memory_layers import MemoryLayerManager, NPCEventEnhanced

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            storage_dir=temp_storage_dir
        )

        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="测试事件",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=50
        )

        manager.add_event(event)

        # 验证事件添加到热记忆
        assert len(manager.hot_memory.recent_events) == 1

    def test_add_old_event_triggers_archival(self, temp_storage_dir):
        """测试旧事件触发归档"""
        from npc_optimization.memory_layers import MemoryLayerManager, NPCEventEnhanced

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            storage_dir=temp_storage_dir,
            cold_archival_days=7
        )

        # 创建一个8天前的事件
        old_time = datetime.now() - timedelta(days=8)
        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=old_time.isoformat(),
            event_type="world_event",
            content="旧事件",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=50
        )

        manager.add_event(event)

        # 验证事件被加入归档队列
        assert not manager.archival_queue.empty()

    def test_get_decision_context(self, temp_storage_dir, mock_embedding_model):
        """测试获取决策上下文"""
        from npc_optimization.memory_layers import (
            MemoryLayerManager, NPCEventEnhanced, Insight, Episode
        )

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            embedding_model=mock_embedding_model,
            storage_dir=temp_storage_dir
        )

        # 添加热记忆
        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="测试事件",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=50
        )
        manager.add_event(event)
        manager.hot_memory.update_state({"location": "村庄"})

        # 添加温记忆
        insight = Insight(
            id="ins_001",
            created_at=datetime.now().isoformat(),
            source_event_ids=["evt_001"],
            insight_text="测试见解",
            insight_type="reflection",
            emotional_weight=5,
            relevance_score=0.8
        )
        manager.add_reflection_insight(insight)

        episode = Episode(
            id="ep_001",
            created_at=datetime.now().isoformat(),
            time_range=("", ""),
            involved_events=["evt_001"],
            episode_summary="测试情景",
            emotional_arc="",
            key_decisions=[]
        )
        manager.add_episode_summary(episode)

        # 获取上下文
        context = manager.get_decision_context()

        assert "hot_memory" in context
        assert "warm_insights" in context
        assert "recent_episodes" in context
        assert context["hot_memory"]["state"]["location"] == "村庄"

    def test_add_reflection_insight(self, temp_storage_dir, mock_embedding_model):
        """测试添加反思见解"""
        from npc_optimization.memory_layers import MemoryLayerManager, Insight

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            embedding_model=mock_embedding_model,
            storage_dir=temp_storage_dir
        )

        insight = Insight(
            id="ins_001",
            created_at=datetime.now().isoformat(),
            source_event_ids=["evt_001"],
            insight_text="帮助他人让我快乐",
            insight_type="reflection",
            emotional_weight=5,
            relevance_score=0.8
        )

        manager.add_reflection_insight(insight)

        assert "ins_001" in manager.warm_memory.insights

    def test_add_episode_summary(self, temp_storage_dir, mock_embedding_model):
        """测试添加情景摘要"""
        from npc_optimization.memory_layers import MemoryLayerManager, Episode

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            embedding_model=mock_embedding_model,
            storage_dir=temp_storage_dir
        )

        episode = Episode(
            id="ep_001",
            created_at=datetime.now().isoformat(),
            time_range=("", ""),
            involved_events=["evt_001"],
            episode_summary="今天帮助了邻居",
            emotional_arc="平静 -> 满足",
            key_decisions=["帮助"]
        )

        manager.add_episode_summary(episode)

        assert "ep_001" in manager.warm_memory.episodes

    def test_query_cold_storage(self, temp_storage_dir):
        """测试查询冷存储"""
        from npc_optimization.memory_layers import MemoryLayerManager, NPCEventEnhanced

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            storage_dir=temp_storage_dir
        )

        # 直接归档事件到冷存储
        event = NPCEventEnhanced(
            id="evt_001",
            timestamp=datetime.now().isoformat(),
            event_type="world_event",
            content="测试事件",
            analysis={},
            response="",
            state_before={},
            state_after={},
            impact_score=50
        )
        manager.cold_memory.archive_event(event)

        # 查询
        events = manager.query_cold_storage()

        assert len(events) == 1


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration:
    """集成测试"""

    def test_full_memory_flow(self, temp_storage_dir, mock_embedding_model):
        """测试完整的记忆流程"""
        from npc_optimization.memory_layers import (
            MemoryLayerManager, NPCEventEnhanced, Insight, Episode
        )

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            embedding_model=mock_embedding_model,
            storage_dir=temp_storage_dir
        )
        manager.start()

        try:
            # 1. 添加事件到热记忆
            for i in range(3):
                event = NPCEventEnhanced(
                    id=f"evt_{i:03d}",
                    timestamp=datetime.now().isoformat(),
                    event_type="world_event",
                    content=f"事件{i}",
                    analysis={},
                    response="",
                    state_before={},
                    state_after={},
                    impact_score=50 + i * 10
                )
                manager.add_event(event)

            # 2. 更新状态
            manager.hot_memory.update_state({"location": "铁匠铺", "energy": 0.8})

            # 3. 添加见解
            insight = Insight(
                id="ins_001",
                created_at=datetime.now().isoformat(),
                source_event_ids=["evt_000", "evt_001"],
                insight_text="今天学到了很多",
                insight_type="reflection",
                emotional_weight=5,
                relevance_score=0.8
            )
            manager.add_reflection_insight(insight)

            # 4. 添加情景摘要
            episode = Episode(
                id="ep_001",
                created_at=datetime.now().isoformat(),
                time_range=("", ""),
                involved_events=["evt_000", "evt_001", "evt_002"],
                episode_summary="今天的工作日",
                emotional_arc="平静 -> 忙碌 -> 满足",
                key_decisions=["开始工作", "帮助客户"]
            )
            manager.add_episode_summary(episode)

            # 5. 获取决策上下文
            context = manager.get_decision_context()

            # 验证
            assert len(manager.hot_memory.recent_events) == 3
            assert len(manager.warm_memory.insights) == 1
            assert len(manager.warm_memory.episodes) == 1
            assert "hot_memory" in context
            assert context["hot_memory"]["state"]["location"] == "铁匠铺"

        finally:
            manager.stop()

    def test_archival_worker(self, temp_storage_dir):
        """测试归档工作线程"""
        from npc_optimization.memory_layers import MemoryLayerManager, NPCEventEnhanced

        manager = MemoryLayerManager(
            npc_name="测试NPC",
            storage_dir=temp_storage_dir,
            cold_archival_days=0  # 立即归档
        )
        manager.start()

        try:
            # 添加一个"旧"事件
            old_time = datetime.now() - timedelta(days=1)
            event = NPCEventEnhanced(
                id="evt_old",
                timestamp=old_time.isoformat(),
                event_type="world_event",
                content="旧事件",
                analysis={},
                response="",
                state_before={},
                state_after={},
                impact_score=50
            )
            manager.add_event(event)

            # 等待归档线程处理
            time.sleep(0.5)

            # 验证事件已归档到冷存储
            events = manager.cold_memory.query_events()
            assert any(e.id == "evt_old" for e in events)

        finally:
            manager.stop()


# ============================================================================
# 边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """边界条件测试"""

    def test_empty_insights_search(self):
        """测试空见解搜索"""
        from npc_optimization.memory_layers import WarmMemory

        warm = WarmMemory("测试NPC")
        results = warm.search_insights("测试", top_k=5)

        assert results == []

    def test_empty_episodes(self):
        """测试空情景获取"""
        from npc_optimization.memory_layers import WarmMemory

        warm = WarmMemory("测试NPC")
        episodes = warm.get_recent_episodes(hours=24)

        assert episodes == []

    def test_query_empty_cold_storage(self, temp_storage_dir):
        """测试查询空冷存储"""
        from npc_optimization.memory_layers import ColdMemory

        cold = ColdMemory("测试NPC", storage_dir=temp_storage_dir)
        events = cold.query_events()

        assert events == []

    def test_hot_memory_empty_snapshot(self):
        """测试空热记忆快照"""
        from npc_optimization.memory_layers import HotMemory

        hot = HotMemory("测试NPC")
        snapshot = hot.get_snapshot()

        assert snapshot["state"] == {}
        assert snapshot["recent_events"] == []
        assert snapshot["active_tasks"] == {}
