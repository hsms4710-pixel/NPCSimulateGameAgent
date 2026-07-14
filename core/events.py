"""事件系统 — 空间广播 + 八卦传播 + 影响力评分

保留原有设定：
- 空间广播：基于地理位置的事件传播
- 八卦传播：社交链异步扩散
- 事件影响力：决定 NPC 是否触发反思
"""
import logging, time
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class WorldEvent:
    id: str
    timestamp: str
    type: str  # move / dialogue / trade / work / rest / quest / custom
    content: str
    location: str = ""
    importance: int = 3  # 1-10
    source_npc: str = ""
    target_npc: str = ""
    spread_to: Set[str] = field(default_factory=set)  # 已传播到的 NPC
    gossiped_by: Set[str] = field(default_factory=set)  # 已八卦传播的 NPC


class EventSystem:
    """事件管理 + 空间广播 + 八卦传播"""

    def __init__(self):
        self.events: List[WorldEvent] = []
        self.event_id_counter = 0
        self.npc_relationships: Dict[str, Set[str]] = {}  # NPC名 -> 认识的NPC列表

    def add_event(self, content: str, etype: str = "custom", location: str = "",
                  importance: int = 3, source_npc: str = "", target_npc: str = "") -> WorldEvent:
        self.event_id_counter += 1
        evt = WorldEvent(
            id=f"evt-{self.event_id_counter}",
            timestamp=datetime.now().isoformat(),
            type=etype, content=content, location=location,
            importance=importance, source_npc=source_npc, target_npc=target_npc,
        )
        self.events.append(evt)
        if len(self.events) > 500:
            self.events = self.events[-300:]
        return evt

    def register_relationship(self, npc1: str, npc2: str):
        self.npc_relationships.setdefault(npc1, set()).add(npc2)
        self.npc_relationships.setdefault(npc2, set()).add(npc1)

    def get_events_at(self, location: str, since: str = "") -> List[WorldEvent]:
        """空间广播 — 获取某位置的近期事件"""
        result = []
        for evt in reversed(self.events):
            if evt.location == location:
                if not since or evt.timestamp > since:
                    result.append(evt)
            if len(result) >= 10:
                break
        return result

    def get_gossip_for(self, npc_name: str) -> List[WorldEvent]:
        """八卦传播 — 获取NPC通过八卦得知的事件"""
        result = []
        acquaintances = self.npc_relationships.get(npc_name, set())
        for evt in reversed(self.events):
            if evt.importance >= 4 and npc_name not in evt.spread_to:
                # 消息源或目标NPC认识当前NPC
                if evt.source_npc in acquaintances or evt.target_npc in acquaintances:
                    if npc_name not in evt.gossiped_by:
                        result.append(evt)
                        evt.gossiped_by.add(npc_name)
                        evt.spread_to.add(npc_name)
            if len(result) >= 5:
                break
        return result

    def get_npc_events(self, npc_name: str, location: str) -> List[WorldEvent]:
        """获取NPC可见的事件 — 空间广播 + 八卦"""
        spatial = self.get_events_at(location)
        gossip = self.get_gossip_for(npc_name)
        seen_ids = set()
        result = []
        for evt in spatial + gossip:
            if evt.id not in seen_ids:
                seen_ids.add(evt.id)
                result.append(evt)
        return result[-10:]

    def to_dict(self) -> dict:
        return {
            "total_events": len(self.events),
            "recent": [{"content": e.content[:60], "type": e.type, "location": e.location, "importance": e.importance}
                       for e in self.events[-5:]],
        }
