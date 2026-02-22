# -*- coding: utf-8 -*-
"""
三方交互系统：世界-NPC-玩家
============================

核心设计原则：
1. 事件中的角色默认是"未实例化的描述"
2. 只有当产生有意义的交互时，才实例化为NPC
3. NPC的创建/销毁作为记忆存入三方记忆系统

判断实例化的触发条件：
- 玩家主动与该角色互动
- NPC主动与该角色互动
- 该角色对剧情产生了持续影响
- LLM判断该角色值得追踪

记忆归属：
- 世界记忆：NPC的存在、状态变化（公共知识）
- NPC记忆：与该角色的个人交互
- 玩家记忆：玩家视角的认知
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


# ==================== 角色状态 ====================

class EntityType(Enum):
    """实体类型"""
    DESCRIPTION = "description"   # 仅描述（如"一个商人"）
    INSTANCE = "instance"         # 已实例化NPC
    PLAYER = "player"             # 玩家
    WORLD = "world"               # 世界本身


class InteractionType(Enum):
    """交互类型"""
    OBSERVE = "observe"           # 观察（不触发实例化）
    TALK = "talk"                 # 对话（可能触发实例化）
    TRADE = "trade"               # 交易（触发实例化）
    CONFLICT = "conflict"         # 冲突（触发实例化）
    COOPERATE = "cooperate"       # 合作（触发实例化）


@dataclass
class UninstantiatedEntity:
    """
    未实例化的实体（事件中的角色描述）

    例如："村口来了个旅行商人" 中的 "旅行商人"
    在产生有意义交互前，只是一个描述，不占用NPC槽位
    """
    description: str              # "旅行商人"
    location: str                 # "村口"
    source_event_id: str          # 来源事件
    created_at: datetime = field(default_factory=datetime.now)

    # 交互记录
    interactions: List[Dict[str, Any]] = field(default_factory=list)

    # 潜在属性（LLM可以补充）
    potential_name: Optional[str] = None      # "老李"
    potential_profession: Optional[str] = None # "商人"
    potential_traits: List[str] = field(default_factory=list)

    def add_interaction(self, actor: str, interaction_type: InteractionType, content: str):
        """记录交互"""
        self.interactions.append({
            "actor": actor,
            "type": interaction_type.value,
            "content": content,
            "time": datetime.now().isoformat()
        })

    @property
    def interaction_count(self) -> int:
        return len(self.interactions)

    @property
    def has_meaningful_interaction(self) -> bool:
        """是否有有意义的交互（可能需要实例化）"""
        meaningful_types = {InteractionType.TALK, InteractionType.TRADE,
                          InteractionType.CONFLICT, InteractionType.COOPERATE}
        return any(
            InteractionType(i["type"]) in meaningful_types
            for i in self.interactions
        )


# ==================== 三方记忆接口 ====================

@dataclass
class MemoryEntry:
    """记忆条目"""
    content: str
    memory_type: str              # "npc_created", "npc_removed", "interaction", etc.
    importance: int               # 0-100
    timestamp: datetime = field(default_factory=datetime.now)
    related_entities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TripartiteMemory:
    """
    三方记忆系统

    管理世界、NPC、玩家三方的记忆，确保一致性
    """

    def __init__(self):
        # 世界记忆（公共知识）
        self.world_memory: List[MemoryEntry] = []

        # NPC记忆（每个NPC独立）
        self.npc_memories: Dict[str, List[MemoryEntry]] = {}

        # 玩家记忆
        self.player_memory: List[MemoryEntry] = []

    def record_npc_creation(self, npc_name: str, origin: str,
                            witnesses: List[str] = None):
        """
        记录NPC创建

        - 世界记忆：公共记录
        - 见证者记忆：个人视角
        """
        # 世界记忆
        world_entry = MemoryEntry(
            content=f"{npc_name} 出现在了这个世界 ({origin})",
            memory_type="npc_created",
            importance=60,
            related_entities=[npc_name],
            metadata={"origin": origin}
        )
        self.world_memory.append(world_entry)

        # 见证者记忆
        for witness in (witnesses or []):
            self._ensure_npc_memory(witness)
            entry = MemoryEntry(
                content=f"我遇见了{npc_name}",
                memory_type="npc_encountered",
                importance=50,
                related_entities=[npc_name]
            )
            self.npc_memories[witness].append(entry)

    def record_npc_removal(self, npc_name: str, reason: str,
                           witnesses: List[str] = None):
        """
        记录NPC移除

        reason: "left", "deceased", "imprisoned", etc.
        """
        reason_text = {
            "left": f"{npc_name} 离开了村庄",
            "deceased": f"{npc_name} 去世了",
            "imprisoned": f"{npc_name} 被关押了",
        }.get(reason, f"{npc_name} 不再出现")

        # 世界记忆
        world_entry = MemoryEntry(
            content=reason_text,
            memory_type="npc_removed",
            importance=70,
            related_entities=[npc_name],
            metadata={"reason": reason}
        )
        self.world_memory.append(world_entry)

        # 见证者记忆
        for witness in (witnesses or []):
            self._ensure_npc_memory(witness)
            entry = MemoryEntry(
                content=f"我得知{reason_text}",
                memory_type="npc_status_change",
                importance=60,
                related_entities=[npc_name]
            )
            self.npc_memories[witness].append(entry)

    def record_interaction(self, actor1: str, actor2: str,
                          interaction_content: str, importance: int = 50):
        """记录两个实体之间的交互"""
        # 双方都记录
        for actor, other in [(actor1, actor2), (actor2, actor1)]:
            if actor == "player":
                entry = MemoryEntry(
                    content=f"与{other}的交互: {interaction_content}",
                    memory_type="interaction",
                    importance=importance,
                    related_entities=[other]
                )
                self.player_memory.append(entry)
            elif actor == "world":
                entry = MemoryEntry(
                    content=interaction_content,
                    memory_type="world_event",
                    importance=importance,
                    related_entities=[other]
                )
                self.world_memory.append(entry)
            else:
                self._ensure_npc_memory(actor)
                entry = MemoryEntry(
                    content=f"与{other}的交互: {interaction_content}",
                    memory_type="interaction",
                    importance=importance,
                    related_entities=[other]
                )
                self.npc_memories[actor].append(entry)

    def _ensure_npc_memory(self, npc_name: str):
        """确保NPC记忆存在"""
        if npc_name not in self.npc_memories:
            self.npc_memories[npc_name] = []

    def get_world_knowledge_about(self, entity_name: str) -> List[MemoryEntry]:
        """获取世界对某实体的记忆"""
        return [m for m in self.world_memory if entity_name in m.related_entities]

    def get_npc_knowledge_about(self, npc_name: str, entity_name: str) -> List[MemoryEntry]:
        """获取NPC对某实体的记忆"""
        if npc_name not in self.npc_memories:
            return []
        return [m for m in self.npc_memories[npc_name] if entity_name in m.related_entities]


# ==================== 实例化判定器 ====================

class InstantiationJudge:
    """
    实例化判定器

    决定事件中的角色描述是否应该实例化为NPC
    """

    # 需要实例化的交互类型
    INSTANTIATION_TRIGGERS = {
        InteractionType.TRADE,      # 交易必须实例化
        InteractionType.CONFLICT,   # 冲突必须实例化
        InteractionType.COOPERATE,  # 合作必须实例化
    }

    # 对话实例化的阈值
    TALK_INSTANTIATION_THRESHOLD = 2  # 对话超过2次就实例化

    # LLM判定提示词
    INSTANTIATION_PROMPT = """你是世界模拟器。请判断以下事件中的角色是否需要实例化为NPC。

## 事件信息
{event_content}

## 角色描述
"{entity_description}" 位于 {location}

## 已发生的交互
{interactions}

## 判断标准
- 该角色是否会持续参与剧情？
- 该角色是否与玩家/NPC建立了关系？
- 该角色是否有独特的价值（交易、信息、任务等）？
- 该角色是一个"路人甲"还是"有名有姓的人物"？

## 请回答（JSON格式）
{{
    "should_instantiate": true/false,
    "reasoning": "判断理由",
    "suggested_name": "如果实例化，建议的名字",
    "suggested_traits": ["特征1", "特征2"],
    "potential_role": "该角色可能扮演的剧情角色"
}}"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def should_instantiate_sync(self, entity: UninstantiatedEntity) -> Tuple[bool, str]:
        """
        同步判断是否应该实例化（基于规则）

        Returns:
            (是否实例化, 原因)
        """
        # 规则1: 触发类型判断
        for interaction in entity.interactions:
            itype = InteractionType(interaction["type"])
            if itype in self.INSTANTIATION_TRIGGERS:
                return True, f"触发了{itype.value}交互"

        # 规则2: 多次对话
        talk_count = sum(1 for i in entity.interactions
                        if i["type"] == InteractionType.TALK.value)
        if talk_count >= self.TALK_INSTANTIATION_THRESHOLD:
            return True, f"对话次数达到{talk_count}次"

        # 规则3: 有潜在名字（已经被"命名"了）
        if entity.potential_name:
            return True, f"已被命名为'{entity.potential_name}'"

        return False, "未达到实例化条件"

    async def should_instantiate_llm(self, entity: UninstantiatedEntity,
                                      event_content: str) -> Tuple[bool, Dict[str, Any]]:
        """
        使用LLM判断是否应该实例化

        Returns:
            (是否实例化, LLM返回的详细信息)
        """
        if not self.llm_client:
            should, reason = self.should_instantiate_sync(entity)
            return should, {"reasoning": reason}

        interactions_str = "\n".join([
            f"- {i['actor']} {i['type']}: {i['content']}"
            for i in entity.interactions
        ]) or "（无交互记录）"

        prompt = self.INSTANTIATION_PROMPT.format(
            event_content=event_content,
            entity_description=entity.description,
            location=entity.location,
            interactions=interactions_str
        )

        try:
            response = await asyncio.to_thread(
                self.llm_client.generate_response,
                prompt=prompt,
                context={},
                temperature=0.7,
                max_tokens=300
            )

            import json
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return data.get("should_instantiate", False), data

        except Exception as e:
            logger.warning(f"LLM判定失败: {e}")

        # 回退到规则判定
        should, reason = self.should_instantiate_sync(entity)
        return should, {"reasoning": reason}


# ==================== 统一交互管理器 ====================

class InteractionManager:
    """
    统一交互管理器

    处理世界-NPC-玩家之间的所有交互，
    管理实体的实例化生命周期

    与NPCRegistry集成：实例化的NPC自动注册到全局注册表
    """

    NPC_LIMIT = 15
    TEMP_NPC_LIMIT = 5

    def __init__(self, llm_client=None, npc_registry=None):
        self.llm_client = llm_client

        # 记忆系统
        self.memory = TripartiteMemory()

        # 实例化判定器
        self.judge = InstantiationJudge(llm_client)

        # 未实例化的实体池
        self.uninstantiated: Dict[str, UninstantiatedEntity] = {}

        # NPC注册表（可选，如果提供则使用全局注册表）
        self._npc_registry = npc_registry

        # 如果没有提供注册表，使用内部存储（兼容模式）
        self.npcs: Dict[str, Dict[str, Any]] = {}
        self.npc_counter = 0

        # 核心NPC（不可删除）
        self.core_npcs: set = set()

    @property
    def npc_registry(self):
        """延迟加载NPC注册表"""
        if self._npc_registry is None:
            try:
                from npc_core.npc_registry import get_npc_registry
                self._npc_registry = get_npc_registry()
            except ImportError:
                logger.warning("无法导入NPCRegistry，使用内部存储")
        return self._npc_registry

    def process_world_event(self, event_content: str, location: str,
                            event_id: str) -> List[UninstantiatedEntity]:
        """
        处理世界事件，提取其中的角色描述

        "村口来了个旅行商人" → 创建 UninstantiatedEntity("旅行商人")
        """
        # 这里简化处理，实际应该用NLP或LLM提取
        # 示例：检测常见角色词
        role_keywords = ["商人", "旅行者", "陌生人", "骑士", "流浪汉", "贵族", "士兵"]

        entities = []
        for keyword in role_keywords:
            if keyword in event_content:
                entity = UninstantiatedEntity(
                    description=keyword,
                    location=location,
                    source_event_id=event_id
                )
                entity_id = f"ue_{event_id}_{keyword}"
                self.uninstantiated[entity_id] = entity
                entities.append(entity)

                logger.info(f"检测到未实例化实体: '{keyword}' @ {location}")

        return entities

    async def handle_interaction(
        self,
        actor: str,                    # 发起者（NPC名/player/world）
        target_description: str,       # 目标描述（"那个商人"）
        interaction_type: InteractionType,
        content: str,
        event_id: str = None
    ) -> Tuple[bool, Optional[str]]:
        """
        处理交互

        Returns:
            (是否触发实例化, 实例化后的NPC ID)
        """
        # 1. 查找目标实体
        target_entity = None
        entity_id = None
        for eid, entity in self.uninstantiated.items():
            if entity.description in target_description or target_description in entity.description:
                target_entity = entity
                entity_id = eid
                break

        if not target_entity:
            # 可能是新出现的角色，创建实体
            target_entity = UninstantiatedEntity(
                description=target_description,
                location="unknown",
                source_event_id=event_id or "unknown"
            )
            entity_id = f"ue_{datetime.now().strftime('%H%M%S')}_{target_description[:10]}"
            self.uninstantiated[entity_id] = target_entity

        # 2. 记录交互
        target_entity.add_interaction(actor, interaction_type, content)

        # 3. 判断是否需要实例化
        should_instantiate, details = await self.judge.should_instantiate_llm(
            target_entity,
            f"{actor} {interaction_type.value} {target_description}: {content}"
        )

        if should_instantiate:
            # 4. 执行实例化
            npc_id = await self._instantiate_entity(target_entity, entity_id, details)
            return True, npc_id

        return False, None

    async def _instantiate_entity(
        self,
        entity: UninstantiatedEntity,
        entity_id: str,
        llm_details: Dict[str, Any]
    ) -> Optional[str]:
        """
        将实体实例化为NPC

        优先使用NPCRegistry（如果可用），否则使用内部存储
        """
        npc_name = llm_details.get("suggested_name") or entity.potential_name or f"无名{entity.description}"
        traits = llm_details.get("suggested_traits", [])

        # 尝试使用全局注册表
        if self.npc_registry:
            entry = self.npc_registry.register_npc(
                name=npc_name,
                npc_type="dynamic",  # 由事件动态生成
                location=entity.location,
                profession=entity.potential_profession or entity.description,
                traits=traits,
                origin="event",
                origin_event_id=entity.source_event_id,
                metadata={
                    "potential_role": llm_details.get("potential_role", ""),
                    "instantiation_reason": llm_details.get("reasoning", ""),
                    "interaction_history": entity.interactions.copy()
                }
            )

            if entry is None:
                logger.warning(f"注册表槽位已满，无法实例化 '{entity.description}'")
                return None

            npc_id = entry.id

        else:
            # 回退到内部存储
            active_count = len([n for n in self.npcs.values() if n.get("status") == "active"])
            if active_count >= self.NPC_LIMIT:
                logger.warning(f"NPC已达上限 ({self.NPC_LIMIT})，无法实例化")
                return None

            self.npc_counter += 1
            npc_id = f"npc_{self.npc_counter:04d}"

            npc_data = {
                "id": npc_id,
                "name": npc_name,
                "profession": entity.potential_profession or entity.description,
                "location": entity.location,
                "status": "active",
                "origin_event_id": entity.source_event_id,
                "traits": traits,
                "potential_role": llm_details.get("potential_role", ""),
                "created_at": datetime.now().isoformat(),
                "interaction_history": entity.interactions.copy()
            }

            self.npcs[npc_id] = npc_data

        # 从未实例化池移除
        if entity_id in self.uninstantiated:
            del self.uninstantiated[entity_id]

        # 记录到三方记忆
        witnesses = [i["actor"] for i in entity.interactions if i["actor"] != "world"]
        self.memory.record_npc_creation(npc_name, entity.source_event_id, witnesses)

        logger.info(f"实体实例化为NPC: '{entity.description}' -> {npc_name} ({npc_id})")

        return npc_id

    def remove_npc(self, npc_id: str = None, name: str = None,
                   reason: str = "left", witnesses: List[str] = None) -> bool:
        """
        移除NPC

        Args:
            npc_id: NPC ID（优先）
            name: NPC名称
            reason: 移除原因 (left/deceased/imprisoned)
            witnesses: 见证者列表

        Returns:
            是否成功
        """
        # 尝试使用全局注册表
        if self.npc_registry:
            success = self.npc_registry.unregister_npc(
                npc_id=npc_id,
                name=name,
                reason=reason,
                witnesses=witnesses
            )
            if success:
                # 同步到三方记忆
                npc_name = name
                if npc_id:
                    entry = self.npc_registry.get(npc_id)
                    if entry:
                        npc_name = entry.name
                if npc_name:
                    self.memory.record_npc_removal(npc_name, reason, witnesses)
            return success

        # 回退到内部存储
        if name and not npc_id:
            # 按名字查找
            for _id, npc in self.npcs.items():
                if npc.get("name") == name:
                    npc_id = _id
                    break

        if not npc_id or npc_id not in self.npcs:
            return False

        npc = self.npcs[npc_id]
        if npc_id in self.core_npcs:
            logger.warning(f"无法移除核心NPC: {npc['name']}")
            return False

        # 更新状态
        npc["status"] = reason  # "left", "deceased", "imprisoned"

        # 记录到记忆
        self.memory.record_npc_removal(npc["name"], reason, witnesses)

        logger.info(f"NPC状态变更: {npc['name']} -> {reason}")
        return True

    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        uninstantiated_count = len(self.uninstantiated)

        # 优先使用注册表
        if self.npc_registry:
            stats = self.npc_registry.get_statistics()
            return {
                "active_npcs": stats["active_npcs"],
                "npc_limit": self.npc_registry.ACTIVE_NPC_LIMIT,
                "uninstantiated_entities": uninstantiated_count,
                "world_memory_count": len(self.memory.world_memory),
                "npc_names": self.npc_registry.get_active_names(),
                "slot_status": stats["slot_status"]
            }

        # 回退到内部存储
        active_npcs = [n for n in self.npcs.values() if n.get("status") == "active"]
        return {
            "active_npcs": len(active_npcs),
            "npc_limit": self.NPC_LIMIT,
            "uninstantiated_entities": uninstantiated_count,
            "world_memory_count": len(self.memory.world_memory),
            "npc_names": [n["name"] for n in active_npcs]
        }


# ==================== 使用示例 ====================

USAGE_EXAMPLE = """
## 场景："村口来了个旅行商人"

### 步骤1: 世界事件触发
```python
manager = InteractionManager(llm_client)
entities = manager.process_world_event(
    event_content="村口来了一个旅行商人，背着沉重的货物",
    location="村口",
    event_id="evt_001"
)
# 结果: 创建 UninstantiatedEntity("商人")
# 此时商人只是"描述"，不占用NPC槽位
```

### 步骤2: NPC观察（不触发实例化）
```python
await manager.handle_interaction(
    actor="农夫",
    target_description="那个商人",
    interaction_type=InteractionType.OBSERVE,
    content="远远看到有人来了"
)
# 结果: 记录交互，但仍未实例化
```

### 步骤3: 玩家/NPC对话（可能触发实例化）
```python
instantiated, npc_id = await manager.handle_interaction(
    actor="杂货店老板",
    target_description="商人",
    interaction_type=InteractionType.TALK,
    content="你好，卖什么货？"
)
# 第一次对话，仍未实例化
```

### 步骤4: 交易（触发实例化）
```python
instantiated, npc_id = await manager.handle_interaction(
    actor="杂货店老板",
    target_description="商人",
    interaction_type=InteractionType.TRADE,
    content="我想买些香料"
)
# 结果:
#   instantiated = True
#   npc_id = "npc_0001"
#   商人被实例化为 "李商人"
#   世界记忆: "李商人 出现在了这个世界"
#   杂货店老板记忆: "我遇见了李商人"
```

### 步骤5: 商人离开（NPC移除）
```python
manager.remove_npc(npc_id, reason="left", witnesses=["杂货店老板"])
# 结果:
#   NPC状态: "left"
#   世界记忆: "李商人 离开了村庄"
#   杂货店老板记忆: "我得知李商人离开了村庄"
```

## 关键点

1. **延迟实例化**: 角色在产生有意义交互前只是描述
2. **交互驱动**: 交易/冲突/合作等交互触发实例化
3. **记忆同步**: NPC创建/销毁自动记录到三方记忆
4. **槽位保护**: 只有实例化的NPC占用槽位
"""


__all__ = [
    'EntityType',
    'InteractionType',
    'UninstantiatedEntity',
    'MemoryEntry',
    'TripartiteMemory',
    'InstantiationJudge',
    'InteractionManager',
]
