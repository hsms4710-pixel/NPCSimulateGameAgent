# -*- coding: utf-8 -*-
"""
NPC统一注册表系统
==================

统一管理所有NPC的生命周期：
- 动态创建NPC
- 动态删除NPC
- 持久化存储
- 与三方交互系统集成

设计原则：
1. 单一入口：所有NPC的增删改查都通过此注册表
2. 持久化：所有NPC状态自动保存到本地
3. 记忆同步：NPC创建/销毁自动记录到三方记忆
4. 槽位管理：控制活跃NPC数量上限
"""

import json
import os
import gzip
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


# ==================== NPC状态定义 ====================

class NPCLifecycleStatus(Enum):
    """NPC生命周期状态"""
    ACTIVE = "active"              # 活跃：正常运行
    INACTIVE = "inactive"          # 非活跃：存在但不占用槽位
    DORMANT = "dormant"            # 休眠：长期不活跃，数据压缩存储
    LEFT = "left"                  # 离开：已离开当前区域
    DECEASED = "deceased"          # 死亡：永久移除
    IMPRISONED = "imprisoned"      # 囚禁：特殊状态


class NPCType(Enum):
    """NPC类型"""
    CORE = "core"                  # 核心NPC：不可删除
    PERMANENT = "permanent"        # 永久NPC：重要角色
    TEMPORARY = "temporary"        # 临时NPC：可被清理
    DYNAMIC = "dynamic"            # 动态NPC：由事件生成


@dataclass
class NPCRegistryEntry:
    """
    NPC注册表条目

    包含NPC的所有核心信息，用于统一管理
    """
    # 基础信息
    id: str                                   # 唯一ID
    name: str                                 # 显示名称
    npc_type: str = "temporary"               # NPCType的值
    status: str = "active"                    # NPCLifecycleStatus的值

    # 来源信息
    origin: str = "manual"                    # 创建来源：manual/event/migration
    origin_event_id: Optional[str] = None     # 来源事件ID
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 位置和职业
    location: str = "未知"
    profession: str = "未知"

    # 人物卡基础信息
    traits: List[str] = field(default_factory=list)
    background: str = ""
    goals: List[str] = field(default_factory=list)

    # 关系网络
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 格式: {"npc_name": {"type": "friend", "strength": 80, "history": []}}

    # 状态快照（用于快速访问）
    current_activity: str = "休息"
    current_emotion: str = "平静"
    energy: float = 1.0

    # 记忆统计（不存储完整记忆，只存储统计）
    memory_count: int = 0
    last_memory_update: Optional[str] = None
    important_memories: List[str] = field(default_factory=list)  # 关键记忆摘要

    # 交互统计
    interaction_count: int = 0
    last_interaction: Optional[str] = None
    interaction_partners: List[str] = field(default_factory=list)  # 最近交互对象

    # 存储路径（指向详细数据文件）
    data_file: Optional[str] = None           # npc_storage/{name}.json.gz
    memory_db: Optional[str] = None           # npc_storage/{name}_cold_memory.db

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPCRegistryEntry':
        """从字典创建"""
        # 处理可能缺失的字段
        return cls(
            id=data.get('id', str(uuid.uuid4())[:8]),
            name=data['name'],
            npc_type=data.get('npc_type', 'temporary'),
            status=data.get('status', 'active'),
            origin=data.get('origin', 'manual'),
            origin_event_id=data.get('origin_event_id'),
            created_at=data.get('created_at', datetime.now().isoformat()),
            location=data.get('location', '未知'),
            profession=data.get('profession', '未知'),
            traits=data.get('traits', []),
            background=data.get('background', ''),
            goals=data.get('goals', []),
            relationships=data.get('relationships', {}),
            current_activity=data.get('current_activity', '休息'),
            current_emotion=data.get('current_emotion', '平静'),
            energy=data.get('energy', 1.0),
            memory_count=data.get('memory_count', 0),
            last_memory_update=data.get('last_memory_update'),
            important_memories=data.get('important_memories', []),
            interaction_count=data.get('interaction_count', 0),
            last_interaction=data.get('last_interaction'),
            interaction_partners=data.get('interaction_partners', []),
            data_file=data.get('data_file'),
            memory_db=data.get('memory_db'),
            metadata=data.get('metadata', {}),
            last_updated=data.get('last_updated', datetime.now().isoformat())
        )


# ==================== NPC注册表 ====================

class NPCRegistry:
    """
    NPC统一注册表

    单例模式，管理所有NPC的生命周期
    """

    # 配置
    ACTIVE_NPC_LIMIT = 15          # 活跃NPC上限
    TEMP_NPC_LIMIT = 5             # 临时NPC上限
    REGISTRY_FILE = "npc_registry.json"

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, storage_dir: str = "npc_storage"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, storage_dir: str = "npc_storage"):
        if self._initialized:
            return

        self.storage_dir = storage_dir
        self.registry_path = os.path.join(storage_dir, self.REGISTRY_FILE)

        # 注册表数据
        self.entries: Dict[str, NPCRegistryEntry] = {}

        # 核心NPC集合（不可删除）
        self.core_npcs: Set[str] = set()

        # 世界记忆接口（稍后注入）
        self.memory_callback: Optional[Callable] = None

        # 确保目录存在
        os.makedirs(storage_dir, exist_ok=True)

        # 加载注册表
        self._load_registry()

        self._initialized = True
        logger.info(f"NPC注册表初始化完成，共 {len(self.entries)} 个NPC")

    def _load_registry(self):
        """加载注册表"""
        try:
            if os.path.exists(self.registry_path):
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 恢复条目
                for entry_data in data.get('entries', []):
                    entry = NPCRegistryEntry.from_dict(entry_data)
                    self.entries[entry.id] = entry

                # 恢复核心NPC
                self.core_npcs = set(data.get('core_npcs', []))

                logger.info(f"加载NPC注册表: {len(self.entries)} 个NPC")
            else:
                logger.info("创建新的NPC注册表")

        except Exception as e:
            logger.error(f"加载NPC注册表失败: {e}")
            self.entries = {}
            self.core_npcs = set()

    def _save_registry(self):
        """保存注册表"""
        try:
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'entries': [entry.to_dict() for entry in self.entries.values()],
                'core_npcs': list(self.core_npcs),
                'statistics': {
                    'total': len(self.entries),
                    'active': self.get_active_count(),
                    'temporary': len([e for e in self.entries.values()
                                     if e.npc_type == 'temporary']),
                }
            }

            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存NPC注册表失败: {e}")

    # ==================== 核心操作 ====================

    def register_npc(
        self,
        name: str,
        npc_type: str = "temporary",
        location: str = "未知",
        profession: str = "未知",
        traits: List[str] = None,
        background: str = "",
        goals: List[str] = None,
        origin: str = "manual",
        origin_event_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[NPCRegistryEntry]:
        """
        注册新NPC

        Returns:
            NPCRegistryEntry 或 None（如果达到上限）
        """
        # 检查是否已存在
        existing = self.get_by_name(name)
        if existing:
            logger.warning(f"NPC '{name}' 已存在，返回现有条目")
            return existing

        # 检查槽位
        if not self._check_slot_available(npc_type):
            logger.warning(f"NPC槽位已满，无法创建 '{name}'")
            return None

        # 创建条目
        npc_id = str(uuid.uuid4())[:8]
        entry = NPCRegistryEntry(
            id=npc_id,
            name=name,
            npc_type=npc_type,
            status="active",
            origin=origin,
            origin_event_id=origin_event_id,
            location=location,
            profession=profession,
            traits=traits or [],
            background=background,
            goals=goals or [],
            data_file=os.path.join(self.storage_dir, f"{name}.json.gz"),
            memory_db=os.path.join(self.storage_dir, f"{name}_cold_memory.db"),
            metadata=metadata or {}
        )

        self.entries[npc_id] = entry

        # 核心NPC标记
        if npc_type == "core":
            self.core_npcs.add(npc_id)

        # 保存
        self._save_registry()

        # 记录到世界记忆
        self._record_creation_memory(entry)

        logger.info(f"注册NPC: {name} ({npc_id}), 类型={npc_type}")
        return entry

    def unregister_npc(
        self,
        npc_id: str = None,
        name: str = None,
        reason: str = "left",
        witnesses: List[str] = None,
        permanent: bool = False
    ) -> bool:
        """
        注销NPC

        Args:
            npc_id: NPC ID
            name: NPC名称（二选一）
            reason: 离开原因 (left/deceased/imprisoned)
            witnesses: 见证者列表
            permanent: 是否永久删除数据文件

        Returns:
            是否成功
        """
        # 查找NPC
        entry = None
        if npc_id:
            entry = self.entries.get(npc_id)
        elif name:
            entry = self.get_by_name(name)

        if not entry:
            logger.warning(f"找不到NPC: id={npc_id}, name={name}")
            return False

        # 检查是否核心NPC
        if entry.id in self.core_npcs:
            logger.warning(f"无法删除核心NPC: {entry.name}")
            return False

        # 更新状态
        old_status = entry.status
        entry.status = reason
        entry.last_updated = datetime.now().isoformat()

        # 记录到世界记忆
        self._record_removal_memory(entry, reason, witnesses)

        # 永久删除
        if permanent:
            # 删除数据文件
            if entry.data_file and os.path.exists(entry.data_file):
                try:
                    os.remove(entry.data_file)
                except Exception as e:
                    logger.error(f"删除NPC数据文件失败: {e}")

            # 删除记忆数据库
            if entry.memory_db and os.path.exists(entry.memory_db):
                try:
                    os.remove(entry.memory_db)
                except Exception as e:
                    logger.error(f"删除NPC记忆数据库失败: {e}")

            # 从注册表移除
            del self.entries[entry.id]
            logger.info(f"永久删除NPC: {entry.name}")
        else:
            logger.info(f"NPC状态变更: {entry.name} {old_status} -> {reason}")

        self._save_registry()
        return True

    def reactivate_npc(self, npc_id: str = None, name: str = None) -> bool:
        """重新激活NPC"""
        entry = self.entries.get(npc_id) if npc_id else self.get_by_name(name)
        if not entry:
            return False

        if entry.status in ['deceased']:
            logger.warning(f"无法重新激活已死亡的NPC: {entry.name}")
            return False

        # 检查槽位
        if not self._check_slot_available(entry.npc_type):
            logger.warning(f"槽位已满，无法重新激活 {entry.name}")
            return False

        entry.status = "active"
        entry.last_updated = datetime.now().isoformat()
        self._save_registry()

        logger.info(f"重新激活NPC: {entry.name}")
        return True

    # ==================== 查询操作 ====================

    def get(self, npc_id: str) -> Optional[NPCRegistryEntry]:
        """根据ID获取NPC"""
        return self.entries.get(npc_id)

    def get_by_name(self, name: str) -> Optional[NPCRegistryEntry]:
        """根据名称获取NPC"""
        for entry in self.entries.values():
            if entry.name == name:
                return entry
        return None

    def get_active_npcs(self) -> List[NPCRegistryEntry]:
        """获取所有活跃NPC"""
        return [e for e in self.entries.values() if e.status == "active"]

    def get_npcs_at_location(self, location: str) -> List[NPCRegistryEntry]:
        """获取指定位置的NPC"""
        return [e for e in self.entries.values()
                if e.status == "active" and e.location == location]

    def get_npcs_by_type(self, npc_type: str) -> List[NPCRegistryEntry]:
        """获取指定类型的NPC"""
        return [e for e in self.entries.values() if e.npc_type == npc_type]

    def get_active_count(self) -> int:
        """获取活跃NPC数量"""
        return len([e for e in self.entries.values() if e.status == "active"])

    def get_all_names(self) -> List[str]:
        """获取所有NPC名称"""
        return [e.name for e in self.entries.values()]

    def get_active_names(self) -> List[str]:
        """获取所有活跃NPC名称"""
        return [e.name for e in self.entries.values() if e.status == "active"]

    # ==================== 更新操作 ====================

    def update_location(self, npc_id: str, location: str):
        """更新NPC位置"""
        if npc_id in self.entries:
            self.entries[npc_id].location = location
            self.entries[npc_id].last_updated = datetime.now().isoformat()
            self._save_registry()

    def update_activity(self, npc_id: str, activity: str):
        """更新NPC当前活动"""
        if npc_id in self.entries:
            self.entries[npc_id].current_activity = activity
            self.entries[npc_id].last_updated = datetime.now().isoformat()
            self._save_registry()

    def update_emotion(self, npc_id: str, emotion: str):
        """更新NPC情绪"""
        if npc_id in self.entries:
            self.entries[npc_id].current_emotion = emotion
            self.entries[npc_id].last_updated = datetime.now().isoformat()
            self._save_registry()

    def record_interaction(self, npc_id: str, partner: str):
        """记录交互"""
        if npc_id in self.entries:
            entry = self.entries[npc_id]
            entry.interaction_count += 1
            entry.last_interaction = datetime.now().isoformat()

            # 更新交互伙伴列表（保留最近10个）
            if partner not in entry.interaction_partners:
                entry.interaction_partners.append(partner)
                if len(entry.interaction_partners) > 10:
                    entry.interaction_partners.pop(0)

            entry.last_updated = datetime.now().isoformat()
            self._save_registry()

    def add_relationship(self, npc_id: str, target_name: str,
                        relation_type: str, strength: int = 50):
        """添加关系"""
        if npc_id in self.entries:
            self.entries[npc_id].relationships[target_name] = {
                "type": relation_type,
                "strength": strength,
                "established": datetime.now().isoformat()
            }
            self.entries[npc_id].last_updated = datetime.now().isoformat()
            self._save_registry()

    def add_important_memory(self, npc_id: str, memory_summary: str):
        """添加重要记忆摘要"""
        if npc_id in self.entries:
            entry = self.entries[npc_id]
            entry.memory_count += 1
            entry.last_memory_update = datetime.now().isoformat()

            # 保留最近20条重要记忆
            entry.important_memories.append(memory_summary)
            if len(entry.important_memories) > 20:
                entry.important_memories.pop(0)

            entry.last_updated = datetime.now().isoformat()
            self._save_registry()

    # ==================== 核心NPC管理 ====================

    def promote_to_core(self, npc_id: str = None, name: str = None,
                        reason: str = "") -> bool:
        """
        将NPC晋升为核心NPC

        触发条件（由外部判断后调用）：
        - 与玩家建立了深厚关系（如：同伴、师徒、恋人）
        - 在重大事件中扮演关键角色
        - 被玩家明确标记为重要
        - 交互次数超过阈值
        - LLM判断该NPC对剧情不可或缺

        Args:
            npc_id: NPC ID
            name: NPC名称（二选一）
            reason: 晋升原因

        Returns:
            是否成功
        """
        entry = self.entries.get(npc_id) if npc_id else self.get_by_name(name)
        if not entry:
            logger.warning(f"找不到NPC: id={npc_id}, name={name}")
            return False

        if entry.id in self.core_npcs:
            logger.info(f"NPC '{entry.name}' 已经是核心NPC")
            return True

        # 晋升
        self.core_npcs.add(entry.id)
        entry.npc_type = "core"
        entry.metadata["promotion_reason"] = reason
        entry.metadata["promoted_at"] = datetime.now().isoformat()
        entry.last_updated = datetime.now().isoformat()

        self._save_registry()

        # 记录到世界记忆
        if self.memory_callback:
            self.memory_callback(
                event_type="npc_promoted",
                content=f"{entry.name} 成为了重要人物",
                related_entities=[entry.name],
                metadata={"reason": reason}
            )

        logger.info(f"NPC晋升为核心: {entry.name}, 原因: {reason}")
        return True

    def demote_from_core(self, npc_id: str = None, name: str = None,
                         reason: str = "") -> bool:
        """
        将核心NPC降级为普通NPC

        触发条件：
        - 与玩家关系破裂
        - 长期不活跃
        - 剧情角色完成
        - 玩家主动取消标记

        注意：降级后NPC可以被正常删除
        """
        entry = self.entries.get(npc_id) if npc_id else self.get_by_name(name)
        if not entry:
            return False

        if entry.id not in self.core_npcs:
            logger.info(f"NPC '{entry.name}' 不是核心NPC")
            return True

        # 降级
        self.core_npcs.discard(entry.id)
        entry.npc_type = "permanent"  # 降级为永久NPC，而非临时
        entry.metadata["demotion_reason"] = reason
        entry.metadata["demoted_at"] = datetime.now().isoformat()
        entry.last_updated = datetime.now().isoformat()

        self._save_registry()

        logger.info(f"核心NPC降级: {entry.name}, 原因: {reason}")
        return True

    def is_core_npc(self, npc_id: str = None, name: str = None) -> bool:
        """检查是否为核心NPC"""
        if npc_id:
            return npc_id in self.core_npcs
        if name:
            entry = self.get_by_name(name)
            return entry.id in self.core_npcs if entry else False
        return False

    def get_core_npcs(self) -> List[NPCRegistryEntry]:
        """获取所有核心NPC"""
        return [self.entries[npc_id] for npc_id in self.core_npcs
                if npc_id in self.entries]

    def check_promotion_eligibility(self, npc_id: str) -> Dict[str, Any]:
        """
        检查NPC是否满足晋升条件

        返回各项指标的评估结果，供LLM或规则系统决策
        """
        entry = self.entries.get(npc_id)
        if not entry:
            return {"eligible": False, "reason": "NPC不存在"}

        if entry.id in self.core_npcs:
            return {"eligible": False, "reason": "已是核心NPC"}

        # 评估指标
        metrics = {
            "interaction_count": entry.interaction_count,
            "memory_count": entry.memory_count,
            "relationship_count": len(entry.relationships),
            "has_player_relationship": "player" in entry.relationships,
            "days_active": self._calculate_days_active(entry),
            "important_memory_count": len(entry.important_memories),
        }

        # 推荐阈值
        thresholds = {
            "interaction_threshold": 10,      # 交互次数 >= 10
            "memory_threshold": 20,           # 记忆数量 >= 20
            "relationship_threshold": 3,      # 关系数量 >= 3
            "days_threshold": 3,              # 活跃天数 >= 3
        }

        # 计算得分
        score = 0
        reasons = []

        if metrics["interaction_count"] >= thresholds["interaction_threshold"]:
            score += 25
            reasons.append(f"交互频繁({metrics['interaction_count']}次)")

        if metrics["memory_count"] >= thresholds["memory_threshold"]:
            score += 25
            reasons.append(f"记忆丰富({metrics['memory_count']}条)")

        if metrics["has_player_relationship"]:
            score += 30
            reasons.append("与玩家建立关系")

        if metrics["relationship_count"] >= thresholds["relationship_threshold"]:
            score += 10
            reasons.append(f"社交广泛({metrics['relationship_count']}人)")

        if metrics["days_active"] >= thresholds["days_threshold"]:
            score += 10
            reasons.append(f"持续活跃({metrics['days_active']}天)")

        return {
            "eligible": score >= 50,
            "score": score,
            "metrics": metrics,
            "reasons": reasons,
            "recommendation": "建议晋升" if score >= 50 else "暂不建议"
        }

    def _calculate_days_active(self, entry: NPCRegistryEntry) -> int:
        """计算NPC活跃天数"""
        try:
            created = datetime.fromisoformat(entry.created_at)
            return (datetime.now() - created).days
        except:
            return 0

    # ==================== 槽位管理 ====================

    def _check_slot_available(self, npc_type: str) -> bool:
        """检查是否有可用槽位"""
        active_count = self.get_active_count()

        if npc_type == "core":
            # 核心NPC总是可以创建
            return True

        if npc_type == "temporary":
            # 临时NPC有单独限制
            temp_count = len([e for e in self.entries.values()
                             if e.status == "active" and e.npc_type == "temporary"])
            return temp_count < self.TEMP_NPC_LIMIT and active_count < self.ACTIVE_NPC_LIMIT

        return active_count < self.ACTIVE_NPC_LIMIT

    def get_slot_status(self) -> Dict[str, Any]:
        """获取槽位状态"""
        active = self.get_active_count()
        temp_count = len([e for e in self.entries.values()
                         if e.status == "active" and e.npc_type == "temporary"])

        return {
            "active_npcs": active,
            "active_limit": self.ACTIVE_NPC_LIMIT,
            "temporary_npcs": temp_count,
            "temporary_limit": self.TEMP_NPC_LIMIT,
            "available_slots": self.ACTIVE_NPC_LIMIT - active,
            "can_create_temporary": temp_count < self.TEMP_NPC_LIMIT
        }

    def cleanup_temporary_npcs(self, keep_recent: int = 3) -> List[str]:
        """
        清理临时NPC

        保留最近创建的 keep_recent 个临时NPC，其余标记为left
        """
        temp_npcs = [e for e in self.entries.values()
                    if e.npc_type == "temporary" and e.status == "active"]

        # 按创建时间排序
        temp_npcs.sort(key=lambda x: x.created_at, reverse=True)

        removed = []
        for npc in temp_npcs[keep_recent:]:
            self.unregister_npc(npc_id=npc.id, reason="left")
            removed.append(npc.name)

        if removed:
            logger.info(f"清理临时NPC: {removed}")

        return removed

    # ==================== 记忆集成 ====================

    def set_memory_callback(self, callback: Callable):
        """设置记忆回调函数"""
        self.memory_callback = callback

    def _record_creation_memory(self, entry: NPCRegistryEntry):
        """记录NPC创建到世界记忆"""
        if self.memory_callback:
            self.memory_callback(
                event_type="npc_created",
                content=f"{entry.name} 出现在了 {entry.location}",
                related_entities=[entry.name],
                metadata={
                    "npc_id": entry.id,
                    "origin": entry.origin,
                    "profession": entry.profession
                }
            )

    def _record_removal_memory(self, entry: NPCRegistryEntry, reason: str,
                               witnesses: List[str] = None):
        """记录NPC移除到世界记忆"""
        reason_text = {
            "left": f"{entry.name} 离开了 {entry.location}",
            "deceased": f"{entry.name} 去世了",
            "imprisoned": f"{entry.name} 被囚禁了",
            "dormant": f"{entry.name} 进入休眠状态",
        }.get(reason, f"{entry.name} 不再活跃")

        if self.memory_callback:
            self.memory_callback(
                event_type="npc_removed",
                content=reason_text,
                related_entities=[entry.name] + (witnesses or []),
                metadata={
                    "npc_id": entry.id,
                    "reason": reason
                }
            )

    # ==================== 导入导出 ====================

    def export_npc(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """导出NPC数据（包括详细数据文件）"""
        entry = self.entries.get(npc_id)
        if not entry:
            return None

        export_data = entry.to_dict()

        # 尝试加载详细数据
        if entry.data_file and os.path.exists(entry.data_file):
            try:
                with gzip.open(entry.data_file, 'rt', encoding='utf-8') as f:
                    export_data['full_data'] = json.load(f)
            except Exception as e:
                logger.warning(f"加载NPC详细数据失败: {e}")

        return export_data

    def import_npc(self, data: Dict[str, Any]) -> Optional[NPCRegistryEntry]:
        """导入NPC数据"""
        try:
            # 创建注册表条目
            entry = NPCRegistryEntry.from_dict(data)

            # 检查槽位
            if not self._check_slot_available(entry.npc_type):
                logger.warning(f"槽位不足，无法导入 {entry.name}")
                return None

            # 添加到注册表
            self.entries[entry.id] = entry

            # 如果有完整数据，保存到文件
            if 'full_data' in data and entry.data_file:
                with gzip.open(entry.data_file, 'wt', encoding='utf-8') as f:
                    json.dump(data['full_data'], f, ensure_ascii=False, indent=2)

            self._save_registry()
            logger.info(f"导入NPC: {entry.name}")
            return entry

        except Exception as e:
            logger.error(f"导入NPC失败: {e}")
            return None

    # ==================== 统计信息 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        entries = list(self.entries.values())

        status_counts = {}
        type_counts = {}
        location_counts = {}

        for entry in entries:
            status_counts[entry.status] = status_counts.get(entry.status, 0) + 1
            type_counts[entry.npc_type] = type_counts.get(entry.npc_type, 0) + 1
            if entry.status == "active":
                location_counts[entry.location] = location_counts.get(entry.location, 0) + 1

        return {
            "total_npcs": len(entries),
            "active_npcs": status_counts.get("active", 0),
            "core_npcs": len(self.core_npcs),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "location_distribution": location_counts,
            "slot_status": self.get_slot_status()
        }


# ==================== 全局访问 ====================

_registry_instance: Optional[NPCRegistry] = None

def get_npc_registry(storage_dir: str = "npc_storage") -> NPCRegistry:
    """获取NPC注册表实例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = NPCRegistry(storage_dir)
    return _registry_instance

def reset_npc_registry():
    """重置NPC注册表（用于测试）"""
    global _registry_instance
    if _registry_instance:
        NPCRegistry._instance = None
        NPCRegistry._lock = threading.Lock()
    _registry_instance = None


# ==================== 使用示例 ====================

USAGE_EXAMPLE = """
## 基本使用

```python
from npc_core.npc_registry import get_npc_registry, NPCRegistry

# 获取注册表
registry = get_npc_registry()

# 注册新NPC
entry = registry.register_npc(
    name="李旅商",
    npc_type="temporary",
    location="村口",
    profession="商人",
    traits=["精明", "健谈"],
    origin="event",
    origin_event_id="evt_001"
)

# 查询NPC
npc = registry.get_by_name("李旅商")
active_npcs = registry.get_active_npcs()

# 更新NPC
registry.update_location(npc.id, "集市")
registry.record_interaction(npc.id, "杂货店老板")

# 移除NPC
registry.unregister_npc(name="李旅商", reason="left", witnesses=["杂货店老板"])

# 查看槽位状态
status = registry.get_slot_status()
print(f"剩余槽位: {status['available_slots']}")
```

## 与三方交互系统集成

```python
from npc_optimization.tripartite_interaction import InteractionManager

# 设置记忆回调
def memory_callback(event_type, content, related_entities, metadata):
    interaction_manager.memory.world_memory.append(MemoryEntry(
        content=content,
        memory_type=event_type,
        importance=60,
        related_entities=related_entities,
        metadata=metadata
    ))

registry.set_memory_callback(memory_callback)
```
"""


__all__ = [
    'NPCLifecycleStatus',
    'NPCType',
    'NPCRegistryEntry',
    'NPCRegistry',
    'get_npc_registry',
    'reset_npc_registry',
]
