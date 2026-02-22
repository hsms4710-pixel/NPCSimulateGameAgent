"""
上下文压缩器
用于减少LLM调用的token消耗，同时保留关键信息
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json


class ContextCompressor:
    """上下文压缩器 - 分层压缩策略"""
    
    def __init__(self, max_tokens: int = 1000):
        """
        初始化上下文压缩器
        
        Args:
            max_tokens: 目标最大token数
        """
        self.max_tokens = max_tokens
    
    def compress_context(self, 
                        npc_config: Dict[str, Any],
                        npc_state: Dict[str, Any],
                        current_task: Optional[Dict[str, Any]] = None,
                        recent_events: Optional[List[Dict[str, Any]]] = None,
                        relevant_memories: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        压缩NPC上下文
        
        Args:
            npc_config: NPC配置（完整）
            npc_state: NPC当前状态
            current_task: 当前任务
            recent_events: 最近事件
            relevant_memories: 相关记忆
            
        Returns:
            压缩后的上下文字典
        """
        compressed = {
            "core_state": self._extract_core_state(npc_state),
            "npc_summary": self._summarize_npc(npc_config),
            "current_task": self._compress_task(current_task) if current_task else None,
            "recent_context": self._compress_recent_context(recent_events, relevant_memories)
        }
        
        return compressed
    
    def _extract_core_state(self, npc_state: Dict[str, Any]) -> Dict[str, Any]:
        """提取核心状态（必需信息）"""
        return {
            "activity": npc_state.get("current_activity", "空闲"),
            "emotion": npc_state.get("current_emotion", "平静"),
            "energy": npc_state.get("energy", 1.0),  # 使用新字段 (0.0-1.0)
            "time": npc_state.get("time", ""),
            "location": npc_state.get("location", ""),
            "needs": {
                "hunger": round(npc_state.get("needs", {}).get("hunger", 0.0), 2),
                "fatigue": round(npc_state.get("needs", {}).get("fatigue", 0.0), 2),
                "social": round(npc_state.get("needs", {}).get("social", 0.0), 2)
            }
        }
    
    def _summarize_npc(self, npc_config: Dict[str, Any]) -> Dict[str, Any]:
        """摘要NPC信息（保留世界观和性格）"""
        personality = npc_config.get("personality", {})
        background = npc_config.get("background", "")
        
        # 压缩背景故事（保留关键信息）
        background_summary = self._summarize_text(background, max_length=150)
        
        return {
            "name": npc_config.get("name", ""),
            "race": npc_config.get("race", ""),
            "profession": npc_config.get("profession", ""),
            "age": npc_config.get("age", 0),
            "traits": personality.get("traits", [])[:5],  # 最多5个特征
            "temperament": personality.get("temperament", ""),
            "background_summary": background_summary,
            "work_hours": npc_config.get("work_hours", ""),  # 从人物卡读取
            "daily_routine": self._extract_daily_routine(npc_config)  # 从人物卡读取
        }
    
    def _extract_daily_routine(self, npc_config: Dict[str, Any]) -> Dict[str, Any]:
        """从人物卡提取日常作息（可自定义）"""
        daily_schedule = npc_config.get("daily_schedule", {})
        
        # 如果没有定义，使用默认值
        if not daily_schedule:
            return {
                "sleep_time": "22:00-6:00",
                "work_time": npc_config.get("work_hours", "9:00-18:00"),
                "meal_times": ["7:00-8:00", "12:00-13:00", "18:00-19:00"]
            }
        
        return {
            "sleep_time": daily_schedule.get("sleep_time", "22:00-6:00"),
            "work_time": daily_schedule.get("work_time", npc_config.get("work_hours", "9:00-18:00")),
            "meal_times": daily_schedule.get("meal_times", ["7:00-8:00", "12:00-13:00", "18:00-19:00"]),
            "habits": daily_schedule.get("habits", [])  # 自定义习惯
        }
    
    def _compress_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """压缩任务信息"""
        if not task:
            return None
        
        return {
            "description": task.get("description", "")[:100],  # 限制长度
            "priority": task.get("priority", 50),
            "progress": round(task.get("progress", 0.0), 2),
            "type": task.get("task_type", "unknown")
        }
    
    def _compress_recent_context(self, 
                                events: Optional[List[Dict[str, Any]]],
                                memories: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """压缩最近上下文"""
        compressed = {}
        
        # 最近事件（最多3个，只保留关键信息）
        if events:
            compressed["recent_events"] = [
                {
                    "type": e.get("event_type", ""),
                    "summary": self._summarize_text(e.get("content", ""), max_length=50),
                    "impact": e.get("impact_score", 0)
                }
                for e in events[-3:]  # 只取最近3个
            ]
        
        # 相关记忆（最多5个）
        if memories:
            compressed["relevant_memories"] = [
                {
                    "content": self._summarize_text(m.get("content", ""), max_length=80),
                    "importance": m.get("importance", 5),
                    "tags": m.get("tags", [])[:3]  # 最多3个标签
                }
                for m in memories[:5]  # 最多5个
            ]
        
        return compressed
    
    def _summarize_text(self, text: str, max_length: int = 100) -> str:
        """简单文本摘要（保留关键信息）"""
        if len(text) <= max_length:
            return text
        
        # 简单截断（实际可以使用LLM摘要，但会增加成本）
        # 这里使用智能截断：保留开头和结尾
        if max_length > 50:
            half = max_length // 2
            return text[:half] + "..." + text[-half:]
        else:
            return text[:max_length] + "..."
    
    def format_compressed_context(self, compressed: Dict[str, Any]) -> str:
        """将压缩后的上下文格式化为字符串（用于prompt）"""
        parts = []
        
        # NPC摘要
        npc = compressed["npc_summary"]
        parts.append(f"角色：{npc['name']}（{npc['race']} {npc['profession']}，{npc['age']}岁）")
        parts.append(f"性格：{', '.join(npc['traits'])}")
        if npc.get("background_summary"):
            parts.append(f"背景：{npc['background_summary']}")
        
        # 核心状态
        core = compressed["core_state"]
        parts.append(f"\n当前状态：{core['activity']} | {core['emotion']} | 能量{core['energy']}/100")
        parts.append(f"时间：{core['time']} | 位置：{core['location']}")
        parts.append(f"需求：饥饿{core['needs']['hunger']:.0%} 疲劳{core['needs']['fatigue']:.0%} 社交{core['needs']['social']:.0%}")
        
        # 当前任务
        if compressed.get("current_task"):
            task = compressed["current_task"]
            parts.append(f"\n当前任务：{task['description']}（优先级{task['priority']}，进度{task['progress']:.0%}）")
        
        # 最近上下文
        recent = compressed.get("recent_context", {})
        if recent.get("recent_events"):
            parts.append(f"\n最近事件：")
            for event in recent["recent_events"]:
                parts.append(f"  - {event['summary']}（影响{event['impact']}）")
        
        if recent.get("relevant_memories"):
            parts.append(f"\n相关记忆：")
            for memory in recent["relevant_memories"]:
                parts.append(f"  - {memory['content']}")
        
        return "\n".join(parts)

