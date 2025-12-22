"""
异步消息总线与社交系统
支持NPC间的信息扩散与空间感知
"""

import uuid
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue, PriorityQueue
import heapq

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    SPATIAL_EVENT = "spatial_event"  # 空间事件（有范围衰减）
    GOSSIP = "gossip"  # 八卦（通过社交传播）
    EMERGENCY = "emergency"  # 紧急事件（无范围限制）
    OBSERVATION = "observation"  # 观察到的事件
    SOCIAL_UPDATE = "social_update"  # 社交关系更新


@dataclass
class SpatialMessage:
    """空间消息 - 具有地理衰减的消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message_type: MessageType = MessageType.SPATIAL_EVENT
    
    source_npc: str = ""  # 消息来源NPC
    event_content: str = ""  # 事件内容
    
    origin_location: tuple = (0, 0)  # 事件发生位置 (x, y)
    spatial_range: float = 50.0  # 可感知范围（单位：米）
    
    intensity: float = 1.0  # 事件强度 0-1，影响传播范围
    
    # 消息传播跟踪
    aware_npcs: List[str] = field(default_factory=list)  # 已感知的NPC列表
    relay_count: int = 0  # 中继次数
    max_relays: int = 3  # 最大中继次数
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None  # 消息过期时间

    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.expires_at is None:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()

    def can_relay(self) -> bool:
        """检查是否还能继续中继"""
        return self.relay_count < self.max_relays

    def distance_to_location(self, location: tuple) -> float:
        """计算到某位置的距离"""
        dx = location[0] - self.origin_location[0]
        dy = location[1] - self.origin_location[1]
        return (dx**2 + dy**2)**0.5

    def is_within_range(self, location: tuple) -> bool:
        """检查位置是否在消息范围内"""
        distance = self.distance_to_location(location)
        # 强度越高，范围越大
        effective_range = self.spatial_range * self.intensity
        return distance <= effective_range


@dataclass
class GossipMessage:
    """八卦消息 - 通过社交传播的信息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    original_source: str = ""  # 原始来源NPC
    current_holder: str = ""  # 当前持有此八卦的NPC
    
    content: str = ""  # 八卦内容
    credibility: float = 0.8  # 可信度 0-1，每次传播递减
    
    # 传播跟踪
    spread_chain: List[str] = field(default_factory=list)  # 传播链: [A->B->C]
    told_to_npcs: List[str] = field(default_factory=list)
    
    emotional_tone: str = "neutral"  # positive, neutral, negative
    distortion_factor: float = 1.0  # 变形程度（高于1表示已扭曲）

    def relay_to(self, new_npc: str) -> "GossipMessage":
        """中继八卦给另一个NPC"""
        new_message = GossipMessage(
            original_source=self.original_source,
            current_holder=new_npc,
            content=self.content,
            credibility=self.credibility * 0.9,  # 可信度每次中继递减10%
            spread_chain=self.spread_chain + [new_npc],
            emotional_tone=self.emotional_tone,
            distortion_factor=self.distortion_factor * 1.1
        )
        return new_message


class WorldEventManager:
    """
    全局事件管理器 - 消息总线核心
    管理NPC间的信息流动和感知
    """

    def __init__(self, world_size: tuple = (1000, 1000)):
        self.world_size = world_size
        
        # 消息队列
        self.spatial_messages: List[SpatialMessage] = []
        self.gossip_messages: Dict[str, List[GossipMessage]] = {}  # 按NPC分组
        
        # NPC位置索引（用于快速范围查询）
        self.npc_positions: Dict[str, tuple] = {}  # {npc_name: (x, y)}
        
        # 锁机制
        self.lock = threading.RLock()
        
        # 后台清理线程
        self.cleanup_thread = None
        self.running = False

    def start(self):
        """启动事件管理器"""
        self.running = True
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True
        )
        self.cleanup_thread.start()

    def stop(self):
        """停止事件管理器"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)

    def update_npc_position(self, npc_name: str, location: tuple):
        """更新NPC位置"""
        with self.lock:
            self.npc_positions[npc_name] = location

    def broadcast_spatial_event(self,
                               source_npc: str,
                               event_content: str,
                               location: tuple,
                               intensity: float = 0.7,
                               range_meters: float = 50.0) -> SpatialMessage:
        """
        广播空间事件
        
        Returns:
            创建的消息对象
        """
        message = SpatialMessage(
            source_npc=source_npc,
            event_content=event_content,
            origin_location=location,
            spatial_range=range_meters,
            intensity=intensity,
            expires_at=(
                datetime.now() + timedelta(hours=1)
            ).isoformat()
        )
        
        with self.lock:
            self.spatial_messages.append(message)
        
        logger.info(
            f"广播空间事件: {source_npc} @ {location}, "
            f"范围: {range_meters}m, 强度: {intensity}"
        )
        
        return message

    def get_spatial_perception(self,
                               npc_name: str,
                               npc_location: tuple,
                               perception_radius: float = 100.0) -> List[Dict[str, Any]]:
        """
        获取NPC的空间感知（本次evaluation_loop会感知的事件）
        
        Returns:
            [
                {
                    "message_id": str,
                    "source_npc": str,
                    "content": str,
                    "distance": float,
                    "intensity": float
                }
            ]
        """
        
        with self.lock:
            perceived_events = []
            
            for message in self.spatial_messages:
                if message.is_expired():
                    continue
                
                # 检查是否在范围内
                if not message.is_within_range(npc_location):
                    continue
                
                # 不能感知自己的消息（在这个循环）
                if message.source_npc == npc_name:
                    continue
                
                # 计算距离（用于优先级排序）
                distance = message.distance_to_location(npc_location)
                
                perceived_events.append({
                    "message_id": message.id,
                    "source_npc": message.source_npc,
                    "content": message.event_content,
                    "distance": distance,
                    "intensity": message.intensity,
                    "timestamp": message.timestamp
                })
            
            # 按距离排序（最近的优先）
            perceived_events.sort(key=lambda x: x["distance"])
            
            return perceived_events

    def start_social_gossip(self,
                           original_source: str,
                           gossip_content: str,
                           emotional_tone: str = "neutral") -> GossipMessage:
        """
        启动八卦传播
        
        Args:
            original_source: 原始来源NPC
            gossip_content: 八卦内容
            emotional_tone: 情感色彩 (positive, neutral, negative)
        
        Returns:
            创建的八卦消息
        """
        
        message = GossipMessage(
            original_source=original_source,
            current_holder=original_source,
            content=gossip_content,
            spread_chain=[original_source],
            emotional_tone=emotional_tone
        )
        
        with self.lock:
            if original_source not in self.gossip_messages:
                self.gossip_messages[original_source] = []
            self.gossip_messages[original_source].append(message)
        
        logger.info(f"开始八卦传播: {original_source} - {gossip_content[:30]}...")
        
        return message

    def relay_gossip(self,
                    gossip_id: str,
                    from_npc: str,
                    to_npc: str) -> Optional[GossipMessage]:
        """
        中继八卦给另一个NPC
        （通常在两个NPC社交时调用）
        
        Returns:
            新的GossipMessage对象，或None如果八卦不存在
        """
        
        with self.lock:
            # 查找原始八卦
            source_gossip = None
            for gossip_list in self.gossip_messages.values():
                for gossip in gossip_list:
                    if gossip.id == gossip_id:
                        source_gossip = gossip
                        break
            
            if not source_gossip:
                logger.warning(f"未找到八卦: {gossip_id}")
                return None
            
            # 生成新的中继消息
            new_gossip = source_gossip.relay_to(to_npc)
            new_gossip.told_to_npcs.append(to_npc)
            
            if to_npc not in self.gossip_messages:
                self.gossip_messages[to_npc] = []
            self.gossip_messages[to_npc].append(new_gossip)
        
        logger.info(f"中继八卦: {from_npc} -> {to_npc}")
        
        return new_gossip

    def get_npc_gossips(self, npc_name: str) -> List[GossipMessage]:
        """获取某NPC持有的所有八卦"""
        with self.lock:
            return self.gossip_messages.get(npc_name, []).copy()

    def broadcast_emergency_alert(self,
                                  source_npc: str,
                                  alert_content: str,
                                  severity: float = 1.0):
        """
        广播紧急事件（不受范围限制，所有NPC都应该收到）
        
        Args:
            source_npc: 警报源
            alert_content: 警报内容
            severity: 严重程度 0-1
        """
        
        # 创建一个范围极大的空间事件
        emergency_message = SpatialMessage(
            message_type=MessageType.EMERGENCY,
            source_npc=source_npc,
            event_content=alert_content,
            origin_location=(
                self.world_size[0] // 2,
                self.world_size[1] // 2
            ),
            spatial_range=max(self.world_size) * 2,  # 覆盖整个世界
            intensity=severity,
            expires_at=(
                datetime.now() + timedelta(hours=2)
            ).isoformat()
        )
        
        with self.lock:
            self.spatial_messages.append(emergency_message)
        
        logger.warning(f"紧急警报: {source_npc} - {alert_content}")

    def _cleanup_worker(self):
        """后台清理过期消息"""
        while self.running:
            try:
                threading.Event().wait(60)  # 每分钟清理一次
                
                with self.lock:
                    # 清理过期的空间消息
                    self.spatial_messages = [
                        msg for msg in self.spatial_messages
                        if not msg.is_expired()
                    ]
                    
                    # 清理过期的八卦
                    cutoff_time = datetime.now() - timedelta(days=7)
                    for npc_name in self.gossip_messages:
                        self.gossip_messages[npc_name] = [
                            gossip for gossip in self.gossip_messages[npc_name]
                            if datetime.fromisoformat(gossip.timestamp) > cutoff_time
                        ]
                
                logger.debug("已清理过期消息")
            
            except Exception as e:
                logger.error(f"清理线程错误: {e}")

    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        with self.lock:
            return {
                "spatial_messages_count": len(self.spatial_messages),
                "gossip_messages_count": sum(
                    len(v) for v in self.gossip_messages.values()
                ),
                "tracked_npcs": len(self.npc_positions)
            }


class NPCToolRegistry_SocialExtension:
    """
    NPC工具注册表的社交扩展
    为Agent添加社交相关工具
    """

    def __init__(self, world_event_manager: WorldEventManager):
        self.world_event_manager = world_event_manager

    def register_social_tools(self, tool_registry):
        """注册社交工具到NPCToolRegistry"""
        
        # 工具1：观察世界事件
        def inspect_world_events(npc_name: str, location: tuple) -> Dict[str, Any]:
            """
            Agent工具：查询周围发生了什么事件
            允许Agent主动感知环境
            """
            events = self.world_event_manager.get_spatial_perception(
                npc_name, location
            )
            return {
                "nearby_events": events,
                "event_count": len(events)
            }
        
        # 工具2：启动社交对话
        def socialize_with_npc(source_npc: str,
                              target_npc: str,
                              interaction_type: str = "chat") -> Dict[str, Any]:
            """
            Agent工具：与另一个NPC进行社交
            interaction_type: chat, gossip, collaborate
            """
            return {
                "interaction_started": True,
                "target_npc": target_npc,
                "available_interactions": ["chat", "gossip", "help"],
                "relationship_potential": 0.7
            }
        
        # 工具3：主动广播事件
        def broadcast_observation(npc_name: str,
                                 observation: str,
                                 location: tuple,
                                 intensity: float = 0.5) -> Dict[str, Any]:
            """
            Agent工具：主动向周围广播观察到的事件
            """
            message = self.world_event_manager.broadcast_spatial_event(
                source_npc=npc_name,
                event_content=observation,
                location=location,
                intensity=intensity
            )
            return {
                "message_id": message.id,
                "broadcast_range": message.spatial_range,
                "affected_npcs": message.aware_npcs
            }
        
        # 工具4：查询已知八卦
        def query_known_gossips(npc_name: str) -> Dict[str, Any]:
            """
            Agent工具：查询NPC当前持有的所有八卦
            """
            gossips = self.world_event_manager.get_npc_gossips(npc_name)
            return {
                "gossip_count": len(gossips),
                "gossips": [
                    {
                        "id": g.id,
                        "content": g.content,
                        "source": g.original_source,
                        "credibility": g.credibility,
                        "emotional_tone": g.emotional_tone
                    }
                    for g in gossips
                ]
            }
        
        # 添加工具到registry（这里需要实际的NPCToolRegistry实现）
        # 伪代码示例
        tool_registry.register("inspect_world_events", inspect_world_events)
        tool_registry.register("socialize_with_npc", socialize_with_npc)
        tool_registry.register("broadcast_observation", broadcast_observation)
        tool_registry.register("query_known_gossips", query_known_gossips)
