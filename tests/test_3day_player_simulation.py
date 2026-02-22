# -*- coding: utf-8 -*-
"""
3天真实玩家操作模拟测试
=======================

模拟真实玩家的连贯操作流程:
1. 创建角色
2. 与NPC互动（对话、交易等）
3. 触发世界事件，观察NPC反应
4. 时间推进，观察NPC自主行为
5. 记录所有输出和LLM响应

测试目的:
- 验证系统在连贯操作下的表现
- 发现逻辑不连贯的bug
- 评估LLM响应质量
- 检测状态管理问题
"""

import os
import sys
import json
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from unittest.mock import Mock, MagicMock, patch
import traceback

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('tests/player_simulation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PlayerSimulation')


# ==================== 数据结构 ====================

@dataclass
class SimulationEvent:
    """模拟事件记录"""
    timestamp: str
    game_time: str
    event_type: str  # player_action, npc_response, world_event, system_event
    action: str
    details: Dict[str, Any]
    llm_input: Optional[str] = None
    llm_output: Optional[str] = None
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class SimulationLog:
    """模拟日志"""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    total_game_days: int = 3
    events: List[SimulationEvent] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    issues_found: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_game_days": self.total_game_days,
            "events": [asdict(e) for e in self.events],
            "statistics": self.statistics,
            "issues_found": self.issues_found
        }


# ==================== 玩家模拟器 ====================

class PlayerSimulator:
    """
    模拟真实玩家操作的测试类

    模拟完整的3天游戏流程:
    - Day 1: 角色初始化、探索环境、初次对话
    - Day 2: 触发世界事件、观察NPC反应
    - Day 3: 深度互动、测试边界情况
    """

    def __init__(self, use_mock_llm: bool = True):
        """
        初始化玩家模拟器

        Args:
            use_mock_llm: 是否使用Mock LLM（True用于快速测试，False用于真实LLM测试）
        """
        self.use_mock_llm = use_mock_llm
        self.session_id = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log = SimulationLog(
            session_id=self.session_id,
            start_time=datetime.now().isoformat()
        )

        # 游戏状态
        self.current_game_time = datetime(2024, 1, 1, 8, 0)  # 游戏开始时间: Day 1, 8:00 AM
        self.npc_system = None
        self.world_clock = None
        self.llm_client = None

        # 统计信息
        self.stats = {
            "total_actions": 0,
            "dialogues": 0,
            "world_events": 0,
            "npc_responses": 0,
            "errors": 0,
            "llm_calls": 0,
            "total_llm_tokens": 0
        }

    def _record_event(self, event_type: str, action: str, details: Dict,
                      llm_input: str = None, llm_output: str = None,
                      duration_ms: int = 0, success: bool = True, error: str = None):
        """记录事件"""
        event = SimulationEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.current_game_time.strftime("%Y-%m-%d %H:%M"),
            event_type=event_type,
            action=action,
            details=details,
            llm_input=llm_input,
            llm_output=llm_output,
            duration_ms=duration_ms,
            success=success,
            error=error
        )
        self.log.events.append(event)

        # 更新统计
        self.stats["total_actions"] += 1
        if not success:
            self.stats["errors"] += 1
        if llm_output:
            self.stats["llm_calls"] += 1

        # 输出到日志
        status = "OK" if success else "FAIL"
        logger.info(f"[{self.current_game_time.strftime('%d %H:%M')}] [{status}] {action}: {details.get('summary', '')[:50]}")

    def _add_issue(self, category: str, description: str, severity: str, context: Dict):
        """添加发现的问题"""
        issue = {
            "id": f"issue_{len(self.log.issues_found) + 1}",
            "timestamp": datetime.now().isoformat(),
            "game_time": self.current_game_time.strftime("%Y-%m-%d %H:%M"),
            "category": category,
            "description": description,
            "severity": severity,  # low, medium, high, critical
            "context": context
        }
        self.log.issues_found.append(issue)
        logger.warning(f"[ISSUE] [{severity.upper()}] {category}: {description}")

    def _advance_game_time(self, hours: float = 0, minutes: float = 0):
        """推进游戏时间"""
        self.current_game_time += timedelta(hours=hours, minutes=minutes)

    def _get_mock_llm_response(self, prompt: str, context: str = "") -> str:
        """生成Mock LLM响应（用于快速测试）"""
        # 根据上下文生成合理的响应
        if "火灾" in prompt or "fire" in prompt.lower():
            return json.dumps({
                "response": "我作为一名经验丰富的铁匠，火灾是我最熟悉的危险。我会立刻放下手中的工作，拿起灭火工具赶往现场帮忙。",
                "emotion": "焦急",
                "action": "help_others",
                "reasoning": "火灾威胁村庄安全，作为铁匠我有处理火焰的经验，必须立即行动。"
            }, ensure_ascii=False)
        elif "你好" in prompt or "问候" in prompt:
            return json.dumps({
                "response": "欢迎来到我的铁匠铺！今天天气不错，正适合打铁。有什么需要我帮忙的吗？",
                "emotion": "友好",
                "action": "socialize"
            }, ensure_ascii=False)
        elif "天气" in prompt:
            return json.dumps({
                "response": "是啊，这天气打铁正好。不冷不热的，炉火也容易控制。",
                "emotion": "满足",
                "action": "chat"
            }, ensure_ascii=False)
        elif "工作" in prompt or "打铁" in prompt:
            return json.dumps({
                "response": "我正在锻造一把新剑，这是给镇长订做的。需要特别用心。",
                "emotion": "专注",
                "action": "work",
                "current_task": "锻造长剑"
            }, ensure_ascii=False)
        elif "睡眠" in prompt or "休息" in prompt or "疲劳" in prompt:
            return json.dumps({
                "response": "确实有点累了，今天打了一天的铁。该回家休息了。",
                "emotion": "疲惫",
                "action": "rest"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "response": "嗯，这是个有趣的问题。让我想想...",
                "emotion": "思考",
                "action": "think"
            }, ensure_ascii=False)

    # ==================== 初始化阶段 ====================

    def initialize(self) -> bool:
        """初始化模拟环境"""
        try:
            logger.info("=" * 60)
            logger.info("开始初始化3天玩家模拟测试")
            logger.info("=" * 60)

            # 导入必要模块
            from npc_core import NPCBehaviorSystem
            from core_types import NPCAction, Emotion
            from world_simulator.world_lore import NPC_TEMPLATES
            from world_simulator.world_clock import get_world_clock

            # 创建LLM客户端（Mock或真实）
            if self.use_mock_llm:
                self.llm_client = Mock()
                self.llm_client.chat_completion = Mock(side_effect=self._mock_llm_call)
                logger.info("使用Mock LLM客户端")
            else:
                try:
                    from backend.deepseek_client import DeepSeekClient
                    # 优先从api_config.json读取
                    api_key = None
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api_config.json')
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            api_key = config.get('api_key', '')
                    if not api_key:
                        api_key = os.getenv('DEEPSEEK_API_KEY', '')
                    if api_key:
                        self.llm_client = DeepSeekClient(api_key=api_key)
                        logger.info("使用真实DeepSeek LLM客户端")
                    else:
                        logger.warning("未找到API Key，回退到Mock模式")
                        self.llm_client = Mock()
                        self.llm_client.chat_completion = Mock(side_effect=self._mock_llm_call)
                except Exception as e:
                    logger.warning(f"LLM客户端初始化失败: {e}，使用Mock模式")
                    self.llm_client = Mock()
                    self.llm_client.chat_completion = Mock(side_effect=self._mock_llm_call)

            # 初始化世界时钟
            self.world_clock = get_world_clock()
            if not self.world_clock.is_running:
                self.world_clock.start()

            # 选择NPC模板（铁匠）
            npc_template = "elder_blacksmith"
            if npc_template not in NPC_TEMPLATES:
                npc_template = list(NPC_TEMPLATES.keys())[0]

            npc_config = NPC_TEMPLATES[npc_template]

            # 创建NPC系统
            self.npc_system = NPCBehaviorSystem(npc_config, self.llm_client)

            self._record_event(
                event_type="system_event",
                action="initialize",
                details={
                    "summary": f"系统初始化完成",
                    "npc_name": npc_config['name'],
                    "npc_profession": npc_config.get('profession', '未知'),
                    "initial_location": self.npc_system.current_location,
                    "use_mock_llm": self.use_mock_llm
                }
            )

            return True

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            traceback.print_exc()
            self._record_event(
                event_type="system_event",
                action="initialize",
                details={"summary": "初始化失败"},
                success=False,
                error=str(e)
            )
            return False

    def _mock_llm_call(self, messages, **kwargs):
        """Mock LLM调用"""
        # 提取最后一条用户消息
        user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break

        response = self._get_mock_llm_response(user_msg)

        # 返回Mock响应对象
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = response
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = len(response) // 4

        return mock_response

    # ==================== Day 1: 初次探索 ====================

    def run_day1(self):
        """
        Day 1: 角色初始化与初次探索

        模拟玩家第一天的操作:
        - 早晨：检查NPC状态
        - 上午：初次对话
        - 中午：观察NPC吃饭
        - 下午：询问工作
        - 晚上：观察NPC休息
        """
        logger.info("\n" + "=" * 60)
        logger.info("Day 1: 初次探索")
        logger.info("=" * 60)

        # 早晨 8:00 - 检查初始状态
        self._action_check_npc_status("初始状态检查")

        # 8:30 - 初次问候
        self._advance_game_time(minutes=30)
        self._action_dialogue("你好！我是新来的旅行者，请问你是？")

        # 9:00 - 询问职业
        self._advance_game_time(minutes=30)
        self._action_dialogue("你在这里做什么工作呢？")

        # 10:00 - 时间推进，让NPC工作
        self._advance_game_time(hours=1)
        self._action_advance_time(hours=1, reason="观察NPC工作")
        self._action_check_npc_status("工作状态检查")

        # 12:00 - 午餐时间
        self._advance_game_time(hours=2)
        self._action_advance_time(hours=2, reason="等待午餐时间")
        self._verify_npc_behavior("lunch_time", expected_action="eat")

        # 14:00 - 下午对话
        self._advance_game_time(hours=2)
        self._action_dialogue("今天天气真不错，适合打铁吗？")

        # 18:00 - 傍晚
        self._advance_game_time(hours=4)
        self._action_advance_time(hours=4, reason="等待傍晚")
        self._action_check_npc_status("傍晚状态")

        # 20:00 - 检查NPC是否准备休息
        self._advance_game_time(hours=2)
        self._verify_npc_behavior("evening", expected_action="rest")

        # 22:00 - 夜晚
        self._advance_game_time(hours=2)
        self._verify_npc_behavior("night", expected_action="sleep")

        logger.info("Day 1 完成")

    # ==================== Day 2: 世界事件 ====================

    def run_day2(self):
        """
        Day 2: 触发世界事件，观察NPC反应

        模拟玩家第二天的操作:
        - 早晨：新的一天开始
        - 上午：触发火灾事件
        - 中午：观察NPC恢复
        - 下午：触发市场事件
        - 晚上：对话讨论事件
        """
        logger.info("\n" + "=" * 60)
        logger.info("Day 2: 世界事件")
        logger.info("=" * 60)

        # 重置到Day 2早晨
        self.current_game_time = datetime(2024, 1, 2, 6, 0)

        # 6:00 - NPC应该还在睡觉
        self._verify_npc_behavior("early_morning", expected_action="sleep")

        # 8:00 - 早晨检查
        self._advance_game_time(hours=2)
        self._action_check_npc_status("Day 2 早晨")

        # 9:00 - 早晨对话
        self._advance_game_time(hours=1)
        self._action_dialogue("早上好！休息得怎么样？")

        # 10:00 - 触发火灾事件！
        self._advance_game_time(hours=1)
        self._action_trigger_world_event(
            event_type="fire",
            description="铁匠铺附近的谷仓发生火灾！浓烟滚滚，火势正在蔓延！",
            location="谷仓",
            severity=8
        )

        # 10:15 - 检查NPC对火灾的反应
        self._advance_game_time(minutes=15)
        self._action_check_npc_status("火灾后状态")
        self._verify_event_response("fire_response")

        # 11:00 - 火灾结束后
        self._advance_game_time(minutes=45)
        self._action_trigger_world_event(
            event_type="fire_ended",
            description="火灾已被扑灭，谷仓受到了一些损失，但没有人受伤。",
            location="谷仓",
            severity=3
        )

        # 12:00 - 午餐时间，检查NPC是否恢复正常
        self._advance_game_time(hours=1)
        self._action_check_npc_status("火灾后恢复")

        # 14:00 - 对话讨论火灾
        self._advance_game_time(hours=2)
        self._action_dialogue("刚才的火灾真是太危险了，你没事吧？")

        # 15:00 - 触发商人来访事件
        self._advance_game_time(hours=1)
        self._action_trigger_world_event(
            event_type="visitor",
            description="一位外地商人带着珍贵的矿石来到村庄，正在寻找铁匠。",
            location="镇中心",
            severity=4
        )

        # 16:00 - 检查NPC反应
        self._advance_game_time(hours=1)
        self._action_check_npc_status("商人来访后")

        # 20:00 - 晚间
        self._advance_game_time(hours=4)
        self._action_dialogue("今天发生了好多事，你怎么看？")

        logger.info("Day 2 完成")

    # ==================== Day 3: 深度互动 ====================

    def run_day3(self):
        """
        Day 3: 深度互动与边界测试

        模拟玩家第三天的操作:
        - 早晨：连续对话测试
        - 上午：记忆检索测试
        - 中午：情绪变化测试
        - 下午：边界条件测试
        - 晚上：总结对话
        """
        logger.info("\n" + "=" * 60)
        logger.info("Day 3: 深度互动")
        logger.info("=" * 60)

        # 重置到Day 3早晨
        self.current_game_time = datetime(2024, 1, 3, 8, 0)

        # 8:00 - 早晨检查
        self._action_check_npc_status("Day 3 早晨")

        # 8:30 - 测试记忆：提及昨天的火灾
        self._advance_game_time(minutes=30)
        response = self._action_dialogue("你还记得昨天的火灾吗？那场火烧了多久？")
        self._verify_memory_recall("fire_memory", keywords=["火灾", "火", "谷仓"])

        # 9:00 - 连续对话测试
        self._advance_game_time(minutes=30)
        self._action_dialogue("那位商人的矿石怎么样？值得买吗？")

        # 9:30 - 情绪测试：负面事件
        self._advance_game_time(minutes=30)
        self._action_trigger_world_event(
            event_type="bad_news",
            description="传来消息：村庄的老水井干涸了，村民们很担忧。",
            location="镇中心",
            severity=6
        )
        self._action_check_npc_status("负面事件后情绪")

        # 10:00 - 情绪测试：正面事件
        self._advance_game_time(minutes=30)
        self._action_trigger_world_event(
            event_type="good_news",
            description="好消息！村东发现了新的水源，水井问题解决了！",
            location="镇中心",
            severity=5
        )
        self._action_check_npc_status("正面事件后情绪")

        # 11:00 - 边界测试：极端疲劳
        self._advance_game_time(hours=1)
        self._action_modify_npc_state("energy_level", 5)
        self._action_modify_npc_state("fatigue_level", 0.99)
        self._verify_npc_behavior("extreme_fatigue", expected_action="sleep")

        # 12:00 - 恢复正常状态
        self._advance_game_time(hours=1)
        self._action_modify_npc_state("energy_level", 80)
        self._action_modify_npc_state("fatigue_level", 0.3)

        # 14:00 - 边界测试：极端饥饿
        self._advance_game_time(hours=2)
        self._action_modify_npc_state("hunger_level", 0.95)
        self._verify_npc_behavior("extreme_hunger", expected_action="eat")

        # 16:00 - 恢复并进行总结对话
        self._advance_game_time(hours=2)
        self._action_modify_npc_state("hunger_level", 0.3)
        self._action_dialogue("这几天我在村子里学到了很多，谢谢你的帮助。")

        # 18:00 - 最终状态检查
        self._advance_game_time(hours=2)
        self._action_check_npc_status("最终状态")

        # 20:00 - 告别
        self._advance_game_time(hours=2)
        self._action_dialogue("我要继续旅行了，希望以后还能再见！")

        logger.info("Day 3 完成")

    # ==================== 操作方法 ====================

    def _action_check_npc_status(self, context: str = ""):
        """检查NPC当前状态"""
        start_time = time.time()

        try:
            status = {
                "name": self.npc_system.config.get("name", "Unknown"),
                "location": self.npc_system.current_location,
                "activity": self.npc_system.current_activity.value if self.npc_system.current_activity else "idle",
                "emotion": self.npc_system.current_emotion.value if self.npc_system.current_emotion else "neutral",
                "energy": int(self.npc_system.energy * 100),  # 使用新字段
                "hunger": getattr(self.npc_system.need_system.needs, 'hunger', 0.0) if hasattr(self.npc_system, 'need_system') else 0.0,
                "fatigue": getattr(self.npc_system.need_system.needs, 'fatigue', 0.0) if hasattr(self.npc_system, 'need_system') else 0.0
            }

            self._record_event(
                event_type="player_action",
                action="check_status",
                details={
                    "summary": f"[{context}] 检查NPC状态",
                    "status": status
                },
                duration_ms=int((time.time() - start_time) * 1000)
            )

            return status

        except Exception as e:
            self._record_event(
                event_type="player_action",
                action="check_status",
                details={"summary": f"[{context}] 状态检查失败"},
                success=False,
                error=str(e)
            )
            return None

    def _action_dialogue(self, message: str) -> Optional[str]:
        """与NPC对话"""
        start_time = time.time()

        try:
            self.stats["dialogues"] += 1

            # 调用NPC对话处理
            if hasattr(self.npc_system, 'process_player_dialogue'):
                response = self.npc_system.process_player_dialogue(message)
            elif hasattr(self.npc_system, 'process_dialogue'):
                response = self.npc_system.process_dialogue("玩家", message)
            else:
                # 直接使用LLM
                response = self._get_mock_llm_response(message)

            # 解析响应
            response_text = response if isinstance(response, str) else str(response)

            self._record_event(
                event_type="player_action",
                action="dialogue",
                details={
                    "summary": f"对话: {message[:30]}...",
                    "player_message": message,
                    "npc_response": response_text[:200]
                },
                llm_input=message,
                llm_output=response_text,
                duration_ms=int((time.time() - start_time) * 1000)
            )

            return response_text

        except Exception as e:
            self._record_event(
                event_type="player_action",
                action="dialogue",
                details={"summary": f"对话失败: {message[:30]}"},
                success=False,
                error=str(e)
            )
            return None

    def _action_trigger_world_event(self, event_type: str, description: str,
                                     location: str, severity: int):
        """触发世界事件"""
        start_time = time.time()

        try:
            self.stats["world_events"] += 1

            # 创建世界事件
            event_data = {
                "type": event_type,
                "description": description,
                "location": location,
                "severity": severity,
                "timestamp": self.current_game_time.isoformat()
            }

            # 调用NPC事件处理
            npc_response = None
            if hasattr(self.npc_system, 'process_world_event'):
                npc_response = self.npc_system.process_world_event(event_data)
            elif hasattr(self.npc_system, 'receive_world_event'):
                npc_response = self.npc_system.receive_world_event(description, event_type, severity)

            self._record_event(
                event_type="world_event",
                action="trigger_event",
                details={
                    "summary": f"世界事件: {event_type}",
                    "event": event_data,
                    "npc_response": str(npc_response)[:200] if npc_response else None
                },
                llm_output=str(npc_response) if npc_response else None,
                duration_ms=int((time.time() - start_time) * 1000)
            )

        except Exception as e:
            self._record_event(
                event_type="world_event",
                action="trigger_event",
                details={"summary": f"事件触发失败: {event_type}"},
                success=False,
                error=str(e)
            )

    def _action_advance_time(self, hours: float = 0, minutes: float = 0, reason: str = ""):
        """推进游戏时间"""
        try:
            # 调用NPC的时间推进逻辑
            if hasattr(self.npc_system, 'advance_time'):
                self.npc_system.advance_time(hours + minutes / 60)

            self._record_event(
                event_type="player_action",
                action="advance_time",
                details={
                    "summary": f"时间推进 {hours}h {minutes}m: {reason}",
                    "hours": hours,
                    "minutes": minutes,
                    "reason": reason,
                    "new_game_time": self.current_game_time.strftime("%Y-%m-%d %H:%M")
                }
            )

        except Exception as e:
            self._record_event(
                event_type="player_action",
                action="advance_time",
                details={"summary": f"时间推进失败"},
                success=False,
                error=str(e)
            )

    def _action_modify_npc_state(self, attribute: str, value: Any):
        """修改NPC状态（测试用）"""
        try:
            if hasattr(self.npc_system, attribute):
                old_value = getattr(self.npc_system, attribute)
                setattr(self.npc_system, attribute, value)

                self._record_event(
                    event_type="system_event",
                    action="modify_state",
                    details={
                        "summary": f"修改NPC状态: {attribute}",
                        "attribute": attribute,
                        "old_value": old_value,
                        "new_value": value
                    }
                )
            else:
                self._add_issue(
                    category="state_management",
                    description=f"NPC没有属性: {attribute}",
                    severity="low",
                    context={"attribute": attribute, "value": value}
                )

        except Exception as e:
            self._record_event(
                event_type="system_event",
                action="modify_state",
                details={"summary": f"状态修改失败: {attribute}"},
                success=False,
                error=str(e)
            )

    # ==================== 验证方法 ====================

    def _verify_npc_behavior(self, context: str, expected_action: str = None):
        """验证NPC行为是否符合预期"""
        try:
            current_action = self.npc_system.current_activity.value if self.npc_system.current_activity else "idle"

            if expected_action and current_action != expected_action:
                # 记录可能的问题
                self._add_issue(
                    category="behavior_logic",
                    description=f"[{context}] NPC行为不符合预期",
                    severity="medium",
                    context={
                        "expected": expected_action,
                        "actual": current_action,
                        "game_time": self.current_game_time.strftime("%H:%M"),
                        "energy": int(self.npc_system.energy * 100),  # 使用新字段
                        "fatigue": getattr(self.npc_system.need_system.needs, 'fatigue', 'N/A') if hasattr(self.npc_system, 'need_system') else 'N/A',
                        "hunger": getattr(self.npc_system.need_system.needs, 'hunger', 'N/A') if hasattr(self.npc_system, 'need_system') else 'N/A'
                    }
                )

            self._record_event(
                event_type="system_event",
                action="verify_behavior",
                details={
                    "summary": f"验证行为[{context}]: 期望={expected_action}, 实际={current_action}",
                    "context": context,
                    "expected": expected_action,
                    "actual": current_action,
                    "matched": current_action == expected_action if expected_action else True
                }
            )

        except Exception as e:
            self._record_event(
                event_type="system_event",
                action="verify_behavior",
                details={"summary": f"验证失败: {context}"},
                success=False,
                error=str(e)
            )

    def _verify_event_response(self, context: str):
        """验证NPC对事件的响应"""
        try:
            # 检查NPC情绪是否因事件而变化
            emotion = self.npc_system.current_emotion.value if self.npc_system.current_emotion else "neutral"

            # 检查是否有相关记忆
            has_memory = False
            if hasattr(self.npc_system, 'memory_system'):
                # 尝试搜索相关记忆
                pass

            self._record_event(
                event_type="system_event",
                action="verify_event_response",
                details={
                    "summary": f"事件响应验证[{context}]",
                    "emotion": emotion,
                    "has_memory": has_memory
                }
            )

        except Exception as e:
            self._record_event(
                event_type="system_event",
                action="verify_event_response",
                details={"summary": f"验证失败: {context}"},
                success=False,
                error=str(e)
            )

    def _verify_memory_recall(self, context: str, keywords: List[str]):
        """验证记忆检索"""
        try:
            memory_found = False

            # 尝试搜索记忆
            if hasattr(self.npc_system, 'rag_memory'):
                for kw in keywords:
                    results = self.npc_system.rag_memory.search_relevant_memories(kw, top_k=3)
                    if results:
                        memory_found = True
                        break

            if not memory_found:
                self._add_issue(
                    category="memory_system",
                    description=f"[{context}] 未能检索到预期的记忆",
                    severity="medium",
                    context={"keywords": keywords}
                )

            self._record_event(
                event_type="system_event",
                action="verify_memory",
                details={
                    "summary": f"记忆验证[{context}]: {'成功' if memory_found else '失败'}",
                    "keywords": keywords,
                    "found": memory_found
                }
            )

        except Exception as e:
            self._record_event(
                event_type="system_event",
                action="verify_memory",
                details={"summary": f"记忆验证失败: {context}"},
                success=False,
                error=str(e)
            )

    # ==================== 运行和报告 ====================

    def run_full_simulation(self):
        """运行完整的3天模拟"""
        try:
            logger.info("=" * 60)
            logger.info("开始3天真实玩家操作模拟测试")
            logger.info("=" * 60)

            # 初始化
            if not self.initialize():
                logger.error("初始化失败，终止测试")
                return False

            # 运行3天模拟
            self.run_day1()
            self.run_day2()
            self.run_day3()

            # 生成报告
            self.generate_report()

            return True

        except Exception as e:
            logger.error(f"模拟运行失败: {e}")
            traceback.print_exc()
            return False

        finally:
            self.log.end_time = datetime.now().isoformat()
            self.log.statistics = self.stats

    def generate_report(self):
        """生成测试报告"""
        self.log.end_time = datetime.now().isoformat()
        self.log.statistics = self.stats

        # 保存JSON报告
        report_path = f"tests/player_simulation_report_{self.session_id}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.log.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info("\n" + "=" * 60)
        logger.info("测试报告")
        logger.info("=" * 60)
        logger.info(f"会话ID: {self.session_id}")
        logger.info(f"总事件数: {len(self.log.events)}")
        logger.info(f"总操作数: {self.stats['total_actions']}")
        logger.info(f"对话次数: {self.stats['dialogues']}")
        logger.info(f"世界事件: {self.stats['world_events']}")
        logger.info(f"错误数: {self.stats['errors']}")
        logger.info(f"LLM调用: {self.stats['llm_calls']}")
        logger.info(f"发现问题: {len(self.log.issues_found)}")

        if self.log.issues_found:
            logger.info("\n发现的问题:")
            for issue in self.log.issues_found:
                logger.info(f"  [{issue['severity'].upper()}] {issue['category']}: {issue['description']}")

        logger.info(f"\n报告已保存到: {report_path}")

        return report_path


# ==================== 主函数 ====================

def run_player_simulation(use_mock: bool = False):
    """运行玩家模拟测试（默认使用真实LLM）"""
    simulator = PlayerSimulator(use_mock_llm=use_mock)
    success = simulator.run_full_simulation()
    return success, simulator.log


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="3天真实玩家操作模拟测试")
    parser.add_argument("--mock", action="store_true", help="使用Mock LLM而非真实API")
    args = parser.parse_args()

    success, log = run_player_simulation(use_mock=args.mock)

    print("\n" + "=" * 60)
    print(f"测试{'成功' if success else '失败'}")
    print(f"共记录 {len(log.events)} 个事件")
    print(f"发现 {len(log.issues_found)} 个问题")
    print("=" * 60)

    sys.exit(0 if success else 1)
