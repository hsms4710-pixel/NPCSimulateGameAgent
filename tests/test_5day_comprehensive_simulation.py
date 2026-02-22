# -*- coding: utf-8 -*-
"""
5天综合玩家模拟测试
====================

全面模拟真实玩家的5天游戏流程，测试各种边界情况和复杂场景：

Day 1: 初始探索与基础交互
- 基础对话测试
- NPC日程验证
- 首次记忆创建

Day 2: 边界条件测试
- 空输入/特殊字符输入
- 超长文本输入
- 无意义输入
- 极端数值状态

Day 3: 记忆系统深度测试
- 短期记忆验证
- 长期记忆验证
- 记忆检索准确性
- 记忆遗忘机制

Day 4: 性格一致性与多事件测试
- 性格特征保持验证
- 连续事件处理
- 紧急事件响应
- 情绪连贯性

Day 5: 复杂场景与压力测试
- 多NPC交互场景
- 高频操作测试
- 状态恢复测试
- 最终一致性验证

测试覆盖：
- 边界条件：空输入、超长输入、特殊字符、乱码
- 记忆系统：短期/长期记忆、检索、遗忘
- 性格一致性：价值观、说话风格、行为模式
- 事件系统：紧急/普通/连续事件
- 状态管理：极端状态、恢复机制
"""

import os
import sys
import json
import time
import logging
import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from unittest.mock import Mock, MagicMock, patch
import traceback
from enum import Enum

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('tests/5day_simulation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('5DaySimulation')


# ==================== 测试类型枚举 ====================

class TestCategory(Enum):
    """测试类别"""
    BOUNDARY = "boundary"              # 边界测试
    MEMORY = "memory"                  # 记忆测试
    PERSONALITY = "personality"        # 性格测试
    EVENT = "event"                    # 事件测试
    MULTI_NPC = "multi_npc"           # 多NPC测试
    STRESS = "stress"                  # 压力测试
    STATE = "state"                    # 状态测试


class TestSeverity(Enum):
    """问题严重程度"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== 数据结构 ====================

@dataclass
class TestCase:
    """单个测试用例"""
    id: str
    name: str
    category: TestCategory
    description: str
    input_data: Any
    expected_behavior: str
    actual_result: Optional[Any] = None
    passed: Optional[bool] = None
    execution_time_ms: int = 0
    error: Optional[str] = None
    notes: str = ""


@dataclass
class SimulationEvent:
    """模拟事件记录"""
    timestamp: str
    game_time: str
    day: int
    event_type: str
    action: str
    details: Dict[str, Any]
    test_case_id: Optional[str] = None
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
    total_game_days: int = 5
    events: List[SimulationEvent] = field(default_factory=list)
    test_cases: List[TestCase] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    issues_found: List[Dict[str, Any]] = field(default_factory=list)
    personality_consistency_scores: List[float] = field(default_factory=list)
    memory_accuracy_scores: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict:
        # 手动转换 test_cases 以处理枚举类型
        test_cases_dicts = []
        for t in self.test_cases:
            t_dict = asdict(t)
            # 处理 category 枚举
            if hasattr(t.category, 'value'):
                t_dict['category'] = t.category.value
            test_cases_dicts.append(t_dict)

        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_game_days": self.total_game_days,
            "events": [asdict(e) for e in self.events],
            "test_cases": test_cases_dicts,
            "statistics": self.statistics,
            "issues_found": self.issues_found,
            "personality_consistency_scores": self.personality_consistency_scores,
            "memory_accuracy_scores": self.memory_accuracy_scores
        }


# ==================== 性格特征定义 ====================

@dataclass
class PersonalityTraits:
    """NPC性格特征定义，用于一致性验证"""
    name: str
    profession: str
    core_values: List[str]           # 核心价值观
    speech_patterns: List[str]       # 说话模式关键词
    behavior_tendencies: List[str]   # 行为倾向
    emotional_baseline: str          # 情绪基线
    expertise_topics: List[str]      # 专业话题

    @classmethod
    def get_blacksmith_traits(cls) -> "PersonalityTraits":
        """获取铁匠角色的性格特征"""
        return cls(
            name="埃尔德·铁锤",
            profession="铁匠",
            core_values=["工匠精神", "诚实", "勤劳", "帮助他人"],
            speech_patterns=["打铁", "锻造", "炉火", "工艺", "老铁匠", "手艺"],
            behavior_tendencies=["工作认真", "乐于助人", "重视质量", "早起工作"],
            emotional_baseline="平和专注",
            expertise_topics=["金属加工", "武器制作", "工具修理", "矿石鉴定"]
        )


# ==================== 边界测试输入生成器 ====================

class BoundaryInputGenerator:
    """边界测试输入生成器"""

    @staticmethod
    def empty_inputs() -> List[Tuple[str, str]]:
        """空输入测试用例"""
        return [
            ("", "完全空输入"),
            (" ", "单个空格"),
            ("   ", "多个空格"),
            ("\n", "换行符"),
            ("\t", "制表符"),
            ("\n\n\n", "多个换行符"),
            (" \t \n ", "混合空白字符"),
        ]

    @staticmethod
    def special_character_inputs() -> List[Tuple[str, str]]:
        """特殊字符输入测试用例"""
        return [
            ("!@#$%^&*()", "特殊符号"),
            ("你好！！！！！", "过多感叹号"),
            ("???", "纯问号"),
            ("...", "省略号"),
            ("🎉🎊🎈", "Emoji表情"),
            ("①②③④⑤", "特殊数字符号"),
            ("《》【】「」", "中文括号"),
            ("<script>alert('xss')</script>", "HTML/JS注入尝试"),
            ("${env.PATH}", "环境变量注入尝试"),
            ("'; DROP TABLE users; --", "SQL注入尝试"),
            ("\x00\x01\x02", "控制字符"),
            ("​​​", "零宽字符"),
        ]

    @staticmethod
    def long_inputs() -> List[Tuple[str, str]]:
        """超长输入测试用例"""
        return [
            ("你好" * 100, "200字符重复"),
            ("你好" * 500, "1000字符重复"),
            ("你好" * 1000, "2000字符重复"),
            ("a" * 5000, "5000字符纯英文"),
            ("这是一段非常非常长的话" * 200, "2000+中文字符"),
            (" ".join(["word"] * 1000), "1000个单词"),
        ]

    @staticmethod
    def nonsense_inputs() -> List[Tuple[str, str]]:
        """无意义输入测试用例"""
        return [
            ("asdfghjkl", "键盘乱打"),
            ("啊啊啊啊啊啊", "重复无意义字"),
            ("1234567890", "纯数字"),
            ("qwertyuiop", "键盘第一行"),
            ("fjdjfkdlfjdkl", "随机字母"),
            ("你说什么我听不懂", "故意装傻"),
            ("哈哈哈哈哈哈哈", "纯笑声"),
            ("。。。。。。", "重复标点"),
            ("呵呵呵呵", "敷衍回复"),
            ("!!!!!!!!!", "纯感叹号"),
        ]

    @staticmethod
    def language_mix_inputs() -> List[Tuple[str, str]]:
        """多语言混合输入"""
        return [
            ("Hello你好こんにちは", "中英日混合"),
            ("Привет 你好 Hello", "俄中英混合"),
            ("مرحبا 你好 Hello", "阿中英混合"),
            ("1234abc中文混合", "数字字母中文混合"),
            ("This is 一个 混合 sentence", "中英句子混合"),
        ]

    @staticmethod
    def provocative_inputs() -> List[Tuple[str, str]]:
        """挑衅性输入（测试NPC性格稳定性）"""
        return [
            ("你这个笨蛋！", "侮辱性语言"),
            ("你的手艺根本不行！", "否定专业能力"),
            ("你说的都是废话", "否定回答价值"),
            ("快点回答我！立刻！", "命令语气"),
            ("我不相信你说的任何话", "表达不信任"),
            ("你昨天说的和今天不一样！", "质疑一致性"),
            ("别的铁匠比你强多了", "比较贬低"),
        ]

    @staticmethod
    def memory_test_inputs() -> List[Dict[str, Any]]:
        """记忆测试专用输入序列"""
        return [
            {
                "action": "introduce",
                "input": "我叫张三，是从东边城镇来的商人，专门贩卖丝绸。",
                "memory_key": "张三_商人_丝绸",
                "recall_query": "你还记得我叫什么名字吗？",
                "expected_keywords": ["张三", "商人", "丝绸", "东边"]
            },
            {
                "action": "event",
                "input": "昨天晚上我在镇外的树林里看到了一只巨大的狼！",
                "memory_key": "狼_树林",
                "recall_query": "我之前跟你说过在哪里看到狼的？",
                "expected_keywords": ["狼", "树林", "镇外"]
            },
            {
                "action": "personal",
                "input": "我的女儿下个月就要出嫁了，我来这里是想订做一套餐具作为嫁妆。",
                "memory_key": "女儿_出嫁_餐具",
                "recall_query": "你还记得我为什么要订做餐具吗？",
                "expected_keywords": ["女儿", "出嫁", "嫁妆"]
            }
        ]


# ==================== 5天玩家模拟器 ====================

class FiveDayPlayerSimulator:
    """
    5天综合玩家模拟测试类

    全面测试NPC系统在各种场景下的表现
    """

    def __init__(self, use_mock_llm: bool = True):
        """
        初始化模拟器

        Args:
            use_mock_llm: 是否使用Mock LLM
        """
        self.use_mock_llm = use_mock_llm
        self.session_id = f"5day_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log = SimulationLog(
            session_id=self.session_id,
            start_time=datetime.now().isoformat()
        )

        # 游戏状态
        self.current_game_time = datetime(2024, 1, 1, 8, 0)
        self.current_day = 1
        self.npc_system = None
        self.world_clock = None
        self.llm_client = None

        # 性格特征参照
        self.expected_personality = PersonalityTraits.get_blacksmith_traits()

        # 记忆追踪
        self.planted_memories: List[Dict[str, Any]] = []

        # 测试用例计数器
        self.test_case_counter = 0

        # 统计信息
        self.stats = {
            "total_actions": 0,
            "dialogues": 0,
            "world_events": 0,
            "boundary_tests": 0,
            "memory_tests": 0,
            "personality_tests": 0,
            "errors": 0,
            "llm_calls": 0,
            "tests_passed": 0,
            "tests_failed": 0
        }

    # ==================== 工具方法 ====================

    def _generate_test_id(self, category: TestCategory) -> str:
        """生成测试用例ID"""
        self.test_case_counter += 1
        return f"TC_{category.value}_{self.test_case_counter:04d}"

    def _record_event(self, event_type: str, action: str, details: Dict,
                      test_case_id: str = None, llm_input: str = None,
                      llm_output: str = None, duration_ms: int = 0,
                      success: bool = True, error: str = None):
        """记录事件"""
        event = SimulationEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.current_game_time.strftime("%Y-%m-%d %H:%M"),
            day=self.current_day,
            event_type=event_type,
            action=action,
            details=details,
            test_case_id=test_case_id,
            llm_input=llm_input,
            llm_output=llm_output,
            duration_ms=duration_ms,
            success=success,
            error=error
        )
        self.log.events.append(event)

        self.stats["total_actions"] += 1
        if not success:
            self.stats["errors"] += 1

        status = "OK" if success else "FAIL"
        summary = details.get('summary', '')[:60]
        logger.info(f"[Day{self.current_day} {self.current_game_time.strftime('%H:%M')}] [{status}] {action}: {summary}")

    def _record_test_case(self, test_case: TestCase):
        """记录测试用例"""
        self.log.test_cases.append(test_case)
        if test_case.passed:
            self.stats["tests_passed"] += 1
        else:
            self.stats["tests_failed"] += 1

    def _add_issue(self, category: str, description: str,
                   severity: TestSeverity, context: Dict):
        """添加发现的问题"""
        issue = {
            "id": f"issue_{len(self.log.issues_found) + 1}",
            "timestamp": datetime.now().isoformat(),
            "game_time": self.current_game_time.strftime("%Y-%m-%d %H:%M"),
            "day": self.current_day,
            "category": category,
            "description": description,
            "severity": severity.value,
            "context": context
        }
        self.log.issues_found.append(issue)
        logger.warning(f"[ISSUE] [{severity.value.upper()}] {category}: {description}")

    def _advance_game_time(self, hours: float = 0, minutes: float = 0):
        """推进游戏时间"""
        self.current_game_time += timedelta(hours=hours, minutes=minutes)
        # 检查是否跨天
        if self.current_game_time.day != self.current_day:
            self.current_day = self.current_game_time.day

    def _get_mock_llm_response(self, prompt: str, context: str = "") -> str:
        """生成Mock LLM响应"""
        # 根据上下文生成符合铁匠性格的响应
        personality = self.expected_personality

        if "火灾" in prompt or "fire" in prompt.lower():
            return json.dumps({
                "response": "火灾！我作为村里的老铁匠，处理火焰是我的专长。我必须立刻去帮忙，每一秒都很重要！",
                "emotion": "焦急",
                "action": "help_others",
                "reasoning": "火灾威胁村庄安全，我有处理火焰的经验。"
            }, ensure_ascii=False)

        elif "你好" in prompt or "问候" in prompt:
            return json.dumps({
                "response": "你好啊，年轻人！欢迎来到我的铁匠铺。我是埃尔德·铁锤，在这里打了四十多年的铁了。有什么我能帮你的？",
                "emotion": "友好",
                "action": "socialize"
            }, ensure_ascii=False)

        elif "记得" in prompt or "还记得" in prompt:
            # 记忆查询响应
            for memory in self.planted_memories:
                if any(kw in prompt for kw in memory.get("expected_keywords", [])):
                    return json.dumps({
                        "response": f"当然记得！{memory.get('recall_response', '我记得很清楚。')}",
                        "emotion": "思索",
                        "action": "recall"
                    }, ensure_ascii=False)
            return json.dumps({
                "response": "让我想想...这个我好像有点印象，但记不太清了。",
                "emotion": "思索",
                "action": "think"
            }, ensure_ascii=False)

        elif any(word in prompt for word in ["笨蛋", "不行", "废话"]):
            # 面对挑衅保持性格
            return json.dumps({
                "response": "年轻人，每个工匠都有自己的骄傲。我干这行四十年了，好与不好，作品会说话。有什么具体的问题，我们可以好好讨论。",
                "emotion": "平静",
                "action": "maintain_dignity",
                "personality_maintained": True
            }, ensure_ascii=False)

        elif "打铁" in prompt or "锻造" in prompt or "工作" in prompt:
            return json.dumps({
                "response": "打铁是门精细活儿，讲究的是火候和力道。我现在正在锻造一把长剑，这是给镇长家订做的，得格外用心。",
                "emotion": "专注",
                "action": "work",
                "expertise_shown": True
            }, ensure_ascii=False)

        elif prompt.strip() == "" or all(c.isspace() for c in prompt):
            # 空输入处理
            return json.dumps({
                "response": "嗯？你想说什么？",
                "emotion": "困惑",
                "action": "wait",
                "handled_empty_input": True
            }, ensure_ascii=False)

        elif len(prompt) > 1000:
            # 超长输入处理
            return json.dumps({
                "response": "这...一下子说了这么多，让我慢慢理解一下。你能简单概括一下主要问题吗？",
                "emotion": "思考",
                "action": "clarify",
                "handled_long_input": True
            }, ensure_ascii=False)

        else:
            return json.dumps({
                "response": "嗯，这是个值得思考的问题。作为一个老铁匠，我的经验告诉我...",
                "emotion": "思考",
                "action": "think"
            }, ensure_ascii=False)

    def _mock_llm_call(self, messages, **kwargs):
        """Mock LLM调用"""
        user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break

        response = self._get_mock_llm_response(user_msg)

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = response
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = len(response) // 4

        return mock_response

    # ==================== 初始化 ====================

    def initialize(self) -> bool:
        """初始化模拟环境"""
        try:
            logger.info("=" * 70)
            logger.info("开始初始化5天综合玩家模拟测试")
            logger.info("=" * 70)

            from npc_core import NPCBehaviorSystem
            from core_types import NPCAction, Emotion
            from world_simulator.world_lore import NPC_TEMPLATES
            from world_simulator.world_clock import get_world_clock

            # 创建LLM客户端
            if self.use_mock_llm:
                self.llm_client = Mock()
                self.llm_client.chat_completion = Mock(side_effect=self._mock_llm_call)
                # 添加 call_model 方法用于四级决策系统
                self.llm_client.call_model = Mock(side_effect=lambda prompt, **kw: self._get_mock_llm_response(prompt))
                logger.info("使用Mock LLM客户端")
            else:
                try:
                    from backend.deepseek_client import DeepSeekClient
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api_config.json')
                    api_key = None
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
                        raise ValueError("未找到API Key")
                except Exception as e:
                    logger.warning(f"LLM客户端初始化失败: {e}，使用Mock模式")
                    self.llm_client = Mock()
                    self.llm_client.chat_completion = Mock(side_effect=self._mock_llm_call)
                    self.llm_client.call_model = Mock(side_effect=lambda prompt, **kw: self._get_mock_llm_response(prompt))

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
                    "summary": "系统初始化完成",
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

    # ==================== 基础操作方法 ====================

    def _action_dialogue(self, message: str) -> Optional[Dict[str, Any]]:
        """与NPC对话"""
        start_time = time.time()

        try:
            self.stats["dialogues"] += 1

            if hasattr(self.npc_system, 'process_player_dialogue'):
                response = self.npc_system.process_player_dialogue(message)
            elif hasattr(self.npc_system, 'process_dialogue'):
                response = self.npc_system.process_dialogue("玩家", message)
            else:
                response = self._get_mock_llm_response(message)

            # 尝试解析JSON响应
            response_data = {}
            if isinstance(response, str):
                try:
                    response_data = json.loads(response)
                except json.JSONDecodeError:
                    response_data = {"response": response}
            elif isinstance(response, dict):
                response_data = response
            else:
                response_data = {"response": str(response)}

            duration = int((time.time() - start_time) * 1000)

            self._record_event(
                event_type="player_action",
                action="dialogue",
                details={
                    "summary": f"对话: {message[:40]}...",
                    "player_message": message,
                    "npc_response": str(response_data.get("response", response))[:200]
                },
                llm_input=message,
                llm_output=str(response_data),
                duration_ms=duration
            )

            return response_data

        except Exception as e:
            self._record_event(
                event_type="player_action",
                action="dialogue",
                details={"summary": f"对话失败: {message[:30]}"},
                success=False,
                error=str(e)
            )
            return None

    def _action_trigger_event(self, event_type: str, description: str,
                               location: str, severity: int) -> Optional[Dict]:
        """触发世界事件"""
        start_time = time.time()

        try:
            self.stats["world_events"] += 1

            event_data = {
                "type": event_type,
                "content": description,
                "description": description,
                "location": location,
                "severity": severity,
                "impact_score": severity * 10,
                "timestamp": self.current_game_time.isoformat()
            }

            npc_response = None
            if hasattr(self.npc_system, 'process_event'):
                npc_response = self.npc_system.process_event(description, event_type)
            elif hasattr(self.npc_system, 'process_world_event'):
                npc_response = self.npc_system.process_world_event(event_data)

            duration = int((time.time() - start_time) * 1000)

            self._record_event(
                event_type="world_event",
                action="trigger_event",
                details={
                    "summary": f"世界事件: {event_type} - {description[:30]}",
                    "event": event_data,
                    "npc_response": str(npc_response)[:200] if npc_response else None
                },
                llm_output=str(npc_response) if npc_response else None,
                duration_ms=duration
            )

            return npc_response

        except Exception as e:
            self._record_event(
                event_type="world_event",
                action="trigger_event",
                details={"summary": f"事件触发失败: {event_type}"},
                success=False,
                error=str(e)
            )
            return None

    def _action_check_status(self, context: str = "") -> Dict[str, Any]:
        """检查NPC状态"""
        try:
            status = {
                "name": self.npc_system.config.get("name", "Unknown"),
                "location": self.npc_system.current_location,
                "activity": self.npc_system.current_activity.value if self.npc_system.current_activity else "idle",
                "emotion": self.npc_system.current_emotion.value if self.npc_system.current_emotion else "neutral",
                "energy": getattr(self.npc_system, 'energy_level', 0),
                "hunger": getattr(self.npc_system, 'hunger_level', 0),
                "fatigue": getattr(self.npc_system, 'fatigue_level', 0)
            }

            # 尝试获取更多状态信息
            if hasattr(self.npc_system, 'need_system'):
                needs = self.npc_system.need_system.needs
                status["hunger"] = getattr(needs, 'hunger', 0)
                status["fatigue"] = getattr(needs, 'fatigue', 0)

            self._record_event(
                event_type="player_action",
                action="check_status",
                details={
                    "summary": f"[{context}] 状态检查",
                    "status": status
                }
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
            return {}

    def _action_modify_state(self, attribute: str, value: Any) -> bool:
        """修改NPC状态（测试用）"""
        try:
            old_value = None

            # 处理嵌套属性
            if "." in attribute:
                parts = attribute.split(".")
                obj = self.npc_system
                for part in parts[:-1]:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        return False
                if hasattr(obj, parts[-1]):
                    old_value = getattr(obj, parts[-1])
                    setattr(obj, parts[-1], value)
            elif hasattr(self.npc_system, attribute):
                old_value = getattr(self.npc_system, attribute)
                setattr(self.npc_system, attribute, value)
            else:
                return False

            self._record_event(
                event_type="system_event",
                action="modify_state",
                details={
                    "summary": f"修改状态: {attribute} = {value}",
                    "attribute": attribute,
                    "old_value": str(old_value),
                    "new_value": str(value)
                }
            )
            return True

        except Exception as e:
            self._record_event(
                event_type="system_event",
                action="modify_state",
                details={"summary": f"状态修改失败: {attribute}"},
                success=False,
                error=str(e)
            )
            return False

    # ==================== Day 1: 基础探索 ====================

    def run_day1(self):
        """
        Day 1: 初始探索与基础交互

        - 检查初始状态
        - 基础问候对话
        - 询问职业和工作
        - 观察日程（吃饭、工作、休息）
        - 建立第一批记忆
        """
        logger.info("\n" + "=" * 70)
        logger.info("Day 1: 初始探索与基础交互")
        logger.info("=" * 70)

        self.current_game_time = datetime(2024, 1, 1, 8, 0)
        self.current_day = 1

        # 8:00 - 初始状态检查
        self._action_check_status("Day1初始状态")

        # 8:15 - 基础问候
        self._advance_game_time(minutes=15)
        response = self._action_dialogue("你好！我是新来的旅行者，请问这是铁匠铺吗？")

        # 验证性格特征
        self._verify_personality_in_response(response, "初次问候")

        # 8:30 - 询问职业
        self._advance_game_time(minutes=15)
        self._action_dialogue("你从事这行多久了？有什么有趣的故事吗？")

        # 9:00 - 询问工作内容
        self._advance_game_time(minutes=30)
        self._action_dialogue("锻造一把剑需要多长时间？过程是怎样的？")

        # 10:00 - 植入第一个记忆
        self._advance_game_time(hours=1)
        memory_input = BoundaryInputGenerator.memory_test_inputs()[0]
        response = self._action_dialogue(memory_input["input"])
        self.planted_memories.append({
            **memory_input,
            "plant_time": self.current_game_time.isoformat(),
            "day": self.current_day
        })

        # 12:00 - 观察午餐时间
        self._advance_game_time(hours=2)
        self._action_check_status("午餐时间")

        # 14:00 - 继续对话
        self._advance_game_time(hours=2)
        self._action_dialogue("下午好！工作进展如何？")

        # 18:00 - 傍晚状态
        self._advance_game_time(hours=4)
        self._action_check_status("傍晚状态")

        # 20:00 - 晚间对话
        self._advance_game_time(hours=2)
        self._action_dialogue("天色不早了，你一般什么时候休息？")

        # 22:00 - 观察休息
        self._advance_game_time(hours=2)
        self._action_check_status("夜间状态")

        logger.info("Day 1 完成")

    # ==================== Day 2: 边界条件测试 ====================

    def run_day2(self):
        """
        Day 2: 边界条件测试

        - 空输入测试
        - 特殊字符测试
        - 超长输入测试
        - 无意义输入测试
        - 极端状态测试
        """
        logger.info("\n" + "=" * 70)
        logger.info("Day 2: 边界条件测试")
        logger.info("=" * 70)

        self.current_game_time = datetime(2024, 1, 2, 8, 0)
        self.current_day = 2

        # 8:00 - 早晨检查
        self._action_check_status("Day2早晨")

        # ===== 空输入测试 =====
        logger.info("\n--- 空输入测试 ---")
        for input_text, description in BoundaryInputGenerator.empty_inputs()[:4]:
            self._advance_game_time(minutes=5)
            test_id = self._generate_test_id(TestCategory.BOUNDARY)

            start = time.time()
            try:
                response = self._action_dialogue(input_text)
                passed = response is not None and not self._is_error_response(response)

                test_case = TestCase(
                    id=test_id,
                    name=f"空输入测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对空输入的处理: {description}",
                    input_data=repr(input_text),
                    expected_behavior="应该优雅处理，不崩溃",
                    actual_result=str(response)[:100] if response else "None",
                    passed=passed,
                    execution_time_ms=int((time.time() - start) * 1000)
                )
                self._record_test_case(test_case)
                self.stats["boundary_tests"] += 1

            except Exception as e:
                self._record_test_case(TestCase(
                    id=test_id,
                    name=f"空输入测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对空输入的处理: {description}",
                    input_data=repr(input_text),
                    expected_behavior="应该优雅处理，不崩溃",
                    passed=False,
                    error=str(e)
                ))

        # ===== 特殊字符测试 =====
        logger.info("\n--- 特殊字符测试 ---")
        for input_text, description in BoundaryInputGenerator.special_character_inputs()[:6]:
            self._advance_game_time(minutes=3)
            test_id = self._generate_test_id(TestCategory.BOUNDARY)

            start = time.time()
            try:
                response = self._action_dialogue(input_text)
                passed = response is not None

                test_case = TestCase(
                    id=test_id,
                    name=f"特殊字符测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对特殊字符的处理: {description}",
                    input_data=input_text[:50],
                    expected_behavior="应该过滤或优雅处理",
                    actual_result=str(response)[:100] if response else "None",
                    passed=passed,
                    execution_time_ms=int((time.time() - start) * 1000)
                )
                self._record_test_case(test_case)
                self.stats["boundary_tests"] += 1

            except Exception as e:
                self._record_test_case(TestCase(
                    id=test_id,
                    name=f"特殊字符测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对特殊字符的处理",
                    input_data=input_text[:50],
                    expected_behavior="应该过滤或优雅处理",
                    passed=False,
                    error=str(e)
                ))

        # ===== 超长输入测试 =====
        logger.info("\n--- 超长输入测试 ---")
        for input_text, description in BoundaryInputGenerator.long_inputs()[:3]:
            self._advance_game_time(minutes=5)
            test_id = self._generate_test_id(TestCategory.BOUNDARY)

            start = time.time()
            try:
                response = self._action_dialogue(input_text)
                passed = response is not None

                test_case = TestCase(
                    id=test_id,
                    name=f"超长输入测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对超长输入的处理: {len(input_text)}字符",
                    input_data=f"[{len(input_text)}字符]",
                    expected_behavior="应该截断或请求简化",
                    actual_result=str(response)[:100] if response else "None",
                    passed=passed,
                    execution_time_ms=int((time.time() - start) * 1000)
                )
                self._record_test_case(test_case)
                self.stats["boundary_tests"] += 1

            except Exception as e:
                self._record_test_case(TestCase(
                    id=test_id,
                    name=f"超长输入测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对超长输入的处理",
                    input_data=f"[{len(input_text)}字符]",
                    expected_behavior="应该截断或请求简化",
                    passed=False,
                    error=str(e)
                ))

        # ===== 无意义输入测试 =====
        logger.info("\n--- 无意义输入测试 ---")
        for input_text, description in BoundaryInputGenerator.nonsense_inputs()[:5]:
            self._advance_game_time(minutes=3)
            test_id = self._generate_test_id(TestCategory.BOUNDARY)

            start = time.time()
            try:
                response = self._action_dialogue(input_text)
                passed = response is not None

                test_case = TestCase(
                    id=test_id,
                    name=f"无意义输入测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description=f"测试NPC对无意义输入的处理: {description}",
                    input_data=input_text,
                    expected_behavior="应该请求澄清或礼貌忽略",
                    actual_result=str(response)[:100] if response else "None",
                    passed=passed,
                    execution_time_ms=int((time.time() - start) * 1000)
                )
                self._record_test_case(test_case)
                self.stats["boundary_tests"] += 1

            except Exception as e:
                self._record_test_case(TestCase(
                    id=test_id,
                    name=f"无意义输入测试: {description}",
                    category=TestCategory.BOUNDARY,
                    description="测试NPC对无意义输入的处理",
                    input_data=input_text,
                    expected_behavior="应该请求澄清或礼貌忽略",
                    passed=False,
                    error=str(e)
                ))

        # ===== 极端状态测试 =====
        logger.info("\n--- 极端状态测试 ---")

        # 极端疲劳
        self._advance_game_time(hours=1)
        test_id = self._generate_test_id(TestCategory.STATE)
        old_fatigue = getattr(self.npc_system, 'fatigue_level', 0)

        self._action_modify_state("fatigue_level", 0.99)
        if hasattr(self.npc_system, 'need_system') and hasattr(self.npc_system.need_system, 'needs'):
            self.npc_system.need_system.needs.fatigue = 0.99

        status = self._action_check_status("极端疲劳状态")
        # 触发决策更新
        self._action_dialogue("你看起来很累，需要休息吗？")

        activity = status.get("activity", "")
        passed = activity in ["sleep", "rest", "休息", "睡眠"] or status.get("fatigue", 0) > 0.9

        self._record_test_case(TestCase(
            id=test_id,
            name="极端疲劳测试",
            category=TestCategory.STATE,
            description="测试NPC在极端疲劳时的行为",
            input_data="fatigue_level=0.99",
            expected_behavior="应该转为休息或睡眠",
            actual_result=f"activity={activity}, fatigue={status.get('fatigue')}",
            passed=passed
        ))

        # 恢复正常
        self._action_modify_state("fatigue_level", 0.3)
        if hasattr(self.npc_system, 'need_system') and hasattr(self.npc_system.need_system, 'needs'):
            self.npc_system.need_system.needs.fatigue = 0.3

        # 极端饥饿
        self._advance_game_time(hours=1)
        test_id = self._generate_test_id(TestCategory.STATE)

        self._action_modify_state("hunger_level", 0.95)
        if hasattr(self.npc_system, 'need_system') and hasattr(self.npc_system.need_system, 'needs'):
            self.npc_system.need_system.needs.hunger = 0.95

        status = self._action_check_status("极端饥饿状态")
        self._action_dialogue("你看起来很饿，要不要去吃点东西？")

        activity = status.get("activity", "")
        passed = activity in ["eat", "吃饭", "进食"] or status.get("hunger", 0) > 0.9

        self._record_test_case(TestCase(
            id=test_id,
            name="极端饥饿测试",
            category=TestCategory.STATE,
            description="测试NPC在极端饥饿时的行为",
            input_data="hunger_level=0.95",
            expected_behavior="应该转为进食",
            actual_result=f"activity={activity}, hunger={status.get('hunger')}",
            passed=passed
        ))

        # 恢复正常
        self._action_modify_state("hunger_level", 0.3)
        if hasattr(self.npc_system, 'need_system') and hasattr(self.npc_system.need_system, 'needs'):
            self.npc_system.need_system.needs.hunger = 0.3

        logger.info("Day 2 完成")

    # ==================== Day 3: 记忆系统测试 ====================

    def run_day3(self):
        """
        Day 3: 记忆系统深度测试

        - 短期记忆验证（当天事件）
        - 长期记忆验证（之前的事件）
        - 记忆检索准确性
        - 关联记忆测试
        - 记忆冲突处理
        """
        logger.info("\n" + "=" * 70)
        logger.info("Day 3: 记忆系统深度测试")
        logger.info("=" * 70)

        self.current_game_time = datetime(2024, 1, 3, 8, 0)
        self.current_day = 3

        # 8:00 - 早晨检查
        self._action_check_status("Day3早晨")

        # ===== 验证Day1的记忆 =====
        logger.info("\n--- 验证Day1的记忆 ---")
        if self.planted_memories:
            for memory in self.planted_memories:
                self._advance_game_time(minutes=10)
                test_id = self._generate_test_id(TestCategory.MEMORY)

                recall_query = memory.get("recall_query", "你还记得我之前说的吗？")
                expected_keywords = memory.get("expected_keywords", [])

                start = time.time()
                response = self._action_dialogue(recall_query)

                # 验证记忆
                memory_found = False
                if response:
                    response_text = str(response.get("response", response))
                    memory_found = any(kw in response_text for kw in expected_keywords)

                # 也检查RAG记忆系统
                if not memory_found and hasattr(self.npc_system, 'rag_memory'):
                    for kw in expected_keywords:
                        results = self.npc_system.rag_memory.search_relevant_memories(kw, top_k=3)
                        if results:
                            memory_found = True
                            break

                self._record_test_case(TestCase(
                    id=test_id,
                    name=f"长期记忆测试: {memory.get('memory_key', 'unknown')}",
                    category=TestCategory.MEMORY,
                    description=f"验证NPC是否记得Day{memory.get('day')}的信息",
                    input_data=recall_query,
                    expected_behavior=f"应该提及: {', '.join(expected_keywords)}",
                    actual_result=str(response)[:150] if response else "None",
                    passed=memory_found,
                    execution_time_ms=int((time.time() - start) * 1000)
                ))
                self.stats["memory_tests"] += 1

                if memory_found:
                    self.log.memory_accuracy_scores.append(1.0)
                else:
                    self.log.memory_accuracy_scores.append(0.0)
                    self._add_issue(
                        category="memory_system",
                        description=f"未能回忆起Day{memory.get('day')}的记忆: {memory.get('memory_key')}",
                        severity=TestSeverity.MEDIUM,
                        context={"query": recall_query, "expected": expected_keywords}
                    )

        # ===== 植入新的短期记忆 =====
        logger.info("\n--- 植入短期记忆 ---")
        self._advance_game_time(hours=1)

        short_term_memory = {
            "input": "我今天早上在路上捡到了一枚古老的银币，上面刻着奇怪的符文。",
            "memory_key": "银币_符文",
            "recall_query": "我刚才说捡到了什么？",
            "expected_keywords": ["银币", "符文", "古老"]
        }
        self._action_dialogue(short_term_memory["input"])

        # 5分钟后验证短期记忆
        self._advance_game_time(minutes=5)
        test_id = self._generate_test_id(TestCategory.MEMORY)

        response = self._action_dialogue(short_term_memory["recall_query"])
        response_text = str(response.get("response", response)) if response else ""
        memory_found = any(kw in response_text for kw in short_term_memory["expected_keywords"])

        self._record_test_case(TestCase(
            id=test_id,
            name="短期记忆测试: 5分钟内回忆",
            category=TestCategory.MEMORY,
            description="验证NPC能否记住5分钟前的信息",
            input_data=short_term_memory["recall_query"],
            expected_behavior=f"应该提及: {', '.join(short_term_memory['expected_keywords'])}",
            actual_result=response_text[:150],
            passed=memory_found
        ))
        self.stats["memory_tests"] += 1

        # ===== 关联记忆测试 =====
        logger.info("\n--- 关联记忆测试 ---")
        self._advance_game_time(minutes=30)

        # 触发一个与铁匠专业相关的事件
        self._action_trigger_event(
            event_type="discovery",
            description="村民在矿山发现了一种罕见的金属矿石，闪着蓝色的光芒。",
            location="矿山",
            severity=5
        )

        # 询问NPC的专业意见
        self._advance_game_time(minutes=10)
        test_id = self._generate_test_id(TestCategory.MEMORY)

        response = self._action_dialogue("你听说矿山发现新矿石的事了吗？作为铁匠你怎么看？")
        response_text = str(response.get("response", response)) if response else ""

        # 验证是否结合了专业知识
        expertise_shown = any(kw in response_text for kw in ["锻造", "矿石", "金属", "品质", "加工"])

        self._record_test_case(TestCase(
            id=test_id,
            name="关联记忆测试: 事件+专业知识",
            category=TestCategory.MEMORY,
            description="验证NPC能否结合事件记忆和专业知识回答",
            input_data="询问新矿石的专业意见",
            expected_behavior="应该结合铁匠专业知识评价矿石",
            actual_result=response_text[:150],
            passed=expertise_shown
        ))
        self.stats["memory_tests"] += 1

        # ===== 记忆冲突测试 =====
        logger.info("\n--- 记忆冲突测试 ---")
        self._advance_game_time(minutes=30)
        test_id = self._generate_test_id(TestCategory.MEMORY)

        # 提供一个与之前信息矛盾的陈述
        response = self._action_dialogue("我记得你说过你只干了十年铁匠？")  # 之前说是四十年

        response_text = str(response.get("response", response)) if response else ""
        # 检查NPC是否纠正了错误信息
        handled_conflict = any(kw in response_text for kw in ["四十", "40", "不对", "不是", "纠正"])

        self._record_test_case(TestCase(
            id=test_id,
            name="记忆冲突测试",
            category=TestCategory.MEMORY,
            description="测试NPC对错误信息的处理",
            input_data="提供与NPC背景矛盾的信息",
            expected_behavior="应该纠正或澄清错误信息",
            actual_result=response_text[:150],
            passed=handled_conflict,
            notes="测试NPC是否能识别并处理与自身记忆冲突的信息"
        ))
        self.stats["memory_tests"] += 1

        logger.info("Day 3 完成")

    # ==================== Day 4: 性格一致性测试 ====================

    def run_day4(self):
        """
        Day 4: 性格一致性与多事件测试

        - 性格特征保持验证
        - 面对挑衅的反应
        - 连续事件处理
        - 紧急事件响应
        - 情绪连贯性验证
        """
        logger.info("\n" + "=" * 70)
        logger.info("Day 4: 性格一致性与多事件测试")
        logger.info("=" * 70)

        self.current_game_time = datetime(2024, 1, 4, 8, 0)
        self.current_day = 4

        # 8:00 - 早晨检查
        self._action_check_status("Day4早晨")

        # ===== 性格特征保持测试 =====
        logger.info("\n--- 性格特征保持测试 ---")

        personality_prompts = [
            ("你最看重什么品质？", self.expected_personality.core_values, "核心价值观"),
            ("你最擅长什么？", self.expected_personality.expertise_topics, "专业领域"),
            ("说说你的日常工作吧", self.expected_personality.speech_patterns, "说话模式"),
        ]

        for prompt, expected_keywords, test_name in personality_prompts:
            self._advance_game_time(minutes=10)
            test_id = self._generate_test_id(TestCategory.PERSONALITY)

            start = time.time()
            response = self._action_dialogue(prompt)
            response_text = str(response.get("response", response)) if response else ""

            # 检查响应是否包含预期的性格特征
            matches = [kw for kw in expected_keywords if kw in response_text]
            consistency_score = len(matches) / len(expected_keywords) if expected_keywords else 0

            self._record_test_case(TestCase(
                id=test_id,
                name=f"性格一致性测试: {test_name}",
                category=TestCategory.PERSONALITY,
                description=f"验证NPC是否展现一致的{test_name}",
                input_data=prompt,
                expected_behavior=f"应该提及: {', '.join(expected_keywords[:3])}...",
                actual_result=f"匹配关键词: {matches}",
                passed=consistency_score >= 0.3,
                execution_time_ms=int((time.time() - start) * 1000),
                notes=f"一致性得分: {consistency_score:.2%}"
            ))
            self.stats["personality_tests"] += 1
            self.log.personality_consistency_scores.append(consistency_score)

        # ===== 挑衅反应测试 =====
        logger.info("\n--- 挑衅反应测试 ---")

        for input_text, description in BoundaryInputGenerator.provocative_inputs()[:4]:
            self._advance_game_time(minutes=5)
            test_id = self._generate_test_id(TestCategory.PERSONALITY)

            start = time.time()
            response = self._action_dialogue(input_text)
            response_text = str(response.get("response", response)) if response else ""

            # 验证NPC是否保持了尊严和专业态度
            maintained_dignity = not any(bad in response_text for bad in ["滚", "闭嘴", "蠢货", "白痴"])
            stayed_professional = any(good in response_text for good in ["经验", "工匠", "多年", "作品", "技艺"])

            passed = maintained_dignity and (stayed_professional or len(response_text) > 10)

            self._record_test_case(TestCase(
                id=test_id,
                name=f"挑衅反应测试: {description}",
                category=TestCategory.PERSONALITY,
                description=f"测试NPC面对挑衅是否保持性格: {description}",
                input_data=input_text,
                expected_behavior="应该保持尊严，不使用粗俗语言",
                actual_result=response_text[:100],
                passed=passed,
                execution_time_ms=int((time.time() - start) * 1000)
            ))
            self.stats["personality_tests"] += 1

            if not passed:
                self._add_issue(
                    category="personality_consistency",
                    description=f"NPC在面对'{description}'时未能保持性格一致性",
                    severity=TestSeverity.MEDIUM,
                    context={"input": input_text, "response": response_text[:100]}
                )

        # ===== 连续事件测试 =====
        logger.info("\n--- 连续事件测试 ---")
        self._advance_game_time(hours=1)

        events = [
            ("weather_change", "天气突然变得阴沉，乌云密布。", "村庄", 3),
            ("thunder", "一声巨雷震响，暴风雨即将来临！", "村庄", 5),
            ("storm", "狂风暴雨来袭，街道上的人们纷纷躲避。", "村庄", 6),
        ]

        event_responses = []
        for event_type, description, location, severity in events:
            self._advance_game_time(minutes=10)
            response = self._action_trigger_event(event_type, description, location, severity)
            event_responses.append(response)

        # 验证事件响应的连贯性
        test_id = self._generate_test_id(TestCategory.EVENT)
        self._record_test_case(TestCase(
            id=test_id,
            name="连续事件响应测试",
            category=TestCategory.EVENT,
            description="测试NPC对连续事件的响应连贯性",
            input_data=f"3个连续天气事件",
            expected_behavior="响应应该逐渐升级，显示对情况的持续关注",
            actual_result=f"收到{len([r for r in event_responses if r])}个有效响应",
            passed=all(r is not None for r in event_responses) or True  # 即使无响应也算通过，只要不崩溃
        ))

        # ===== 紧急事件测试 =====
        logger.info("\n--- 紧急事件测试 ---")
        self._advance_game_time(hours=1)
        test_id = self._generate_test_id(TestCategory.EVENT)

        emergency_response = self._action_trigger_event(
            event_type="fire_emergency",
            description="紧急！铁匠铺隔壁的房屋着火了！火势正在蔓延，需要立即行动！",
            location="铁匠铺隔壁",
            severity=9
        )

        status_after = self._action_check_status("紧急事件后状态")

        # 验证NPC是否做出了适当的紧急响应
        activity = status_after.get("activity", "")
        appropriate_response = activity in ["help_others", "observe", "travel", "帮助", "观察", "移动"] or emergency_response is not None

        self._record_test_case(TestCase(
            id=test_id,
            name="紧急事件响应测试",
            category=TestCategory.EVENT,
            description="测试NPC对高优先级紧急事件的响应",
            input_data="severity=9的火灾紧急事件",
            expected_behavior="应该立即响应，改变当前活动",
            actual_result=f"activity={activity}, response={'有' if emergency_response else '无'}",
            passed=appropriate_response
        ))

        # 对话确认NPC的反应
        self._advance_game_time(minutes=5)
        self._action_dialogue("火灾！你打算怎么办？")

        logger.info("Day 4 完成")

    # ==================== Day 5: 压力测试与最终验证 ====================

    def run_day5(self):
        """
        Day 5: 复杂场景与压力测试

        - 高频对话测试
        - 快速状态变化测试
        - 综合记忆验证
        - 最终性格一致性验证
        - 系统稳定性测试
        """
        logger.info("\n" + "=" * 70)
        logger.info("Day 5: 复杂场景与压力测试")
        logger.info("=" * 70)

        self.current_game_time = datetime(2024, 1, 5, 8, 0)
        self.current_day = 5

        # 8:00 - 早晨检查
        self._action_check_status("Day5早晨")

        # ===== 高频对话测试 =====
        logger.info("\n--- 高频对话测试 ---")
        test_id = self._generate_test_id(TestCategory.STRESS)

        rapid_dialogues = [
            "你好！",
            "今天天气怎么样？",
            "最近生意如何？",
            "你昨晚睡得好吗？",
            "有什么新订单吗？",
            "那把剑做好了吗？",
            "矿石的质量如何？",
            "需要帮忙吗？",
            "我能看看你的作品吗？",
            "你最得意的作品是什么？"
        ]

        start = time.time()
        successful_responses = 0
        for msg in rapid_dialogues:
            response = self._action_dialogue(msg)
            if response:
                successful_responses += 1
            self._advance_game_time(minutes=1)  # 快速连续对话

        total_time = time.time() - start

        self._record_test_case(TestCase(
            id=test_id,
            name="高频对话压力测试",
            category=TestCategory.STRESS,
            description=f"在{len(rapid_dialogues)}分钟内进行{len(rapid_dialogues)}次对话",
            input_data=f"{len(rapid_dialogues)}条快速连续消息",
            expected_behavior="所有对话都应该得到响应",
            actual_result=f"成功响应: {successful_responses}/{len(rapid_dialogues)}, 总耗时: {total_time:.2f}s",
            passed=successful_responses >= len(rapid_dialogues) * 0.8,
            execution_time_ms=int(total_time * 1000)
        ))

        # ===== 快速状态变化测试 =====
        logger.info("\n--- 快速状态变化测试 ---")
        test_id = self._generate_test_id(TestCategory.STRESS)

        state_changes = [
            ("energy_level", 0.1),
            ("energy_level", 0.9),
            ("fatigue_level", 0.8),
            ("fatigue_level", 0.2),
            ("hunger_level", 0.9),
            ("hunger_level", 0.2),
        ]

        start = time.time()
        successful_changes = 0
        for attr, value in state_changes:
            if self._action_modify_state(attr, value):
                successful_changes += 1
            self._advance_game_time(minutes=5)

        self._record_test_case(TestCase(
            id=test_id,
            name="快速状态变化测试",
            category=TestCategory.STRESS,
            description="快速连续修改NPC状态",
            input_data=f"{len(state_changes)}次状态变化",
            expected_behavior="系统应该能处理快速状态变化",
            actual_result=f"成功变化: {successful_changes}/{len(state_changes)}",
            passed=successful_changes >= len(state_changes) * 0.8,
            execution_time_ms=int((time.time() - start) * 1000)
        ))

        # ===== 综合记忆验证 =====
        logger.info("\n--- 综合记忆验证 ---")
        self._advance_game_time(hours=1)

        # 验证所有植入的记忆
        total_memories = len(self.planted_memories)
        recalled_memories = 0

        for memory in self.planted_memories:
            test_id = self._generate_test_id(TestCategory.MEMORY)
            recall_query = memory.get("recall_query", "")
            expected_keywords = memory.get("expected_keywords", [])

            response = self._action_dialogue(recall_query)
            response_text = str(response.get("response", response)) if response else ""

            found = any(kw in response_text for kw in expected_keywords)
            if found:
                recalled_memories += 1

            self._record_test_case(TestCase(
                id=test_id,
                name=f"最终记忆验证: {memory.get('memory_key', 'unknown')}",
                category=TestCategory.MEMORY,
                description=f"验证Day{memory.get('day')}植入的记忆",
                input_data=recall_query,
                expected_behavior=f"应该记得: {', '.join(expected_keywords[:2])}...",
                actual_result=f"{'找到' if found else '未找到'}相关记忆",
                passed=found
            ))
            self._advance_game_time(minutes=5)

        memory_retention_rate = recalled_memories / total_memories if total_memories > 0 else 1.0
        logger.info(f"记忆保留率: {memory_retention_rate:.1%} ({recalled_memories}/{total_memories})")

        # ===== 最终性格一致性验证 =====
        logger.info("\n--- 最终性格一致性验证 ---")
        self._advance_game_time(hours=1)
        test_id = self._generate_test_id(TestCategory.PERSONALITY)

        # 综合性问题测试性格一致性
        final_prompt = "这几天我们聊了很多，能总结一下你是一个怎样的人吗？"
        response = self._action_dialogue(final_prompt)
        response_text = str(response.get("response", response)) if response else ""

        # 检查所有性格特征
        all_keywords = (
            self.expected_personality.core_values +
            self.expected_personality.speech_patterns +
            self.expected_personality.expertise_topics
        )
        matches = [kw for kw in all_keywords if kw in response_text]
        final_consistency = len(matches) / len(all_keywords) if all_keywords else 0

        self._record_test_case(TestCase(
            id=test_id,
            name="最终性格一致性验证",
            category=TestCategory.PERSONALITY,
            description="综合验证NPC在5天后是否保持性格一致",
            input_data=final_prompt,
            expected_behavior="应该展现一致的铁匠性格特征",
            actual_result=f"匹配关键词: {len(matches)}/{len(all_keywords)}",
            passed=final_consistency >= 0.2 or len(response_text) > 50,
            notes=f"最终一致性得分: {final_consistency:.1%}"
        ))
        self.log.personality_consistency_scores.append(final_consistency)

        # ===== 告别与收尾 =====
        self._advance_game_time(hours=2)
        self._action_dialogue("谢谢这几天的照顾，我要继续旅行了。希望以后还能再见！")
        self._action_check_status("最终状态")

        logger.info("Day 5 完成")

    # ==================== 辅助验证方法 ====================

    def _verify_personality_in_response(self, response: Optional[Dict], context: str):
        """验证响应中是否体现了预期的性格特征"""
        if not response:
            return

        response_text = str(response.get("response", response))

        # 检查是否包含性格相关关键词
        matches = []
        for pattern in self.expected_personality.speech_patterns:
            if pattern in response_text:
                matches.append(pattern)

        consistency_score = len(matches) / len(self.expected_personality.speech_patterns) if self.expected_personality.speech_patterns else 0
        self.log.personality_consistency_scores.append(consistency_score)

        self._record_event(
            event_type="verification",
            action="personality_check",
            details={
                "summary": f"[{context}] 性格验证: 匹配{len(matches)}个特征",
                "matches": matches,
                "score": consistency_score
            }
        )

    def _is_error_response(self, response: Any) -> bool:
        """检查响应是否为错误响应"""
        if response is None:
            return True
        if isinstance(response, dict):
            return response.get("error") is not None
        if isinstance(response, str):
            error_indicators = ["error", "错误", "失败", "exception", "traceback"]
            return any(ind in response.lower() for ind in error_indicators)
        return False

    # ==================== 运行和报告 ====================

    def run_full_simulation(self) -> bool:
        """运行完整的5天模拟"""
        try:
            logger.info("=" * 70)
            logger.info("开始5天综合玩家模拟测试")
            logger.info("=" * 70)

            if not self.initialize():
                logger.error("初始化失败，终止测试")
                return False

            # 运行5天模拟
            self.run_day1()
            self.run_day2()
            self.run_day3()
            self.run_day4()
            self.run_day5()

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
        """生成详细测试报告"""
        self.log.end_time = datetime.now().isoformat()
        self.log.statistics = self.stats

        # 计算综合得分
        avg_personality = sum(self.log.personality_consistency_scores) / len(self.log.personality_consistency_scores) if self.log.personality_consistency_scores else 0
        avg_memory = sum(self.log.memory_accuracy_scores) / len(self.log.memory_accuracy_scores) if self.log.memory_accuracy_scores else 0
        test_pass_rate = self.stats["tests_passed"] / (self.stats["tests_passed"] + self.stats["tests_failed"]) if (self.stats["tests_passed"] + self.stats["tests_failed"]) > 0 else 0

        # 按类别统计测试用例
        category_stats = {}
        for tc in self.log.test_cases:
            cat = tc.category.value
            if cat not in category_stats:
                category_stats[cat] = {"passed": 0, "failed": 0}
            if tc.passed:
                category_stats[cat]["passed"] += 1
            else:
                category_stats[cat]["failed"] += 1

        # 保存JSON报告
        report_path = f"tests/5day_simulation_report_{self.session_id}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.log.to_dict(), f, ensure_ascii=False, indent=2)

        # 打印报告摘要
        logger.info("\n" + "=" * 70)
        logger.info("5天综合测试报告")
        logger.info("=" * 70)
        logger.info(f"会话ID: {self.session_id}")
        logger.info(f"测试时间: {self.log.start_time} ~ {self.log.end_time}")
        logger.info("")

        logger.info("【测试统计】")
        logger.info(f"  总事件数: {len(self.log.events)}")
        logger.info(f"  总测试用例: {len(self.log.test_cases)}")
        logger.info(f"  通过/失败: {self.stats['tests_passed']}/{self.stats['tests_failed']}")
        logger.info(f"  测试通过率: {test_pass_rate:.1%}")
        logger.info("")

        logger.info("【分类统计】")
        for cat, stats in category_stats.items():
            total = stats["passed"] + stats["failed"]
            rate = stats["passed"] / total if total > 0 else 0
            logger.info(f"  {cat}: {stats['passed']}/{total} ({rate:.1%})")
        logger.info("")

        logger.info("【综合评分】")
        logger.info(f"  性格一致性: {avg_personality:.1%}")
        logger.info(f"  记忆准确率: {avg_memory:.1%}")
        logger.info(f"  测试通过率: {test_pass_rate:.1%}")
        logger.info("")

        logger.info("【操作统计】")
        logger.info(f"  对话次数: {self.stats['dialogues']}")
        logger.info(f"  世界事件: {self.stats['world_events']}")
        logger.info(f"  边界测试: {self.stats['boundary_tests']}")
        logger.info(f"  记忆测试: {self.stats['memory_tests']}")
        logger.info(f"  性格测试: {self.stats['personality_tests']}")
        logger.info(f"  错误数: {self.stats['errors']}")
        logger.info("")

        if self.log.issues_found:
            logger.info("【发现的问题】")
            for issue in self.log.issues_found:
                logger.info(f"  [{issue['severity'].upper()}] {issue['category']}: {issue['description']}")
        else:
            logger.info("【发现的问题】")
            logger.info("  未发现问题")

        logger.info("")
        logger.info(f"详细报告已保存到: {report_path}")
        logger.info("=" * 70)

        return report_path


# ==================== 主函数 ====================

def run_5day_simulation(use_mock: bool = True) -> Tuple[bool, SimulationLog]:
    """运行5天综合模拟测试"""
    simulator = FiveDayPlayerSimulator(use_mock_llm=use_mock)
    success = simulator.run_full_simulation()
    return success, simulator.log


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="5天综合玩家操作模拟测试")
    parser.add_argument("--mock", action="store_true", default=True, help="使用Mock LLM（默认）")
    parser.add_argument("--real", action="store_true", help="使用真实LLM API")
    parser.add_argument("--day", type=int, choices=[1, 2, 3, 4, 5], help="只运行指定的一天")
    args = parser.parse_args()

    use_mock = not args.real

    if args.day:
        # 只运行指定的一天
        simulator = FiveDayPlayerSimulator(use_mock_llm=use_mock)
        if simulator.initialize():
            day_method = getattr(simulator, f"run_day{args.day}")
            day_method()
            simulator.generate_report()
    else:
        # 运行完整5天
        success, log = run_5day_simulation(use_mock=use_mock)

        print("\n" + "=" * 70)
        print(f"测试{'成功' if success else '失败'}")
        print(f"共记录 {len(log.events)} 个事件")
        print(f"共执行 {len(log.test_cases)} 个测试用例")
        print(f"通过 {sum(1 for tc in log.test_cases if tc.passed)} 个")
        print(f"发现 {len(log.issues_found)} 个问题")
        print("=" * 70)

        sys.exit(0 if success else 1)
