# -*- coding: utf-8 -*-
"""
记忆系统接口协议
===============

定义记忆系统的标准接口，解决以下问题：
1. add_memory 在不同模块中参数签名不一致
2. 记忆检索方法命名不一致（search, query, retrieve, recall）
3. 记忆存储格式不统一

接口方法：
- add_memory: 添加记忆
- search_memories: 搜索记忆
- get_memory: 获取单条记忆
- update_memory: 更新记忆
- delete_memory: 删除记忆
- get_recent_memories: 获取最近记忆
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable


@dataclass
class MemorySearchResult:
    """
    记忆搜索结果

    封装搜索返回的记忆及其相关性分数
    """
    memory_id: str
    content: str
    relevance_score: float          # 相关性分数 0.0-1.0
    importance: int                  # 重要性 1-10
    memory_type: str                 # 记忆类型
    timestamp: datetime              # 记忆时间
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'memory_id': self.memory_id,
            'content': self.content,
            'relevance_score': self.relevance_score,
            'importance': self.importance,
            'memory_type': self.memory_type,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'tags': self.tags,
            'metadata': self.metadata
        }


@runtime_checkable
class MemoryInterface(Protocol):
    """
    记忆系统接口协议

    所有记忆系统实现都应遵循此接口。

    使用方式：
        class MyMemorySystem:
            def add_memory(self, content: str, ...) -> str:
                ...

        # 类型检查
        memory_system: MemoryInterface = MyMemorySystem()
    """

    def add_memory(
        self,
        content: str,
        importance: int = 5,
        memory_type: str = "一般",
        tags: Optional[List[str]] = None,
        emotional_impact: int = 0,
        related_npcs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加一条记忆

        Args:
            content: 记忆内容
            importance: 重要性 1-10，默认5
            memory_type: 记忆类型，默认"一般"
            tags: 标签列表
            emotional_impact: 情感影响 -10到+10，默认0
            related_npcs: 相关NPC名称列表
            metadata: 额外元数据

        Returns:
            str: 新记忆的ID
        """
        ...

    def search_memories(
        self,
        query: str,
        top_k: int = 5,
        memory_types: Optional[List[str]] = None,
        min_importance: int = 0,
        time_range: Optional[tuple] = None,
        tags: Optional[List[str]] = None
    ) -> List[MemorySearchResult]:
        """
        搜索相关记忆

        Args:
            query: 搜索查询
            top_k: 返回结果数量，默认5
            memory_types: 限定记忆类型
            min_importance: 最低重要性
            time_range: 时间范围 (start_datetime, end_datetime)
            tags: 必须包含的标签

        Returns:
            List[MemorySearchResult]: 搜索结果列表，按相关性排序
        """
        ...

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单条记忆

        Args:
            memory_id: 记忆ID

        Returns:
            Optional[Dict]: 记忆内容，不存在则返回None
        """
        ...

    def get_recent_memories(
        self,
        count: int = 10,
        memory_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取最近的记忆

        Args:
            count: 返回数量
            memory_types: 限定记忆类型

        Returns:
            List[Dict]: 最近记忆列表
        """
        ...


class BaseMemorySystem(ABC):
    """
    记忆系统抽象基类

    提供记忆系统的默认实现骨架。
    子类需要实现具体的存储和检索逻辑。
    """

    @abstractmethod
    def add_memory(
        self,
        content: str,
        importance: int = 5,
        memory_type: str = "一般",
        tags: Optional[List[str]] = None,
        emotional_impact: int = 0,
        related_npcs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加记忆"""
        pass

    @abstractmethod
    def search_memories(
        self,
        query: str,
        top_k: int = 5,
        memory_types: Optional[List[str]] = None,
        min_importance: int = 0,
        time_range: Optional[tuple] = None,
        tags: Optional[List[str]] = None
    ) -> List[MemorySearchResult]:
        """搜索记忆"""
        pass

    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """获取单条记忆"""
        pass

    def get_recent_memories(
        self,
        count: int = 10,
        memory_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """获取最近记忆 - 默认实现"""
        # 子类可以覆盖此方法提供更高效的实现
        return []

    def update_memory(
        self,
        memory_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新记忆

        Args:
            memory_id: 记忆ID
            updates: 要更新的字段

        Returns:
            bool: 是否更新成功
        """
        # 默认实现：不支持更新
        return False

    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆ID

        Returns:
            bool: 是否删除成功
        """
        # 默认实现：不支持删除
        return False

    def clear_memories(self, memory_types: Optional[List[str]] = None) -> int:
        """
        清空记忆

        Args:
            memory_types: 限定清空的类型，None表示全部

        Returns:
            int: 清空的记忆数量
        """
        # 默认实现：不支持清空
        return 0

    # ==================== 兼容性方法别名 ====================

    def store_memory(self, *args, **kwargs) -> str:
        """别名: add_memory"""
        return self.add_memory(*args, **kwargs)

    def save_memory(self, *args, **kwargs) -> str:
        """别名: add_memory"""
        return self.add_memory(*args, **kwargs)

    def query_memories(self, *args, **kwargs) -> List[MemorySearchResult]:
        """别名: search_memories"""
        return self.search_memories(*args, **kwargs)

    def retrieve_memories(self, *args, **kwargs) -> List[MemorySearchResult]:
        """别名: search_memories"""
        return self.search_memories(*args, **kwargs)

    def recall(self, *args, **kwargs) -> List[MemorySearchResult]:
        """别名: search_memories"""
        return self.search_memories(*args, **kwargs)

    def search(self, *args, **kwargs) -> List[MemorySearchResult]:
        """别名: search_memories"""
        return self.search_memories(*args, **kwargs)
