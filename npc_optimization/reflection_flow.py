"""
ReflectionFlow - 自动反思系统
每24小时自动运行LLM任务，将原始记录转化为高维见解
解决长期运行后的记忆过载和幻觉问题
"""

import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ReflectionType(Enum):
    """反思类型"""
    DAILY_SUMMARY = "daily_summary"  # 每日总结
    BEHAVIORAL_PATTERN = "behavioral_pattern"  # 行为模式识别
    EMOTIONAL_ARC = "emotional_arc"  # 情感弧线分析
    RELATIONSHIP_EVOLUTION = "relationship_evolution"  # 关系演变
    MORAL_DEVELOPMENT = "moral_development"  # 道德成长
    SKILL_PROGRESSION = "skill_progression"  # 技能进展
    GOAL_REFLECTION = "goal_reflection"  # 目标反思


@dataclass
class ReflectionTask:
    """反思任务配置"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    npc_name: str = ""
    reflection_type: ReflectionType = ReflectionType.DAILY_SUMMARY
    
    source_events: List[str] = field(default_factory=list)  # 事件ID列表
    source_episodes: List[str] = field(default_factory=list)  # 情景ID列表
    
    scheduled_time: Optional[str] = None
    is_periodic: bool = True
    period_hours: int = 24
    
    status: str = "pending"  # pending, running, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ReflectionResult:
    """反思结果"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    npc_name: str = ""
    reflection_type: ReflectionType = ReflectionType.DAILY_SUMMARY
    
    # 反思内容
    summary_text: str = ""  # 主要反思文本
    key_insights: List[str] = field(default_factory=list)  # 关键见解
    behavioral_patterns: List[str] = field(default_factory=list)  # 识别的行为模式
    emotional_shifts: Dict[str, float] = field(default_factory=dict)  # 情感变化
    
    # 关系更新
    affected_relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 目标/进度更新
    goal_status_updates: Dict[str, str] = field(default_factory=dict)
    
    confidence_score: float = 0.7  # 反思的置信度
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ReflectionPromptTemplates:
    """反思提示词模板"""

    @staticmethod
    def daily_summary(npc_name: str,
                     profession: str,
                     events: List[Dict[str, Any]],
                     current_goals: List[str]) -> str:
        """日常总结提示"""
        
        events_summary = "\n".join([
            f"- [{e.get('timestamp', 'N/A')}] {e.get('event_type', 'unknown')}: {e.get('content', '')[:100]}"
            for e in events[-10:]  # 最近10条事件
        ])
        
        return f"""你是{npc_name}，一位{profession}。
        
今天，你经历了以下事件：
{events_summary}

你的当前目标：
{chr(10).join([f"- {g}" for g in current_goals[:3]])}

请回顾今天，按以下格式生成反思：

1. 今天的关键事件（2-3句）：
2. 学到了什么（1-2句）：
3. 明天的计划（1-2句）：
4. 对自己的评价（1句）：

直接回答，不需要额外的解释。"""

    @staticmethod
    def behavioral_pattern(npc_name: str,
                          profession: str,
                          recent_behaviors: Dict[str, int],
                          personality_traits: List[str]) -> str:
        """行为模式识别提示"""
        
        behavior_summary = json.dumps(recent_behaviors, ensure_ascii=False, indent=2)
        
        return f"""你是{npc_name}，一位{profession}。
        
你最近一周的行为频率：
{behavior_summary}

你的性格特征：{', '.join(personality_traits)}

请分析：
1. 你最常采取的行为模式是什么？为什么？
2. 是否有异常的行为改变？
3. 这些模式如何反映你的性格和价值观？
4. 这些模式对你长期目标的影响？

简洁回答，每项1-2句。"""

    @staticmethod
    def emotional_arc(npc_name: str,
                     emotional_history: List[Dict[str, Any]],
                     major_events: List[str]) -> str:
        """情感弧线分析提示"""
        
        return f"""你是{npc_name}。
        
近期你经历的主要事件：
{chr(10).join([f"- {e}" for e in major_events])}

你的情感变化历史：
{json.dumps(emotional_history[-7:], ensure_ascii=False, indent=2)}

请分析你的情感弧线：
1. 整体的情感趋势（上升/下降/波动）：
2. 触发情感变化的关键事件：
3. 你现在的情感状态：
4. 未来可能的情感变化预期：

简洁回答。"""

    @staticmethod
    def relationship_evolution(npc_name: str,
                              relationship_history: Dict[str, Any],
                              recent_interactions: List[Dict[str, Any]]) -> str:
        """关系演变分析提示"""
        
        return f"""你是{npc_name}。
        
你与他人的关系历史：
{json.dumps(relationship_history, ensure_ascii=False, indent=2)}

最近的互动记录：
{json.dumps(recent_interactions[-5:], ensure_ascii=False, indent=2)}

请分析你的关系发展：
1. 哪些关系在改善或恶化？
2. 原因是什么？
3. 你想如何改变这些关系？
4. 谁是你最信任的人？

简洁回答。"""


class ReflectionEngine:
    """
    反思引擎 - 执行实际的反思任务
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def execute_daily_summary(self,
                             npc_name: str,
                             npc_profile: Dict[str, Any],
                             events: List[Dict[str, Any]],
                             current_goals: List[str]) -> ReflectionResult:
        """执行日常总结反思"""
        
        prompt = ReflectionPromptTemplates.daily_summary(
            npc_name,
            npc_profile.get("profession", "村民"),
            events,
            current_goals
        )
        
        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.7
            )
            
            result = ReflectionResult(
                npc_name=npc_name,
                reflection_type=ReflectionType.DAILY_SUMMARY,
                summary_text=response,
                key_insights=self._extract_insights(response),
                confidence_score=0.75
            )
            
            return result
        
        except Exception as e:
            logger.error(f"日常总结执行失败: {e}")
            return None

    def execute_behavioral_pattern_analysis(self,
                                            npc_name: str,
                                            npc_profile: Dict[str, Any],
                                            behavior_frequency: Dict[str, int],
                                            recent_events: List[Dict[str, Any]]) -> ReflectionResult:
        """执行行为模式分析"""
        
        prompt = ReflectionPromptTemplates.behavioral_pattern(
            npc_name,
            npc_profile.get("profession", "村民"),
            behavior_frequency,
            npc_profile.get("personality", {}).get("traits", [])
        )
        
        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.6
            )
            
            result = ReflectionResult(
                npc_name=npc_name,
                reflection_type=ReflectionType.BEHAVIORAL_PATTERN,
                summary_text=response,
                behavioral_patterns=self._extract_patterns(response),
                confidence_score=0.7
            )
            
            return result
        
        except Exception as e:
            logger.error(f"行为模式分析失败: {e}")
            return None

    def execute_emotional_arc_analysis(self,
                                       npc_name: str,
                                       emotional_history: List[Dict[str, Any]],
                                       major_events: List[str]) -> ReflectionResult:
        """执行情感弧线分析"""
        
        prompt = ReflectionPromptTemplates.emotional_arc(
            npc_name,
            emotional_history,
            major_events
        )
        
        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.7
            )
            
            result = ReflectionResult(
                npc_name=npc_name,
                reflection_type=ReflectionType.EMOTIONAL_ARC,
                summary_text=response,
                emotional_shifts=self._extract_emotional_shifts(response),
                confidence_score=0.75
            )
            
            return result
        
        except Exception as e:
            logger.error(f"情感分析失败: {e}")
            return None

    def execute_relationship_evolution(self,
                                       npc_name: str,
                                       relationship_history: Dict[str, Any],
                                       recent_interactions: List[Dict[str, Any]]) -> ReflectionResult:
        """执行关系演变分析"""
        
        prompt = ReflectionPromptTemplates.relationship_evolution(
            npc_name,
            relationship_history,
            recent_interactions
        )
        
        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.7
            )
            
            result = ReflectionResult(
                npc_name=npc_name,
                reflection_type=ReflectionType.RELATIONSHIP_EVOLUTION,
                summary_text=response,
                affected_relationships=self._extract_relationships(response),
                confidence_score=0.7
            )
            
            return result
        
        except Exception as e:
            logger.error(f"关系分析失败: {e}")
            return None

    def _extract_insights(self, text: str) -> List[str]:
        """从反思文本中提取关键见解"""
        lines = text.split('\n')
        insights = []
        
        # 简化实现：提取包含特定关键词的行
        for line in lines:
            if any(keyword in line for keyword in ["学到", "意识到", "明白", "发现", "认识到"]):
                insights.append(line.strip())
        
        return insights[:3]  # 最多3条

    def _extract_patterns(self, text: str) -> List[str]:
        """从反思文本中提取行为模式"""
        lines = text.split('\n')
        patterns = []
        
        for line in lines:
            if any(keyword in line for keyword in ["模式", "习惯", "倾向", "通常", "经常"]):
                patterns.append(line.strip())
        
        return patterns[:3]

    def _extract_emotional_shifts(self, text: str) -> Dict[str, float]:
        """从文本中提取情感变化"""
        # 简化实现：返回示例
        return {
            "happiness": 0.1,  # 变化值
            "stress": -0.2,
            "confidence": 0.15
        }

    def _extract_relationships(self, text: str) -> Dict[str, Dict[str, Any]]:
        """从文本中提取关系信息"""
        # 简化实现：返回示例
        return {
            "sample_npc": {
                "affection_change": 0.1,
                "trust_change": 0.05,
                "status": "improving"
            }
        }


class ReflectionFlowManager:
    """
    反思流程管理器
    协调反思任务的调度、执行、存储
    """

    def __init__(self,
                 llm_client,
                 memory_layer_manager,
                 npc_profile: Dict[str, Any],
                 execution_interval_hours: int = 24):
        self.llm_client = llm_client
        self.memory_manager = memory_layer_manager
        self.npc_profile = npc_profile
        self.execution_interval = execution_interval_hours * 3600  # 转秒
        
        self.reflection_engine = ReflectionEngine(llm_client)
        
        # 任务队列和历史
        self.pending_tasks: List[ReflectionTask] = []
        self.completed_reflections: List[ReflectionResult] = []
        
        # 最后执行时间
        self.last_reflection_time = datetime.now()
        
        # 后台线程
        self.worker_thread = None
        self.running = False

    def start(self):
        """启动反思流程管理器"""
        self.running = True
        self.worker_thread = threading.Thread(
            target=self._reflection_worker,
            daemon=True
        )
        self.worker_thread.start()
        logger.info(f"已启动{self.npc_profile.get('name', 'NPC')}的反思流程")

    def stop(self):
        """停止反思流程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

    def schedule_reflection(self,
                           reflection_type: ReflectionType,
                           source_events: Optional[List[str]] = None) -> ReflectionTask:
        """
        手动调度反思任务
        
        Returns:
            创建的任务对象
        """
        task = ReflectionTask(
            npc_name=self.npc_profile.get("name", "NPC"),
            reflection_type=reflection_type,
            source_events=source_events or [],
            scheduled_time=datetime.now().isoformat()
        )
        
        self.pending_tasks.append(task)
        logger.info(f"已调度反思任务: {reflection_type.value}")
        
        return task

    def _reflection_worker(self):
        """后台反思工作线程"""
        while self.running:
            try:
                # 检查是否该执行定期反思
                elapsed = (datetime.now() - self.last_reflection_time).total_seconds()
                if elapsed >= self.execution_interval:
                    self._execute_periodic_reflection()
                    self.last_reflection_time = datetime.now()
                
                # 处理待执行任务
                if self.pending_tasks:
                    task = self.pending_tasks.pop(0)
                    result = self._execute_reflection_task(task)
                    if result:
                        self.completed_reflections.append(result)
                
                # 避免过度占用CPU
                threading.Event().wait(5)
            
            except Exception as e:
                logger.error(f"反思流程错误: {e}")

    def _execute_periodic_reflection(self):
        """执行定期反思"""
        
        npc_name = self.npc_profile.get("name", "NPC")
        logger.info(f"执行{npc_name}的定期反思（24小时检查点）")
        
        # 收集最近24小时的事件
        recent_events = self._get_recent_events(hours=24)
        
        if not recent_events:
            logger.info(f"{npc_name}: 无最近事件，跳过反思")
            return
        
        # 执行多个反思任务
        reflections = [
            self.reflection_engine.execute_daily_summary(
                npc_name,
                self.npc_profile,
                recent_events,
                self._get_current_goals()
            ),
            self.reflection_engine.execute_behavioral_pattern_analysis(
                npc_name,
                self.npc_profile,
                self._analyze_behavior_frequency(recent_events),
                recent_events
            ),
            self.reflection_engine.execute_emotional_arc_analysis(
                npc_name,
                self._get_emotional_history(),
                self._get_major_events(recent_events)
            )
        ]
        
        # 存储反思结果
        for reflection in reflections:
            if reflection:
                self._store_reflection_as_insight(reflection)
                self.completed_reflections.append(reflection)

    def _execute_reflection_task(self, task: ReflectionTask) -> Optional[ReflectionResult]:
        """执行单个反思任务"""
        
        task.status = "running"
        task.started_at = datetime.now().isoformat()
        
        try:
            # 根据任务类型执行相应的反思
            if task.reflection_type == ReflectionType.DAILY_SUMMARY:
                result = self.reflection_engine.execute_daily_summary(
                    task.npc_name,
                    self.npc_profile,
                    [{"content": f"Event {e}"} for e in task.source_events],
                    self._get_current_goals()
                )
            
            elif task.reflection_type == ReflectionType.BEHAVIORAL_PATTERN:
                result = self.reflection_engine.execute_behavioral_pattern_analysis(
                    task.npc_name,
                    self.npc_profile,
                    {},
                    []
                )
            
            else:
                result = None
            
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            
            if result:
                self._store_reflection_as_insight(result)
            
            return result
        
        except Exception as e:
            logger.error(f"反思任务执行失败: {e}")
            task.status = "failed"
            return None

    def _store_reflection_as_insight(self, reflection: ReflectionResult):
        """将反思结果存入RAG系统"""
        
        from npc_optimization.memory_layers import Insight
        
        insight = Insight(
            id=f"reflection_{reflection.id}",
            created_at=reflection.generated_at,
            source_event_ids=[],
            insight_text=reflection.summary_text,
            insight_type=reflection.reflection_type.value,
            emotional_weight=0,
            relevance_score=reflection.confidence_score,
            keywords=reflection.key_insights[:3]
        )
        
        self.memory_manager.add_reflection_insight(insight)
        logger.info(f"已存储反思见解: {insight.id}")

    def _get_recent_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近N小时的事件"""
        # 从热记忆或冷存储获取
        context = self.memory_manager.get_decision_context()
        return context.get("hot_memory", {}).get("recent_events", [])

    def _get_current_goals(self) -> List[str]:
        """获取当前活跃目标"""
        # 应该从NPC系统获取
        return ["生存", "获得尊重", "实现目标"]

    def _analyze_behavior_frequency(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """分析行为频率"""
        frequency = {}
        for event in events:
            event_type = event.get("event_type", "unknown")
            frequency[event_type] = frequency.get(event_type, 0) + 1
        return frequency

    def _get_emotional_history(self) -> List[Dict[str, Any]]:
        """获取情感历史"""
        return []

    def _get_major_events(self, recent_events: List[Dict[str, Any]]) -> List[str]:
        """识别主要事件"""
        major_events = []
        for event in recent_events[:5]:
            impact = event.get("impact_score", 0)
            if impact > 50:
                major_events.append(event.get("content", ""))
        return major_events

    def get_reflection_summary(self) -> Dict[str, Any]:
        """获取反思摘要"""
        return {
            "total_reflections": len(self.completed_reflections),
            "pending_tasks": len(self.pending_tasks),
            "last_reflection": (
                self.completed_reflections[-1].generated_at
                if self.completed_reflections else None
            ),
            "reflection_types_count": {
                rt.value: sum(
                    1 for r in self.completed_reflections
                    if r.reflection_type == rt
                )
                for rt in ReflectionType
            }
        }
