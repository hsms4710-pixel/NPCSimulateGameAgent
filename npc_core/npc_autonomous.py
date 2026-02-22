"""
NPC 自主行为循环模块

包含自主行为相关的方法：
- _autonomous_behavior_loop: 自主行为主循环
- _assess_current_state: 评估当前状态
- _change_activity: 改变活动
- _execute_current_activity: 执行当前活动
- _should_change_activity: 判断是否需要改变活动
- _select_new_activity: 选择新活动
- 其他相关方法
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Any

from core_types import NPCAction, Emotion


class NPCAutonomousMixin:
    """NPC 自主行为混入类"""

    def _autonomous_behavior_loop(self):
        """自主行为主循环"""
        evaluation_interval = 30  # 每30秒评估一次

        while not self.autonomous_stop_event.is_set():
            try:
                # 更新环境感知
                self.environment_perception.update_perception()

                # 更新需求状态
                time_passed = evaluation_interval / 60.0  # 转换为分钟
                self.need_system.update_needs(time_passed, self.current_activity)

                # 实时状态评估
                self._assess_current_state()

                # 优先检查：如果有活跃的事件响应任务，但当前活动不合适，立即切换
                current_task = self.persistence.current_task
                if current_task and current_task.task_type == "event_response" and current_task.status == "active":
                    # 检查当前活动是否适合处理这个任务
                    appropriate_activity = self._analyze_task_and_select_activity(current_task)
                    if appropriate_activity != self.current_activity:
                        # 立即切换到合适的活动
                        self._change_activity(appropriate_activity)

                # 使用行为决策树判断是否需要改变活动（优化：减少LLM调用）
                current_hour = self.world_clock.current_time.hour
                needs_dict = {
                    "hunger": self.need_system.needs.hunger,
                    "fatigue": self.need_system.needs.fatigue,
                    "social": self.need_system.needs.social
                }

                current_task_dict = None
                if current_task:
                    current_task_dict = {
                        "priority": current_task.priority,
                        "description": current_task.description
                    }

                # 先尝试规则决策（日常行为，从人物卡读取）
                routine_action = self.behavior_tree.decide_routine_behavior(
                    current_hour=current_hour,
                    energy_level=self.energy,  # 使用新的能量字段 (0.0-1.0)
                    needs=needs_dict,
                    current_task=current_task_dict
                )

                if routine_action and routine_action != self.current_activity:
                    # 规则决策成功，切换活动（不需要LLM）
                    self._change_activity(routine_action)
                elif self._should_change_activity():
                    # 规则决策失败，使用LLM决策（复杂情况）
                    new_activity = self._select_new_activity()
                    if new_activity != self.current_activity:
                        self._change_activity(new_activity)

                # 执行当前活动（这会更新任务进度）
                self._execute_current_activity()

                # 通知GUI更新（如果设置了回调）
                if self.gui_update_callback:
                    try:
                        self.gui_update_callback()
                    except Exception as e:
                        print(f"GUI更新回调失败: {e}")

                # 定期输出状态摘要（每3次评估一次）
                if hasattr(self, '_evaluation_count'):
                    self._evaluation_count += 1
                else:
                    self._evaluation_count = 1

                # 定期状态检查（可选的调试功能）
                pass

            except Exception as e:
                # 记录错误但不中断循环
                import traceback
                print(f"自主行为循环错误: {e}")
                traceback.print_exc()

            # 等待下一次评估
            self.autonomous_stop_event.wait(evaluation_interval)

    def _cleanup_memories(self):
        """定期清理记忆"""
        try:
            # 将记忆转换为字典格式
            memories_dict = [
                {
                    "id": f"mem_{i}",
                    "content": m.content,
                    "importance": m.importance,
                    "tags": m.tags if hasattr(m, 'tags') else [],
                    "timestamp": m.timestamp.isoformat() if isinstance(m.timestamp, datetime) else str(m.timestamp)
                }
                for i, m in enumerate(self.memories)
            ]

            # 将事件转换为字典格式
            events_dict = [
                {
                    "id": f"evt_{i}",
                    "event_type": e.event_type,
                    "content": e.content,
                    "impact_score": e.impact_score,
                    "timestamp": e.timestamp
                }
                for i, e in enumerate(self.persistence.event_history)
            ]

            # 执行清理
            cleanup_result = self.memory_manager.cleanup_memories(memories_dict, events_dict)

            # 更新记忆列表
            from .data_models import Memory
            self.memories = [Memory(**m) for m in cleanup_result["kept"]]

            # 创建情景（如果有归档的事件）
            if cleanup_result["archived"]:
                episodes = self.memory_manager.create_episodes_from_events(
                    cleanup_result["archived"],
                    time_window_hours=24
                )
                # 可以将情景存储到持久化系统

            print(f"[记忆清理] 保留{len(cleanup_result['kept'])}个，压缩{len(cleanup_result['compressed'])}个，归档{len(cleanup_result['archived'])}个，删除{len(cleanup_result['deleted'])}个")

        except Exception as e:
            print(f"记忆清理失败: {e}")

    def _assess_current_state(self):
        """评估当前状态"""
        # 检查需求紧急程度
        urgent_need, need_level = self.need_system.get_most_urgent_need()

        # 检查环境安全性
        safety_level = self.environment_perception.assess_safety()

        # 检查当前活动是否仍然合适
        activity_appropriateness = self._evaluate_activity_appropriateness()

        # 记录状态评估结果
        self.decision_history.append({
            'timestamp': datetime.now(),
            'type': 'state_assessment',
            'urgent_need': urgent_need,
            'need_level': need_level,
            'safety_level': safety_level,
            'current_activity': self._get_activity_value(),
            'activity_appropriateness': activity_appropriateness
        })

        # 保持决策历史在合理长度
        if len(self.decision_history) > 50:
            self.decision_history = self.decision_history[-50:]

    def _execute_current_activity(self):
        """执行当前活动"""
        activity_duration = (datetime.now() - self.activity_start_time).total_seconds() / 60  # 分钟

        # 如果有当前任务，使用LLM决策更新任务进度
        if self.persistence.current_task and self.persistence.current_task.status == "active":
            # 计算时间差（自主行为循环每30秒执行一次，约0.008小时）
            time_diff = 0.008  # 约30秒
            self._update_task_progress(time_diff)

        # 基于活动类型更新状态
        if self.current_activity == NPCAction.WORK:
            # 工作会消耗能量，积累疲劳
            self.energy = max(0.0, self.energy - 0.005)  # 使用0.0-1.0范围
            self.need_system.needs.fatigue = min(1.0, self.need_system.needs.fatigue + 0.01)
        elif self.current_activity == NPCAction.REST:
            # 休息恢复能量
            self.energy = min(1.0, self.energy + 0.01)
            self.need_system.needs.fatigue = max(0.0, self.need_system.needs.fatigue - 0.02)
        elif self.current_activity == NPCAction.SLEEP:
            # 睡觉大幅恢复
            self.energy = min(1.0, self.energy + 0.02)
            self.need_system.needs.fatigue = max(0.0, self.need_system.needs.fatigue - 0.05)
        elif self.current_activity == NPCAction.EAT:
            # 吃饭恢复饥饿
            self.need_system.needs.hunger = max(0.0, self.need_system.needs.hunger - 0.1)
        elif self.current_activity == NPCAction.SOCIALIZE:
            # 社交满足社交需求
            self.need_system.needs.social = max(0.0, self.need_system.needs.social - 0.05)
        elif self.current_activity == NPCAction.OBSERVE:
            # 普通的观察活动，轻微消耗能量
            if not (self.persistence.current_task and self.persistence.current_task.status == "active"):
                self.energy = max(0.0, self.energy - 0.001)
        elif self.current_activity == NPCAction.HELP_OTHERS:
            # 普通的帮助活动，消耗一定能量但满足社交需求
            if not (self.persistence.current_task and self.persistence.current_task.status == "active"):
                self.energy = max(0.0, self.energy - 0.002)
                self.need_system.needs.social = max(0.0, self.need_system.needs.social - 0.03)

    def _evaluate_activity_appropriateness(self) -> float:
        """评估当前活动的合适程度 0-1"""
        appropriateness = 1.0

        # 基于时间评估
        current_hour = self.world_clock.current_time.hour
        if self.current_activity == NPCAction.SLEEP:
            if not (22 <= current_hour or current_hour <= 6):
                appropriateness *= 0.3  # 白天睡觉不合适
        elif self.current_activity == NPCAction.WORK:
            if not (9 <= current_hour <= 18):
                appropriateness *= 0.5  # 非工作时间工作

        # 基于需求评估
        urgent_need, need_level = self.need_system.get_most_urgent_need()
        if need_level > 0.7:
            # 如果有紧急需求，当前活动可能不合适
            appropriateness *= 0.7

        return appropriateness

    def _is_time_for_routine_change(self, current_hour: int) -> bool:
        """检查是否到了常规活动转换时间"""
        # 定义常规活动转换时间点
        routine_changes = [
            (6, "wake_up"),
            (9, "start_work"),
            (12, "lunch"),
            (18, "end_work"),
            (20, "dinner"),
            (22, "bedtime")
        ]

        for hour, routine in routine_changes:
            if current_hour == hour:
                return True

        return False

    def _should_change_activity(self) -> bool:
        """判断是否应该切换活动"""
        # 检查需求紧急性
        urgent_need, need_level = self.need_system.get_most_urgent_need()

        # 如果有非常紧急的需求
        if need_level > 0.8:
            return True

        # 检查当前活动是否超时
        if self.activity_start_time:
            activity_duration = (self.world_clock.current_time - self.activity_start_time).total_seconds() / 3600
            max_duration = self._get_max_activity_duration(self.current_activity)
            if activity_duration > max_duration:
                return True

        # 检查能量水平
        if self.energy < 0.2 and self.current_activity != NPCAction.SLEEP:
            return True

        # 检查是否有紧急任务需要处理
        current_task = self.persistence.current_task
        if current_task and current_task.task_type == "event_response" and current_task.status == "active":
            # 检查任务优先级和时间
            priority = current_task.priority
            current_hour = self.world_clock.current_time.hour
            is_sleep_time = current_hour >= 22 or current_hour <= 6

            # 高优先级任务总是需要处理
            if priority >= 90:
                return True
            # 中等优先级任务在非睡觉时间处理
            elif priority >= 70 and not is_sleep_time:
                return True

        # 检查时间周期
        current_hour = self.world_clock.current_time.hour
        if current_hour >= 22 and self.current_activity != NPCAction.SLEEP:
            return True

        return False

    def _get_max_activity_duration(self, activity: NPCAction) -> float:
        """获取活动最大持续时间（小时）"""
        durations = {
            NPCAction.WORK: 4,
            NPCAction.SOCIALIZE: 2,
            NPCAction.REST: 1,
            NPCAction.EAT: 0.5,
            NPCAction.SLEEP: 8,
            NPCAction.TRAVEL: 1,
        }
        return durations.get(activity, 2)

    def _select_new_activity(self) -> NPCAction:
        """选择新活动"""
        # 检查当前时间是否应该睡觉
        current_hour = self.world_clock.current_time.hour
        is_sleep_time = current_hour >= 22 or current_hour <= 6

        # 优先检查是否有活跃的事件响应任务
        current_task = self.persistence.current_task
        if current_task and current_task.task_type == "event_response" and current_task.status == "active":
            # 如果是睡觉时间，只有重要事件才会中断睡眠
            if is_sleep_time:
                task_priority = current_task.priority
                # 重要事件（优先级>85）可以在睡觉时间处理，但会影响睡眠质量
                if task_priority > 85:
                    selected_activity = self._analyze_task_and_select_activity(current_task)
                    return selected_activity
                # 其他事件等到早上再处理
                else:
                    return NPCAction.SLEEP
            else:
                # 白天正常处理任务
                selected_activity = self._analyze_task_and_select_activity(current_task)
                return selected_activity

        # 如果没有活跃任务，则基于常规逻辑选择

        # 基于时间选择活动
        if 6 <= current_hour < 8:
            # 早上：起床、早餐
            possible_actions = [NPCAction.EAT, NPCAction.REST]
        elif 8 <= current_hour < 18:
            # 白天：工作时间
            if self.config["profession"] in ["blacksmith", "farmer", "merchant"]:
                possible_actions = [NPCAction.WORK, NPCAction.SOCIALIZE]
            else:
                possible_actions = [NPCAction.WORK, NPCAction.HELP_OTHERS]
        elif 18 <= current_hour < 22:
            # 晚上：社交、休息
            possible_actions = [NPCAction.SOCIALIZE, NPCAction.EAT, NPCAction.REST]
        else:
            # 深夜：睡觉
            possible_actions = [NPCAction.SLEEP]

        # 考虑能量水平
        if self.energy < 0.3:
            possible_actions = [NPCAction.REST, NPCAction.SLEEP]

        # 基于性格偏好调整
        personality = self.config["personality"]
        if "社交" in str(personality.get("traits", [])):
            if NPCAction.SOCIALIZE not in possible_actions:
                possible_actions.append(NPCAction.SOCIALIZE)

        # 随机选择，但考虑权重
        weights = [1] * len(possible_actions)

        # 工作时间更可能工作
        if NPCAction.WORK in possible_actions and 9 <= current_hour <= 17:
            work_index = possible_actions.index(NPCAction.WORK)
            weights[work_index] = 3

        # 疲惫时更可能休息
        if self.energy < 0.5 and NPCAction.REST in possible_actions:
            rest_index = possible_actions.index(NPCAction.REST)
            weights[rest_index] = 2

        selected_action = random.choices(possible_actions, weights=weights)[0]

        self.current_activity = selected_action
        self.activity_start_time = self.world_clock.current_time

        return selected_action

    def _adjust_activity_for_time(self, current_time: datetime):
        """根据当前时间自动调整活动状态"""
        hour = current_time.hour
        weekday = current_time.weekday()  # 0-6, 0是周一

        # 获取NPC的职业信息
        profession = self.config.get("profession", "")
        work_hours = self.config.get("work_hours", "")

        # 解析工作时间（简单实现）
        is_workday = weekday < 5  # 周一到周五工作

        # 根据时间段和职业判断应该的活动

        if 22 <= hour or hour < 6:  # 晚上10点到早上6点
            # 睡觉时间
            if self.current_activity != NPCAction.SLEEP:
                self.current_activity = NPCAction.SLEEP
                self.persistence.current_state.current_activity = "睡觉"
                self.persistence.current_state.is_sleeping = True
                self.activity_start_time = current_time

        elif 6 <= hour < 9:  # 早上6-9点
            # 起床准备时间
            if profession in ["铁匠", "商人", "牧师", "农民"]:
                if self.current_activity != NPCAction.WORK:
                    self.current_activity = NPCAction.WORK  # 准备工作
                    self.persistence.current_state.current_activity = "工作"
                    self.persistence.current_state.is_sleeping = False
                    self.activity_start_time = current_time

        elif 9 <= hour < 18:  # 白天工作时间 9-18点
            if is_workday and profession in ["铁匠", "商人", "牧师", "农民"]:
                if self.current_activity != NPCAction.WORK:
                    self.current_activity = NPCAction.WORK
                    self.persistence.current_state.current_activity = "工作"
                    self.persistence.current_state.is_sleeping = False
                    self.activity_start_time = current_time
            else:
                # 非工作日或非工作职业
                if self.current_activity != NPCAction.REST:
                    self.current_activity = NPCAction.REST
                    self.persistence.current_state.current_activity = "休息"
                    self.persistence.current_state.is_sleeping = False
                    self.activity_start_time = current_time

        elif 18 <= hour < 22:  # 晚上18-22点
            # 下班后的社交时间
            if profession == "铁匠":
                if self.current_activity != NPCAction.SOCIALIZE:
                    self.current_activity = NPCAction.SOCIALIZE  # 去酒馆
                    self.persistence.current_state.current_activity = "社交"
                    self.persistence.current_state.is_sleeping = False
                    self.activity_start_time = current_time
            else:
                if self.current_activity != NPCAction.REST:
                    self.current_activity = NPCAction.REST
                    self.persistence.current_state.current_activity = "休息"
                    self.persistence.current_state.is_sleeping = False
                    self.activity_start_time = current_time

    def _set_initial_activity(self):
        """根据当前时间和职业设置初始活动"""
        current_hour = self.world_clock.current_time.hour
        profession = self.config.get("profession", "")

        # 基于时间和职业设置初始活动
        if 22 <= current_hour or current_hour < 6:
            # 深夜：睡觉
            self.current_activity = NPCAction.SLEEP
        elif 6 <= current_hour < 8:
            # 早上：起床准备
            self.current_activity = NPCAction.REST
        elif 8 <= current_hour < 18:
            # 白天工作时间
            if profession in ["铁匠", "blacksmith"]:
                # 铁匠在工作时间内工作
                work_hours = self.config.get("work_hours", "早上6点-晚上7点")
                if "6" in work_hours and current_hour >= 8:
                    self.current_activity = NPCAction.WORK
                else:
                    self.current_activity = NPCAction.REST
            elif profession in ["酒馆老板", "innkeeper"]:
                # 酒馆老板在营业时间工作
                work_hours = self.config.get("work_hours", "早上8点到深夜12点")
                if current_hour >= 8:
                    self.current_activity = NPCAction.WORK
                else:
                    self.current_activity = NPCAction.REST
            elif profession in ["牧师", "priest"]:
                # 牧师在工作时间内工作
                work_hours = self.config.get("work_hours", "早上8点-下午4点")
                if 8 <= current_hour < 16:
                    self.current_activity = NPCAction.WORK
                else:
                    self.current_activity = NPCAction.REST
            else:
                # 其他职业默认工作
                self.current_activity = NPCAction.WORK
        elif 18 <= current_hour < 22:
            # 晚上：社交或休息
            if profession in ["酒馆老板", "innkeeper"]:
                self.current_activity = NPCAction.WORK  # 晚班
            else:
                self.current_activity = NPCAction.SOCIALIZE
        else:
            # 默认睡觉
            self.current_activity = NPCAction.SLEEP

        # 设置活动开始时间为当前时间
        self.activity_start_time = self.world_clock.current_time

    def update_time(self, new_time: datetime):
        """更新时间并处理时间相关的状态变化"""
        time_diff = (new_time - self.world_clock.current_time).total_seconds() / 3600  # 小时差

        # 1. 处理待处理事件队列
        self._process_pending_events(new_time)

        # 2. 更新移动状态（如果正在移动）
        self._update_movement(time_diff)

        # 3. 根据新时间调整活动状态
        self._adjust_activity_for_time(new_time)

        # 更新能量水平（基于活动和时间）- 使用新的 0.0-1.0 范围
        if self.current_activity:
            energy_cost = self._get_activity_energy_cost(self.current_activity)
            self.energy = max(0.0, self.energy - energy_cost * time_diff)

        # 自然能量恢复（睡觉时更快）
        if self.current_activity == NPCAction.SLEEP:
            recovery_rate = 0.2  # 每小时恢复0.2能量 (即20%)
        else:
            recovery_rate = 0.05

        self.energy = min(1.0, self.energy + recovery_rate * time_diff)

        # 使用LLM决策更新任务进度
        self._update_task_progress(time_diff)

        # 检查是否需要切换活动（额外的随机切换）
        if self._should_change_activity():
            self._select_new_activity()

    def _process_pending_events(self, current_time: datetime):
        """处理待处理事件队列"""
        events_to_process = []

        # 找出所有已到期且未处理的事件
        for event in self.pending_events:
            if not event.get("processed") and event.get("process_at", current_time) <= current_time:
                events_to_process.append(event)

        # 处理事件
        for event in events_to_process:
            event["processed"] = True

            # 通过四级决策系统处理事件
            result = self.process_event(
                event_content=event["content"],
                event_type=event["type"]
            )

            # 如果事件需要NPC移动到事件位置
            event_location = event.get("location")
            if event_location and event_location != self.current_location:
                # 根据事件影响度决定是否移动
                if result.get("impact_analysis", {}).get("impact_score", 0) > 50:
                    self.move_to(event_location)

            # 记录事件处理日志
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"NPC {self.npc_name} 处理待处理事件: {event['content'][:30]}...")

        # 清理已处理的事件
        self.pending_events = [e for e in self.pending_events if not e.get("processed")]

    def _update_movement(self, time_diff_hours: float):
        """更新NPC的移动状态"""
        if self.current_activity != NPCAction.TRAVEL:
            return

        # 使用空间系统更新移动
        arrived_location = self.spatial_system.update_movement(self.npc_name, time_diff_hours)

        if arrived_location:
            # 到达目的地
            self.current_location = arrived_location
            self.movement_destination = None

            # 到达后切换到适当的活动
            self._on_arrival_at_destination(arrived_location)

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"NPC {self.npc_name} 到达 {arrived_location}")

    def _on_arrival_at_destination(self, location: str):
        """到达目的地后的处理"""
        # 根据位置类型决定活动
        location_info = self.spatial_system.get_location(location)

        if location_info:
            zone_type = location_info.zone_type.value if hasattr(location_info.zone_type, 'value') else str(location_info.zone_type)

            if zone_type == "industrial":
                self._change_activity(NPCAction.WORK)
            elif zone_type == "commercial":
                self._change_activity(NPCAction.SOCIALIZE)
            elif zone_type == "religious":
                self._change_activity(NPCAction.PRAY)
            elif zone_type == "residential":
                self._change_activity(NPCAction.REST)
            else:
                self._change_activity(NPCAction.OBSERVE)

    def _get_activity_energy_cost(self, activity: NPCAction) -> float:
        """获取活动能量消耗"""
        costs = {
            NPCAction.WORK: 15,
            NPCAction.SOCIALIZE: 8,
            NPCAction.TRAVEL: 12,
            NPCAction.THINK: 5,
            NPCAction.REST: 3,
            NPCAction.SLEEP: -10,  # 睡觉恢复能量
        }
        return costs.get(activity, 5)

    def _analyze_task_and_select_activity(self, task) -> NPCAction:
        """
        智能分析任务内容并选择合适的应对活动

        Args:
            task: 要分析的任务

        Returns:
            合适的NPC活动
        """
        description = task.description.lower()

        # 基于任务优先级和内容的智能分析
        priority = task.priority

        # 高优先级任务（>80）通常需要立即关注
        if priority > 80:
            # 分析任务内容的语义特征
            activity = self._classify_task_by_content(description)
            return activity

        # 中等优先级任务（>=50）根据具体内容决定
        elif priority >= 50:
            activity = self._classify_task_by_content(description)
            return activity

        # 低优先级任务（<50）通常只需要观察
        else:
            return NPCAction.OBSERVE

    def _classify_task_by_content(self, description: str) -> NPCAction:
        """
        基于任务内容分类选择活动

        Args:
            description: 任务描述（小写）

        Returns:
            合适的活动类型
        """
        # 威胁和安全相关任务
        threat_keywords = [
            '小偷', '偷窃', '盗贼', '入侵', '闯入', '威胁', '危险', '攻击',
            'theft', 'steal', 'intruder', 'threat', 'danger', 'attack',
            'robber', 'burglar', 'intrusion'
        ]
        if any(keyword in description for keyword in threat_keywords):
            return NPCAction.OBSERVE  # 警戒观察

        # 帮助和救援相关任务
        help_keywords = [
            '帮助', '救援', '救人', '援助', '协助', '支持',
            'help', 'rescue', 'aid', 'assist', 'support',
            'save', 'protect', 'defend'
        ]
        if any(keyword in description for keyword in help_keywords):
            return NPCAction.HELP_OTHERS

        # 社交和沟通相关任务
        social_keywords = [
            '谈话', '聊天', '会面', '交流', '沟通', '拜访',
            'talk', 'chat', 'meet', 'communicate', 'visit',
            'conversation', 'discussion'
        ]
        if any(keyword in description for keyword in social_keywords):
            return NPCAction.SOCIALIZE

        # 调查和探索相关任务
        investigation_keywords = [
            '调查', '检查', '寻找', '搜索', '探索', '查看',
            'investigate', 'check', 'find', 'search', 'explore',
            'examine', 'inspect'
        ]
        if any(keyword in description for keyword in investigation_keywords):
            return NPCAction.OBSERVE

        # 工作和劳动相关任务
        work_keywords = [
            '工作', '劳动', '修理', '制作', '建造', '维护',
            'work', 'labor', 'repair', 'make', 'build', 'maintain',
            'craft', 'create', 'construct'
        ]
        if any(keyword in description for keyword in work_keywords):
            return NPCAction.WORK

        # 学习和研究相关任务
        learn_keywords = [
            '学习', '研究', '阅读', '练习', '训练', '钻研',
            'learn', 'study', 'read', 'practice', 'train',
            'research', 'explore'
        ]
        if any(keyword in description for keyword in learn_keywords):
            return NPCAction.LEARN

        # 医疗和治疗相关任务
        medical_keywords = [
            '治疗', '医疗', '救治', '护理', '康复',
            'treat', 'heal', 'medical', 'care', 'recovery',
            'medicine', 'cure', 'nurse'
        ]
        if any(keyword in description for keyword in medical_keywords):
            return NPCAction.HELP_OTHERS  # 用帮助他人代替医疗活动

        # 祈祷和精神相关任务
        spiritual_keywords = [
            '祈祷', '祷告', '冥想', '礼拜', '仪式',
            'pray', 'prayer', 'meditate', 'worship', 'ritual',
            'spiritual', 'religious'
        ]
        if any(keyword in description for keyword in spiritual_keywords):
            return NPCAction.PRAY

        # 旅行和移动相关任务
        travel_keywords = [
            '旅行', '移动', '前往', '出发', '行走',
            'travel', 'move', 'go', 'journey', 'walk',
            'transport', 'journey'
        ]
        if any(keyword in description for keyword in travel_keywords):
            return NPCAction.TRAVEL

        # 默认情况下，对未知任务保持观察状态
        return NPCAction.OBSERVE
