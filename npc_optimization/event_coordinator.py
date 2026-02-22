"""
EventCoordinator - 事件协调器（主Agent）

负责：
1. 接收世界事件并生成总览分析
2. 确定受影响的NPC及其响应优先级
3. 为每个NPC分配角色（救援者、通知者、观察者等）
4. 异步分发任务给各NPC子Agent并汇总结果
5. 基于距离的事件传播延迟
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime

from npc_optimization.spatial_system import get_spatial_system, SpatialSystem

# 从统一类型模块导入
from core_types import NPCRole, EventPriority
from core_types.event_types import (
    Event,
    EventAnalysis,
    NPCEventResponse,
    EventType,
    EventSeverity,
    PropagationMethod,
)

logger = logging.getLogger(__name__)


# EventAnalysis 和 NPCEventResponse 现在从 core_types.event_types 导入
# 不再在此处重复定义


class EventCoordinator:
    """
    事件协调器 - 主Agent

    协调多个NPC对世界事件的响应，使用两阶段处理：
    1. 分析阶段：LLM分析事件，生成总览和NPC角色分配
    2. 执行阶段：异步分发给各NPC子Agent执行
    """

    # 职业与事件类型的关联度
    PROFESSION_EVENT_RELEVANCE = {
        "fire": ["牧师", "铁匠"],           # 火灾：牧师（教堂）、铁匠（有水桶/工具）
        "attack": ["铁匠", "守卫"],         # 攻击：铁匠（武器）、守卫
        "illness": ["牧师", "草药师"],       # 疾病：牧师（祝福）、草药师
        "theft": ["商人", "守卫"],          # 盗窃：商人（受害者）、守卫
        "weather": ["农民", "商人"],        # 天气：农民（庄稼）、商人（货物）
        "celebration": ["酒馆老板", "牧师"], # 庆典：酒馆老板、牧师
    }

    # 位置邻接关系
    LOCATION_ADJACENCY = {
        "教堂": ["中心广场", "墓地"],
        "中心广场": ["教堂", "酒馆", "杂货店", "铁匠铺"],
        "酒馆": ["中心广场", "住宅区"],
        "铁匠铺": ["中心广场", "矿洞入口"],
        "杂货店": ["中心广场", "农田"],
        "农田": ["杂货店", "磨坊", "住宅区"],
        "住宅区": ["农田", "酒馆"],
        "磨坊": ["农田"],
        "矿洞入口": ["铁匠铺"],
        "墓地": ["教堂"],
    }

    def __init__(self, llm_client=None, spatial_system: SpatialSystem = None):
        """
        初始化事件协调器

        Args:
            llm_client: LLM客户端，用于生成事件分析
            spatial_system: 空间系统实例，用于距离计算和传播延迟
        """
        self.llm_client = llm_client
        self.active_events: Dict[str, EventAnalysis] = {}
        self.response_history: List[Dict[str, Any]] = []

        # 已注册的NPC及其处理器
        self.registered_npcs: Dict[str, Dict[str, Any]] = {}
        self.npc_processors: Dict[str, Callable] = {}

        # 空间系统（用于距离计算）
        self.spatial_system = spatial_system or get_spatial_system()

    def set_llm_client(self, llm_client):
        """设置LLM客户端"""
        self.llm_client = llm_client

    def register_npc(self, npc_name: str, npc_location: str,
                     npc_status: Dict[str, Any], processor: Callable):
        """
        注册NPC及其处理器

        Args:
            npc_name: NPC名称
            npc_location: NPC当前位置
            npc_status: NPC状态信息
            processor: 异步处理器函数
        """
        self.registered_npcs[npc_name] = {
            'name': npc_name,
            'location': npc_location,
            'profession': npc_status.get('profession', '村民'),
            'current_activity': npc_status.get('current_activity', '空闲'),
            'emotion': npc_status.get('emotion', '平静'),
            'energy': npc_status.get('energy', 1.0)  # 使用新字段 (0.0-1.0)
        }
        self.npc_processors[npc_name] = processor
        logger.info(f"已注册NPC: {npc_name}，位于 {npc_location}")

    def update_npc_status(self, npc_name: str, location: str, status: Dict[str, Any]):
        """
        更新NPC状态

        Args:
            npc_name: NPC名称
            location: 新的位置
            status: 新的状态信息
        """
        if npc_name in self.registered_npcs:
            self.registered_npcs[npc_name].update({
                'location': location,
                'current_activity': status.get('current_activity', '空闲'),
                'emotion': status.get('emotion', '平静'),
                'energy': status.get('energy', 1.0),  # 使用新字段 (0.0-1.0)
                'fatigue': status.get('fatigue', 0),
                'hunger': status.get('hunger', 0)
            })

    def _get_registered_npcs_list(self) -> List[Dict[str, Any]]:
        """获取已注册NPC列表（供analyze_event使用）"""
        return list(self.registered_npcs.values())

    async def analyze_event_async(self, event_content: str,
                                   event_type: str = "general") -> EventAnalysis:
        """
        异步分析事件（使用已注册的NPC信息）

        Args:
            event_content: 事件内容
            event_type: 事件类型

        Returns:
            EventAnalysis: 事件分析结果
        """
        # 从事件内容中推断位置（简单规则）
        event_location = self._infer_event_location(event_content)

        # 使用已注册的NPC列表
        available_npcs = self._get_registered_npcs_list()

        # 估算影响分数
        impact_score = self._estimate_impact_score(event_content, event_type)

        # 调用原有的同步分析方法
        return self.analyze_event(
            event_content=event_content,
            event_location=event_location,
            event_type=event_type,
            available_npcs=available_npcs,
            impact_score=impact_score
        )

    def _infer_event_location(self, event_content: str) -> str:
        """从事件内容推断位置"""
        location_keywords = {
            "教堂": ["教堂", "祈祷", "牧师"],
            "铁匠铺": ["铁匠铺", "铁匠", "打铁", "锻造"],
            "酒馆": ["酒馆", "喝酒", "酒吧"],
            "中心广场": ["广场", "中心", "集市"],
            "农田": ["农田", "庄稼", "农场"],
            "住宅区": ["住宅", "家", "房屋"],
            "杂货店": ["杂货店", "商店", "购物"],
            "磨坊": ["磨坊", "面粉"],
            "墓地": ["墓地", "坟墓"],
            "矿洞入口": ["矿洞", "矿山"],
        }

        for location, keywords in location_keywords.items():
            for keyword in keywords:
                if keyword in event_content:
                    return location

        return "中心广场"  # 默认位置

    def _estimate_impact_score(self, event_content: str, event_type: str) -> int:
        """估算事件影响分数"""
        score = 50  # 默认分数

        # 紧急关键词增加分数
        urgent_keywords = ["火灾", "着火", "攻击", "袭击", "死亡", "紧急", "危险"]
        for keyword in urgent_keywords:
            if keyword in event_content:
                score += 20

        # 事件类型调整
        type_modifiers = {
            "fire": 30,
            "attack": 25,
            "illness": 15,
            "theft": 10,
            "weather": 5,
            "celebration": -10
        }
        score += type_modifiers.get(event_type, 0)

        return min(100, max(0, score))

    async def dispatch_to_npcs_with_registered(self,
                                                analysis: EventAnalysis,
                                                timeout_seconds: float = 30.0) -> List[NPCEventResponse]:
        """
        使用已注册的NPC处理器分发事件

        Args:
            analysis: 事件分析结果
            timeout_seconds: 超时时间

        Returns:
            NPC响应列表
        """
        # 使用已注册的处理器
        results = await self.dispatch_to_npcs(
            analysis=analysis,
            npc_processors=self.npc_processors,
            timeout_seconds=timeout_seconds
        )
        return list(results.values())

    def analyze_event(self,
                      event_content: str,
                      event_location: str,
                      event_type: str,
                      available_npcs: List[Dict[str, Any]],
                      impact_score: int = 50,
                      use_propagation_delay: bool = False) -> EventAnalysis:
        """
        分析事件并生成协调计划

        Args:
            event_content: 事件内容
            event_location: 事件发生位置
            event_type: 事件类型
            available_npcs: 可用的NPC列表 [{"name": "...", "profession": "...", "location": "..."}]
            impact_score: 事件影响度 (0-100)
            use_propagation_delay: 是否使用传播延迟功能（默认False，保持向后兼容）

        Returns:
            EventAnalysis: 事件分析结果，包含NPC角色分配
        """
        event_id = f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(event_content) % 10000}"

        # 1. 确定事件优先级（考虑距离因素）
        priority = self._determine_priority(event_type, impact_score, event_location, available_npcs)

        # 2. 确定受影响的区域
        affected_zones = self._get_affected_zones(event_location, priority)

        # 3. 确定主要响应者（基于职业相关性）
        primary_responders = self._get_primary_responders(event_type, available_npcs)

        # 4. 为每个NPC分配角色
        npc_assignments = self._assign_npc_roles(
            available_npcs,
            event_location,
            affected_zones,
            primary_responders,
            priority
        )

        # 5. 生成各NPC的建议行动
        suggested_actions = self._generate_suggested_actions(
            npc_assignments,
            event_content,
            event_location,
            available_npcs
        )

        # 6. 如果有LLM，使用LLM增强分析
        coordination_notes = ""
        if self.llm_client:
            coordination_notes = self._llm_enhanced_analysis(
                event_content, event_location, event_type,
                available_npcs, npc_assignments
            )
        else:
            coordination_notes = self._generate_basic_coordination_notes(
                event_content, priority, npc_assignments
            )

        # 7. 如果启用传播延迟，计算NPC通知顺序
        npc_notification_order = []
        propagation_delays = {}
        if use_propagation_delay:
            severity = impact_score // 10  # 转换为1-10
            # 使用空间系统获取NPC通知顺序
            npc_notification_order = self.spatial_system.get_npc_event_notification_order(
                event_location, severity
            )
            # 构建NPC名称到延迟时间的映射
            for npc in available_npcs:
                npc_name = npc.get("name", "")
                npc_location = npc.get("location", "中心广场")
                delay = self.spatial_system.calculate_event_propagation_delay(
                    origin_location=event_location,
                    target_location=npc_location,
                    severity=severity
                )
                propagation_delays[npc_name] = delay

            logger.info(f"启用传播延迟: {len(npc_notification_order)} 个NPC按距离排序")

        analysis = EventAnalysis(
            event_id=event_id,
            event_content=event_content,
            event_location=event_location,
            event_type=event_type,
            priority=priority,
            impact_score=impact_score,
            affected_zones=affected_zones,
            primary_responders=primary_responders,
            npc_assignments=npc_assignments,
            suggested_actions=suggested_actions,
            coordination_notes=coordination_notes,
            npc_notification_order=npc_notification_order,
            propagation_delays=propagation_delays
        )

        # 缓存分析结果
        self.active_events[event_id] = analysis

        logger.info(f"事件分析完成: {event_id}, 优先级: {priority.name}, "
                   f"分配了 {len(npc_assignments)} 个NPC角色")

        return analysis

    def _determine_priority(self, event_type: str, impact_score: int,
                            event_location: str = None,
                            available_npcs: List[Dict[str, Any]] = None) -> EventPriority:
        """
        确定事件优先级（考虑距离因素）

        Args:
            event_type: 事件类型
            impact_score: 影响分数
            event_location: 事件发生位置（可选，用于距离调整）
            available_npcs: 可用NPC列表（可选，用于距离调整）

        Returns:
            EventPriority: 事件优先级
        """
        # 紧急事件类型
        critical_types = ["fire", "attack", "collapse", "flood"]
        high_types = ["illness", "theft", "storm"]

        # 基础优先级判断
        base_score = impact_score

        # 如果提供了位置信息，考虑距离因素调整优先级
        if event_location and available_npcs and self.spatial_system:
            # 计算有多少NPC在事件附近
            nearby_count = 0
            for npc in available_npcs:
                npc_location = npc.get("location", "")
                if npc_location == event_location:
                    nearby_count += 2  # 同一位置权重更高
                elif npc_location in self.LOCATION_ADJACENCY.get(event_location, []):
                    nearby_count += 1  # 邻近位置

            # 附近NPC越多，优先级可能需要提高（影响面更广）
            if nearby_count >= 4:
                base_score += 15  # 多人在场，提高紧急度
            elif nearby_count >= 2:
                base_score += 10

        # 确保分数在有效范围内
        base_score = min(100, max(0, base_score))

        if event_type in critical_types or base_score >= 80:
            return EventPriority.CRITICAL
        elif event_type in high_types or base_score >= 60:
            return EventPriority.HIGH
        elif base_score >= 40:
            return EventPriority.MEDIUM
        else:
            return EventPriority.LOW

    def _get_affected_zones(self, event_location: str, priority: EventPriority) -> List[str]:
        """获取受影响的区域"""
        affected = [event_location]

        # 根据优先级扩展影响范围
        if priority in [EventPriority.CRITICAL, EventPriority.HIGH]:
            # 高优先级事件影响邻近区域
            adjacent = self.LOCATION_ADJACENCY.get(event_location, [])
            affected.extend(adjacent)

            # 关键事件进一步扩展
            if priority == EventPriority.CRITICAL:
                for adj_loc in adjacent:
                    second_level = self.LOCATION_ADJACENCY.get(adj_loc, [])
                    for loc in second_level:
                        if loc not in affected:
                            affected.append(loc)

        return affected

    def _get_primary_responders(self, event_type: str, available_npcs: List[Dict]) -> List[str]:
        """获取主要响应者列表"""
        relevant_professions = self.PROFESSION_EVENT_RELEVANCE.get(event_type, [])

        primary = []
        for npc in available_npcs:
            profession = npc.get("profession", "")
            if profession in relevant_professions:
                primary.append(npc.get("name", ""))

        return primary

    def _assign_npc_roles(self,
                          available_npcs: List[Dict],
                          event_location: str,
                          affected_zones: List[str],
                          primary_responders: List[str],
                          priority: EventPriority) -> Dict[str, NPCRole]:
        """为NPC分配角色"""
        assignments = {}

        rescuer_count = 0
        alerter_assigned = False

        for npc in available_npcs:
            name = npc.get("name", "")
            location = npc.get("location", "")
            profession = npc.get("profession", "")

            # 在事件位置的NPC
            if location == event_location:
                if name in primary_responders and rescuer_count < 2:
                    assignments[name] = NPCRole.RESCUER
                    rescuer_count += 1
                elif priority == EventPriority.CRITICAL:
                    assignments[name] = NPCRole.HELPER
                else:
                    assignments[name] = NPCRole.OBSERVER

            # 在邻近区域的NPC
            elif location in affected_zones:
                if name in primary_responders and rescuer_count < 3:
                    assignments[name] = NPCRole.HELPER
                    rescuer_count += 1
                elif not alerter_assigned and profession in ["酒馆老板", "商人"]:
                    # 酒馆老板和商人适合通知他人
                    assignments[name] = NPCRole.ALERTER
                    alerter_assigned = True
                elif priority == EventPriority.CRITICAL:
                    assignments[name] = NPCRole.EVACUEE
                else:
                    assignments[name] = NPCRole.OBSERVER

            # 不在影响区域的NPC
            else:
                if priority == EventPriority.CRITICAL and not alerter_assigned:
                    assignments[name] = NPCRole.ALERTER
                    alerter_assigned = True
                else:
                    assignments[name] = NPCRole.UNAFFECTED

        return assignments

    def _generate_suggested_actions(self,
                                    npc_assignments: Dict[str, NPCRole],
                                    event_content: str,
                                    event_location: str,
                                    available_npcs: List[Dict]) -> Dict[str, str]:
        """生成各NPC的建议行动"""
        npc_info = {npc["name"]: npc for npc in available_npcs}
        suggestions = {}

        for name, role in npc_assignments.items():
            npc = npc_info.get(name, {})
            profession = npc.get("profession", "村民")
            location = npc.get("location", "")

            if role == NPCRole.RESCUER:
                if location != event_location:
                    suggestions[name] = f"立即前往{event_location}，使用{profession}技能参与救援"
                else:
                    suggestions[name] = f"立即参与救援，发挥{profession}专长"

            elif role == NPCRole.HELPER:
                suggestions[name] = f"前往{event_location}协助救援工作"

            elif role == NPCRole.ALERTER:
                suggestions[name] = f"向周围的人通报：{event_content[:20]}..."

            elif role == NPCRole.OBSERVER:
                suggestions[name] = "观察事态发展，准备在需要时提供帮助"

            elif role == NPCRole.EVACUEE:
                suggestions[name] = "远离危险区域，确保自身安全"

            else:  # UNAFFECTED
                suggestions[name] = "继续当前活动"

        return suggestions

    def _llm_enhanced_analysis(self,
                               event_content: str,
                               event_location: str,
                               event_type: str,
                               available_npcs: List[Dict],
                               npc_assignments: Dict[str, NPCRole]) -> str:
        """使用LLM增强分析"""
        npc_list = ", ".join([
            f"{npc['name']}({npc.get('profession', '村民')}, 在{npc.get('location', '未知')})"
            for npc in available_npcs
        ])

        assignments_str = ", ".join([
            f"{name}: {role.value}" for name, role in npc_assignments.items()
        ])

        prompt = f"""作为世界事件协调者，请简要分析以下事件并给出协调建议：

事件：{event_content}
位置：{event_location}
类型：{event_type}

可用NPC：{npc_list}

当前角色分配：{assignments_str}

请用2-3句话给出协调建议，说明各NPC应如何配合。"""

        try:
            response = self.llm_client.generate_response(
                prompt=prompt,
                context={},
                temperature=0.7,
                max_tokens=150
            )
            return response.strip()
        except Exception as e:
            logger.warning(f"LLM分析失败: {e}")
            return self._generate_basic_coordination_notes(
                event_content,
                self._determine_priority(event_type, 50),
                npc_assignments
            )

    def _generate_basic_coordination_notes(self,
                                           event_content: str,
                                           priority: EventPriority,
                                           npc_assignments: Dict[str, NPCRole]) -> str:
        """生成基础协调说明"""
        rescuers = [n for n, r in npc_assignments.items() if r == NPCRole.RESCUER]
        helpers = [n for n, r in npc_assignments.items() if r == NPCRole.HELPER]
        alerters = [n for n, r in npc_assignments.items() if r == NPCRole.ALERTER]

        notes = []

        if priority == EventPriority.CRITICAL:
            notes.append("紧急事件！需要立即响应。")

        if rescuers:
            notes.append(f"主要救援: {', '.join(rescuers)}")
        if helpers:
            notes.append(f"协助人员: {', '.join(helpers)}")
        if alerters:
            notes.append(f"负责通知: {', '.join(alerters)}")

        return " ".join(notes)

    async def dispatch_to_npcs(self,
                               analysis: EventAnalysis,
                               npc_processors: Dict[str, Callable],
                               timeout_seconds: float = 30.0) -> Dict[str, NPCEventResponse]:
        """
        异步分发任务给各NPC

        Args:
            analysis: 事件分析结果
            npc_processors: NPC处理器字典 {npc_name: async processor_func}
            timeout_seconds: 超时时间

        Returns:
            各NPC的响应结果
        """
        results = {}
        tasks = []
        npc_names = []

        # 只处理有角色分配的NPC（排除UNAFFECTED）
        for npc_name, role in analysis.npc_assignments.items():
            if role == NPCRole.UNAFFECTED:
                continue

            if npc_name not in npc_processors:
                logger.warning(f"NPC {npc_name} 没有处理器")
                continue

            processor = npc_processors[npc_name]
            suggested_action = analysis.suggested_actions.get(npc_name, "")

            # 创建异步任务
            task = asyncio.create_task(
                self._process_npc_with_timeout(
                    npc_name=npc_name,
                    role=role,
                    processor=processor,
                    event=analysis,
                    suggested_action=suggested_action,
                    timeout=timeout_seconds
                )
            )
            tasks.append(task)
            npc_names.append(npc_name)

        if not tasks:
            logger.warning("没有NPC需要处理此事件")
            return results

        # 并行执行所有任务
        logger.info(f"开始异步处理 {len(tasks)} 个NPC的响应...")

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for npc_name, response in zip(npc_names, responses):
            if isinstance(response, Exception):
                results[npc_name] = NPCEventResponse(
                    npc_name=npc_name,
                    role=analysis.npc_assignments.get(npc_name, NPCRole.UNAFFECTED),
                    action_taken="处理失败",
                    action_type="error",
                    target_location=None,
                    speech_content=None,
                    thinking_process="",
                    success=False,
                    error=str(response)
                )
            else:
                results[npc_name] = response

        # 记录到历史
        self.response_history.append({
            "event_id": analysis.event_id,
            "timestamp": datetime.now().isoformat(),
            "responses": {k: v.to_dict() for k, v in results.items()}
        })

        logger.info(f"事件 {analysis.event_id} 处理完成，成功: {sum(1 for r in results.values() if r.success)}/{len(results)}")

        return results

    async def _process_npc_with_timeout(self,
                                        npc_name: str,
                                        role: NPCRole,
                                        processor: Callable,
                                        event: EventAnalysis,
                                        suggested_action: str,
                                        timeout: float) -> NPCEventResponse:
        """带超时的NPC处理"""
        start_time = datetime.now()

        try:
            # 构建传递给NPC的事件上下文
            event_context = {
                "event_id": event.event_id,
                "content": event.event_content,
                "location": event.event_location,
                "type": event.event_type,
                "priority": event.priority.name,
                "impact_score": event.impact_score,
                "role": role.value,
                "suggested_action": suggested_action,
                "coordination_notes": event.coordination_notes
            }

            # 调用NPC处理器（带超时）
            result = await asyncio.wait_for(
                processor(event_context),
                timeout=timeout
            )

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return NPCEventResponse(
                npc_name=npc_name,
                role=role,
                action_taken=result.get("action_taken", "未知行动"),
                action_type=result.get("action_type", "unknown"),
                target_location=result.get("target_location"),
                speech_content=result.get("speech_content"),
                thinking_process=result.get("thinking_process", ""),
                success=True,
                execution_time_ms=execution_time
            )

        except asyncio.TimeoutError:
            return NPCEventResponse(
                npc_name=npc_name,
                role=role,
                action_taken="处理超时",
                action_type="timeout",
                target_location=None,
                speech_content=None,
                thinking_process="",
                success=False,
                error=f"处理超时 ({timeout}s)",
                execution_time_ms=timeout * 1000
            )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return NPCEventResponse(
                npc_name=npc_name,
                role=role,
                action_taken="处理异常",
                action_type="error",
                target_location=None,
                speech_content=None,
                thinking_process="",
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )

    def get_active_events(self) -> List[EventAnalysis]:
        """获取活跃事件列表"""
        return list(self.active_events.values())

    def clear_event(self, event_id: str):
        """清除已处理的事件"""
        if event_id in self.active_events:
            del self.active_events[event_id]

    def get_response_history(self, limit: int = 10) -> List[Dict]:
        """获取响应历史"""
        return self.response_history[-limit:]

    async def coordinate_response(self,
                                   event_content: str,
                                   event_location: str,
                                   event_type: str = "general",
                                   impact_score: int = 50,
                                   use_propagation_delay: bool = False,
                                   timeout_seconds: float = 30.0) -> Tuple[EventAnalysis, Dict[str, NPCEventResponse]]:
        """
        协调事件响应的完整流程（分析 + 分发）

        这是一个便捷方法，结合了 analyze_event 和事件分发功能。
        根据 use_propagation_delay 参数决定是否使用传播延迟。

        Args:
            event_content: 事件内容
            event_location: 事件发生位置
            event_type: 事件类型
            impact_score: 事件影响度 (0-100)
            use_propagation_delay: 是否使用传播延迟功能
            timeout_seconds: 单个NPC处理超时时间

        Returns:
            Tuple[EventAnalysis, Dict[str, NPCEventResponse]]: 事件分析和NPC响应结果
        """
        # 获取已注册的NPC列表
        available_npcs = self._get_registered_npcs_list()

        # 分析事件
        analysis = self.analyze_event(
            event_content=event_content,
            event_location=event_location,
            event_type=event_type,
            available_npcs=available_npcs,
            impact_score=impact_score,
            use_propagation_delay=use_propagation_delay
        )

        # 根据是否启用传播延迟选择分发方法
        if use_propagation_delay:
            # 使用带延迟的分发
            responses = await self.schedule_delayed_notifications(
                analysis=analysis,
                timeout_seconds=timeout_seconds
            )
        else:
            # 使用普通分发
            responses = await self.dispatch_to_npcs(
                analysis=analysis,
                npc_processors=self.npc_processors,
                timeout_seconds=timeout_seconds
            )

        return analysis, responses

    async def schedule_delayed_notifications(self,
                                              analysis: EventAnalysis,
                                              timeout_seconds: float = 30.0) -> Dict[str, NPCEventResponse]:
        """
        根据传播延迟安排NPC通知

        按照距离远近，分批次异步通知NPC。
        延迟时间 = delay_minutes / 10（即10分钟游戏时间 = 1秒模拟时间）

        Args:
            analysis: 事件分析结果（包含传播延迟信息）
            timeout_seconds: 单个NPC处理超时时间

        Returns:
            Dict[str, NPCEventResponse]: NPC响应结果
        """
        results = {}

        # 获取传播延迟信息
        propagation_delays = analysis.propagation_delays

        if not propagation_delays:
            # 如果没有延迟信息，回退到普通分发
            logger.warning("没有传播延迟信息，使用普通分发")
            return await self.dispatch_to_npcs(
                analysis=analysis,
                npc_processors=self.npc_processors,
                timeout_seconds=timeout_seconds
            )

        # 按延迟时间对NPC进行排序
        sorted_npcs = sorted(
            [(npc, delay) for npc, delay in propagation_delays.items()
             if npc in analysis.npc_assignments and
                analysis.npc_assignments[npc] != NPCRole.UNAFFECTED],
            key=lambda x: x[1]
        )

        if not sorted_npcs:
            logger.warning("没有需要通知的NPC")
            return results

        logger.info(f"开始按距离顺序通知 {len(sorted_npcs)} 个NPC...")

        # 记录上一个批次的延迟时间，用于计算相对等待时间
        last_delay = 0.0

        for npc_name, delay_minutes in sorted_npcs:
            # 计算需要等待的相对时间（与上一个NPC的时间差）
            relative_delay = delay_minutes - last_delay
            last_delay = delay_minutes

            # 转换为模拟时间：10分钟 = 1秒
            wait_seconds = relative_delay / 10.0

            # 如果需要等待，则等待
            if wait_seconds > 0:
                logger.debug(f"等待 {wait_seconds:.2f} 秒后通知 {npc_name}（游戏时间延迟: {delay_minutes:.1f}分钟）")
                await asyncio.sleep(wait_seconds)

            # 处理该NPC
            if npc_name not in self.npc_processors:
                logger.warning(f"NPC {npc_name} 没有处理器")
                continue

            processor = self.npc_processors[npc_name]
            role = analysis.npc_assignments[npc_name]
            suggested_action = analysis.suggested_actions.get(npc_name, "")

            try:
                response = await self._process_npc_with_timeout(
                    npc_name=npc_name,
                    role=role,
                    processor=processor,
                    event=analysis,
                    suggested_action=suggested_action,
                    timeout=timeout_seconds
                )
                results[npc_name] = response
                logger.debug(f"NPC {npc_name} 响应完成: {response.action_taken}")
            except Exception as e:
                results[npc_name] = NPCEventResponse(
                    npc_name=npc_name,
                    role=role,
                    action_taken="处理失败",
                    action_type="error",
                    target_location=None,
                    speech_content=None,
                    thinking_process="",
                    success=False,
                    error=str(e)
                )

        # 记录到历史
        self.response_history.append({
            "event_id": analysis.event_id,
            "timestamp": datetime.now().isoformat(),
            "propagation_delays": propagation_delays,
            "notification_order": [npc for npc, _ in sorted_npcs],
            "responses": {k: v.to_dict() for k, v in results.items()}
        })

        logger.info(f"延迟通知完成: {len(results)} 个NPC已响应")

        return results

    def calculate_npc_notification_delays(self, event_location: str,
                                          severity: int = 5) -> Dict[str, float]:
        """
        计算每个NPC接收事件通知的延迟时间

        Args:
            event_location: 事件发生位置
            severity: 事件严重程度 (1-10)

        Returns:
            NPC名称到延迟时间（分钟）的映射
        """
        delays = {}

        for npc_name, npc_info in self.registered_npcs.items():
            npc_location = npc_info.get('location', '中心广场')

            if npc_location == event_location:
                # 同一位置，即时通知
                delays[npc_name] = 0.0
            else:
                # 使用空间系统计算延迟
                delay = self.spatial_system.calculate_event_propagation_delay(
                    origin_location=event_location,
                    target_location=npc_location,
                    severity=severity
                )
                delays[npc_name] = delay

        return delays

    async def dispatch_with_propagation_delay(self,
                                               analysis: EventAnalysis,
                                               npc_processors: Dict[str, Callable],
                                               timeout_seconds: float = 30.0,
                                               simulate_delay: bool = False) -> Dict[str, NPCEventResponse]:
        """
        带传播延迟的事件分发

        根据NPC到事件发生地的距离，按顺序通知NPC。
        可以选择模拟延迟（用于测试）或实际等待。

        Args:
            analysis: 事件分析结果
            npc_processors: NPC处理器字典
            timeout_seconds: 单个NPC处理超时时间
            simulate_delay: 是否模拟延迟（True时实际等待）

        Returns:
            NPC响应结果
        """
        results = {}

        # 计算每个NPC的通知延迟
        severity = analysis.impact_score // 10  # 转换为1-10
        delays = self.calculate_npc_notification_delays(analysis.event_location, severity)

        # 按延迟时间分组NPC
        # 将延迟分成几个批次：0分钟、1-5分钟、5-15分钟、15+分钟
        batches = {
            'immediate': [],    # 0分钟
            'quick': [],        # 1-5分钟
            'moderate': [],     # 5-15分钟
            'delayed': []       # 15+分钟
        }

        for npc_name, role in analysis.npc_assignments.items():
            if role == NPCRole.UNAFFECTED:
                continue

            delay = delays.get(npc_name, 60.0)

            if delay == 0:
                batches['immediate'].append(npc_name)
            elif delay <= 5:
                batches['quick'].append(npc_name)
            elif delay <= 15:
                batches['moderate'].append(npc_name)
            else:
                batches['delayed'].append(npc_name)

        logger.info(f"事件传播分批: 即时={len(batches['immediate'])}, "
                   f"快速={len(batches['quick'])}, 中等={len(batches['moderate'])}, "
                   f"延迟={len(batches['delayed'])}")

        # 处理每个批次
        batch_order = ['immediate', 'quick', 'moderate', 'delayed']
        batch_delays = [0, 2, 5, 10]  # 模拟延迟秒数

        for batch_name, batch_delay in zip(batch_order, batch_delays):
            batch_npcs = batches[batch_name]

            if not batch_npcs:
                continue

            if simulate_delay and batch_delay > 0:
                logger.debug(f"等待 {batch_delay} 秒后通知 {batch_name} 批次...")
                await asyncio.sleep(batch_delay)

            # 并行处理该批次的所有NPC
            tasks = []
            for npc_name in batch_npcs:
                if npc_name not in npc_processors:
                    continue

                processor = npc_processors[npc_name]
                role = analysis.npc_assignments[npc_name]
                suggested_action = analysis.suggested_actions.get(npc_name, "")

                # 在上下文中添加传播延迟信息
                task = asyncio.create_task(
                    self._process_npc_with_timeout(
                        npc_name=npc_name,
                        role=role,
                        processor=processor,
                        event=analysis,
                        suggested_action=suggested_action,
                        timeout=timeout_seconds
                    )
                )
                tasks.append((npc_name, task))

            if tasks:
                task_results = await asyncio.gather(
                    *[t for _, t in tasks],
                    return_exceptions=True
                )

                for (npc_name, _), response in zip(tasks, task_results):
                    if isinstance(response, Exception):
                        results[npc_name] = NPCEventResponse(
                            npc_name=npc_name,
                            role=analysis.npc_assignments.get(npc_name, NPCRole.UNAFFECTED),
                            action_taken="处理失败",
                            action_type="error",
                            target_location=None,
                            speech_content=None,
                            thinking_process="",
                            success=False,
                            error=str(response)
                        )
                    else:
                        results[npc_name] = response

                logger.info(f"批次 {batch_name} 完成: {len(task_results)} 个NPC")

        # 记录到历史
        self.response_history.append({
            "event_id": analysis.event_id,
            "timestamp": datetime.now().isoformat(),
            "propagation_delays": delays,
            "responses": {k: v.to_dict() for k, v in results.items()}
        })

        return results

    def get_event_propagation_info(self, event_location: str,
                                   severity: int = 5) -> Dict[str, Any]:
        """
        获取事件传播信息（用于前端显示）

        Args:
            event_location: 事件发生位置
            severity: 事件严重程度

        Returns:
            包含传播时间表和NPC通知顺序的信息
        """
        # 获取位置传播时间表
        schedule = self.spatial_system.get_event_propagation_schedule(
            event_location, severity
        )

        # 获取NPC通知延迟
        npc_delays = self.calculate_npc_notification_delays(event_location, severity)

        # 按延迟排序NPC
        sorted_npcs = sorted(npc_delays.items(), key=lambda x: x[1])

        return {
            "event_location": event_location,
            "severity": severity,
            "location_schedule": schedule,
            "npc_notification_order": [
                {
                    "npc_name": npc,
                    "delay_minutes": delay,
                    "location": self.registered_npcs.get(npc, {}).get('location', 'unknown')
                }
                for npc, delay in sorted_npcs
            ]
        }


# 全局协调器实例
_coordinator_instance: Optional[EventCoordinator] = None


def get_event_coordinator() -> EventCoordinator:
    """获取全局事件协调器实例"""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = EventCoordinator()
    return _coordinator_instance


def set_coordinator_llm_client(llm_client):
    """设置协调器的LLM客户端"""
    coordinator = get_event_coordinator()
    coordinator.set_llm_client(llm_client)
