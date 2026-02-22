# -*- coding: utf-8 -*-
"""
多NPC并行运行系统测试
=====================

测试 parallel_npc_system.py 中的各个组件:
- SimulationClock: 模拟时钟
- EventScheduler: 事件调度器
- NPCAgent: NPC Agent包装器
- WorldSimulator: 世界模拟器
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world_simulator.parallel_npc_system import (
    GameTime,
    AgentState,
    ScheduledEvent,
    SimulationClock,
    EventScheduler,
    NPCAgent,
    WorldSimulator,
    create_world_simulator,
    run_simple_simulation
)
from npc_optimization.message_bus import Message, MessageType, MessagePriority


class TestGameTime:
    """GameTime 测试"""

    def test_init_default(self):
        """测试默认初始化"""
        gt = GameTime()
        assert gt.day == 1
        assert gt.hour == 8
        assert gt.minute == 0

    def test_init_custom(self):
        """测试自定义初始化"""
        gt = GameTime(day=5, hour=14, minute=30)
        assert gt.day == 5
        assert gt.hour == 14
        assert gt.minute == 30

    def test_advance_minutes(self):
        """测试分钟推进"""
        gt = GameTime(day=1, hour=8, minute=0)
        gt.advance(30)
        assert gt.minute == 30
        assert gt.hour == 8
        assert gt.day == 1

    def test_advance_hour_overflow(self):
        """测试小时溢出"""
        gt = GameTime(day=1, hour=8, minute=45)
        gt.advance(30)
        assert gt.minute == 15
        assert gt.hour == 9
        assert gt.day == 1

    def test_advance_day_overflow(self):
        """测试天数溢出"""
        gt = GameTime(day=1, hour=23, minute=30)
        gt.advance(60)
        assert gt.minute == 30
        assert gt.hour == 0
        assert gt.day == 2

    def test_to_string(self):
        """测试字符串转换"""
        gt = GameTime(day=3, hour=14, minute=5)
        assert gt.to_string() == "Day 3 14:05"

    def test_copy(self):
        """测试复制"""
        gt1 = GameTime(day=2, hour=10, minute=20)
        gt2 = gt1.copy()
        assert gt1 == gt2
        gt2.advance(10)
        assert gt1 != gt2  # 确认是独立副本

    def test_comparison(self):
        """测试比较运算"""
        gt1 = GameTime(day=1, hour=8, minute=0)
        gt2 = GameTime(day=1, hour=8, minute=30)
        gt3 = GameTime(day=1, hour=9, minute=0)
        gt4 = GameTime(day=2, hour=0, minute=0)

        assert gt1 < gt2
        assert gt2 < gt3
        assert gt3 < gt4
        assert gt1 <= gt1
        assert gt1 <= gt2


class TestSimulationClock:
    """SimulationClock 测试"""

    def test_init(self):
        """测试初始化"""
        clock = SimulationClock()
        assert clock.current_time == GameTime()
        assert clock.time_scale == 1.0

    def test_init_with_time(self):
        """测试带初始时间的初始化"""
        initial = GameTime(day=5, hour=12, minute=0)
        clock = SimulationClock(initial)
        assert clock.current_time == initial

    def test_advance(self):
        """测试时间推进"""
        clock = SimulationClock()
        start = clock.current_time
        clock.advance(30)
        end = clock.current_time
        assert end.minute == start.minute + 30

    def test_time_scale(self):
        """测试时间缩放设置"""
        clock = SimulationClock()
        clock.time_scale = 60.0
        assert clock.time_scale == 60.0

    def test_time_scale_invalid(self):
        """测试无效时间缩放"""
        clock = SimulationClock()
        with pytest.raises(ValueError):
            clock.time_scale = 0

    def test_add_callback(self):
        """测试添加回调"""
        clock = SimulationClock(GameTime(day=1, hour=8, minute=0))
        callback_called = []

        def my_callback():
            callback_called.append(True)

        trigger_time = GameTime(day=1, hour=8, minute=30)
        callback_id = clock.add_callback(trigger_time, my_callback)

        assert callback_id is not None
        assert len(callback_called) == 0

        # 推进时间触发回调
        clock.advance(60)  # 推进60分钟
        assert len(callback_called) == 1

    def test_remove_callback(self):
        """测试移除回调"""
        clock = SimulationClock(GameTime(day=1, hour=8, minute=0))
        callback_called = []

        def my_callback():
            callback_called.append(True)

        trigger_time = GameTime(day=1, hour=8, minute=30)
        callback_id = clock.add_callback(trigger_time, my_callback)

        clock.remove_callback(callback_id)
        clock.advance(60)

        assert len(callback_called) == 0

    def test_reset(self):
        """测试重置"""
        clock = SimulationClock()
        clock.advance(100)
        clock.reset()
        assert clock.current_time == GameTime()


class TestEventScheduler:
    """EventScheduler 测试"""

    def test_init(self):
        """测试初始化"""
        clock = SimulationClock()
        scheduler = EventScheduler(clock)
        assert len(scheduler.get_pending_events()) == 0

    def test_schedule_event(self):
        """测试安排事件"""
        clock = SimulationClock(GameTime(day=1, hour=8, minute=0))
        scheduler = EventScheduler(clock)

        event_id = scheduler.schedule_event(
            event_type="test_event",
            content="测试事件内容",
            trigger_time=GameTime(day=1, hour=9, minute=0)
        )

        assert event_id is not None
        pending = scheduler.get_pending_events()
        assert len(pending) == 1
        assert pending[0].event_type == "test_event"

    def test_cancel_event(self):
        """测试取消事件"""
        clock = SimulationClock()
        scheduler = EventScheduler(clock)

        event_id = scheduler.schedule_event(
            event_type="test",
            content="test",
            trigger_time=GameTime(day=1, hour=10, minute=0)
        )

        assert scheduler.cancel_event(event_id) is True
        assert len(scheduler.get_pending_events()) == 0

    @pytest.mark.asyncio
    async def test_process_scheduled_events(self):
        """测试处理调度事件"""
        clock = SimulationClock(GameTime(day=1, hour=8, minute=0))
        scheduler = EventScheduler(clock)

        # 安排一个即将触发的事件
        scheduler.schedule_event(
            event_type="immediate",
            content="即时事件",
            trigger_time=GameTime(day=1, hour=8, minute=30)
        )

        # 安排一个未来的事件
        scheduler.schedule_event(
            event_type="future",
            content="未来事件",
            trigger_time=GameTime(day=1, hour=12, minute=0)
        )

        # 推进时间
        clock.advance(60)

        # 处理事件
        triggered = await scheduler.process_scheduled_events()

        assert len(triggered) == 1
        assert triggered[0].event_type == "immediate"

    def test_event_history(self):
        """测试事件历史"""
        clock = SimulationClock()
        scheduler = EventScheduler(clock)

        # 初始历史应该为空
        history = scheduler.get_event_history()
        assert len(history) == 0


class TestNPCAgent:
    """NPCAgent 测试"""

    def test_init(self):
        """测试初始化"""
        mock_npc = Mock()
        mock_npc.npc_name = "测试NPC"

        agent = NPCAgent(mock_npc)

        assert agent.agent_id == "测试NPC"
        assert agent.state == AgentState.IDLE
        assert agent.npc_system is mock_npc

    def test_init_custom_id(self):
        """测试自定义ID初始化"""
        mock_npc = Mock()
        agent = NPCAgent(mock_npc, agent_id="custom_agent")

        assert agent.agent_id == "custom_agent"

    def test_pause_resume(self):
        """测试暂停和恢复"""
        mock_npc = Mock()
        agent = NPCAgent(mock_npc)

        agent.pause()
        assert agent.state == AgentState.PAUSED

        agent.resume()
        assert agent.state == AgentState.RUNNING

    def test_stop(self):
        """测试停止"""
        mock_npc = Mock()
        agent = NPCAgent(mock_npc)

        agent.stop()
        assert agent.state == AgentState.STOPPED

    @pytest.mark.asyncio
    async def test_receive_message(self):
        """测试接收消息"""
        mock_npc = Mock()
        agent = NPCAgent(mock_npc)

        # 模拟消息队列已初始化
        agent._message_queue = asyncio.Queue()

        message = Message(
            id="test_msg",
            message_type=MessageType.WORLD_EVENT,
            sender_id="system",
            content="测试消息",
            timestamp=datetime.now()
        )

        await agent.receive_message(message)

        assert agent.stats["messages_received"] == 1
        assert not agent._message_queue.empty()

    def test_get_state_snapshot(self):
        """测试获取状态快照"""
        mock_npc = Mock()
        mock_npc.current_location = "铁匠铺"
        mock_npc.current_activity = Mock(value="工作")
        mock_npc.current_emotion = Mock(value="平静")

        agent = NPCAgent(mock_npc, agent_id="blacksmith")

        snapshot = agent.get_state_snapshot()

        assert snapshot["agent_id"] == "blacksmith"
        assert snapshot["state"] == AgentState.IDLE.value
        assert snapshot["location"] == "铁匠铺"
        assert snapshot["activity"] == "工作"
        assert snapshot["emotion"] == "平静"

    @pytest.mark.asyncio
    async def test_process_tick(self):
        """测试处理tick"""
        mock_npc = Mock()
        mock_npc.autonomous_tick = AsyncMock(return_value=["action1"])

        agent = NPCAgent(mock_npc)
        agent._message_queue = asyncio.Queue()

        game_time = GameTime(day=1, hour=10, minute=0)
        result = await agent.process_tick(game_time)

        assert result["agent_id"] == agent.agent_id
        assert result["game_time"] == game_time.to_string()
        assert agent.stats["ticks_processed"] == 1


class TestWorldSimulator:
    """WorldSimulator 测试"""

    def test_init(self):
        """测试初始化"""
        simulator = WorldSimulator()

        assert simulator.clock is not None
        assert simulator.event_scheduler is not None
        assert simulator.message_bus is not None
        assert simulator.is_running is False
        assert simulator.is_paused is False

    def test_init_with_time(self):
        """测试带初始时间的初始化"""
        initial = GameTime(day=3, hour=15, minute=30)
        simulator = WorldSimulator(initial_time=initial)

        assert simulator.clock.current_time == initial

    def test_register_npc(self):
        """测试注册NPC"""
        simulator = WorldSimulator()
        mock_npc = Mock()
        mock_npc.npc_name = "测试铁匠"

        agent = simulator.register_npc(mock_npc)

        assert agent is not None
        assert agent.agent_id == "测试铁匠"
        assert simulator.get_agent("测试铁匠") is agent

    def test_register_duplicate_npc(self):
        """测试注册重复NPC"""
        simulator = WorldSimulator()
        mock_npc = Mock()
        mock_npc.npc_name = "NPC1"

        simulator.register_npc(mock_npc)

        with pytest.raises(ValueError):
            simulator.register_npc(mock_npc)

    def test_unregister_npc(self):
        """测试取消注册NPC"""
        simulator = WorldSimulator()
        mock_npc = Mock()
        mock_npc.npc_name = "ToRemove"

        simulator.register_npc(mock_npc)
        assert simulator.get_agent("ToRemove") is not None

        result = simulator.unregister_npc("ToRemove")
        assert result is True
        assert simulator.get_agent("ToRemove") is None

    def test_get_all_agents(self):
        """测试获取所有Agent"""
        simulator = WorldSimulator()

        for i in range(3):
            mock_npc = Mock()
            mock_npc.npc_name = f"NPC_{i}"
            simulator.register_npc(mock_npc)

        agents = simulator.get_all_agents()
        assert len(agents) == 3

    def test_get_all_npc_states(self):
        """测试获取所有NPC状态"""
        simulator = WorldSimulator()

        mock_npc = Mock()
        mock_npc.npc_name = "StateTest"
        mock_npc.current_location = "市场"
        mock_npc.current_activity = Mock(value="购物")

        simulator.register_npc(mock_npc)

        states = simulator.get_all_npc_states()
        assert "StateTest" in states
        assert states["StateTest"]["location"] == "市场"

    def test_pause_resume_simulation(self):
        """测试暂停和恢复模拟"""
        simulator = WorldSimulator()

        simulator.pause_simulation()
        assert simulator.is_paused is True

        simulator.resume_simulation()
        assert simulator.is_paused is False

    def test_pause_resume_agent(self):
        """测试暂停和恢复单个Agent"""
        simulator = WorldSimulator()
        mock_npc = Mock()
        mock_npc.npc_name = "PauseTest"

        simulator.register_npc(mock_npc)

        result = simulator.pause_agent("PauseTest")
        assert result is True

        agent = simulator.get_agent("PauseTest")
        assert agent.state == AgentState.PAUSED

        result = simulator.resume_agent("PauseTest")
        assert result is True
        assert agent.state == AgentState.RUNNING

    def test_get_simulation_stats(self):
        """测试获取模拟统计信息"""
        simulator = WorldSimulator()

        mock_npc = Mock()
        mock_npc.npc_name = "StatsTest"
        simulator.register_npc(mock_npc)

        stats = simulator.get_simulation_stats()

        assert "current_time" in stats
        assert stats["agents_count"] == 1
        assert stats["running"] is False

    @pytest.mark.asyncio
    async def test_broadcast_event(self):
        """测试广播事件"""
        simulator = WorldSimulator()

        mock_npc1 = Mock()
        mock_npc1.npc_name = "NPC1"
        mock_npc2 = Mock()
        mock_npc2.npc_name = "NPC2"

        agent1 = simulator.register_npc(mock_npc1)
        agent2 = simulator.register_npc(mock_npc2)

        # 初始化消息队列
        agent1._message_queue = asyncio.Queue()
        agent2._message_queue = asyncio.Queue()

        await simulator.broadcast_event(
            event_type="test_broadcast",
            content="广播测试消息"
        )

        # 验证两个Agent都收到了消息
        assert agent1.stats["messages_received"] == 1
        assert agent2.stats["messages_received"] == 1

    @pytest.mark.asyncio
    async def test_broadcast_event_to_specific_agents(self):
        """测试广播事件给特定Agent"""
        simulator = WorldSimulator()

        mock_npc1 = Mock()
        mock_npc1.npc_name = "Target"
        mock_npc2 = Mock()
        mock_npc2.npc_name = "NonTarget"

        agent1 = simulator.register_npc(mock_npc1)
        agent2 = simulator.register_npc(mock_npc2)

        agent1._message_queue = asyncio.Queue()
        agent2._message_queue = asyncio.Queue()

        await simulator.broadcast_event(
            event_type="targeted",
            content="目标消息",
            target_agents=["Target"]
        )

        assert agent1.stats["messages_received"] == 1
        assert agent2.stats["messages_received"] == 0

    def test_add_remove_event_callback(self):
        """测试添加和移除事件回调"""
        simulator = WorldSimulator()
        callback_called = []

        def my_callback(event):
            callback_called.append(event)

        simulator.add_event_callback(my_callback)
        assert my_callback in simulator._event_callbacks

        simulator.remove_event_callback(my_callback)
        assert my_callback not in simulator._event_callbacks


class TestScheduledEvent:
    """ScheduledEvent 测试"""

    def test_init(self):
        """测试初始化"""
        event = ScheduledEvent(
            event_id="test123",
            trigger_time=GameTime(day=1, hour=12, minute=0),
            event_type="test",
            content="测试内容"
        )

        assert event.event_id == "test123"
        assert event.executed is False

    def test_auto_id(self):
        """测试自动生成ID"""
        event = ScheduledEvent(
            event_id="",
            trigger_time=GameTime(),
            event_type="auto",
            content="自动ID测试"
        )

        assert event.event_id != ""
        assert len(event.event_id) == 8


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_create_world_simulator(self):
        """测试创建世界模拟器"""
        simulator = create_world_simulator()
        assert isinstance(simulator, WorldSimulator)

    def test_create_world_simulator_with_time(self):
        """测试带时间创建世界模拟器"""
        initial = GameTime(day=5, hour=18, minute=45)
        simulator = create_world_simulator(initial)
        assert simulator.clock.current_time == initial


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_short_simulation(self):
        """测试短时模拟"""
        simulator = WorldSimulator()

        # 创建模拟NPC
        mock_npc = Mock()
        mock_npc.npc_name = "IntegrationNPC"
        mock_npc.autonomous_tick = AsyncMock(return_value=[])

        simulator.register_npc(mock_npc)

        # 安排一个事件
        simulator.event_scheduler.schedule_event(
            event_type="test_event",
            content="集成测试事件",
            trigger_time=GameTime(day=1, hour=8, minute=30)
        )

        # 运行很短的模拟（0.1小时 = 6分钟游戏时间）
        result = await simulator.run_simulation(
            duration_hours=0.1,
            time_scale=60.0,
            tick_interval=0.01  # 快速tick
        )

        assert result["success"] is True
        assert "IntegrationNPC" in result["agents"]

    @pytest.mark.asyncio
    async def test_multiple_npcs_parallel(self):
        """测试多NPC并行运行"""
        simulator = WorldSimulator()

        # 创建多个模拟NPC
        npcs = []
        for i in range(3):
            mock_npc = Mock()
            mock_npc.npc_name = f"ParallelNPC_{i}"
            mock_npc.autonomous_tick = AsyncMock(return_value=[f"action_{i}"])
            npcs.append(mock_npc)
            simulator.register_npc(mock_npc)

        # 运行短模拟
        result = await simulator.run_simulation(
            duration_hours=0.05,
            time_scale=60.0,
            tick_interval=0.01
        )

        assert result["success"] is True
        assert len(result["agents"]) == 3

        # 验证所有Agent都处理了tick
        for agent_id, agent in simulator.get_all_agents().items():
            assert agent.stats["ticks_processed"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
