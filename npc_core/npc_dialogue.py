"""
NPC 对话和记忆模块

包含对话和记忆相关的方法：
- add_memory: 添加记忆
- respond_to_world_event: 响应世界事件
- make_decision: 决策方法
- 任务进度更新相关方法
- 初始化和序列化方法
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from core_types import NPCAction, Emotion
from npc_core.npc_persistence import NPCTask

from .data_models import Memory, Goal, Relationship


class NPCDialogueMixin:
    """NPC 对话和记忆混入类"""

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
        添加新记忆（符合MemoryInterface标准接口）

        同时添加到RAG系统
        """
        memory = Memory(
            content=content,
            emotional_impact=emotional_impact,
            importance=importance,
            timestamp=self.world_clock.current_time,
            tags=tags or []
        )
        self.memories.append(memory)

        # 同时添加到RAG记忆系统
        memory_id = f"mem_{len(self.memories)}_{hash(content)}"
        try:
            self.rag_memory.add_memory(
                content=content,
                importance=importance,
                memory_type=memory_type,
                tags=tags or [],
                emotional_impact=emotional_impact,
                related_npcs=related_npcs,
                metadata=metadata
            )
        except Exception as e:
            print(f"添加RAG记忆失败: {e}")

        # 限制记忆数量
        if len(self.memories) > 50:
            # 删除最不重要的记忆
            self.memories.sort(key=lambda x: x.importance)
            self.memories = self.memories[10:]

        return memory_id

    def get_relationship_status(self, npc_name: str) -> Relationship:
        """获取与特定NPC的关系状态"""
        return self.relationships.get(npc_name, Relationship(npc_name, 0, 50))

    def interact_with_other(self, other_npc_name: str, interaction_type: str):
        """与其他NPC互动"""
        if other_npc_name not in self.relationships:
            self.relationships[other_npc_name] = Relationship(
                npc_name=other_npc_name,
                affection=0,
                trust=50
            )

        relationship = self.relationships[other_npc_name]
        relationship.interactions_count += 1
        relationship.last_interaction = self.world_clock.current_time

        # 根据互动类型调整关系
        if interaction_type == "help":
            relationship.affection = min(100, relationship.affection + 5)
            relationship.trust = min(100, relationship.trust + 3)
        elif interaction_type == "conflict":
            relationship.affection = max(-100, relationship.affection - 10)
            relationship.trust = max(0, relationship.trust - 5)

    def respond_to_world_event(self, event_description: str) -> Dict[str, Any]:
        """对世界事件做出响应"""
        response = self.llm_client.generate_world_event_response(
            self.config,
            event_description
        )

        # 分析事件类型并调整行为
        event_type = self._analyze_event_type(event_description)
        self._adjust_behavior_for_event(event_type, event_description)

        # 添加到记忆
        self.add_memory(
            f"世界事件：{event_description}，我的反应：{response['thoughts']}",
            emotional_impact=response.get('emotional_impact_score', 0),
            importance=7,
            tags=["world_event", "reaction", event_type]
        )

        return response

    def _analyze_event_type(self, event_description: str) -> str:
        """分析事件类型"""
        desc_lower = event_description.lower()

        # 威胁性事件
        if any(word in desc_lower for word in ["小偷", "盗贼", "强盗", "入侵", "攻击", "怪物", "野兽"]):
            return "threat"

        # 自然灾害
        if any(word in desc_lower for word in ["火灾", "地震", "洪水", "风暴"]):
            return "disaster"

        # 社会事件
        if any(word in desc_lower for word in ["拜访", "来访", "客人", "访客", "送信"]):
            return "social"

        # 其他事件
        return "general"

    def _adjust_behavior_for_event(self, event_type: str, event_description: str):
        """根据事件类型调整行为"""
        if event_type == "threat":
            # 面对威胁时，改变当前活动为防御或调查
            self.current_activity = NPCAction.OBSERVE  # 改为观察/调查
            self.energy = min(1.0, self.energy + 0.2)  # 肾上腺素提升 (使用0.0-1.0范围)
            self.current_emotion = Emotion.ANGRY if "小偷" in event_description else Emotion.WORRIED

        elif event_type == "disaster":
            # 面对灾害时，改变为求助或逃跑
            self.current_activity = NPCAction.HELP_OTHERS
            self.current_emotion = Emotion.WORRIED

        elif event_type == "social":
            # 面对社交事件时，改变为社交
            self.current_activity = NPCAction.SOCIALIZE
            self.current_emotion = Emotion.HAPPY

        # 重置活动开始时间
        self.activity_start_time = self.world_clock.current_time

    def make_decision(self, available_actions: List[str], situation: str = "日常决策") -> Dict[str, Any]:
        """使用新的 ReActAgent 系统做出智能决策"""
        # 构建NPC上下文
        npc_context = self._build_npc_context()

        # 使用 ReActAgent 进行决策（简化实现）
        selected_action = available_actions[0] if available_actions else "休息"
        decision = {
            "action": selected_action,
            "reasoning": f"在'{situation}'情况下选择: {selected_action}",
            "confidence": 0.7
        }

        # 记录决策历史
        self.decision_history.append({
            "timestamp": self.world_clock.current_time,
            "situation": situation,
            "decision": decision,
            "available_actions": available_actions
        })

        # 执行工具调用（如果有）
        if decision.get('tool_calls'):
            for tool_call in decision['tool_calls']:
                self._execute_tool_call(tool_call)

        # 更新情感状态
        self._update_emotion_from_decision(decision)

        return decision

    def _build_npc_context(self) -> Dict[str, Any]:
        """构建NPC上下文字典"""
        # 获取最近记忆
        recent_memories = []
        if hasattr(self, 'memories') and self.memories:
            # 转换记忆到新的格式
            sorted_memories = sorted(self.memories, key=lambda x: x.timestamp, reverse=True)[:5]
            for memory in sorted_memories:
                recent_memories.append({
                    "content": memory.content,
                    "importance": memory.importance,
                    "emotional_impact": memory.emotional_impact,
                    "timestamp": memory.timestamp.isoformat(),
                    "tags": memory.tags if hasattr(memory, 'tags') else []
                })

        # 构建时间上下文
        time_context = {
            "season": self._get_season(),
            "time_of_day": self._get_time_of_day(),
            "day_of_week": self.world_clock.current_time.strftime("%A"),
            "weather": "正常",  # 可以扩展
            "hour": self.world_clock.current_time.hour
        }

        # 当前任务
        current_task = None
        if self.persistence.current_task:
            current_task = {
                "description": self.persistence.current_task.description,
                "progress": self.persistence.current_task.progress,
                "id": self.persistence.current_task.id
            }

        return {
            "name": self.config["name"],
            "race": self.config["race"],
            "profession": self.config["profession"],
            "personality": self.config["personality"]["traits"],
            "background": self.config["background"],
            "current_activity": self.current_activity.value if self.current_activity else "空闲",
            "current_emotion": self.current_emotion.value,
            "current_needs": {
                "hunger": self.need_system.needs.hunger if hasattr(self, 'need_system') else 0.5,
                "fatigue": self.need_system.needs.fatigue if hasattr(self, 'need_system') else 0.5,
                "social": self.need_system.needs.social if hasattr(self, 'need_system') else 0.5,
                "achievement": getattr(self, 'achievement_need', 0.5)
            },
            "current_task": current_task,
            "recent_memories": recent_memories,
            "time_context": time_context
        }

    def _execute_tool_call(self, tool_call: Dict[str, Any]):
        """执行工具调用"""
        tool_name = tool_call.get('tool')
        args = tool_call.get('args', {})

        try:
            # 使用新版 NPCToolRegistry 执行工具
            result = self.tool_registry.execute_tool(tool_name, **args)
            if not result['success']:
                print(f"工具执行失败: {tool_name} - {result.get('error', '未知错误')}")
        except Exception as e:
            print(f"工具调用异常: {tool_name} - {e}")

    def _get_season(self) -> str:
        """获取当前季节"""
        month = self.world_clock.current_time.month
        if month in [12, 1, 2]:
            return "冬季"
        elif month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        else:
            return "秋季"

    def _get_time_of_day(self) -> str:
        """获取当前时间段"""
        hour = self.world_clock.current_time.hour
        if 5 <= hour < 12:
            return "上午"
        elif 12 <= hour < 18:
            return "下午"
        elif 18 <= hour < 22:
            return "晚上"
        else:
            return "深夜"

    def _update_emotion_from_decision(self, decision: Dict[str, Any]):
        """根据决策更新情感状态"""
        emotion_str = decision.get("emotion", "").lower()

        emotion_map = {
            "高兴": Emotion.HAPPY,
            "平静": Emotion.CALM,
            "担心": Emotion.WORRIED,
            "悲伤": Emotion.SAD,
            "愤怒": Emotion.ANGRY,
            "兴奋": Emotion.EXCITED,
            "疲惫": Emotion.EXHAUSTED,
            "满足": Emotion.CONTENT
        }

        if emotion_str in emotion_map:
            self.current_emotion = emotion_map[emotion_str]

    def _update_goals_from_decision(self, decision: Dict[str, Any]):
        """根据决策更新目标进度"""
        action = decision.get("action", "")
        reasoning = decision.get("reasoning", "")

        for goal in self.short_term_goals + self.long_term_goals:
            if goal.status == "active":
                # 检查是否与目标相关
                if any(keyword in reasoning for keyword in goal.description.split()):
                    goal.progress = min(1.0, goal.progress + 0.1)
                    if goal.progress >= 1.0:
                        goal.status = "completed"

    def _update_task_progress(self, time_diff: float):
        """
        更新任务进度 - 优化版本（基于时间流逝而非每次LLM调用）
        策略：在创建任务时由LLM预估总时长，日常更新基于比例，只在突发事件时重新评估
        """
        task = self.persistence.current_task
        if not task or task.status != "active":
            return

        # 如果任务未设置预估时长，首次调用LLM获取预估值
        if not hasattr(task, 'estimated_total_hours') or task.estimated_total_hours is None:
            task.estimated_total_hours = self._llm_estimate_task_duration(task)
            self.persistence._save_data()

        # 基于时间流逝计算进度增量（而非LLM每次决策）
        if task.estimated_total_hours > 0:
            progress_increment = time_diff / task.estimated_total_hours
        else:
            progress_increment = 0.05  # 默认进度增量

        # 只在进度有明显变化或达到阈值时更新
        old_progress = task.progress
        task.progress = min(1.0, task.progress + progress_increment)

        # 每达到 20% 的进度或任务完成时，重新用 LLM 评估（动态调整）
        should_recheck = (int(old_progress * 5) != int(task.progress * 5)) or task.progress >= 1.0

        if should_recheck and task.progress < 1.0:
            # 重新评估：任务是否应该加速或减速完成
            dynamic_adjustment = self._llm_recheck_task_progress(task, time_diff)
            if dynamic_adjustment != 0:
                task.progress += dynamic_adjustment
                print(f"[LLM动态调整] 任务: {task.description[:30]}... 调整: {dynamic_adjustment*100:.1f}%")

        task.progress = min(1.0, task.progress)  # 确保不超过 100%
        self.persistence._save_data()

        if task.progress - old_progress > 0.01:
            print(f"[任务进度] {task.description[:30]}... {old_progress*100:.1f}% -> {task.progress*100:.1f}%")

        # 如果任务完成
        if task.progress >= 1.0:
            task.status = "completed"
            self.persistence.current_state.current_task_id = None
            self.persistence._save_data()
            self.sync_goals_to_persistence()
            print(f"[任务完成] {task.description}")

            # 检查是否有后续影响
            self._handle_task_completion(task)

    def _llm_estimate_task_duration(self, task) -> float:
        """
        使用LLM预估任务的总时长（仅在创建任务时调用一次）

        Args:
            task: 任务对象

        Returns:
            预估小时数
        """
        try:
            prompt = f"""
你是一个 NPC 行为预测专家。请预估以下任务的完成时长（单位：小时）：

任务: {task.description}
优先级: {task.priority}
任务类型: {task.task_type}
NPC 工作: {self.config['profession']}
NPC 名字: {self.config['name']}

只返回一个数字（小时数），不要其他说明。
如果是短期任务（如制作物品），通常 0.5-4 小时。
如果是中期目标（如学习技能），通常 4-24 小时。
如果是长期目标，通常 24+ 小时。

预估时长（小时）："""

            response = self.deepseek_client.chat(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )

            try:
                # 提取数字
                duration_str = response['choices'][0]['message']['content'].strip()
                estimated_hours = float(''.join(filter(lambda x: x.isdigit() or x == '.', duration_str)))
                return max(0.5, min(720, estimated_hours))  # 限制在 0.5-720 小时
            except:
                return 4.0  # 默认 4 小时

        except Exception as e:
            print(f"LLM 预估任务时长失败: {e}")
            return 4.0  # 默认降级为 4 小时

    def _llm_recheck_task_progress(self, task, time_diff: float) -> float:
        """
        动态重新评估任务进度（仅在每 20% 进度时调用）
        检查任务是否应该加速或减速完成

        Args:
            task: 任务对象
            time_diff: 时间差（小时）

        Returns:
            进度调整增量 (-0.2 to 0.2)
        """
        try:
            # 简化的 prompt，只检查是否需要加速或减速
            prompt = f"""
任务进度检查：{task.description}
当前进度：{task.progress*100:.0f}%
预估总时长：{task.estimated_total_hours:.1f} 小时
当前情感状态：{self.current_emotion.value}
当前能量：{int(self.energy * 100)}%

请判断任务是否需要加速（+）、正常（0）或减速（-）？
只返回一个符号：+ 或 0 或 - （加速、正常或减速）"""

            response = self.deepseek_client.chat(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10
            )

            decision = response['choices'][0]['message']['content'].strip()[0]  # 取第一个字符

            if decision == '+':
                return 0.1  # 加速 10% 进度
            elif decision == '-':
                return -0.05  # 减速 5% 进度
            else:
                return 0  # 正常，无调整

        except Exception as e:
            print(f"[LLM 动态评估失败] {e}，保持正常进度")
            return 0  # 失败时不调整

    def _handle_task_completion(self, completed_task: NPCTask):
        """处理任务完成的影响 - 使用LLM智能决策后续任务"""
        # 使用LLM判断是否需要创建后续任务，以及任务的优先级和截止时间
        try:
            prompt = f"""
任务已完成：{completed_task.description}

请分析：
1. 是否需要创建后续任务？
2. 如果需要，任务应该是什么？优先级是多少？需要多长时间完成？
3. 后续任务是否应该立即执行，还是可以插入到日常规划中？

请用JSON格式回复：
{{
    "create_followup": true/false,
    "task_description": "后续任务描述（如果需要）",
    "priority": 1-100,
    "estimated_hours": 0.5-4.0,
    "should_immediate": true/false,
    "reasoning": "你的推理"
}}

注意：
- 简单任务（如检查、报告）应该在0.5-1小时内完成
- 后续任务不一定需要立即执行，可以安排到合适的时间
- 考虑任务的紧急程度和重要性
"""

            response = self.llm_client.generate_response(prompt, max_tokens=300)
            import re

            json_match = re.search(r'\{[^{}]*"create_followup"[^{}]*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())

                if result.get('create_followup', False):
                    task_desc = result.get('task_description', '')
                    priority = result.get('priority', 60)
                    estimated_hours = result.get('estimated_hours', 1.0)
                    should_immediate = result.get('should_immediate', False)

                    if task_desc:
                        # 创建后续任务
                        deadline = None
                        if not should_immediate:
                            # 不立即执行，安排在当天合适时间
                            current_hour = self.world_clock.current_time.hour
                            # 如果现在是工作时间，安排在下午；如果是晚上，安排在明天
                            if 9 <= current_hour < 18:
                                deadline_hour = min(17, current_hour + 2)  # 2小时后或17点
                            else:
                                deadline_hour = 14  # 明天下午2点
                            deadline = (self.world_clock.current_time + timedelta(days=0 if 9 <= current_hour < 18 else 1)).replace(hour=deadline_hour, minute=0)

                        follow_up_task = self.persistence.create_task(
                            description=task_desc,
                            task_type="event_followup",
                            priority=priority,
                            deadline=deadline.isoformat() if deadline else None
                        )

                        # 只有高优先级或需要立即执行的任务才设置为当前任务
                        if should_immediate or priority >= 80:
                            task_obj = self.persistence.tasks[follow_up_task]
                            self.persistence.set_current_task(task_obj)
                        # 否则作为待办任务，由Agent自主规划

                        reasoning = result.get('reasoning', '')
                        if reasoning:
                            print(f"[后续任务] {reasoning}")
        except Exception as e:
            print(f"后续任务决策失败: {e}")

        # 保存状态
        self.persistence._save_data()

    def _initialize_from_config(self):
        """从配置初始化NPC状态"""
        # 初始化情感状态
        base_mood = self.config["emotional_state"]["base_mood"]
        if base_mood == "cheerful":
            self.current_emotion = Emotion.HAPPY
        elif base_mood == "calm":
            self.current_emotion = Emotion.CALM
        elif base_mood == "serious":
            self.current_emotion = Emotion.CONTENT

        # 初始化记忆
        for memory_text in self.config.get("memories", []):
            memory = Memory(
                content=memory_text,
                emotional_impact=random.randint(-5, 5),
                importance=random.randint(1, 10),
                timestamp=self.world_clock.current_time - timedelta(days=random.randint(1, 365))
            )
            self.memories.append(memory)

        # 初始化知识库
        self.knowledge_base = {
            "skills": self.config.get("skills", {}),
            "world_knowledge": {
                "town_layout": "小镇由中央广场、铁匠铺、酒馆、教堂等区域组成",
                "daily_routine": self.config.get("daily_schedule", {}),
                "important_people": list(self.config.get("relationships", {}).keys())
            }
        }

    def _initialize_goals(self):
        """初始化目标系统"""
        # 短期目标
        for goal_text in self.config["goals"]["short_term"]:
            goal = Goal(
                description=goal_text,
                priority=random.randint(3, 8),
                progress=random.uniform(0, 0.3)
            )
            self.short_term_goals.append(goal)

        # 长期目标
        for goal_text in self.config["goals"]["long_term"]:
            goal = Goal(
                description=goal_text,
                priority=random.randint(5, 10),
                deadline=self.world_clock.current_time + timedelta(days=random.randint(30, 365)),
                progress=random.uniform(0, 0.1)
            )
            self.long_term_goals.append(goal)

    def _initialize_relationships(self):
        """初始化人际关系"""
        for rel_key, rel_info in self.config.get("relationships", {}).items():
            relationship = Relationship(
                npc_name=rel_key,
                affection=random.randint(-20, 80),
                trust=random.randint(20, 90),
                relationship_type=rel_info.get("relationship", "acquaintance")
            )
            self.relationships[rel_key] = relationship

    def get_status_summary(self) -> Dict[str, Any]:
        """获取NPC状态摘要"""
        current_task_data = None
        if self.persistence.current_task:
            task = self.persistence.current_task
            current_task_data = {
                'id': task.id,
                'description': task.description,
                'task_type': task.task_type,
                'priority': task.priority,
                'status': task.status,
                'progress': task.progress
            }

        return {
            "name": self.config["name"],
            "profession": self.config["profession"],
            "current_emotion": self.current_emotion.value,
            "energy": self.energy,  # 使用新字段 (0.0-1.0)
            "current_activity": self.current_activity.value if self.current_activity else "无",
            "current_state": {
                "current_activity": self.persistence.current_state.current_activity,
                "current_task": current_task_data,
                "current_task_id": self.persistence.current_state.current_task_id
            },
            "location": self.current_location,
            "time": self.world_clock.current_time.strftime("%H:%M"),
            "active_goals": len([g for g in self.short_term_goals + self.long_term_goals if g.status == "active"]),
            "recent_memories": len([m for m in self.memories if (self.world_clock.current_time - m.timestamp).days < 7])
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "config": self.config,
            "current_emotion": self.current_emotion.value,
            "energy": self.energy,  # 使用新字段 (0.0-1.0)
            "current_time": self.world_clock.current_time.isoformat(),
            "location": self.current_location,
            "current_activity": self.current_activity.value if self.current_activity else None,
            "memories": [m.__dict__ for m in self.memories],
            "goals": {
                "short_term": [g.__dict__ for g in self.short_term_goals],
                "long_term": [g.__dict__ for g in self.long_term_goals]
            },
            "relationships": {k: v.__dict__ for k, v in self.relationships.items()},
            "decision_history": self.decision_history[-10:]  # 只保存最近10个决策
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], deepseek_client) -> 'NPCDialogueMixin':
        """从字典反序列化"""
        npc = cls(data["config"], deepseek_client)

        npc.current_emotion = Emotion(data.get("current_emotion", "平静"))
        # 兼容旧数据格式
        if "energy" in data:
            npc.energy = data["energy"]
        elif "energy_level" in data:
            energy_val = data["energy_level"]
            npc.energy = energy_val / 100.0 if energy_val > 1 else energy_val
        else:
            npc.energy = 1.0
        npc.current_time = datetime.fromisoformat(data["current_time"])
        npc.current_location = data.get("location", data.get("current_location", "住宅"))
        npc.current_activity = NPCAction(data["current_activity"]) if data.get("current_activity") else None

        # 恢复记忆
        npc.memories = [Memory(**m) for m in data.get("memories", [])]

        # 恢复目标
        goals_data = data.get("goals", {})
        npc.short_term_goals = [Goal(**g) for g in goals_data.get("short_term", [])]
        npc.long_term_goals = [Goal(**g) for g in goals_data.get("long_term", [])]

        # 恢复关系
        npc.relationships = {k: Relationship(**v) for k, v in data.get("relationships", {}).items()}

        npc.decision_history = data.get("decision_history", [])

        return npc
