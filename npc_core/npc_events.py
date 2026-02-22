"""
NPC 事件处理模块

包含事件处理相关的方法：
- process_event: 处理事件的统一入口
- process_event_with_react: 使用ReAct模式处理事件
- _evaluate_event_impact: 评估事件冲击力
- _execute_decision: 执行决策
- _generate_response_for_event: 生成事件响应
- 其他相关方法
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from core_types import NPCAction, Emotion
from npc_core.npc_persistence import NPCEvent
from npc_optimization import NPCEventEnhanced
from npc_optimization.event_coordinator import NPCRole, NPCEventResponse, EventAnalysis

logger = logging.getLogger(__name__)


class NPCEventsMixin:
    """NPC 事件处理混入类"""

    def process_event(self, event_content: str, event_type: str,
                     max_reasoning_steps: Optional[int] = None,
                     event_location: str = None) -> Dict[str, Any]:
        """
        处理事件的统一入口 - 使用四级决策系统

        决策流程：
        L1: 生物钟硬判决 (0 tokens) - 是否遵循日程
        L2: 快速重要性过滤 (50 tokens) - 是否忽视这个事件
        L3: 战略规划 (200 tokens) - 制定行动计划
        L4: 深度推理 (500+ tokens) - 复杂情况下的树搜索推理

        Args:
            event_content: 事件内容
            event_type: 事件类型
            max_reasoning_steps: 最大推理步数（仅用于L4）
            event_location: 事件发生位置
        """
        # 0. 预处理：构建当前状态快照
        current_state = self._build_current_state_snapshot()

        # 1. 评估事件冲击力（0-100）
        impact_score = self._evaluate_event_impact(event_content, event_type)

        # 2. 构建事件对象
        event = {
            "content": event_content,
            "type": event_type,
            "impact_score": impact_score,
            "timestamp": datetime.now().isoformat(),
            "location": event_location or self.current_location
        }

        # 3. 使用四级决策系统做出决策
        decision_result = self.decision_maker.make_decision(
            event=event,
            current_state=current_state,
            latest_impact_score=impact_score
        )

        # 4. 执行决策的行动
        response_data = self._execute_decision(decision_result, event, current_state)

        # 5. 记录决策过程和结果
        self._record_decision_and_event(event, decision_result, response_data)

        return response_data

    async def process_event_with_react(self, event_content: str, event_type: str,
                                       coordinator_context: Optional[Dict[str, Any]] = None,
                                       event_location: str = None) -> Dict[str, Any]:
        """
        使用ReAct模式处理事件（异步版本）

        在L3/L4层级决策时会调用LLM选择并执行工具，确保NPC真正"行动"而不只是"思考"。

        Args:
            event_content: 事件内容
            event_type: 事件类型
            coordinator_context: 来自EventCoordinator的上下文（角色分配、建议行动等）
            event_location: 事件发生位置

        Returns:
            处理结果，包含决策、工具执行结果等
        """
        start_time = time.time()

        # 0. 预处理：构建当前状态快照
        current_state = self._build_current_state_snapshot()

        # 1. 评估事件冲击力（0-100）
        impact_score = self._evaluate_event_impact(event_content, event_type)

        # 2. 构建事件对象
        event = {
            "content": event_content,
            "type": event_type,
            "impact_score": impact_score,
            "timestamp": datetime.now().isoformat(),
            "location": event_location or self.current_location
        }

        # 3. 使用带ReAct的四级决策系统做出决策
        decision_result = self.decision_maker.make_decision_with_react(
            event=event,
            current_state=current_state,
            latest_impact_score=impact_score,
            coordinator_context=coordinator_context
        )

        # 4. 执行决策的行动（如果ReAct没有执行工具）
        response_data = self._execute_decision(decision_result, event, current_state)

        # 5. 合并ReAct工具执行结果
        if "tool_execution" in decision_result:
            response_data["tool_execution"] = decision_result["tool_execution"]
            response_data["react_enabled"] = True

            # 如果工具执行成功，更新响应文本
            tool_result = decision_result["tool_execution"]
            if tool_result.get("success"):
                tool_name = tool_result.get("tool", "")
                tool_params = tool_result.get("params", {})

                # 根据工具类型生成更丰富的响应
                response_data["response_text"] = self._generate_react_response(
                    tool_name, tool_params, event
                )

        # 6. 处理协调器上下文（如果有）
        if coordinator_context:
            response_data["coordinator_role"] = coordinator_context.get("role", "")
            response_data["coordinator_suggestion"] = coordinator_context.get("suggested_action", "")

        # 7. 记录决策过程和结果
        self._record_decision_and_event(event, decision_result, response_data)

        # 8. 计算执行时间
        response_data["execution_time_ms"] = (time.time() - start_time) * 1000

        logger.info(f"NPC {self.npc_name} ReAct处理完成: {event_content[:30]}... "
                   f"工具执行: {response_data.get('react_enabled', False)}")

        return response_data

    def _generate_react_response(self, tool_name: str, tool_params: Dict[str, Any],
                                  event: Dict[str, Any]) -> str:
        """
        根据ReAct工具执行结果生成响应文本

        Args:
            tool_name: 执行的工具名称
            tool_params: 工具参数
            event: 原始事件

        Returns:
            响应文本
        """
        responses = {
            "move_to": lambda p: f"（立即前往{p.get('destination', '目的地')}）",
            "flee": lambda p: f"（紧急逃往{p.get('destination', '安全地点')}！）",
            "speak": lambda p: p.get("content", "..."),
            "notify_others": lambda p: f"（大声通知周围的人）{p.get('content', '注意了！')}",
            "alert": lambda p: f"（发出警报！）{p.get('message', '危险！')}",
            "help_action": lambda p: f"（开始帮助：{p.get('action', '救援')}）",
            "observe": lambda p: f"（仔细观察{p.get('target', '周围情况')}）",
            "work": lambda p: f"（继续工作：{p.get('task', '手头的事')}）",
            "change_activity": lambda p: f"（切换到：{p.get('activity', '新活动')}）",
            "update_emotion": lambda p: f"（感到{p.get('emotion', '...')}）",
            "continue_current": lambda p: f"（{p.get('reason', '继续当前活动')}）",
            "add_memory": lambda p: "（记住了这件事）",
            "search_memories": lambda p: "（回忆起相关的事情...）"
        }

        generator = responses.get(tool_name)
        if generator:
            return generator(tool_params)
        return f"（执行了{tool_name}）"

    def create_async_processor(self, coordinator_context: Optional[Dict[str, Any]] = None):
        """
        创建一个异步处理器函数，供EventCoordinator调用

        Args:
            coordinator_context: 协调器上下文

        Returns:
            异步处理器函数
        """
        async def processor(event: EventAnalysis, role: NPCRole,
                           suggested_action: str) -> NPCEventResponse:
            """
            处理来自EventCoordinator的事件

            Args:
                event: 事件分析结果
                role: 分配给此NPC的角色
                suggested_action: 建议的行动

            Returns:
                NPC响应结果
            """
            start_time = time.time()

            try:
                # 构建协调器上下文
                context = {
                    "role": role.value,
                    "suggested_action": suggested_action,
                    "event_priority": event.priority.name,
                    "coordination_notes": event.coordination_notes
                }

                # 使用ReAct模式处理事件
                result = await self.process_event_with_react(
                    event_content=event.event_content,
                    event_type=event.event_type,
                    coordinator_context=context,
                    event_location=event.event_location
                )

                # 构建响应
                action_taken = result.get("response_text", "已处理")
                action_type = result.get("recommended_action", "unknown")

                # 获取工具执行信息
                tool_exec = result.get("tool_execution", {})
                target_location = None
                speech_content = None

                if tool_exec.get("success"):
                    tool_name = tool_exec.get("tool", "")
                    params = tool_exec.get("params", {})

                    if tool_name in ["move_to", "flee"]:
                        target_location = params.get("destination")
                    elif tool_name in ["speak", "notify_others", "alert"]:
                        speech_content = params.get("content") or params.get("message")

                execution_time = (time.time() - start_time) * 1000

                return NPCEventResponse(
                    npc_name=self.npc_name,
                    role=role,
                    action_taken=action_taken,
                    action_type=action_type,
                    target_location=target_location,
                    speech_content=speech_content,
                    thinking_process=result.get("reasoning", ""),
                    success=True,
                    execution_time_ms=execution_time
                )

            except Exception as e:
                logger.error(f"NPC {self.npc_name} 处理事件失败: {e}")
                return NPCEventResponse(
                    npc_name=self.npc_name,
                    role=role,
                    action_taken="处理失败",
                    action_type="error",
                    target_location=None,
                    speech_content=None,
                    thinking_process="",
                    success=False,
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000
                )

        return processor

    def _build_current_state_snapshot(self) -> Dict[str, Any]:
        """构建当前NPC状态快照，供决策系统使用"""
        current_hour = self.world_clock.current_time.hour

        # 获取对话历史（用于LLM prompt）
        dialogue_history = ""
        if hasattr(self, 'persistence') and self.persistence:
            dialogue_history = self.persistence.get_dialogue_context_for_llm(limit=5)

        return {
            "current_activity": self.current_activity,
            "current_hour": current_hour,
            "energy": self.energy,  # 使用新的能量字段 (0.0-1.0)
            "hunger": self.need_system.needs.hunger,
            "fatigue": self.need_system.needs.fatigue,
            "current_emotion": self.current_emotion.value,
            "location": self.current_location,
            "current_task": self.persistence.current_task.description if self.persistence.current_task else None,
            "time_string": self.world_clock.current_time.strftime("%H:%M"),
            "relationships": self._get_relevant_relationships(event_content=""),
            "recent_memory": self._get_recent_memory_context(),
            "dialogue_history": dialogue_history
        }

    def _evaluate_event_impact(self, event_content: str, event_type: str) -> int:
        """
        评估事件冲击力 (0-100)

        冲击力决定事件是否能打断当前活动（与ACTIVITY_INERTIA比较）
        """
        # 基础分值（基于事件类型）
        base_scores = {
            "dialogue": 20,        # 对话
            "world_event": 40,     # 世界事件
            "preset_event": 50,    # 预设事件
            "status_change": 30,   # 状态变化
            "social": 35,          # 社交
            "danger": 80,          # 危险事件
            "emergency": 100       # 紧急事件
        }

        impact = base_scores.get(event_type, 30)

        # 根据内容关键词调整冲击力
        keywords_high_impact = ["死亡", "受伤", "失火", "救助", "紧急", "危险", "攻击"]
        keywords_low_impact = ["问好", "闲聊", "观察", "想"]

        content_lower = event_content.lower()
        for keyword in keywords_high_impact:
            if keyword in content_lower:
                impact = min(100, impact + 20)

        for keyword in keywords_low_impact:
            if keyword in content_lower:
                impact = max(0, impact - 10)

        return impact

    def _execute_decision(self, decision_result: Dict[str, Any],
                         event: Dict[str, Any],
                         current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行决策系统的输出

        如果推荐改变活动，则：
        1. 更新当前活动
        2. 生成合适的响应文本
        3. 创建/更新任务（如需要）
        4. 如需要移动到事件位置，触发移动
        """
        recommended_action = decision_result.get("action")
        decision_level = decision_result.get("decision_level")
        reasoning = decision_result.get("reasoning", "")
        confidence = decision_result.get("confidence", 0.5)

        response_data = {
            "should_respond": True,  # 添加这个必需的键
            "decision_level": decision_level.value if hasattr(decision_level, 'value') else str(decision_level),
            "recommended_action": recommended_action.value if hasattr(recommended_action, 'value') else str(recommended_action),
            "reasoning": reasoning,
            "confidence": confidence,
            "response_text": "",
            "state_changed": False,
            "new_task_created": False,
            "task_description": "",
            "movement_triggered": False,
            "movement_destination": None,
            "impact_analysis": {  # 添加这个必需的键
                "impact_score": event.get("impact_score", 0)
            }
        }

        # 如果推荐的行动与当前行动不同，则改变活动
        if recommended_action != current_state.get("current_activity"):
            try:
                self._change_activity(recommended_action)
                response_data["state_changed"] = True
            except Exception as e:
                logger.warning(f"改变活动失败: {e}")

        # 检查是否需要移动到事件位置（高优先级事件）
        event_location = event.get("location")
        impact_score = event.get("impact_score", 0)

        if event_location and event_location != self.current_location and impact_score > 60:
            # 决定是否需要移动到事件位置
            if recommended_action in [NPCAction.HELP_OTHERS, NPCAction.OBSERVE, NPCAction.TRAVEL]:
                if self.move_to(event_location):
                    response_data["movement_triggered"] = True
                    response_data["movement_destination"] = event_location
                    logger.info(f"NPC {self.npc_name} 开始移动到 {event_location}")

        # 检查是否需要通知其他NPC（社交行动 + 高影响事件）
        if recommended_action == NPCAction.SOCIALIZE and impact_score > 50:
            # 检查原始步骤是否包含"通知"相关关键词
            original_step = decision_result.get("original_step", "")
            all_steps = decision_result.get("all_steps", [])

            should_notify = any(
                kw in str(all_steps).lower()
                for kw in ['通知', '告诉', '告知', '呼叫', '喊', '传达', '报告', '组织']
            )

            if should_notify:
                self.notify_others_about_event(event)
                response_data["notified_others"] = True
                logger.info(f"NPC {self.npc_name} 通知了附近的人关于事件: {event.get('content', '')[:30]}...")

        # 生成自然语言响应
        response_text = self._generate_response_for_event(
            event,
            recommended_action,
            decision_level,
            reasoning
        )
        response_data["response_text"] = response_text

        # 如果是高优先级事件（影响度>70）且L3/L4决策，可能需要创建任务
        if event.get("impact_score", 0) > 70 and hasattr(decision_level, 'value') and decision_level.value >= 3:
            task_created, task_desc = self._potentially_create_task_for_event(event, reasoning)
            response_data["new_task_created"] = task_created
            response_data["task_description"] = task_desc

        return response_data

    def _generate_response_for_event(self, event: Dict[str, Any],
                                     action: NPCAction,
                                     decision_level,
                                     reasoning: str) -> str:
        """
        根据事件和决策生成NPC的自然语言响应

        这里可以用轻量级的规则或简单的LLM调用，避免过度消耗Token
        """
        action_responses = {
            NPCAction.SLEEP: "我现在很累，需要休息一下...",
            NPCAction.EAT: "我有点饿了，得去吃点东西。",
            NPCAction.WORK: "我得继续我的工作。",
            NPCAction.REST: "我需要休息一会儿。",
            NPCAction.SOCIALIZE: "让我们聊一聊吧。",
            NPCAction.OBSERVE: "让我看看发生了什么。",
            NPCAction.THINK: "这需要我好好思考一下...",
            NPCAction.PRAY: "我要去祈祷。",
            NPCAction.LEARN: "这很有趣，我想了解更多。",
            NPCAction.CREATE: "我想创造点什么。",
            NPCAction.HELP_OTHERS: "我应该去帮忙。",
            NPCAction.TRAVEL: "我需要移动到其他地方。"
        }

        # 根据事件类型添加特定的回应
        event_type_responses = {
            "dialogue": f"（听到了）{event.get('content', '')}",
            "world_event": "（注意到周围发生了什么变化）",
            "danger": "（立即警觉起来！）",
            "emergency": "（这是紧急情况！）"
        }

        base_response = event_type_responses.get(
            event.get("type", ""),
            action_responses.get(action, "我在处理这个情况。")
        )

        return base_response

    def _potentially_create_task_for_event(self, event: Dict[str, Any], reasoning: str) -> tuple:
        """
        在必要时为事件创建任务

        返回：(是否成功创建了任务, 任务描述)
        """
        # 仅为特定类型的高影响事件创建任务
        should_create = event.get("type") in ["world_event", "preset_event", "emergency"]
        task_description = ""

        if should_create:
            try:
                task_description = f"处理事件: {event['content'][:50]}"
                task_id = self.persistence.create_task(
                    description=task_description,
                    task_type="event_response",
                    priority=min(100, event.get("impact_score", 50) + 20)
                )

                # 如果这是紧急任务，立即设为当前任务
                if event.get("impact_score", 0) > 80:
                    task = self.persistence.tasks.get(task_id)
                    if task:
                        self.persistence.set_current_task(task)

                return True, task_description
            except Exception as e:
                logger.warning(f"创建事件任务失败: {e}")

        return False, task_description

    def _record_decision_and_event(self, event: Dict[str, Any],
                                   decision_result: Dict[str, Any],
                                   response_data: Dict[str, Any]):
        """
        记录事件和决策过程到持久化存储
        """
        try:
            # 记录到决策历史
            self.decision_history.append({
                'timestamp': datetime.now(),
                'type': 'event_processing',
                'event': event,
                'decision_level': decision_result.get('decision_level'),
                'recommended_action': decision_result.get('action'),
                'confidence': decision_result.get('confidence'),
                'response': response_data.get('response_text')
            })

            # 限制历史长度
            if len(self.decision_history) > 100:
                self.decision_history = self.decision_history[-100:]

            # 根据事件类型保存到记忆
            event_type = event.get('type', 'unknown')
            event_content = event.get('content', '')
            response_text = response_data.get('response_text', '')

            # 对话事件 - 保存对话历史
            if event_type == 'dialogue':
                self.persistence.add_dialogue('user', event_content)
                if response_text:
                    self.persistence.add_dialogue('npc', response_text)

            # 世界事件或其他重要事件 - 保存到记忆
            elif event_type in ['world_event', 'preset_event', 'status_change']:
                importance = min(10, max(1, event.get('impact_score', 50) // 10))
                memory_content = f"[{event_type}] {event_content[:200]}"
                if response_text:
                    memory_content += f" -> 我的反应: {response_text[:100]}"

                self.persistence.add_memory(
                    content=memory_content,
                    memory_type='event',
                    importance=importance,
                    tags=[event_type]
                )

                # 同时添加到三层记忆管理器
                if hasattr(self, 'memory_layer_manager'):
                    enhanced_event = NPCEventEnhanced(
                        id=f"evt_{int(time.time())}",
                        timestamp=datetime.now().isoformat(),
                        event_type=event_type,
                        content=event_content,
                        analysis=decision_result,
                        response=response_text,
                        emotion_impact=response_data.get('emotion_change', {}),
                        importance_score=importance / 10.0,
                        related_npcs=[],
                        location=event.get('location', self.current_location)
                    )
                    self.memory_layer_manager.add_event(enhanced_event)

        except Exception as e:
            logger.warning(f"记录决策和事件失败: {e}")

    def _get_relevant_relationships(self, event_content: str) -> List[str]:
        """
        获取与事件相关的关系信息

        返回：相关NPC名称列表
        """
        try:
            if hasattr(self, 'relationships') and isinstance(self.relationships, dict):
                # 简单实现：返回关系得分最高的几个NPC
                sorted_rels = sorted(
                    self.relationships.items(),
                    key=lambda x: abs(x[1].affection),
                    reverse=True
                )
                return [npc_name for npc_name, _ in sorted_rels[:3]]
            return []
        except Exception as e:
            logger.warning(f"获取相关关系失败: {e}")
            return []

    def _get_recent_memory_context(self) -> str:
        """
        获取最近的记忆上下文

        返回：最近事件的简要总结
        """
        try:
            if hasattr(self, 'memories') and self.memories:
                # 获取最近3条记忆
                recent = self.memories[-3:] if len(self.memories) > 3 else self.memories
                context_parts = []
                for mem in recent:
                    if hasattr(mem, 'content'):
                        context_parts.append(mem.content[:50])
                return " | ".join(context_parts)
            return "（暂无最近记忆）"
        except Exception as e:
            logger.warning(f"获取记忆上下文失败: {e}")
            return "（记忆访问失败）"

    def _generate_event_response(self, event_content: str, event_type: str,
                                impact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成事件响应和状态变化"""
        # 使用LLM分析应该如何响应
        prompt = f"""
你是一个{self.config['name']}，{self.config['profession']}。
当前活动：{self.persistence.current_state.current_activity}
当前任务：{self.persistence.current_task.description if self.persistence.current_task else '无'}
情绪状态：{self.persistence.current_state.emotion}
警觉度：{int(self.persistence.current_state.alertness * 100)}%

事件：{event_content}
事件影响度：{impact_analysis['impact_score']}
是否应该改变状态：{impact_analysis['should_change_state']}

请分析：
1. 应该如何回应这个事件
2. 是否需要改变当前活动
3. 是否需要创建新任务来处理这个事件
4. 对情感状态的影响

请用JSON格式回复：
{{
    "response": "你的回应内容",
    "reasoning": "回应的理由",
    "activity_change": "睡觉/工作/休息/社交/none",
    "emotion_change": "平静/愤怒/恐惧/快乐/悲伤/none",
    "create_task": true/false,
    "task_description": "如果需要创建任务，这里填写任务描述",
    "task_priority": 1-100
}}
"""

        try:
            llm_response = self.llm_client.generate_response(prompt)
            result = json.loads(llm_response)

            # 应用状态变化
            state_changed = self._apply_state_changes(result)

            return {
                'response_text': result.get('response', ''),
                'reasoning': result.get('reasoning', ''),
                'state_changed': state_changed,
                'new_task_created': result.get('create_task', False),
                'task_description': result.get('task_description', ''),
                'task_priority': result.get('task_priority', 50)
            }

        except Exception as e:
            # 如果LLM分析失败，使用默认响应
            return {
                'response_text': "（看起来有些困惑）这是怎么回事？",
                'reasoning': f"LLM分析失败: {e}",
                'state_changed': False,
                'new_task_created': False
            }

    def _apply_state_changes(self, llm_result: Dict[str, Any]) -> bool:
        """应用LLM建议的状态变化"""
        state_changed = False

        # 活动变化 - 使用新字段
        activity_change = llm_result.get('activity_change', 'none')
        if activity_change != 'none':
            current_activity = self.persistence.current_state.current_activity
            if activity_change != current_activity:
                old_activity = current_activity
                self.persistence.current_state.current_activity = activity_change
                self.persistence.current_state.is_sleeping = (activity_change in ["睡觉", "休息"])
                state_changed = True

                # 根据新活动调整当前活动枚举
                activity_map = {
                    "睡觉": NPCAction.SLEEP,
                    "工作": NPCAction.WORK,
                    "休息": NPCAction.REST,
                    "社交": NPCAction.SOCIALIZE,
                    "观察": NPCAction.OBSERVE,
                    "吃饭": NPCAction.EAT,
                }
                self.current_activity = activity_map.get(activity_change, NPCAction.REST)

        # 情感变化 - 使用新字段
        emotion_change = llm_result.get('emotion_change', 'none')
        if emotion_change != 'none':
            self.persistence.current_state.emotion = emotion_change
            emotion_map = {
                "平静": Emotion.CALM,
                "愤怒": Emotion.ANGRY,
                "恐惧": Emotion.WORRIED,
                "快乐": Emotion.HAPPY,
                "悲伤": Emotion.SAD,
                # 兼容英文
                "calm": Emotion.CALM,
                "angry": Emotion.ANGRY,
                "fearful": Emotion.WORRIED,
                "happy": Emotion.HAPPY,
                "sad": Emotion.SAD
            }
            self.current_emotion = emotion_map.get(emotion_change, Emotion.CALM)

        # 创建新任务
        if llm_result.get('create_task', False):
            task_desc = llm_result.get('task_description', '')
            if task_desc:
                task_id = self.persistence.create_task(
                    description=task_desc,
                    task_type="event_response",
                    priority=llm_result.get('task_priority', 50)
                )

                # 如果这是高优先级任务，设置为当前任务并立即切换活动
                task_priority = llm_result.get('task_priority', 50)
                if task_priority > 70:
                    task = self.persistence.tasks[task_id]
                    self.persistence.set_current_task(task)
                    # 立即切换到合适的活动来处理任务
                    appropriate_activity = self._analyze_task_and_select_activity(task)
                    if appropriate_activity != self.current_activity:
                        self._change_activity(appropriate_activity)
                        # 立即执行一次新活动
                        self._execute_current_activity()

        return state_changed

    def _record_event(self, event_content: str, event_type: str,
                     impact_analysis: Dict[str, Any], response_data: Dict[str, Any]):
        """记录事件到持久化存储"""
        # 获取事件前后的状态 - 使用新字段
        state_before = {
            'current_activity': self.persistence.current_state.current_activity,
            'current_task': self.persistence.current_task.description if self.persistence.current_task else None,
            'emotion': self.persistence.current_state.emotion,
            'energy': self.persistence.current_state.energy
        }

        # 创建事件记录
        event = NPCEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            content=event_content,
            analysis=impact_analysis,
            response=response_data.get('response_text', ''),
            state_before=state_before,
            state_after={
                'current_activity': self.persistence.current_state.current_activity,
                'current_task': self.persistence.current_task.description if self.persistence.current_task else None,
                'emotion': self.persistence.current_state.emotion,
                'energy': self.persistence.current_state.energy
            },
            impact_score=impact_analysis.get('impact_score', 0)
        )

        # 记录事件
        self.persistence.record_event(event)

        # 同步goals变化到持久化系统
        self.sync_goals_to_persistence()

    def _update_relationship(self, target: str, affection_delta: int = 0,
                             trust_delta: int = 0, content: str = "") -> None:
        """
        更新与目标的关系（C4：关系系统）
        关系数据绑在 UnifiedNPCState.relationships 上，不使用游离全局变量。
        """
        try:
            rels = self.persistence.current_state.relationships
            if target not in rels:
                rels[target] = {
                    "affection": 0, "trust": 30,
                    "type": "stranger", "interactions": 0
                }

            rel = rels[target]
            rel["affection"] = max(-100, min(100, rel["affection"] + affection_delta))
            rel["trust"] = max(0, min(100, rel["trust"] + trust_delta))
            rel["interactions"] = rel.get("interactions", 0) + 1

            # 动态阈值（可由配置覆盖，不写死枚举）
            thresholds = [
                (-60, "enemy"), (-20, "unfriendly"), (0, "stranger"),
                (20, "acquaintance"), (50, "friend"), (80, "close_friend")
            ]
            rel_type = "enemy"
            for v, t in thresholds:
                if rel["affection"] >= v:
                    rel_type = t
            rel["type"] = rel_type

            # 记录到持久化
            self.persistence._save_data()

            # 写入八卦/记忆
            if content and hasattr(self, 'world_event_manager'):
                gossip_content = f"{self.npc_name}与{target}发生了互动: {content[:50]}"
                self.world_event_manager.start_social_gossip(
                    original_source=self.npc_name,
                    gossip_content=gossip_content,
                    emotional_tone="neutral"
                )

            logger.debug(f"{self.npc_name} 与 {target} 关系更新: affection={rel['affection']}, type={rel_type}")

        except Exception as e:
            logger.warning(f"_update_relationship 失败: {e}")
