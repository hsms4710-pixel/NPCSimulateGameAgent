"""
记忆管理系统
实现记忆摘要、时间清理、压缩等功能
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json


@dataclass
class Episode:
    """情景摘要数据类"""
    summary: str
    start_time: datetime
    end_time: datetime
    importance: int  # 1-10
    key_events: List[str]  # 关键事件ID列表
    emotional_impact: int  # -10 到 +10


@dataclass
class CompressedMemory:
    """压缩后的记忆"""
    original_id: str
    compressed_content: str
    importance: int
    timestamp: datetime
    tags: List[str]


class MemorySummarizer:
    """记忆摘要系统"""
    
    def __init__(self, llm_client=None):
        """
        初始化记忆摘要器
        
        Args:
            llm_client: LLM客户端（可选，用于生成摘要）
        """
        self.llm_client = llm_client
    
    def summarize_episode(self, 
                         events: List[Dict[str, Any]], 
                         time_window: timedelta) -> str:
        """
        将一段时间内的事件摘要为情景
        
        Args:
            events: 事件列表
            time_window: 时间窗口
            
        Returns:
            情景摘要文本
        """
        if not events:
            return ""
        
        if len(events) == 1:
            # 单个事件，直接返回摘要
            return self._summarize_single_event(events[0])
        
        # 多个事件，生成情景摘要
        if self.llm_client:
            return self._llm_summarize_episode(events)
        else:
            return self._simple_summarize_episode(events)
    
    def _summarize_single_event(self, event: Dict[str, Any]) -> str:
        """摘要单个事件"""
        content = event.get("content", "")
        event_type = event.get("event_type", "")
        
        # 简单截断
        if len(content) > 100:
            return content[:100] + "..."
        return content
    
    def _simple_summarize_episode(self, events: List[Dict[str, Any]]) -> str:
        """简单情景摘要（不使用LLM）"""
        if not events:
            return ""
        
        # 提取关键信息
        event_types = [e.get("event_type", "") for e in events]
        main_type = max(set(event_types), key=event_types.count)
        
        # 提取高影响事件
        high_impact = [e for e in events if e.get("impact_score", 0) > 70]
        
        if high_impact:
            summary = f"{main_type}事件：{high_impact[0].get('content', '')[:50]}..."
        else:
            summary = f"{main_type}事件：{len(events)}个相关事件"
        
        return summary
    
    def _llm_summarize_episode(self, events: List[Dict[str, Any]]) -> str:
        """使用LLM生成情景摘要"""
        if not self.llm_client:
            return self._simple_summarize_episode(events)
        
        # 格式化事件
        events_text = "\n".join([
            f"- {e.get('event_type', '')}: {e.get('content', '')[:100]}"
            for e in events
        ])
        
        prompt = f"""
将以下事件摘要为一个连贯的情景描述（控制在100字以内）：

{events_text}

要求：
1. 保留关键信息（人物、地点、结果）
2. 合并相似事件
3. 突出重要转折点
4. 使用简洁的语言
"""
        
        try:
            summary = self.llm_client.generate_response(prompt, max_tokens=150)
            return summary[:150]  # 限制长度
        except Exception as e:
            print(f"LLM摘要失败: {e}, 使用简单摘要")
            return self._simple_summarize_episode(events)
    
    def create_episode(self, events: List[Dict[str, Any]]) -> Episode:
        """创建情景对象"""
        if not events:
            return None
        
        summary = self.summarize_episode(events, timedelta(hours=24))
        
        # 计算重要性（基于事件影响度）
        max_impact = max([e.get("impact_score", 0) for e in events], default=0)
        importance = min(10, max(1, max_impact // 10))
        
        # 提取关键事件ID
        key_events = [
            e.get("id", "") for e in events 
            if e.get("impact_score", 0) > 70
        ]
        
        # 计算情感影响
        emotional_impacts = [e.get("emotional_impact", 0) for e in events if "emotional_impact" in e]
        avg_emotional = sum(emotional_impacts) // len(emotional_impacts) if emotional_impacts else 0
        
        return Episode(
            summary=summary,
            start_time=datetime.fromisoformat(events[0].get("timestamp", datetime.now().isoformat())),
            end_time=datetime.fromisoformat(events[-1].get("timestamp", datetime.now().isoformat())),
            importance=importance,
            key_events=key_events,
            emotional_impact=avg_emotional
        )


class MemoryManager:
    """记忆管理器 - 实现清理、压缩、归档策略"""
    
    CLEANUP_RULES = {
        "daily": {
            "age_days": 1,
            "keep_importance": 7,  # 保留重要性>=7的记忆
            "compress_others": True
        },
        "weekly": {
            "age_days": 7,
            "keep_importance": 5,
            "compress_others": True
        },
        "monthly": {
            "age_days": 30,
            "keep_importance": 3,
            "compress_to_episodes": True  # 压缩为情景
        }
    }
    
    def __init__(self, llm_client=None):
        """
        初始化记忆管理器
        
        Args:
            llm_client: LLM客户端（可选，用于摘要）
        """
        self.llm_client = llm_client
        self.summarizer = MemorySummarizer(llm_client)
        self.episodes: List[Episode] = []
    
    def cleanup_memories(self, 
                        memories: List[Dict[str, Any]],
                        events: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        清理记忆
        
        Args:
            memories: 记忆列表
            events: 事件列表（可选）
            
        Returns:
            清理结果 {"kept": [], "compressed": [], "archived": [], "deleted": []}
        """
        now = datetime.now()
        result = {
            "kept": [],
            "compressed": [],
            "archived": [],
            "deleted": []
        }
        
        for memory in memories:
            age_days = (now - datetime.fromisoformat(memory.get("timestamp", now.isoformat()))).days
            importance = memory.get("importance", 5)
            
            # 每日清理：压缩低重要性旧记忆
            if age_days > self.CLEANUP_RULES["daily"]["age_days"]:
                if importance < self.CLEANUP_RULES["daily"]["keep_importance"]:
                    compressed = self._compress_memory(memory)
                    result["compressed"].append(compressed)
                    continue
            
            # 每周清理：合并到情景
            if age_days > self.CLEANUP_RULES["weekly"]["age_days"]:
                if importance < self.CLEANUP_RULES["weekly"]["keep_importance"]:
                    # 标记为归档（稍后处理）
                    result["archived"].append(memory)
                    continue
            
            # 每月清理：删除低重要性记忆
            if age_days > self.CLEANUP_RULES["monthly"]["age_days"]:
                if importance < self.CLEANUP_RULES["monthly"]["keep_importance"]:
                    result["deleted"].append(memory)
                    continue
            
            # 保留
            result["kept"].append(memory)
        
        return result
    
    def _compress_memory(self, memory: Dict[str, Any]) -> CompressedMemory:
        """压缩单个记忆"""
        content = memory.get("content", "")
        original_id = memory.get("id", "")
        
        if len(content) > 200:
            # 使用LLM压缩（如果可用）
            if self.llm_client:
                compressed_content = self._llm_compress_text(content, target_length=100)
            else:
                # 简单截断
                compressed_content = content[:100] + "..."
        else:
            compressed_content = content
        
        return CompressedMemory(
            original_id=original_id,
            compressed_content=compressed_content,
            importance=memory.get("importance", 5),
            timestamp=datetime.fromisoformat(memory.get("timestamp", datetime.now().isoformat())),
            tags=memory.get("tags", [])
        )
    
    def _llm_compress_text(self, text: str, target_length: int = 100) -> str:
        """使用LLM压缩文本"""
        if not self.llm_client:
            return text[:target_length] + "..."
        
        prompt = f"""
压缩以下文本，保留关键信息，控制在{target_length}字以内：

{text}
"""
        
        try:
            compressed = self.llm_client.generate_response(prompt, max_tokens=150)
            return compressed[:target_length]
        except Exception as e:
            print(f"LLM压缩失败: {e}")
            return text[:target_length] + "..."
    
    def create_episodes_from_events(self, 
                                   events: List[Dict[str, Any]],
                                   time_window_hours: int = 24) -> List[Episode]:
        """
        从事件创建情景
        
        Args:
            events: 事件列表
            time_window_hours: 时间窗口（小时）
            
        Returns:
            情景列表
        """
        if not events:
            return []
        
        # 按时间窗口分组事件
        episodes = []
        current_window_start = None
        current_window_events = []
        
        for event in sorted(events, key=lambda e: e.get("timestamp", "")):
            event_time = datetime.fromisoformat(event.get("timestamp", datetime.now().isoformat()))
            
            if current_window_start is None:
                current_window_start = event_time
                current_window_events = [event]
            else:
                time_diff = event_time - current_window_start
                if time_diff.total_seconds() / 3600 <= time_window_hours:
                    # 在同一时间窗口内
                    current_window_events.append(event)
                else:
                    # 新时间窗口，创建情景
                    if current_window_events:
                        episode = self.summarizer.create_episode(current_window_events)
                        if episode:
                            episodes.append(episode)
                    
                    # 开始新窗口
                    current_window_start = event_time
                    current_window_events = [event]
        
        # 处理最后一个窗口
        if current_window_events:
            episode = self.summarizer.create_episode(current_window_events)
            if episode:
                episodes.append(episode)
        
        return episodes
    
    def get_relevant_memories(self,
                             query: str,
                             memories: List[Dict[str, Any]],
                             top_k: int = 5) -> List[Dict[str, Any]]:
        """
        获取相关记忆（简单关键词匹配，后续可升级为向量搜索）
        
        Args:
            query: 查询文本
            memories: 记忆列表
            top_k: 返回数量
            
        Returns:
            相关记忆列表
        """
        # 简单关键词匹配
        query_words = set(query.lower().split())
        
        scored_memories = []
        for memory in memories:
            content = memory.get("content", "").lower()
            importance = memory.get("importance", 5)
            
            # 计算匹配分数
            matches = sum(1 for word in query_words if word in content)
            score = matches * importance
            
            if score > 0:
                scored_memories.append((score, memory))
        
        # 按分数排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        return [m[1] for m in scored_memories[:top_k]]

