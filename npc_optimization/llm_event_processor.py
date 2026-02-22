# -*- coding: utf-8 -*-
"""
LLM驱动的事件处理系统
====================

负责：
1. 使用LLM分析事件影响
2. 生成NPC对事件的反应
3. 将事件结果反馈到记忆系统

设计原则：
- 所有事件处理都通过LLM进行
- 事件结果自动反馈到记忆系统
- 支持异步并行处理多个NPC响应
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field

from core_types.event_types import (
    Event,
    EventAnalysis,
    NPCEventResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class MemoryFeedback:
    """
    记忆反馈结构

    事件处理完成后，需要反馈到记忆系统的内容。
    """
    # NPC记忆
    npc_memories: Dict[str, List[str]] = field(default_factory=dict)  # NPC名 -> 记忆列表

    # 世界记忆
    world_memory: Optional[str] = None

    # 情感变化
    emotion_changes: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # NPC名 -> 情感变化

    # 关系变化
    relationship_changes: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # NPC名 -> 关系变化

    def add_npc_memory(self, npc_name: str, memory: str):
        """添加NPC记忆"""
        if npc_name not in self.npc_memories:
            self.npc_memories[npc_name] = []
        self.npc_memories[npc_name].append(memory)

    def add_emotion_change(self, npc_name: str, emotion: str, intensity: float):
        """添加情感变化"""
        self.emotion_changes[npc_name] = {
            "emotion": emotion,
            "intensity": intensity,
            "timestamp": datetime.now().isoformat()
        }

    def add_relationship_change(self, npc_name: str, target: str, change: float, reason: str):
        """添加关系变化"""
        if npc_name not in self.relationship_changes:
            self.relationship_changes[npc_name] = {}
        self.relationship_changes[npc_name][target] = {
            "change": change,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }


@dataclass
class EventProcessingResult:
    """
    事件处理结果

    包含事件分析、NPC响应和记忆反馈。
    """
    event: Event
    analysis: Optional[EventAnalysis] = None
    responses: Dict[str, NPCEventResponse] = field(default_factory=dict)
    memory_feedback: Optional[MemoryFeedback] = None
    processing_time_ms: float = 0
    success: bool = True
    error: Optional[str] = None


class LLMEventProcessor:
    """
    LLM驱动的事件处理器

    主要功能：
    1. 分析事件（确定影响范围、优先级、NPC角色分配）
    2. 生成NPC响应（对话、行动、情感反应）
    3. 反馈到记忆系统
    """

    # 事件分析提示词模板
    EVENT_ANALYSIS_PROMPT = """你是一个世界事件分析师。请分析以下事件并给出结构化的响应。

事件内容: {event_content}
事件位置: {event_location}
事件类型: {event_type}
事件重要度: {importance}/100

可用NPC及其位置:
{npc_list}

请回答：
1. 事件优先级 (1=低, 2=中, 3=高, 4=危急):
2. 受影响区域（列表）:
3. 每个NPC应该分配的角色（rescuer/helper/alerter/observer/evacuee/victim/unaffected）:
4. 每个NPC的建议行动:
5. 协调建议（2-3句话）:

请用JSON格式回答：
{{
    "priority": 数字,
    "affected_zones": ["区域1", "区域2"],
    "npc_roles": {{"NPC名": "角色"}},
    "npc_actions": {{"NPC名": "建议行动"}},
    "coordination_notes": "协调建议"
}}"""

    # NPC响应生成提示词模板
    NPC_RESPONSE_PROMPT = """你正在扮演 {npc_name}，一个{profession}。

事件信息:
- 内容: {event_content}
- 位置: {event_location}
- 你的位置: {npc_location}
- 你被分配的角色: {role}
- 建议行动: {suggested_action}

你的当前状态:
- 情绪: {emotion}
- 精力: {energy}%
- 当前活动: {current_activity}

请用第一人称回答：
1. 你的内心想法（1-2句话）
2. 你会说什么（如果要说话的话）
3. 你会采取什么行动
4. 这件事对你的情感影响（情绪变化）
5. 你会记住什么（1句话总结）

请用JSON格式回答：
{{
    "thinking": "我的内心想法",
    "speech": "我说的话（可以为空）",
    "action": "我采取的行动",
    "action_type": "行动类型（rescue/help/alert/observe/flee/continue）",
    "target_location": "目标位置（如果移动的话）",
    "emotion_change": {{"emotion": "新情绪", "intensity": 0.0到1.0}},
    "memory": "我要记住的事情"
}}"""

    def __init__(self, llm_client=None, memory_manager=None):
        """
        初始化事件处理器

        Args:
            llm_client: LLM客户端（需要有generate_response方法）
            memory_manager: 记忆管理器（用于存储记忆反馈）
        """
        self.llm_client = llm_client
        self.memory_manager = memory_manager
        self.processing_history: List[EventProcessingResult] = []

    def set_llm_client(self, llm_client):
        """设置LLM客户端"""
        self.llm_client = llm_client

    def set_memory_manager(self, memory_manager):
        """设置记忆管理器"""
        self.memory_manager = memory_manager

    async def process_event(
        self,
        event: Event,
        available_npcs: List[Dict[str, Any]],
        apply_memory_feedback: bool = True
    ) -> EventProcessingResult:
        """
        处理事件的完整流程

        Args:
            event: 事件对象
            available_npcs: 可用的NPC列表
            apply_memory_feedback: 是否自动应用记忆反馈

        Returns:
            EventProcessingResult: 处理结果
        """
        start_time = datetime.now()
        result = EventProcessingResult(event=event)

        try:
            # 1. 分析事件
            analysis = await self._analyze_event(event, available_npcs)
            result.analysis = analysis

            if analysis is None:
                # 如果分析失败，使用规则生成基础分析
                analysis = self._generate_fallback_analysis(event, available_npcs)
                result.analysis = analysis

            # 2. 生成每个NPC的响应
            responses = await self._generate_npc_responses(
                event, analysis, available_npcs
            )
            result.responses = responses

            # 3. 收集记忆反馈
            memory_feedback = self._collect_memory_feedback(event, responses)
            result.memory_feedback = memory_feedback

            # 4. 如果启用，应用记忆反馈
            if apply_memory_feedback and self.memory_manager:
                await self._apply_memory_feedback(memory_feedback)

            result.success = True

        except Exception as e:
            logger.error(f"事件处理失败: {e}")
            result.success = False
            result.error = str(e)

        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.processing_history.append(result)

        return result

    async def _analyze_event(
        self,
        event: Event,
        available_npcs: List[Dict[str, Any]]
    ) -> Optional[EventAnalysis]:
        """使用LLM分析事件"""
        if not self.llm_client:
            logger.warning("没有LLM客户端，无法进行事件分析")
            return None

        # 构建NPC列表字符串
        npc_list = "\n".join([
            f"- {npc.get('name', '未知')}: {npc.get('profession', '村民')}, 位于{npc.get('location', '未知')}"
            for npc in available_npcs
        ])

        prompt = self.EVENT_ANALYSIS_PROMPT.format(
            event_content=event.content,
            event_location=event.location,
            event_type=event.event_type,
            importance=event.importance,
            npc_list=npc_list
        )

        try:
            response = await asyncio.to_thread(
                self.llm_client.generate_response,
                prompt=prompt,
                context={},
                temperature=0.7,
                max_tokens=500
            )

            # 解析JSON响应
            import json
            # 尝试提取JSON部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                return EventAnalysis(
                    event_id=event.id,
                    event_content=event.content,
                    event_location=event.location,
                    event_type=event.event_type,
                    priority=data.get("priority", 2),
                    impact_score=event.importance,
                    affected_zones=data.get("affected_zones", [event.location]),
                    npc_assignments=data.get("npc_roles", {}),
                    suggested_actions=data.get("npc_actions", {}),
                    coordination_notes=data.get("coordination_notes", "")
                )

        except Exception as e:
            logger.warning(f"LLM分析事件失败: {e}")
            return None

    def _generate_fallback_analysis(
        self,
        event: Event,
        available_npcs: List[Dict[str, Any]]
    ) -> EventAnalysis:
        """生成回退分析（当LLM不可用时）"""
        # 基于重要度确定优先级
        if event.importance >= 80:
            priority = 4
        elif event.importance >= 60:
            priority = 3
        elif event.importance >= 40:
            priority = 2
        else:
            priority = 1

        # 简单的角色分配
        npc_assignments = {}
        npc_actions = {}
        for i, npc in enumerate(available_npcs):
            name = npc.get("name", f"NPC{i}")
            location = npc.get("location", "")

            if location == event.location:
                npc_assignments[name] = "observer"
                npc_actions[name] = "观察事态发展"
            else:
                npc_assignments[name] = "unaffected"
                npc_actions[name] = "继续当前活动"

        return EventAnalysis(
            event_id=event.id,
            event_content=event.content,
            event_location=event.location,
            event_type=event.event_type,
            priority=priority,
            impact_score=event.importance,
            affected_zones=[event.location],
            npc_assignments=npc_assignments,
            suggested_actions=npc_actions,
            coordination_notes="自动生成的基础分析"
        )

    async def _generate_npc_responses(
        self,
        event: Event,
        analysis: EventAnalysis,
        available_npcs: List[Dict[str, Any]]
    ) -> Dict[str, NPCEventResponse]:
        """为每个NPC生成响应"""
        responses = {}
        tasks = []

        # 创建NPC信息映射
        npc_info = {npc.get("name", ""): npc for npc in available_npcs}

        # 只处理有角色分配的NPC（排除unaffected）
        for npc_name, role in analysis.npc_assignments.items():
            if role == "unaffected":
                continue

            npc = npc_info.get(npc_name, {})
            suggested_action = analysis.suggested_actions.get(npc_name, "")

            task = self._generate_single_npc_response(
                event, npc_name, role, suggested_action, npc
            )
            tasks.append((npc_name, task))

        if not tasks:
            return responses

        # 并行执行所有NPC响应生成
        results = await asyncio.gather(
            *[t for _, t in tasks],
            return_exceptions=True
        )

        for (npc_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                responses[npc_name] = NPCEventResponse(
                    npc_name=npc_name,
                    role=analysis.npc_assignments.get(npc_name, "observer"),
                    action_taken="处理失败",
                    action_type="error",
                    thinking_process="",
                    success=False,
                    error=str(result)
                )
            else:
                responses[npc_name] = result

        return responses

    async def _generate_single_npc_response(
        self,
        event: Event,
        npc_name: str,
        role: str,
        suggested_action: str,
        npc_info: Dict[str, Any]
    ) -> NPCEventResponse:
        """为单个NPC生成响应"""
        if not self.llm_client:
            # 没有LLM，返回默认响应
            return NPCEventResponse(
                npc_name=npc_name,
                role=role,
                action_taken=suggested_action or "观察事态",
                action_type="observe",
                thinking_process="（无LLM，使用默认响应）",
                success=True,
                memory_to_store=f"在{event.location}发生了{event.event_type}事件"
            )

        prompt = self.NPC_RESPONSE_PROMPT.format(
            npc_name=npc_name,
            profession=npc_info.get("profession", "村民"),
            event_content=event.content,
            event_location=event.location,
            npc_location=npc_info.get("location", "未知"),
            role=role,
            suggested_action=suggested_action,
            emotion=npc_info.get("emotion", "平静"),
            energy=int(npc_info.get("energy", 1.0) * 100),
            current_activity=npc_info.get("current_activity", "空闲")
        )

        try:
            response = await asyncio.to_thread(
                self.llm_client.generate_response,
                prompt=prompt,
                context={},
                temperature=0.8,
                max_tokens=300
            )

            # 解析JSON响应
            import json
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                return NPCEventResponse(
                    npc_name=npc_name,
                    role=role,
                    action_taken=data.get("action", "观察事态"),
                    action_type=data.get("action_type", "observe"),
                    target_location=data.get("target_location"),
                    speech_content=data.get("speech"),
                    thinking_process=data.get("thinking", ""),
                    success=True,
                    memory_to_store=data.get("memory"),
                    emotion_change=data.get("emotion_change")
                )

        except Exception as e:
            logger.warning(f"生成NPC响应失败 ({npc_name}): {e}")

        # 回退响应
        return NPCEventResponse(
            npc_name=npc_name,
            role=role,
            action_taken=suggested_action or "观察事态",
            action_type="observe",
            thinking_process="（响应生成失败）",
            success=True,
            memory_to_store=f"在{event.location}发生了事件"
        )

    def _collect_memory_feedback(
        self,
        event: Event,
        responses: Dict[str, NPCEventResponse]
    ) -> MemoryFeedback:
        """收集所有需要反馈到记忆系统的内容"""
        feedback = MemoryFeedback()

        # 世界记忆：事件本身
        feedback.world_memory = f"[{event.timestamp.strftime('%Y-%m-%d %H:%M')}] " \
                                f"在{event.location}发生了{event.event_type}事件: {event.content}"

        # 收集每个NPC的记忆反馈
        for npc_name, response in responses.items():
            if not response.success:
                continue

            # NPC记忆
            if response.memory_to_store:
                feedback.add_npc_memory(npc_name, response.memory_to_store)

            # 情感变化
            if response.emotion_change:
                feedback.add_emotion_change(
                    npc_name,
                    response.emotion_change.get("emotion", "平静"),
                    response.emotion_change.get("intensity", 0.5)
                )

            # 关系变化（如果响应中有的话）
            if response.relationship_change:
                for target, change_info in response.relationship_change.items():
                    feedback.add_relationship_change(
                        npc_name, target,
                        change_info.get("change", 0),
                        change_info.get("reason", "事件影响")
                    )

        return feedback

    async def _apply_memory_feedback(self, feedback: MemoryFeedback):
        """应用记忆反馈到记忆系统"""
        if not self.memory_manager:
            logger.warning("没有记忆管理器，无法应用记忆反馈")
            return

        try:
            # 存储世界记忆
            if feedback.world_memory and hasattr(self.memory_manager, 'add_world_memory'):
                await asyncio.to_thread(
                    self.memory_manager.add_world_memory,
                    feedback.world_memory
                )

            # 存储NPC记忆
            for npc_name, memories in feedback.npc_memories.items():
                if hasattr(self.memory_manager, 'add_npc_memory'):
                    for memory in memories:
                        await asyncio.to_thread(
                            self.memory_manager.add_npc_memory,
                            npc_name, memory
                        )

            # 应用情感变化
            for npc_name, emotion_info in feedback.emotion_changes.items():
                if hasattr(self.memory_manager, 'update_npc_emotion'):
                    await asyncio.to_thread(
                        self.memory_manager.update_npc_emotion,
                        npc_name,
                        emotion_info["emotion"],
                        emotion_info["intensity"]
                    )

            logger.info(f"记忆反馈已应用: {len(feedback.npc_memories)} 个NPC记忆, "
                       f"{len(feedback.emotion_changes)} 个情感变化")

        except Exception as e:
            logger.error(f"应用记忆反馈失败: {e}")

    def get_processing_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取处理历史"""
        results = []
        for result in self.processing_history[-limit:]:
            results.append({
                "event_id": result.event.id,
                "event_type": result.event.event_type,
                "success": result.success,
                "processing_time_ms": result.processing_time_ms,
                "npc_count": len(result.responses),
                "memory_feedback": {
                    "npc_count": len(result.memory_feedback.npc_memories) if result.memory_feedback else 0,
                    "has_world_memory": bool(result.memory_feedback and result.memory_feedback.world_memory)
                } if result.memory_feedback else None
            })
        return results


# 便捷函数
async def process_event_with_llm(
    event: Event,
    available_npcs: List[Dict[str, Any]],
    llm_client=None,
    memory_manager=None
) -> EventProcessingResult:
    """
    便捷函数：处理事件并获取结果

    Args:
        event: 事件对象
        available_npcs: 可用NPC列表
        llm_client: LLM客户端
        memory_manager: 记忆管理器

    Returns:
        EventProcessingResult: 处理结果
    """
    processor = LLMEventProcessor(llm_client, memory_manager)
    return await processor.process_event(event, available_npcs)


__all__ = [
    'MemoryFeedback',
    'EventProcessingResult',
    'LLMEventProcessor',
    'process_event_with_llm',
]
