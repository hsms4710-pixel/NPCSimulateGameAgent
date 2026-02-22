"""
世界数据系统 - 管理经济、工作、住宿、好感度等世界状态
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import logging
import json

logger = logging.getLogger(__name__)


# ========== 经济系统 ==========

class Currency(Enum):
    """货币类型"""
    GOLD = "gold"          # 金币（主要货币）
    SILVER = "silver"      # 银币
    COPPER = "copper"      # 铜币


@dataclass
class Transaction:
    """交易记录"""
    id: str
    timestamp: str
    from_entity: str       # 付款方
    to_entity: str         # 收款方
    amount: int
    currency: Currency
    category: str          # 分类：work, lodging, purchase, reward等
    description: str

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "from": self.from_entity,
            "to": self.to_entity,
            "amount": self.amount,
            "currency": self.currency.value,
            "category": self.category,
            "description": self.description
        }


# ========== 工作系统 ==========

class JobStatus(Enum):
    """工作状态"""
    AVAILABLE = "available"      # 可申请
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    EXPIRED = "expired"          # 过期


@dataclass
class Job:
    """工作/任务"""
    id: str
    employer: str              # 雇主（NPC名称）
    title: str                 # 工作标题
    description: str           # 工作描述
    location: str              # 工作地点
    reward: int                # 报酬（金币）
    duration_hours: float      # 预计时长（小时）
    required_skill: Optional[str] = None  # 需要的技能
    status: JobStatus = JobStatus.AVAILABLE
    worker: Optional[str] = None  # 接受工作的人
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    progress: float = 0.0      # 进度 0-1

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "employer": self.employer,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "reward": self.reward,
            "duration_hours": self.duration_hours,
            "required_skill": self.required_skill,
            "status": self.status.value,
            "worker": self.worker,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "progress": self.progress
        }


# ========== 住宿系统 ==========

class LodgingType(Enum):
    """住宿类型"""
    INN_BASIC = "inn_basic"        # 普通客房
    INN_COMFORT = "inn_comfort"    # 舒适客房
    INN_LUXURY = "inn_luxury"      # 豪华客房
    RENT_ROOM = "rent_room"        # 租房


@dataclass
class Lodging:
    """住宿"""
    id: str
    provider: str              # 提供者（NPC名称）
    location: str              # 位置
    lodging_type: LodgingType
    price_per_night: int       # 每晚价格
    energy_restore: float      # 恢复的体力值 (0-1)
    is_available: bool = True
    current_guest: Optional[str] = None
    check_in_time: Optional[str] = None
    nights_booked: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "location": self.location,
            "type": self.lodging_type.value,
            "price_per_night": self.price_per_night,
            "energy_restore": self.energy_restore,
            "is_available": self.is_available,
            "current_guest": self.current_guest,
            "check_in_time": self.check_in_time,
            "nights_booked": self.nights_booked
        }


# ========== 好感度系统 ==========

class RelationshipLevel(Enum):
    """关系等级"""
    HOSTILE = "hostile"        # 敌对 (-100 ~ -50)
    UNFRIENDLY = "unfriendly"  # 不友好 (-50 ~ -10)
    NEUTRAL = "neutral"        # 中立 (-10 ~ 10)
    FRIENDLY = "friendly"      # 友好 (10 ~ 50)
    CLOSE = "close"            # 亲近 (50 ~ 80)
    TRUSTED = "trusted"        # 信任 (80 ~ 100)


@dataclass
class Relationship:
    """关系数据"""
    entity_a: str              # 实体A
    entity_b: str              # 实体B
    affinity: int = 0          # 好感度 (-100 ~ 100)
    trust: int = 0             # 信任度 (0 ~ 100)
    interaction_count: int = 0  # 互动次数
    last_interaction: Optional[str] = None
    relationship_type: str = "acquaintance"  # 关系类型
    notes: List[str] = field(default_factory=list)  # 关系备注

    @property
    def level(self) -> RelationshipLevel:
        """根据好感度计算关系等级"""
        if self.affinity < -50:
            return RelationshipLevel.HOSTILE
        elif self.affinity < -10:
            return RelationshipLevel.UNFRIENDLY
        elif self.affinity < 10:
            return RelationshipLevel.NEUTRAL
        elif self.affinity < 50:
            return RelationshipLevel.FRIENDLY
        elif self.affinity < 80:
            return RelationshipLevel.CLOSE
        else:
            return RelationshipLevel.TRUSTED

    def to_dict(self) -> Dict:
        return {
            "entity_a": self.entity_a,
            "entity_b": self.entity_b,
            "affinity": self.affinity,
            "trust": self.trust,
            "level": self.level.value,
            "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction,
            "relationship_type": self.relationship_type,
            "notes": self.notes[-5:]  # 最近5条
        }


# ========== 事件传播系统 ==========

@dataclass
class PropagatingEvent:
    """正在传播的事件"""
    id: str
    content: str
    origin_location: str
    origin_time: str           # 事件发生时间
    event_type: str
    severity: int              # 严重程度 1-10
    reached_locations: List[str] = field(default_factory=list)
    pending_notifications: List[Dict] = field(default_factory=list)
    is_active: bool = True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "origin_location": self.origin_location,
            "origin_time": self.origin_time,
            "event_type": self.event_type,
            "severity": self.severity,
            "reached_locations": self.reached_locations,
            "pending_count": len(self.pending_notifications),
            "is_active": self.is_active
        }


class WorldDataManager:
    """世界数据管理器"""

    def __init__(self):
        # 经济数据
        self.entity_wallets: Dict[str, Dict[str, int]] = {}  # {entity: {gold: x, silver: y}}
        self.transactions: List[Transaction] = []

        # 工作数据
        self.available_jobs: Dict[str, Job] = {}
        self.active_jobs: Dict[str, Job] = {}
        self.completed_jobs: List[Job] = []

        # 住宿数据
        self.lodgings: Dict[str, Lodging] = {}

        # 关系数据
        self.relationships: Dict[str, Relationship] = {}  # key: "entityA_entityB"

        # 事件传播
        self.propagating_events: Dict[str, PropagatingEvent] = {}
        self.event_queue: asyncio.Queue = None  # 异步事件队列

        # 地点邻接关系
        self.location_adjacency = {
            "村庄大门": ["镇中心", "森林边缘"],
            "镇中心": ["村庄大门", "酒馆", "市场区", "教堂"],
            "酒馆": ["镇中心", "市场区"],
            "市场区": ["镇中心", "酒馆", "铁匠铺"],
            "铁匠铺": ["市场区", "工坊区"],
            "教堂": ["镇中心", "农田"],
            "工坊区": ["铁匠铺", "农田"],
            "农田": ["教堂", "工坊区", "森林边缘"],
            "森林边缘": ["村庄大门", "农田"]
        }

        self._init_default_data()

    def _init_default_data(self):
        """初始化默认数据"""
        # 初始化NPC钱包
        default_npcs = [
            "埃尔德·铁锤", "贝拉·欢笑", "西奥多·光明",
            "玛格丽特·花语", "汉斯·巧手", "老农托马斯"
        ]
        for npc in default_npcs:
            self.entity_wallets[npc] = {"gold": 100, "silver": 50}

        # 初始化默认工作
        self._init_default_jobs()

        # 初始化住宿
        self._init_default_lodgings()

        # 初始化默认关系
        self._init_default_relationships()

    def _init_default_jobs(self):
        """初始化默认工作"""
        jobs = [
            Job(
                id="job_tavern_help",
                employer="贝拉·欢笑",
                title="酒馆帮工",
                description="帮忙打扫酒馆、招待客人、端酒送菜",
                location="酒馆",
                reward=15,
                duration_hours=4,
            ),
            Job(
                id="job_blacksmith_assist",
                employer="埃尔德·铁锤",
                title="铁匠铺学徒",
                description="帮忙拉风箱、递工具、搬运铁料",
                location="铁匠铺",
                reward=20,
                duration_hours=6,
                required_skill="体力"
            ),
            Job(
                id="job_farm_harvest",
                employer="老农托马斯",
                title="农田收割",
                description="帮助收割成熟的庄稼",
                location="农田",
                reward=12,
                duration_hours=3,
            ),
            Job(
                id="job_flower_delivery",
                employer="玛格丽特·花语",
                title="鲜花配送",
                description="将鲜花送到镇上各处的客户手中",
                location="市场区",
                reward=8,
                duration_hours=2,
            ),
            Job(
                id="job_church_cleanup",
                employer="西奥多·光明",
                title="教堂清洁",
                description="打扫教堂内外，整理祈祷室",
                location="教堂",
                reward=10,
                duration_hours=2,
            ),
        ]
        for job in jobs:
            self.available_jobs[job.id] = job

    def _init_default_lodgings(self):
        """初始化住宿"""
        lodgings = [
            Lodging(
                id="inn_basic_1",
                provider="贝拉·欢笑",
                location="酒馆",
                lodging_type=LodgingType.INN_BASIC,
                price_per_night=5,
                energy_restore=0.6
            ),
            Lodging(
                id="inn_comfort_1",
                provider="贝拉·欢笑",
                location="酒馆",
                lodging_type=LodgingType.INN_COMFORT,
                price_per_night=15,
                energy_restore=0.8
            ),
            Lodging(
                id="inn_luxury_1",
                provider="贝拉·欢笑",
                location="酒馆",
                lodging_type=LodgingType.INN_LUXURY,
                price_per_night=30,
                energy_restore=1.0
            ),
        ]
        for lodging in lodgings:
            self.lodgings[lodging.id] = lodging

    def _init_default_relationships(self):
        """初始化NPC之间的默认关系"""
        # NPC之间的关系
        default_relations = [
            ("埃尔德·铁锤", "贝拉·欢笑", 40, "old_friends"),  # 老朋友
            ("埃尔德·铁锤", "汉斯·巧手", 60, "colleagues"),   # 同行
            ("贝拉·欢笑", "玛格丽特·花语", 50, "friends"),    # 朋友
            ("西奥多·光明", "老农托马斯", 30, "acquaintance"), # 熟人
            ("西奥多·光明", "贝拉·欢笑", 20, "acquaintance"),
        ]
        for a, b, affinity, rel_type in default_relations:
            self.set_relationship(a, b, affinity, relationship_type=rel_type)

    # ========== 经济系统方法 ==========

    def get_balance(self, entity: str) -> Dict[str, int]:
        """获取实体的余额"""
        if entity not in self.entity_wallets:
            self.entity_wallets[entity] = {"gold": 0, "silver": 0}
        return self.entity_wallets[entity].copy()

    def add_funds(self, entity: str, amount: int, currency: str = "gold"):
        """增加资金"""
        if entity not in self.entity_wallets:
            self.entity_wallets[entity] = {"gold": 0, "silver": 0}
        self.entity_wallets[entity][currency] = \
            self.entity_wallets[entity].get(currency, 0) + amount

    def deduct_funds(self, entity: str, amount: int, currency: str = "gold") -> bool:
        """扣除资金，返回是否成功"""
        balance = self.get_balance(entity)
        if balance.get(currency, 0) < amount:
            return False
        self.entity_wallets[entity][currency] -= amount
        return True

    def transfer(self, from_entity: str, to_entity: str, amount: int,
                 category: str, description: str, currency: str = "gold") -> Optional[Transaction]:
        """转账"""
        if not self.deduct_funds(from_entity, amount, currency):
            return None

        self.add_funds(to_entity, amount, currency)

        tx = Transaction(
            id=f"tx_{datetime.now().timestamp()}",
            timestamp=datetime.now().isoformat(),
            from_entity=from_entity,
            to_entity=to_entity,
            amount=amount,
            currency=Currency(currency),
            category=category,
            description=description
        )
        self.transactions.append(tx)

        # 限制交易历史长度
        if len(self.transactions) > 100:
            self.transactions = self.transactions[-100:]

        logger.info(f"交易: {from_entity} -> {to_entity}, {amount} {currency}, {category}")
        return tx

    # ========== 工作系统方法 ==========

    def get_available_jobs(self, location: str = None) -> List[Job]:
        """获取可用工作列表"""
        jobs = [j for j in self.available_jobs.values()
                if j.status == JobStatus.AVAILABLE]
        if location:
            jobs = [j for j in jobs if j.location == location]
        return jobs

    def accept_job(self, job_id: str, worker: str) -> Optional[Job]:
        """接受工作"""
        if job_id not in self.available_jobs:
            return None

        job = self.available_jobs[job_id]
        if job.status != JobStatus.AVAILABLE:
            return None

        job.status = JobStatus.IN_PROGRESS
        job.worker = worker
        job.start_time = datetime.now().isoformat()

        # 移动到活动工作
        self.active_jobs[job_id] = job
        del self.available_jobs[job_id]

        logger.info(f"工作接受: {worker} 接受了 '{job.title}'")
        return job

    def update_job_progress(self, job_id: str, progress: float) -> Optional[Job]:
        """更新工作进度"""
        if job_id not in self.active_jobs:
            return None

        job = self.active_jobs[job_id]
        job.progress = min(1.0, max(0.0, progress))

        if job.progress >= 1.0:
            return self.complete_job(job_id)

        return job

    def complete_job(self, job_id: str) -> Optional[Job]:
        """完成工作"""
        if job_id not in self.active_jobs:
            return None

        job = self.active_jobs[job_id]
        job.status = JobStatus.COMPLETED
        job.end_time = datetime.now().isoformat()
        job.progress = 1.0

        # 支付报酬
        if job.worker:
            self.transfer(
                job.employer, job.worker, job.reward,
                "work", f"完成工作: {job.title}"
            )

            # 增加好感度
            self.modify_affinity(job.employer, job.worker, 5, "完成工作")

        self.completed_jobs.append(job)
        del self.active_jobs[job_id]

        logger.info(f"工作完成: {job.worker} 完成了 '{job.title}'，获得 {job.reward} 金币")
        return job

    def get_worker_jobs(self, worker: str) -> List[Job]:
        """获取某人的工作"""
        return [j for j in self.active_jobs.values() if j.worker == worker]

    # ========== 住宿系统方法 ==========

    def get_available_lodgings(self, location: str = None) -> List[Lodging]:
        """获取可用住宿"""
        lodgings = [l for l in self.lodgings.values() if l.is_available]
        if location:
            lodgings = [l for l in lodgings if l.location == location]
        return lodgings

    def book_lodging(self, lodging_id: str, guest: str, nights: int = 1) -> Optional[Dict]:
        """预订住宿"""
        if lodging_id not in self.lodgings:
            return None

        lodging = self.lodgings[lodging_id]
        if not lodging.is_available:
            return None

        total_cost = lodging.price_per_night * nights

        # 扣款
        if not self.deduct_funds(guest, total_cost):
            return {"error": "余额不足", "required": total_cost}

        # 支付给提供者
        self.add_funds(lodging.provider, total_cost)

        # 记录交易
        self.transactions.append(Transaction(
            id=f"tx_{datetime.now().timestamp()}",
            timestamp=datetime.now().isoformat(),
            from_entity=guest,
            to_entity=lodging.provider,
            amount=total_cost,
            currency=Currency.GOLD,
            category="lodging",
            description=f"住宿 {nights} 晚"
        ))

        # 更新住宿状态
        lodging.is_available = False
        lodging.current_guest = guest
        lodging.check_in_time = datetime.now().isoformat()
        lodging.nights_booked = nights

        # 增加好感度
        self.modify_affinity(lodging.provider, guest, 3, "入住酒店")

        logger.info(f"住宿: {guest} 入住 {lodging.location}，{nights} 晚，花费 {total_cost} 金币")

        return {
            "success": True,
            "lodging": lodging.to_dict(),
            "total_cost": total_cost,
            "energy_restore": lodging.energy_restore
        }

    def checkout_lodging(self, lodging_id: str) -> Optional[Lodging]:
        """退房"""
        if lodging_id not in self.lodgings:
            return None

        lodging = self.lodgings[lodging_id]
        lodging.is_available = True
        lodging.current_guest = None
        lodging.check_in_time = None
        lodging.nights_booked = 0

        return lodging

    # ========== 好感度系统方法 ==========

    def _get_relationship_key(self, a: str, b: str) -> str:
        """获取关系键（保证顺序一致）"""
        return f"{min(a, b)}_{max(a, b)}"

    def get_relationship(self, a: str, b: str) -> Relationship:
        """获取两个实体之间的关系"""
        key = self._get_relationship_key(a, b)
        if key not in self.relationships:
            self.relationships[key] = Relationship(entity_a=a, entity_b=b)
        return self.relationships[key]

    def set_relationship(self, a: str, b: str, affinity: int,
                         trust: int = None, relationship_type: str = None):
        """设置关系"""
        rel = self.get_relationship(a, b)
        rel.affinity = max(-100, min(100, affinity))
        if trust is not None:
            rel.trust = max(0, min(100, trust))
        if relationship_type:
            rel.relationship_type = relationship_type

    def modify_affinity(self, a: str, b: str, delta: int, reason: str = ""):
        """修改好感度"""
        rel = self.get_relationship(a, b)
        old_level = rel.level
        rel.affinity = max(-100, min(100, rel.affinity + delta))
        rel.interaction_count += 1
        rel.last_interaction = datetime.now().isoformat()

        if reason:
            rel.notes.append(f"{datetime.now().strftime('%m-%d %H:%M')}: {reason} ({delta:+d})")
            if len(rel.notes) > 20:
                rel.notes = rel.notes[-20:]

        new_level = rel.level
        if old_level != new_level:
            logger.info(f"关系变化: {a} 与 {b} 的关系从 {old_level.value} 变为 {new_level.value}")

        return rel

    def modify_trust(self, a: str, b: str, delta: int, reason: str = ""):
        """修改信任度"""
        rel = self.get_relationship(a, b)
        rel.trust = max(0, min(100, rel.trust + delta))

        if reason:
            rel.notes.append(f"{datetime.now().strftime('%m-%d %H:%M')}: {reason} (信任{delta:+d})")

        return rel

    def get_entity_relationships(self, entity: str) -> List[Dict]:
        """获取实体的所有关系"""
        relations = []
        for key, rel in self.relationships.items():
            if entity in (rel.entity_a, rel.entity_b):
                other = rel.entity_b if rel.entity_a == entity else rel.entity_a
                relations.append({
                    "target": other,
                    **rel.to_dict()
                })
        return sorted(relations, key=lambda x: x["affinity"], reverse=True)

    # ========== 事件传播系统 ==========

    def calculate_propagation_delay(self, from_loc: str, to_loc: str, severity: int) -> float:
        """
        计算事件从一个位置传播到另一个位置的延迟（秒）
        severity越高，传播越快
        """
        distance = self._calculate_distance(from_loc, to_loc)
        if distance == 0:
            return 0

        # 基础延迟：每步距离2-5秒，紧急事件更快
        base_delay = 3.0  # 秒
        urgency_factor = max(0.3, 1.0 - (severity / 10) * 0.7)

        return distance * base_delay * urgency_factor

    def _calculate_distance(self, loc1: str, loc2: str) -> int:
        """计算两个地点之间的距离（BFS）"""
        if loc1 == loc2:
            return 0

        visited = {loc1}
        queue = [(loc1, 0)]

        while queue:
            current, dist = queue.pop(0)
            for neighbor in self.location_adjacency.get(current, []):
                if neighbor == loc2:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return 999

    def create_propagating_event(self, event_id: str, content: str,
                                  origin_location: str, event_type: str,
                                  severity: int = 5) -> PropagatingEvent:
        """创建一个需要传播的事件"""
        event = PropagatingEvent(
            id=event_id,
            content=content,
            origin_location=origin_location,
            origin_time=datetime.now().isoformat(),
            event_type=event_type,
            severity=severity,
            reached_locations=[origin_location]
        )

        # 计算到各个位置的传播时间
        for location in self.location_adjacency.keys():
            if location != origin_location:
                delay = self.calculate_propagation_delay(origin_location, location, severity)
                event.pending_notifications.append({
                    "location": location,
                    "delay_seconds": delay,
                    "scheduled_time": None,
                    "notified": False
                })

        # 按延迟排序
        event.pending_notifications.sort(key=lambda x: x["delay_seconds"])

        self.propagating_events[event_id] = event
        logger.info(f"事件传播创建: {content[:30]}... 从 {origin_location} 开始传播")

        return event

    def get_next_propagation(self, event_id: str) -> Optional[Dict]:
        """获取下一个待传播的通知"""
        if event_id not in self.propagating_events:
            return None

        event = self.propagating_events[event_id]
        for notification in event.pending_notifications:
            if not notification["notified"]:
                return {
                    "event": event.to_dict(),
                    "notification": notification
                }

        return None

    def mark_location_notified(self, event_id: str, location: str):
        """标记位置已通知"""
        if event_id not in self.propagating_events:
            return

        event = self.propagating_events[event_id]
        for notification in event.pending_notifications:
            if notification["location"] == location:
                notification["notified"] = True
                event.reached_locations.append(location)
                break

    def get_event_propagation_status(self, event_id: str) -> Optional[Dict]:
        """获取事件传播状态"""
        if event_id not in self.propagating_events:
            return None

        event = self.propagating_events[event_id]
        notified_count = sum(1 for n in event.pending_notifications if n["notified"])

        return {
            "event": event.to_dict(),
            "total_locations": len(event.pending_notifications) + 1,  # +1 for origin
            "notified_locations": notified_count + 1,
            "pending_notifications": [n for n in event.pending_notifications if not n["notified"]]
        }

    # ========== 数据导出 ==========

    def get_location_coords(self, location_name: str) -> Optional[tuple]:
        """返回地点的 (x, y) 坐标，用于空间广播；从预置网格或数据文件读取"""
        # 默认地点网格坐标（单位：米，供空间广播使用）
        _DEFAULT_COORDS = {
            "村庄大门":  (0.0,    0.0),
            "镇中心":    (100.0,  0.0),
            "酒馆":      (100.0,  80.0),
            "市场区":    (180.0,  0.0),
            "铁匠铺":    (260.0,  0.0),
            "教堂":      (100.0, -100.0),
            "工坊区":    (260.0,  80.0),
            "农田":      (180.0, -150.0),
            "森林边缘":  (-80.0, -80.0),
        }
        return _DEFAULT_COORDS.get(location_name)

    def get_world_state(self) -> Dict[str, Any]:
        """获取完整的世界状态"""
        return {
            "economy": {
                "wallets": self.entity_wallets,
                "recent_transactions": [t.to_dict() for t in self.transactions[-10:]]
            },
            "jobs": {
                "available": [j.to_dict() for j in self.available_jobs.values()],
                "active": [j.to_dict() for j in self.active_jobs.values()],
                "completed_count": len(self.completed_jobs)
            },
            "lodgings": {
                "all": [l.to_dict() for l in self.lodgings.values()]
            },
            "relationships_count": len(self.relationships),
            "active_events": [e.to_dict() for e in self.propagating_events.values() if e.is_active]
        }


import os
import glob as _glob


def load_world_npcs(world_name: str) -> Dict[str, Any]:
    """扫描 data/worlds/{world}/npcs/*.json 动态加载NPC"""
    result = {}
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "worlds", world_name, "npcs")
    if not os.path.exists(base_path):
        return result
    for fp in _glob.glob(os.path.join(base_path, "*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                npc_data = json.load(f)
                name = npc_data.get("name", os.path.basename(fp).replace(".json", ""))
                result[name] = npc_data
        except Exception:
            pass
    return result


def load_world_locations(world_name: str) -> Dict[str, Any]:
    """从 data/worlds/{world}/locations.json 加载地点及邻接关系"""
    fp = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "worlds", world_name, "locations.json")
    if not os.path.exists(fp):
        return {}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_active_world_data(world_name: str = "default") -> Dict[str, Any]:
    """当前激活世界的NPC+地点合并数据，供 api_server 使用"""
    return {
        "npcs": load_world_npcs(world_name),
        "locations": load_world_locations(world_name),
    }


# 全局世界数据管理器实例
world_data_manager = WorldDataManager()
