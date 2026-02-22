"""
空间定位系统
管理NPC的位置、移动和区域交互
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ZoneType(Enum):
    """区域类型"""
    RESIDENTIAL = "residential"     # 居民区
    COMMERCIAL = "commercial"       # 商业区
    INDUSTRIAL = "industrial"       # 工业区
    RELIGIOUS = "religious"         # 宗教区
    NATURE = "nature"               # 自然区域
    PUBLIC = "public"               # 公共区域


@dataclass
class Location:
    """位置数据类"""
    name: str                       # 位置名称
    zone: str                       # 所属区域
    x: float = 0.0                  # X坐标
    y: float = 0.0                  # Y坐标
    zone_type: ZoneType = ZoneType.PUBLIC

    # 位置属性
    is_indoor: bool = False         # 是否室内
    capacity: int = 0               # 容量（0表示无限）
    is_private: bool = False        # 是否私人区域

    # 关联信息
    owner_id: Optional[str] = None  # 所有者NPC ID
    connected_locations: List[str] = field(default_factory=list)  # 相邻位置

    def distance_to(self, other: 'Location') -> float:
        """计算到另一个位置的距离"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def is_same_zone(self, other: 'Location') -> bool:
        """检查是否在同一区域"""
        return self.zone == other.zone


@dataclass
class NPCPosition:
    """NPC位置状态"""
    npc_id: str
    current_location: str           # 当前位置名称
    x: float = 0.0
    y: float = 0.0
    zone: str = ""

    # 移动状态
    is_moving: bool = False
    destination: Optional[str] = None
    path: List[str] = field(default_factory=list)
    movement_speed: float = 1.0     # 移动速度（单位/小时）

    # 时间戳
    arrived_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)


class SpatialSystem:
    """
    空间系统
    管理世界地图、位置和NPC移动
    """

    def __init__(self):
        self.locations: Dict[str, Location] = {}
        self.npc_positions: Dict[str, NPCPosition] = {}
        self.zones: Dict[str, Dict[str, Any]] = {}

        # 初始化默认地图
        self._init_default_map()

    def _init_default_map(self):
        """初始化艾伦谷默认地图"""
        # 定义区域
        self.zones = {
            "town_center": {
                "name": "镇中心",
                "type": ZoneType.PUBLIC,
                "description": "艾伦谷的中心广场"
            },
            "market": {
                "name": "市场区",
                "type": ZoneType.COMMERCIAL,
                "description": "热闹的交易市场"
            },
            "residential_north": {
                "name": "北区住宅",
                "type": ZoneType.RESIDENTIAL,
                "description": "镇北的居民区"
            },
            "industrial": {
                "name": "工坊区",
                "type": ZoneType.INDUSTRIAL,
                "description": "铁匠铺、木工坊等工坊聚集地"
            },
            "church_district": {
                "name": "教堂区",
                "type": ZoneType.RELIGIOUS,
                "description": "圣光教堂及周边"
            },
            "forest_edge": {
                "name": "森林边缘",
                "type": ZoneType.NATURE,
                "description": "艾伦谷外围的森林"
            }
        }

        # 定义具体位置
        default_locations = [
            # 镇中心
            Location("中心广场", "town_center", 0, 0, ZoneType.PUBLIC,
                    connected_locations=["市场入口", "北区大街", "工坊街", "教堂广场"]),
            Location("镇长府邸", "town_center", 10, 5, ZoneType.PUBLIC, is_indoor=True,
                    is_private=True, connected_locations=["中心广场"]),

            # 市场区
            Location("市场入口", "market", -20, 0, ZoneType.COMMERCIAL,
                    connected_locations=["中心广场", "水果摊", "杂货店", "酒馆"]),
            Location("水果摊", "market", -25, 5, ZoneType.COMMERCIAL,
                    connected_locations=["市场入口", "杂货店"]),
            Location("杂货店", "market", -25, -5, ZoneType.COMMERCIAL, is_indoor=True,
                    connected_locations=["市场入口", "水果摊"]),
            Location("酒馆", "market", -30, 0, ZoneType.COMMERCIAL, is_indoor=True, capacity=30,
                    connected_locations=["市场入口"]),

            # 工坊区
            Location("工坊街", "industrial", 20, 0, ZoneType.INDUSTRIAL,
                    connected_locations=["中心广场", "铁匠铺", "木工坊"]),
            Location("铁匠铺", "industrial", 25, 5, ZoneType.INDUSTRIAL, is_indoor=True,
                    owner_id="elder_blacksmith", connected_locations=["工坊街"]),
            Location("木工坊", "industrial", 25, -5, ZoneType.INDUSTRIAL, is_indoor=True,
                    connected_locations=["工坊街"]),

            # 北区住宅
            Location("北区大街", "residential_north", 0, 20, ZoneType.RESIDENTIAL,
                    connected_locations=["中心广场", "阿尔弗雷德的家", "玛丽的家"]),
            Location("阿尔弗雷德的家", "residential_north", 5, 25, ZoneType.RESIDENTIAL,
                    is_indoor=True, is_private=True, owner_id="elder_blacksmith",
                    connected_locations=["北区大街"]),
            Location("玛丽的家", "residential_north", -5, 25, ZoneType.RESIDENTIAL,
                    is_indoor=True, is_private=True, connected_locations=["北区大街"]),

            # 教堂区
            Location("教堂广场", "church_district", 0, -20, ZoneType.RELIGIOUS,
                    connected_locations=["中心广场", "圣光教堂"]),
            Location("圣光教堂", "church_district", 0, -30, ZoneType.RELIGIOUS,
                    is_indoor=True, capacity=100, connected_locations=["教堂广场"]),

            # 森林边缘
            Location("东森林入口", "forest_edge", 50, 0, ZoneType.NATURE,
                    connected_locations=["工坊街", "猎人小屋"]),
            Location("猎人小屋", "forest_edge", 60, 10, ZoneType.NATURE, is_indoor=True,
                    is_private=True, connected_locations=["东森林入口"]),
        ]

        for loc in default_locations:
            self.add_location(loc)

    def add_location(self, location: Location):
        """添加位置"""
        self.locations[location.name] = location
        logger.debug(f"添加位置: {location.name} ({location.zone})")

    def get_location(self, name: str) -> Optional[Location]:
        """获取位置信息"""
        return self.locations.get(name)

    def register_npc(self, npc_id: str, initial_location: str = "中心广场"):
        """注册NPC到空间系统"""
        location = self.get_location(initial_location)
        if not location:
            location = self.get_location("中心广场")
            initial_location = "中心广场"

        position = NPCPosition(
            npc_id=npc_id,
            current_location=initial_location,
            x=location.x if location else 0,
            y=location.y if location else 0,
            zone=location.zone if location else "town_center",
            arrived_at=datetime.now()
        )
        self.npc_positions[npc_id] = position
        logger.debug(f"NPC {npc_id} 注册到位置: {initial_location}")

    def get_npc_position(self, npc_id: str) -> Optional[NPCPosition]:
        """获取NPC位置"""
        return self.npc_positions.get(npc_id)

    def move_npc(self, npc_id: str, destination: str) -> bool:
        """
        移动NPC到目标位置

        Args:
            npc_id: NPC ID
            destination: 目标位置名称

        Returns:
            是否成功开始移动
        """
        position = self.get_npc_position(npc_id)
        if not position:
            logger.warning(f"NPC {npc_id} 未注册")
            return False

        dest_location = self.get_location(destination)
        if not dest_location:
            logger.warning(f"目标位置 {destination} 不存在")
            return False

        # 计算路径
        path = self._find_path(position.current_location, destination)
        if not path:
            logger.warning(f"无法找到从 {position.current_location} 到 {destination} 的路径")
            return False

        position.is_moving = True
        position.destination = destination
        position.path = path
        position.last_updated = datetime.now()

        return True

    def update_movement(self, npc_id: str, time_passed_hours: float) -> Optional[str]:
        """
        更新NPC移动状态

        Args:
            npc_id: NPC ID
            time_passed_hours: 经过的时间（小时）

        Returns:
            如果到达新位置，返回位置名称；否则返回None
        """
        position = self.get_npc_position(npc_id)
        if not position or not position.is_moving:
            return None

        if not position.path:
            position.is_moving = False
            return None

        # 计算可移动距离
        distance_can_travel = position.movement_speed * time_passed_hours

        # 逐步移动
        while distance_can_travel > 0 and position.path:
            next_loc_name = position.path[0]
            next_location = self.get_location(next_loc_name)
            if not next_location:
                position.path.pop(0)
                continue

            current_location = self.get_location(position.current_location)
            if not current_location:
                break

            distance_to_next = current_location.distance_to(next_location)

            if distance_can_travel >= distance_to_next:
                # 到达下一个位置
                distance_can_travel -= distance_to_next
                position.current_location = next_loc_name
                position.x = next_location.x
                position.y = next_location.y
                position.zone = next_location.zone
                position.path.pop(0)
                position.arrived_at = datetime.now()

                # 检查是否到达最终目的地
                if not position.path:
                    position.is_moving = False
                    position.destination = None
                    logger.debug(f"NPC {npc_id} 到达 {next_loc_name}")
                    return next_loc_name
            else:
                # 还在路上
                break

        position.last_updated = datetime.now()
        return None

    def _find_path(self, start: str, end: str) -> List[str]:
        """
        使用BFS查找路径

        Args:
            start: 起始位置
            end: 目标位置

        Returns:
            路径列表（不包含起点）
        """
        if start == end:
            return []

        start_loc = self.get_location(start)
        if not start_loc:
            return []

        # BFS
        visited = {start}
        queue = [(start, [])]

        while queue:
            current, path = queue.pop(0)
            current_loc = self.get_location(current)
            if not current_loc:
                continue

            for neighbor in current_loc.connected_locations:
                if neighbor == end:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []  # 没有找到路径

    def get_npcs_at_location(self, location_name: str) -> List[str]:
        """获取某位置的所有NPC"""
        return [
            npc_id for npc_id, pos in self.npc_positions.items()
            if pos.current_location == location_name and not pos.is_moving
        ]

    def get_npcs_in_zone(self, zone: str) -> List[str]:
        """获取某区域的所有NPC"""
        return [
            npc_id for npc_id, pos in self.npc_positions.items()
            if pos.zone == zone
        ]

    def get_nearby_npcs(self, npc_id: str, radius: float = 10.0) -> List[Tuple[str, float]]:
        """
        获取附近的NPC

        Args:
            npc_id: 中心NPC ID
            radius: 搜索半径

        Returns:
            (npc_id, distance) 列表
        """
        position = self.get_npc_position(npc_id)
        if not position:
            return []

        nearby = []
        for other_id, other_pos in self.npc_positions.items():
            if other_id == npc_id:
                continue

            # 不同区域跳过
            if other_pos.zone != position.zone:
                continue

            distance = math.sqrt(
                (position.x - other_pos.x) ** 2 +
                (position.y - other_pos.y) ** 2
            )

            if distance <= radius:
                nearby.append((other_id, distance))

        # 按距离排序
        nearby.sort(key=lambda x: x[1])
        return nearby

    def get_locations_in_zone(self, zone: str) -> List[Location]:
        """获取某区域的所有位置"""
        return [loc for loc in self.locations.values() if loc.zone == zone]

    def get_all_zones(self) -> Dict[str, Dict[str, Any]]:
        """获取所有区域信息"""
        return self.zones.copy()

    def get_world_map_summary(self) -> Dict[str, Any]:
        """获取世界地图摘要"""
        return {
            "total_locations": len(self.locations),
            "total_zones": len(self.zones),
            "registered_npcs": len(self.npc_positions),
            "zones": {
                zone_id: {
                    "name": zone_info["name"],
                    "locations_count": len(self.get_locations_in_zone(zone_id)),
                    "npcs_count": len(self.get_npcs_in_zone(zone_id))
                }
                for zone_id, zone_info in self.zones.items()
            }
        }

    def get_distance_between_locations(self, loc1_name: str, loc2_name: str) -> float:
        """
        计算两个位置之间的距离

        Args:
            loc1_name: 第一个位置名称
            loc2_name: 第二个位置名称

        Returns:
            距离（单位距离），如果位置不存在返回无穷大
        """
        loc1 = self.get_location(loc1_name)
        loc2 = self.get_location(loc2_name)

        if not loc1 or not loc2:
            return float('inf')

        return loc1.distance_to(loc2)

    def calculate_event_propagation_delay(self, origin_location: str, target_location: str,
                                          severity: int = 5, base_speed: float = 10.0) -> float:
        """
        计算事件传播到目标位置的延迟时间（分钟）

        事件传播考虑：
        1. 距离 - 越远延迟越长
        2. 紧急度 - 严重事件传播更快
        3. 区域类型 - 公共区域传播更快

        Args:
            origin_location: 事件发生位置
            target_location: 目标位置
            severity: 事件严重程度 (1-10)
            base_speed: 基础传播速度（单位距离/分钟）

        Returns:
            传播延迟（分钟）
        """
        distance = self.get_distance_between_locations(origin_location, target_location)

        if distance == float('inf'):
            return 60.0  # 默认1小时

        if distance == 0:
            return 0.0  # 同一位置，即时传播

        # 紧急度调整：severity 1-10，越高传播越快
        urgency_multiplier = 1.0 / (0.5 + severity * 0.1)  # severity=5时multiplier=1, severity=10时multiplier=0.67

        # 区域类型调整
        target_loc = self.get_location(target_location)
        zone_multiplier = 1.0
        if target_loc:
            if target_loc.zone_type == ZoneType.PUBLIC:
                zone_multiplier = 0.8  # 公共区域传播更快
            elif target_loc.zone_type == ZoneType.NATURE:
                zone_multiplier = 1.5  # 自然区域传播较慢
            elif target_loc.is_private:
                zone_multiplier = 1.3  # 私人区域传播较慢

        # 计算延迟
        delay = (distance / base_speed) * urgency_multiplier * zone_multiplier

        # 确保最小延迟
        return max(1.0, min(delay, 120.0))  # 1-120分钟

    def get_event_propagation_schedule(self, origin_location: str, severity: int = 5) -> List[Dict[str, Any]]:
        """
        获取事件传播到所有位置的时间表

        Args:
            origin_location: 事件发生位置
            severity: 事件严重程度

        Returns:
            按传播时间排序的位置列表，每项包含位置名称、延迟时间、区域等信息
        """
        schedule = []

        for loc_name, location in self.locations.items():
            if loc_name == origin_location:
                delay = 0.0
            else:
                delay = self.calculate_event_propagation_delay(origin_location, loc_name, severity)

            # 获取该位置的NPC
            npcs_at_location = self.get_npcs_at_location(loc_name)

            schedule.append({
                "location": loc_name,
                "zone": location.zone,
                "zone_type": location.zone_type.value,
                "delay_minutes": delay,
                "npcs": npcs_at_location,
                "npc_count": len(npcs_at_location)
            })

        # 按延迟时间排序
        schedule.sort(key=lambda x: x["delay_minutes"])

        return schedule

    def get_npc_event_notification_order(self, origin_location: str, severity: int = 5) -> List[Dict[str, Any]]:
        """
        获取NPC接收事件通知的顺序（基于位置距离）

        Args:
            origin_location: 事件发生位置
            severity: 事件严重程度

        Returns:
            按通知时间排序的NPC列表
        """
        npc_order = []

        for npc_id, position in self.npc_positions.items():
            delay = self.calculate_event_propagation_delay(
                origin_location,
                position.current_location,
                severity
            )

            npc_order.append({
                "npc_id": npc_id,
                "location": position.current_location,
                "zone": position.zone,
                "delay_minutes": delay,
                "is_moving": position.is_moving
            })

        # 按延迟时间排序
        npc_order.sort(key=lambda x: x["delay_minutes"])

        return npc_order


# 全局空间系统实例
_global_spatial_system: Optional[SpatialSystem] = None


def get_spatial_system() -> SpatialSystem:
    """获取全局空间系统实例"""
    global _global_spatial_system
    if _global_spatial_system is None:
        _global_spatial_system = SpatialSystem()
    return _global_spatial_system


def reset_spatial_system():
    """重置全局空间系统"""
    global _global_spatial_system
    _global_spatial_system = None
