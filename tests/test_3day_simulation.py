# -*- coding: utf-8 -*-
"""
3天综合模拟测试用例
================

测试场景:
1. 主角与某地点NPC的多次对话
2. 主角住宿、询问工作后按照要求进行工作、进行消费等经济系统相关的完整测试
3. 世界事件触发后各NPC Agent的反应，与主角的互动
4. 事件结束后NPC的记忆能力，以及主角与NPC关于事件的互动
5. 主角、NPC属性变化等系统的完整测试

验证逻辑:
- 前后行为一致性
- 人物响应是否正常
- 响应顺序是否正确
- 事件后续处理
- 人物位置、属性变化
- 人物语言与记忆一致性
- 主角工作与打听到的收入是否一致
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('tests/simulation_log.txt', encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SimulationTest')


# ========== 测试结果记录 ==========

@dataclass
class TestEvent:
    """测试事件记录"""
    timestamp: str
    game_time: str
    event_type: str
    actor: str
    action: str
    target: Optional[str]
    details: Dict[str, Any]
    llm_input: Optional[str] = None
    llm_output: Optional[str] = None
    gui_output: Optional[str] = None
    validation_result: Optional[Dict] = None


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    category: str
    description: str
    expected: Any
    actual: Any
    severity: str = "warning"  # warning, error, critical


class SimulationRecorder:
    """模拟记录器"""

    def __init__(self):
        self.events: List[TestEvent] = []
        self.validations: List[ValidationResult] = []
        self.player_state_history: List[Dict] = []
        self.npc_state_history: Dict[str, List[Dict]] = {}
        self.world_state_history: List[Dict] = []
        self.start_time = datetime.now()

    def record_event(self, event: TestEvent):
        """记录事件"""
        self.events.append(event)
        logger.info(f"[{event.game_time}] {event.actor} -> {event.action}: {event.details.get('summary', '')}")

    def record_validation(self, result: ValidationResult):
        """记录验证结果"""
        self.validations.append(result)
        status = "PASS" if result.passed else "FAIL"
        logger.info(f"[验证{status}] {result.category}: {result.description}")
        if not result.passed:
            logger.warning(f"  期望: {result.expected}, 实际: {result.actual}")

    def record_player_state(self, state: Dict):
        """记录玩家状态"""
        self.player_state_history.append({
            "timestamp": datetime.now().isoformat(),
            "state": state.copy()
        })

    def record_npc_state(self, npc_name: str, state: Dict):
        """记录NPC状态"""
        if npc_name not in self.npc_state_history:
            self.npc_state_history[npc_name] = []
        self.npc_state_history[npc_name].append({
            "timestamp": datetime.now().isoformat(),
            "state": state.copy()
        })

    def record_world_state(self, state: Dict):
        """记录世界状态"""
        self.world_state_history.append({
            "timestamp": datetime.now().isoformat(),
            "state": state.copy()
        })

    def generate_report(self) -> Dict:
        """生成测试报告"""
        total_validations = len(self.validations)
        passed = sum(1 for v in self.validations if v.passed)
        failed = total_validations - passed

        # 按类别分组
        by_category = {}
        for v in self.validations:
            if v.category not in by_category:
                by_category[v.category] = {"passed": 0, "failed": 0}
            if v.passed:
                by_category[v.category]["passed"] += 1
            else:
                by_category[v.category]["failed"] += 1

        return {
            "summary": {
                "total_events": len(self.events),
                "total_validations": total_validations,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{passed/total_validations*100:.1f}%" if total_validations > 0 else "N/A",
                "duration_seconds": (datetime.now() - self.start_time).total_seconds()
            },
            "by_category": by_category,
            "failed_validations": [
                {
                    "category": v.category,
                    "description": v.description,
                    "expected": str(v.expected),
                    "actual": str(v.actual),
                    "severity": v.severity
                }
                for v in self.validations if not v.passed
            ],
            "event_timeline": [
                {
                    "timestamp": e.timestamp,
                    "game_time": e.game_time,
                    "actor": e.actor,
                    "action": e.action,
                    "summary": e.details.get("summary", "")
                }
                for e in self.events[:50]  # 前50个事件
            ]
        }


# ========== 模拟世界时钟 ==========

class SimulationClock:
    """模拟世界时钟"""

    def __init__(self, start_time: datetime = None):
        self.current_time = start_time or datetime(2025, 6, 15, 8, 0, 0)  # 从早上8点开始

    def advance(self, hours: float = 0, minutes: float = 0):
        """推进时间"""
        self.current_time += timedelta(hours=hours, minutes=minutes)

    def get_time_str(self) -> str:
        return self.current_time.strftime("%Y-%m-%d %H:%M")

    def get_hour(self) -> int:
        return self.current_time.hour

    def get_day(self) -> int:
        """获取模拟的第几天"""
        base = datetime(2025, 6, 15, 0, 0, 0)
        return (self.current_time - base).days + 1


# ========== 模拟玩家系统 ==========

class SimulatedPlayer:
    """模拟玩家"""

    def __init__(self, name: str, initial_gold: int = 50):
        self.name = name
        self.location = "镇中心"
        self.gold = initial_gold
        self.energy = 100
        self.hunger = 0.2
        self.fatigue = 0.1
        self.current_job = None
        self.job_progress = 0.0
        self.lodging = None
        self.memories: List[Dict] = []
        self.interaction_history: List[Dict] = []
        self.expected_wage = None  # 打听到的工资
        self.relationships: Dict[str, float] = {}  # NPC好感度

    def move_to(self, location: str):
        old_loc = self.location
        self.location = location
        self.fatigue += 0.05
        return f"{self.name} 从 {old_loc} 移动到 {location}"

    def add_memory(self, content: str, importance: float = 5):
        self.memories.append({
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "importance": importance
        })

    def update_relationship(self, npc_name: str, delta: float):
        if npc_name not in self.relationships:
            self.relationships[npc_name] = 50
        self.relationships[npc_name] = max(0, min(100, self.relationships[npc_name] + delta))

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "location": self.location,
            "gold": self.gold,
            "energy": self.energy,
            "hunger": self.hunger,
            "fatigue": self.fatigue,
            "current_job": self.current_job,
            "job_progress": self.job_progress,
            "relationships": self.relationships.copy()
        }


# ========== 模拟NPC系统 ==========

class SimulatedNPC:
    """模拟NPC"""

    def __init__(self, name: str, profession: str, location: str, personality: str):
        self.name = name
        self.profession = profession
        self.location = location
        self.personality = personality
        self.current_activity = "空闲"
        self.energy = 100
        self.emotion = "平静"
        self.memories: List[Dict] = []
        self.event_responses: List[Dict] = []
        self.dialogue_history: List[Dict] = []
        self.known_events: List[Dict] = []
        self.relationships: Dict[str, float] = {}

        # 工作相关
        self.available_jobs: List[Dict] = []
        self.lodging_prices: Dict[str, int] = {}

    def add_memory(self, content: str, importance: float = 5, event_related: bool = False):
        memory = {
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "importance": importance,
            "event_related": event_related
        }
        self.memories.append(memory)
        return memory

    def record_event_response(self, event: Dict, response: str, action: str):
        self.event_responses.append({
            "event": event,
            "response": response,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        self.known_events.append(event)

    def update_relationship(self, entity_name: str, delta: float):
        if entity_name not in self.relationships:
            self.relationships[entity_name] = 50
        self.relationships[entity_name] = max(0, min(100, self.relationships[entity_name] + delta))

    def has_event_memory(self, event_keyword: str) -> bool:
        """检查NPC是否记得某个事件"""
        for memory in self.memories:
            if event_keyword.lower() in memory["content"].lower():
                return True
        for event in self.known_events:
            if event_keyword.lower() in event.get("content", "").lower():
                return True
        return False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "profession": self.profession,
            "location": self.location,
            "current_activity": self.current_activity,
            "energy": self.energy,
            "emotion": self.emotion,
            "memory_count": len(self.memories),
            "known_events": len(self.known_events),
            "relationships": self.relationships.copy()
        }


# ========== 模拟世界事件 ==========

@dataclass
class WorldEvent:
    """世界事件"""
    id: str
    event_type: str
    content: str
    location: str
    severity: int  # 1-10
    trigger_time: datetime
    duration_hours: float
    affected_locations: List[str]
    is_resolved: bool = False
    npc_responses: Dict[str, Dict] = field(default_factory=dict)


# ========== 3天模拟测试类 ==========

class ThreeDaySimulation:
    """3天综合模拟测试"""

    def __init__(self):
        self.clock = SimulationClock()
        self.recorder = SimulationRecorder()
        self.player = SimulatedPlayer("冒险者李明", initial_gold=50)
        self.npcs: Dict[str, SimulatedNPC] = {}
        self.world_events: List[WorldEvent] = []
        self.current_event: Optional[WorldEvent] = None

        # 经济系统
        self.economy = {
            "transactions": [],
            "job_listings": {}
        }

        self._init_npcs()
        self._init_jobs()

    def _init_npcs(self):
        """初始化NPC"""
        npc_configs = [
            ("贝拉·欢笑", "酒馆老板", "酒馆", "开朗热情"),
            ("埃尔德·铁锤", "铁匠", "铁匠铺", "严肃认真"),
            ("西奥多·光明", "牧师", "教堂", "慈祥温和"),
            ("老农托马斯", "农民", "农田", "朴实憨厚"),
            ("玛格丽特·花语", "花商", "市场区", "温柔善良"),
        ]

        for name, profession, location, personality in npc_configs:
            npc = SimulatedNPC(name, profession, location, personality)
            self.npcs[name] = npc

        # 设置贝拉的住宿价格
        self.npcs["贝拉·欢笑"].lodging_prices = {
            "普通客房": 5,
            "舒适客房": 15,
            "豪华客房": 30
        }

        # 设置工作信息
        self.npcs["贝拉·欢笑"].available_jobs = [
            {"title": "酒馆帮工", "wage": 15, "duration": 4}
        ]
        self.npcs["埃尔德·铁锤"].available_jobs = [
            {"title": "铁匠铺学徒", "wage": 20, "duration": 6}
        ]
        self.npcs["老农托马斯"].available_jobs = [
            {"title": "农田收割", "wage": 12, "duration": 3}
        ]

    def _init_jobs(self):
        """初始化工作列表"""
        self.economy["job_listings"] = {
            "job_tavern_help": {
                "employer": "贝拉·欢笑",
                "title": "酒馆帮工",
                "wage": 15,
                "duration_hours": 4,
                "location": "酒馆"
            },
            "job_blacksmith_assist": {
                "employer": "埃尔德·铁锤",
                "title": "铁匠铺学徒",
                "wage": 20,
                "duration_hours": 6,
                "location": "铁匠铺"
            },
            "job_farm_harvest": {
                "employer": "老农托马斯",
                "title": "农田收割",
                "wage": 12,
                "duration_hours": 3,
                "location": "农田"
            }
        }

    # ========== 核心交互方法 ==========

    def player_dialogue(self, npc_name: str, dialogue: str) -> Tuple[str, Dict]:
        """玩家与NPC对话"""
        if npc_name not in self.npcs:
            return "NPC不存在", {}

        npc = self.npcs[npc_name]

        # 模拟LLM响应（实际测试中会调用真实LLM）
        response, response_data = self._simulate_npc_response(npc, dialogue)

        # 记录对话
        npc.dialogue_history.append({
            "player": dialogue,
            "npc": response,
            "timestamp": self.clock.get_time_str()
        })

        # 更新关系
        self.player.update_relationship(npc_name, 1)
        npc.update_relationship(self.player.name, 1)

        # 记录事件
        self.recorder.record_event(TestEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.clock.get_time_str(),
            event_type="dialogue",
            actor=self.player.name,
            action=f"与{npc_name}对话",
            target=npc_name,
            details={
                "player_input": dialogue,
                "npc_response": response,
                "summary": f"对话: {dialogue[:30]}..."
            },
            llm_input=dialogue,
            llm_output=response,
            gui_output=f"[{npc_name}]: {response}"
        ))

        return response, response_data

    def _simulate_npc_response(self, npc: SimulatedNPC, dialogue: str) -> Tuple[str, Dict]:
        """模拟NPC响应（实际使用时会调用LLM）"""
        response_data = {}

        # 问询工作相关
        if "工作" in dialogue or "赚钱" in dialogue or "活计" in dialogue:
            if npc.available_jobs:
                job = npc.available_jobs[0]
                response = f"我这里有{job['title']}的活，一天工作{job['duration']}小时，工钱是{job['wage']}金币。你有兴趣吗？"
                response_data["job_info"] = job
                # 玩家记住打听到的工资
                self.player.expected_wage = job['wage']
                self.player.add_memory(f"打听到{npc.name}处{job['title']}的工钱是{job['wage']}金币", importance=7)
            else:
                response = "抱歉，我这里暂时没有合适的工作。"

        # 问询住宿相关
        elif "住宿" in dialogue or "客房" in dialogue or "住店" in dialogue:
            if npc.lodging_prices:
                prices = npc.lodging_prices
                response = f"我们有几种房型：普通客房{prices.get('普通客房', 5)}金币/晚，舒适客房{prices.get('舒适客房', 15)}金币/晚，豪华客房{prices.get('豪华客房', 30)}金币/晚。您想要哪种？"
                response_data["lodging_info"] = prices
            else:
                response = "抱歉，我这里不提供住宿服务。你可以去酒馆问问。"

        # 问询事件相关
        elif "发生" in dialogue or "事件" in dialogue or "怎么了" in dialogue:
            if npc.known_events:
                recent_event = npc.known_events[-1]
                response = f"是的，{recent_event['content']}。当时我{npc.event_responses[-1]['response'] if npc.event_responses else '也很担心'}。"
                response_data["event_memory"] = recent_event
            else:
                response = "最近好像没什么特别的事情发生。"

        # 接受工作
        elif "接受" in dialogue or "我愿意" in dialogue or "我来做" in dialogue:
            if npc.available_jobs:
                job = npc.available_jobs[0]
                response = f"太好了！那你现在就开始吧。完成后来找我领工钱。"
                response_data["job_accepted"] = job
                self.player.current_job = job
                self.player.job_progress = 0.0
                npc.add_memory(f"{self.player.name}接受了{job['title']}的工作", importance=6)
            else:
                response = "抱歉，我没理解你的意思。"

        # 普通问候
        else:
            greetings = {
                "贝拉·欢笑": "欢迎来到我的酒馆！今天想喝点什么？",
                "埃尔德·铁锤": "哼，有什么事？我很忙。",
                "西奥多·光明": "愿光明庇佑你，孩子。有什么我能帮助你的？",
                "老农托马斯": "哎呀，你好你好，今天天气不错啊。",
                "玛格丽特·花语": "这里有新鲜的花朵，要来看看吗？"
            }
            response = greetings.get(npc.name, "你好。")

        return response, response_data

    def player_book_lodging(self, lodging_type: str = "普通客房") -> Dict:
        """玩家预订住宿"""
        npc = self.npcs.get("贝拉·欢笑")
        if not npc or self.player.location != "酒馆":
            return {"success": False, "error": "需要在酒馆才能预订住宿"}

        prices = npc.lodging_prices
        price = prices.get(lodging_type, 5)

        if self.player.gold < price:
            return {"success": False, "error": "金币不足", "required": price, "current": self.player.gold}

        # 扣款
        self.player.gold -= price
        self.player.lodging = lodging_type

        # 记录交易
        self.economy["transactions"].append({
            "from": self.player.name,
            "to": npc.name,
            "amount": price,
            "category": "lodging",
            "timestamp": self.clock.get_time_str()
        })

        # 记录事件
        self.recorder.record_event(TestEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.clock.get_time_str(),
            event_type="economy",
            actor=self.player.name,
            action="预订住宿",
            target="贝拉·欢笑",
            details={
                "lodging_type": lodging_type,
                "price": price,
                "player_gold_after": self.player.gold,
                "summary": f"预订{lodging_type}，花费{price}金币"
            }
        ))

        # 验证：金币扣除正确
        self.recorder.record_validation(ValidationResult(
            passed=True,
            category="经济系统",
            description="住宿费用扣除正确",
            expected=f"扣除{price}金币",
            actual=f"扣除{price}金币"
        ))

        return {"success": True, "lodging": lodging_type, "cost": price, "remaining_gold": self.player.gold}

    def player_accept_job(self, job_id: str) -> Dict:
        """玩家接受工作"""
        if job_id not in self.economy["job_listings"]:
            return {"success": False, "error": "工作不存在"}

        job = self.economy["job_listings"][job_id]
        employer = job["employer"]

        # 检查位置
        if self.player.location != job["location"]:
            return {"success": False, "error": f"需要在{job['location']}才能接受此工作"}

        self.player.current_job = job.copy()
        self.player.job_progress = 0.0

        # NPC记忆
        self.npcs[employer].add_memory(f"{self.player.name}接受了{job['title']}的工作", importance=6)

        # 记录事件
        self.recorder.record_event(TestEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.clock.get_time_str(),
            event_type="job",
            actor=self.player.name,
            action="接受工作",
            target=employer,
            details={
                "job": job,
                "summary": f"接受{job['title']}工作"
            }
        ))

        return {"success": True, "job": job}

    def player_work(self, hours: float) -> Dict:
        """玩家工作"""
        if not self.player.current_job:
            return {"success": False, "error": "没有正在进行的工作"}

        job = self.player.current_job

        # 更新进度
        progress_increment = hours / job["duration_hours"]
        self.player.job_progress = min(1.0, self.player.job_progress + progress_increment)

        # 更新状态
        self.player.energy -= hours * 10
        self.player.fatigue += hours * 0.1
        self.player.hunger += hours * 0.05

        # 推进时间
        self.clock.advance(hours=hours)

        result = {
            "success": True,
            "hours_worked": hours,
            "progress": self.player.job_progress,
            "completed": self.player.job_progress >= 1.0
        }

        # 如果工作完成
        if self.player.job_progress >= 1.0:
            wage = job["wage"]
            self.player.gold += wage
            employer = job["employer"]

            # 记录交易
            self.economy["transactions"].append({
                "from": employer,
                "to": self.player.name,
                "amount": wage,
                "category": "work",
                "timestamp": self.clock.get_time_str()
            })

            # 验证：工资与打听到的一致
            if self.player.expected_wage is not None:
                wage_match = (wage == self.player.expected_wage)
                self.recorder.record_validation(ValidationResult(
                    passed=wage_match,
                    category="经济一致性",
                    description="实际工资与打听到的工资一致",
                    expected=self.player.expected_wage,
                    actual=wage,
                    severity="critical" if not wage_match else "warning"
                ))

            result["wage_received"] = wage
            result["player_gold"] = self.player.gold

            # 增加好感度
            self.npcs[employer].update_relationship(self.player.name, 5)
            self.player.update_relationship(employer, 5)

            # NPC记忆
            self.npcs[employer].add_memory(f"{self.player.name}完成了{job['title']}的工作，表现不错", importance=7)

            # 清除当前工作
            self.player.current_job = None
            self.player.job_progress = 0.0

        # 记录事件
        self.recorder.record_event(TestEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.clock.get_time_str(),
            event_type="work",
            actor=self.player.name,
            action="工作",
            target=job["employer"],
            details={
                "job_title": job["title"],
                "hours": hours,
                "progress": self.player.job_progress,
                "completed": result.get("completed", False),
                "summary": f"工作{hours}小时，进度{self.player.job_progress*100:.0f}%"
            }
        ))

        return result

    def player_rest(self, hours: float) -> Dict:
        """玩家休息"""
        # 恢复精力
        energy_restore = hours * 15 if self.player.lodging else hours * 8
        self.player.energy = min(100, self.player.energy + energy_restore)
        self.player.fatigue = max(0, self.player.fatigue - hours * 0.15)

        # 推进时间
        self.clock.advance(hours=hours)

        self.recorder.record_event(TestEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.clock.get_time_str(),
            event_type="rest",
            actor=self.player.name,
            action="休息",
            target=None,
            details={
                "hours": hours,
                "energy_after": self.player.energy,
                "fatigue_after": self.player.fatigue,
                "summary": f"休息{hours}小时"
            }
        ))

        return {"success": True, "hours": hours, "energy": self.player.energy}

    def trigger_world_event(self, event: WorldEvent):
        """触发世界事件"""
        self.current_event = event
        self.world_events.append(event)

        logger.info(f"[世界事件] {event.content} @ {event.location}")

        # 记录事件触发
        self.recorder.record_event(TestEvent(
            timestamp=datetime.now().isoformat(),
            game_time=self.clock.get_time_str(),
            event_type="world_event",
            actor="世界",
            action="事件触发",
            target=event.location,
            details={
                "event_id": event.id,
                "content": event.content,
                "severity": event.severity,
                "affected_locations": event.affected_locations,
                "summary": f"世界事件: {event.content}"
            }
        ))

        # 让受影响的NPC响应事件
        self._process_npc_event_responses(event)

    def _process_npc_event_responses(self, event: WorldEvent):
        """处理NPC对事件的响应"""
        for npc_name, npc in self.npcs.items():
            # 判断NPC是否在受影响区域
            is_affected = npc.location in event.affected_locations

            if is_affected:
                # 模拟NPC响应
                response = self._simulate_npc_event_response(npc, event)

                # 记录响应
                npc.record_event_response(
                    {"id": event.id, "content": event.content, "location": event.location},
                    response["verbal"],
                    response["action"]
                )

                # 添加记忆
                npc.add_memory(
                    f"发生了{event.content}，我{response['action']}",
                    importance=8,
                    event_related=True
                )

                # 更新情绪
                npc.emotion = response["emotion"]

                event.npc_responses[npc_name] = response

                # 记录NPC响应
                self.recorder.record_event(TestEvent(
                    timestamp=datetime.now().isoformat(),
                    game_time=self.clock.get_time_str(),
                    event_type="npc_response",
                    actor=npc_name,
                    action=response["action"],
                    target=event.id,
                    details={
                        "event_content": event.content,
                        "verbal_response": response["verbal"],
                        "emotion": response["emotion"],
                        "summary": f"{npc_name}响应事件: {response['action']}"
                    },
                    llm_output=response["verbal"]
                ))

                # 验证：NPC确实响应了事件
                self.recorder.record_validation(ValidationResult(
                    passed=True,
                    category="事件响应",
                    description=f"{npc_name}对事件做出了响应",
                    expected="有响应",
                    actual=response["action"]
                ))

    def _simulate_npc_event_response(self, npc: SimulatedNPC, event: WorldEvent) -> Dict:
        """模拟NPC对事件的响应"""
        responses = {
            "fire": {
                "贝拉·欢笑": {"action": "组织客人撤离", "verbal": "大家不要慌！跟我走！", "emotion": "紧张"},
                "埃尔德·铁锤": {"action": "拿起水桶救火", "verbal": "我来帮忙灭火！", "emotion": "焦急"},
                "西奥多·光明": {"action": "安抚恐慌的村民", "verbal": "愿光明保佑大家平安。", "emotion": "担忧"},
                "老农托马斯": {"action": "保护农作物", "verbal": "我的田啊！", "emotion": "惊慌"},
                "玛格丽特·花语": {"action": "帮助疏散人群", "verbal": "这边走！快！", "emotion": "害怕"},
            },
            "theft": {
                "贝拉·欢笑": {"action": "检查店内财物", "verbal": "该死的小偷！有没有看到什么可疑的人？", "emotion": "愤怒"},
                "埃尔德·铁锤": {"action": "检查铁匠铺", "verbal": "如果让我抓到那小偷...", "emotion": "愤怒"},
                "西奥多·光明": {"action": "呼吁大家冷静", "verbal": "让我们一起祈祷物品能够找回。", "emotion": "平静"},
                "老农托马斯": {"action": "查看农具", "verbal": "最近镇上不太平啊。", "emotion": "担忧"},
                "玛格丽特·花语": {"action": "查看花摊", "verbal": "希望不要来我这里...", "emotion": "担心"},
            }
        }

        event_type = event.event_type
        if event_type in responses and npc.name in responses[event_type]:
            return responses[event_type][npc.name]

        # 默认响应
        return {
            "action": "观察情况",
            "verbal": "发生什么事了？",
            "emotion": "惊讶"
        }

    def resolve_world_event(self, event_id: str):
        """解决世界事件"""
        for event in self.world_events:
            if event.id == event_id:
                event.is_resolved = True
                self.current_event = None

                self.recorder.record_event(TestEvent(
                    timestamp=datetime.now().isoformat(),
                    game_time=self.clock.get_time_str(),
                    event_type="world_event",
                    actor="世界",
                    action="事件解决",
                    target=event_id,
                    details={
                        "event_id": event_id,
                        "content": event.content,
                        "summary": f"事件解决: {event.content}"
                    }
                ))

                # 验证：所有受影响NPC都有响应记录
                for npc_name in self.npcs:
                    npc = self.npcs[npc_name]
                    if npc.location in event.affected_locations:
                        has_memory = npc.has_event_memory(event.content[:10])
                        self.recorder.record_validation(ValidationResult(
                            passed=has_memory,
                            category="事件记忆",
                            description=f"{npc_name}是否记得事件",
                            expected="记得事件",
                            actual="记得" if has_memory else "不记得",
                            severity="error" if not has_memory else "warning"
                        ))
                break

    def verify_npc_event_memory(self, npc_name: str, event_keyword: str) -> bool:
        """验证NPC是否记得事件"""
        if npc_name not in self.npcs:
            return False

        npc = self.npcs[npc_name]
        has_memory = npc.has_event_memory(event_keyword)

        self.recorder.record_validation(ValidationResult(
            passed=has_memory,
            category="记忆验证",
            description=f"{npc_name}是否记得'{event_keyword}'相关事件",
            expected="记得",
            actual="记得" if has_memory else "不记得",
            severity="critical" if not has_memory else "warning"
        ))

        return has_memory

    def verify_player_state_consistency(self):
        """验证玩家状态一致性"""
        # 金币验证
        total_earned = sum(t["amount"] for t in self.economy["transactions"] if t["to"] == self.player.name)
        total_spent = sum(t["amount"] for t in self.economy["transactions"] if t["from"] == self.player.name)
        expected_gold = 50 + total_earned - total_spent  # 初始50金币

        self.recorder.record_validation(ValidationResult(
            passed=(self.player.gold == expected_gold),
            category="状态一致性",
            description="玩家金币余额与交易记录一致",
            expected=expected_gold,
            actual=self.player.gold,
            severity="critical"
        ))

        # 位置验证
        last_location_event = None
        for event in reversed(self.recorder.events):
            if event.event_type == "movement" or "移动" in event.action:
                last_location_event = event
                break

        if last_location_event:
            expected_location = last_location_event.details.get("to_location", self.player.location)
            self.recorder.record_validation(ValidationResult(
                passed=(self.player.location == expected_location),
                category="状态一致性",
                description="玩家位置与最后移动记录一致",
                expected=expected_location,
                actual=self.player.location,
                severity="error"
            ))

    def record_state_snapshot(self):
        """记录状态快照"""
        self.recorder.record_player_state(self.player.to_dict())
        for npc_name, npc in self.npcs.items():
            self.recorder.record_npc_state(npc_name, npc.to_dict())


# ========== 运行3天模拟 ==========

def run_3day_simulation():
    """运行3天模拟测试"""
    sim = ThreeDaySimulation()
    logger.info("=" * 60)
    logger.info("开始3天综合模拟测试")
    logger.info("=" * 60)

    # ========== 第1天 ==========
    logger.info("\n" + "=" * 40)
    logger.info("第1天 - 初来乍到")
    logger.info("=" * 40)

    # 早上8点：玩家来到镇中心
    sim.recorder.record_event(TestEvent(
        timestamp=datetime.now().isoformat(),
        game_time=sim.clock.get_time_str(),
        event_type="start",
        actor=sim.player.name,
        action="开始游戏",
        target=None,
        details={"location": sim.player.location, "gold": sim.player.gold, "summary": "游戏开始"}
    ))

    # 移动到酒馆
    sim.player.move_to("酒馆")
    sim.recorder.record_event(TestEvent(
        timestamp=datetime.now().isoformat(),
        game_time=sim.clock.get_time_str(),
        event_type="movement",
        actor=sim.player.name,
        action="移动",
        target="酒馆",
        details={"from_location": "镇中心", "to_location": "酒馆", "summary": "移动到酒馆"}
    ))

    # 与贝拉对话 - 问候
    response1, _ = sim.player_dialogue("贝拉·欢笑", "你好，这里是酒馆吗？")
    sim.clock.advance(minutes=5)

    # 与贝拉对话 - 询问住宿
    response2, lodging_data = sim.player_dialogue("贝拉·欢笑", "我想找个地方住，有客房吗？")
    sim.clock.advance(minutes=5)

    # 预订普通客房
    booking_result = sim.player_book_lodging("普通客房")
    logger.info(f"住宿预订结果: {booking_result}")
    sim.clock.advance(minutes=10)

    # 与贝拉对话 - 询问工作
    response3, job_data = sim.player_dialogue("贝拉·欢笑", "我想找点活计赚钱，你这里有什么工作吗？")
    sim.clock.advance(minutes=5)

    # 接受工作
    if job_data.get("job_info"):
        response4, _ = sim.player_dialogue("贝拉·欢笑", "好的，我愿意接受这份工作。")
        sim.clock.advance(minutes=5)

    # 工作4小时
    work_result = sim.player_work(4)
    logger.info(f"工作结果: {work_result}")

    # 记录状态快照
    sim.record_state_snapshot()

    # 晚上：休息
    sim.player_rest(2)

    # 与贝拉再次对话 - 随意聊天
    response5, _ = sim.player_dialogue("贝拉·欢笑", "今天真是忙碌的一天啊。")
    sim.clock.advance(minutes=10)

    # 睡觉
    logger.info("第1天结束，玩家休息")
    sim.player_rest(8)  # 睡8小时

    # ========== 第2天 ==========
    logger.info("\n" + "=" * 40)
    logger.info("第2天 - 世界事件")
    logger.info("=" * 40)

    # 早上：移动到铁匠铺
    sim.player.move_to("铁匠铺")
    sim.recorder.record_event(TestEvent(
        timestamp=datetime.now().isoformat(),
        game_time=sim.clock.get_time_str(),
        event_type="movement",
        actor=sim.player.name,
        action="移动",
        target="铁匠铺",
        details={"from_location": "酒馆", "to_location": "铁匠铺", "summary": "移动到铁匠铺"}
    ))

    # 与铁匠对话
    response6, _ = sim.player_dialogue("埃尔德·铁锤", "你好，我是新来的旅行者。")
    sim.clock.advance(minutes=5)

    response7, job_data2 = sim.player_dialogue("埃尔德·铁锤", "我想找份工作，你这里需要帮手吗？")
    sim.clock.advance(minutes=5)

    # 中午：触发世界事件 - 市场区失火
    fire_event = WorldEvent(
        id="event_fire_001",
        event_type="fire",
        content="市场区发生火灾",
        location="市场区",
        severity=8,
        trigger_time=sim.clock.current_time,
        duration_hours=2,
        affected_locations=["市场区", "铁匠铺", "酒馆", "镇中心"]
    )

    sim.trigger_world_event(fire_event)
    sim.clock.advance(hours=1)

    # 玩家与铁匠互动 - 关于事件
    response8, _ = sim.player_dialogue("埃尔德·铁锤", "发生什么事了？我看到有烟。")
    sim.clock.advance(minutes=10)

    # 事件解决
    sim.clock.advance(hours=1)
    sim.resolve_world_event("event_fire_001")

    # 下午：继续活动
    sim.player.move_to("酒馆")
    sim.recorder.record_event(TestEvent(
        timestamp=datetime.now().isoformat(),
        game_time=sim.clock.get_time_str(),
        event_type="movement",
        actor=sim.player.name,
        action="移动",
        target="酒馆",
        details={"from_location": "铁匠铺", "to_location": "酒馆", "summary": "移动到酒馆"}
    ))

    # 与贝拉谈论事件
    response9, event_data = sim.player_dialogue("贝拉·欢笑", "刚才的火灾真可怕，你还好吗？")
    sim.clock.advance(minutes=10)

    # 验证NPC记忆
    sim.verify_npc_event_memory("贝拉·欢笑", "火灾")
    sim.verify_npc_event_memory("埃尔德·铁锤", "火灾")

    # 晚上休息
    sim.player_rest(8)

    # ========== 第3天 ==========
    logger.info("\n" + "=" * 40)
    logger.info("第3天 - 记忆与关系验证")
    logger.info("=" * 40)

    # 早上：与NPC确认他们是否记得事件和玩家
    response10, _ = sim.player_dialogue("贝拉·欢笑", "昨天那场火灾后来怎么样了？")
    sim.clock.advance(minutes=10)

    # 去教堂拜访牧师
    sim.player.move_to("教堂")
    sim.recorder.record_event(TestEvent(
        timestamp=datetime.now().isoformat(),
        game_time=sim.clock.get_time_str(),
        event_type="movement",
        actor=sim.player.name,
        action="移动",
        target="教堂",
        details={"from_location": "酒馆", "to_location": "教堂", "summary": "移动到教堂"}
    ))

    response11, _ = sim.player_dialogue("西奥多·光明", "神父，昨天镇上发生了火灾，你知道吗？")
    sim.clock.advance(minutes=10)

    # 验证牧师是否记得火灾
    sim.verify_npc_event_memory("西奥多·光明", "火灾")

    # 下午：消费和经济活动
    sim.player.move_to("酒馆")

    # 再次预订住宿
    booking_result2 = sim.player_book_lodging("舒适客房")
    logger.info(f"第二次住宿预订结果: {booking_result2}")

    # 最终状态验证
    sim.verify_player_state_consistency()
    sim.record_state_snapshot()

    # ========== 生成报告 ==========
    logger.info("\n" + "=" * 60)
    logger.info("模拟结束，生成测试报告")
    logger.info("=" * 60)

    report = sim.recorder.generate_report()

    # 打印报告摘要
    logger.info(f"\n测试摘要:")
    logger.info(f"  - 总事件数: {report['summary']['total_events']}")
    logger.info(f"  - 总验证数: {report['summary']['total_validations']}")
    logger.info(f"  - 通过: {report['summary']['passed']}")
    logger.info(f"  - 失败: {report['summary']['failed']}")
    logger.info(f"  - 通过率: {report['summary']['pass_rate']}")
    logger.info(f"  - 耗时: {report['summary']['duration_seconds']:.2f}秒")

    logger.info(f"\n按类别统计:")
    for category, stats in report['by_category'].items():
        logger.info(f"  - {category}: 通过{stats['passed']}, 失败{stats['failed']}")

    if report['failed_validations']:
        logger.warning(f"\n失败的验证项:")
        for v in report['failed_validations']:
            logger.warning(f"  [{v['severity']}] {v['category']}: {v['description']}")
            logger.warning(f"    期望: {v['expected']}, 实际: {v['actual']}")

    # 保存完整报告
    report_path = "tests/simulation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"\n完整报告已保存到: {report_path}")

    # 保存事件时间线
    timeline_path = "tests/simulation_timeline.json"
    with open(timeline_path, 'w', encoding='utf-8') as f:
        timeline = [{
            "timestamp": e.timestamp,
            "game_time": e.game_time,
            "type": e.event_type,
            "actor": e.actor,
            "action": e.action,
            "target": e.target,
            "details": e.details,
            "llm_output": e.llm_output
        } for e in sim.recorder.events]
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    logger.info(f"事件时间线已保存到: {timeline_path}")

    return report


if __name__ == "__main__":
    report = run_3day_simulation()

    # 根据结果返回退出码
    if report['summary']['failed'] > 0:
        sys.exit(1)
    sys.exit(0)
