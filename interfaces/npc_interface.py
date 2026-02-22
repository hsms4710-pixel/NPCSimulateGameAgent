# -*- coding: utf-8 -*-
"""
NPC系统接口协议
===============

定义NPC注册、状态管理的标准接口，解决以下问题：
1. NPC注册和查找方法不一致
2. NPC状态访问接口不统一
3. 位置信息格式不统一

接口方法：
- NPCRegistryInterface: NPC注册和查找
- NPCStateInterface: NPC状态访问
- Position: 统一位置数据类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable, Callable, Iterator
from enum import Enum


@dataclass
class Position:
    """
    统一位置数据类

    支持2D和3D坐标，以及区域标识
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    region: str = ""  # 区域标识，如 "市场", "铁匠铺"

    def distance_to(self, other: 'Position') -> float:
        """计算到另一位置的距离"""
        import math
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def is_near(self, other: 'Position', threshold: float = 10.0) -> bool:
        """判断是否在附近"""
        return self.distance_to(other) <= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'region': self.region
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        return cls(
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            z=data.get('z', 0.0),
            region=data.get('region', '')
        )

    def __str__(self) -> str:
        if self.region:
            return f"{self.region}({self.x:.1f}, {self.y:.1f})"
        return f"({self.x:.1f}, {self.y:.1f}, {self.z:.1f})"


@runtime_checkable
class NPCStateInterface(Protocol):
    """
    NPC状态接口协议

    定义NPC状态的访问方法
    """

    @property
    def npc_id(self) -> str:
        """NPC唯一标识"""
        ...

    @property
    def name(self) -> str:
        """NPC名称"""
        ...

    @property
    def position(self) -> Position:
        """当前位置"""
        ...

    @property
    def current_activity(self) -> str:
        """当前活动"""
        ...

    @property
    def energy(self) -> float:
        """能量值 0.0-1.0"""
        ...

    @property
    def is_active(self) -> bool:
        """是否活跃"""
        ...

    def get_state_dict(self) -> Dict[str, Any]:
        """获取完整状态字典"""
        ...


@runtime_checkable
class NPCRegistryInterface(Protocol):
    """
    NPC注册表接口协议

    定义NPC的注册、查找、管理方法
    """

    def register_npc(
        self,
        npc_id: str,
        name: str,
        npc_type: str = "普通",
        initial_position: Optional[Position] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        注册NPC

        Args:
            npc_id: NPC唯一标识
            name: NPC名称
            npc_type: NPC类型
            initial_position: 初始位置
            metadata: 额外元数据

        Returns:
            bool: 是否注册成功
        """
        ...

    def unregister_npc(self, npc_id: str) -> bool:
        """
        注销NPC

        Args:
            npc_id: NPC唯一标识

        Returns:
            bool: 是否注销成功
        """
        ...

    def get_npc(self, npc_id: str) -> Optional[NPCStateInterface]:
        """
        获取NPC

        Args:
            npc_id: NPC唯一标识

        Returns:
            Optional[NPCStateInterface]: NPC状态接口，不存在则返回None
        """
        ...

    def get_npc_by_name(self, name: str) -> Optional[NPCStateInterface]:
        """
        按名称获取NPC

        Args:
            name: NPC名称

        Returns:
            Optional[NPCStateInterface]: NPC状态接口
        """
        ...

    def get_all_npcs(self) -> List[NPCStateInterface]:
        """
        获取所有NPC

        Returns:
            List[NPCStateInterface]: 所有NPC列表
        """
        ...

    def get_npcs_in_region(self, region: str) -> List[NPCStateInterface]:
        """
        获取指定区域的NPC

        Args:
            region: 区域标识

        Returns:
            List[NPCStateInterface]: 该区域的NPC列表
        """
        ...

    def get_npcs_near(
        self,
        position: Position,
        radius: float = 10.0
    ) -> List[NPCStateInterface]:
        """
        获取附近的NPC

        Args:
            position: 中心位置
            radius: 搜索半径

        Returns:
            List[NPCStateInterface]: 附近的NPC列表
        """
        ...

    def count_npcs(self) -> int:
        """
        获取NPC总数

        Returns:
            int: NPC数量
        """
        ...


class BaseNPCRegistry(ABC):
    """
    NPC注册表抽象基类

    提供NPC注册表的默认实现骨架
    """

    @abstractmethod
    def register_npc(
        self,
        npc_id: str,
        name: str,
        npc_type: str = "普通",
        initial_position: Optional[Position] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """注册NPC"""
        pass

    @abstractmethod
    def unregister_npc(self, npc_id: str) -> bool:
        """注销NPC"""
        pass

    @abstractmethod
    def get_npc(self, npc_id: str) -> Optional[NPCStateInterface]:
        """获取NPC"""
        pass

    def get_npc_by_name(self, name: str) -> Optional[NPCStateInterface]:
        """按名称获取NPC - 默认实现"""
        for npc in self.get_all_npcs():
            if npc.name == name:
                return npc
        return None

    @abstractmethod
    def get_all_npcs(self) -> List[NPCStateInterface]:
        """获取所有NPC"""
        pass

    def get_npcs_in_region(self, region: str) -> List[NPCStateInterface]:
        """获取指定区域的NPC - 默认实现"""
        return [
            npc for npc in self.get_all_npcs()
            if npc.position.region == region
        ]

    def get_npcs_near(
        self,
        position: Position,
        radius: float = 10.0
    ) -> List[NPCStateInterface]:
        """获取附近的NPC - 默认实现"""
        return [
            npc for npc in self.get_all_npcs()
            if npc.position.is_near(position, radius)
        ]

    def count_npcs(self) -> int:
        """获取NPC总数 - 默认实现"""
        return len(self.get_all_npcs())

    # ==================== 兼容性方法别名 ====================

    def add_npc(self, *args, **kwargs) -> bool:
        """别名: register_npc"""
        return self.register_npc(*args, **kwargs)

    def remove_npc(self, npc_id: str) -> bool:
        """别名: unregister_npc"""
        return self.unregister_npc(npc_id)

    def find_npc(self, npc_id: str) -> Optional[NPCStateInterface]:
        """别名: get_npc"""
        return self.get_npc(npc_id)

    def find_npc_by_name(self, name: str) -> Optional[NPCStateInterface]:
        """别名: get_npc_by_name"""
        return self.get_npc_by_name(name)

    def list_npcs(self) -> List[NPCStateInterface]:
        """别名: get_all_npcs"""
        return self.get_all_npcs()

    def get_nearby_npcs(self, *args, **kwargs) -> List[NPCStateInterface]:
        """别名: get_npcs_near"""
        return self.get_npcs_near(*args, **kwargs)

    def find_npcs_in_area(self, *args, **kwargs) -> List[NPCStateInterface]:
        """别名: get_npcs_in_region"""
        return self.get_npcs_in_region(*args, **kwargs)
