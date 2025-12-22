"""
四级决策混合架构 (4-Level Decision Architecture)
按需分配算力：80%琐事 L1，15%常规 L2-L3，5%关键 L4
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
from constants import NPCAction, ACTIVITY_INERTIA

logger = logging.getLogger(__name__)


class DecisionLevel(Enum):
    """决策层级"""
    L1_ROUTINE = 1
    L2_FILTER = 2
    L3_STRATEGY = 3
    L4_DEEP_REASONING = 4


class ImpactClassification(Enum):
    """事件冲击力分类"""
    TRIVIAL = 0  # 0-10: 可忽略
    MINOR = 1    # 10-30: 轻微
    MODERATE = 2  # 30-60: 中等
    SIGNIFICANT = 3  # 60-80: 重要
    CRITICAL = 4  # 80-100: 关键


class L1RoutineDecision:
    """
    L1 决策层 - 生理与生物钟硬判决
    处理日常作息：睡眠、吃饭、工作循环等
    特点：零LLM调用，基于惯性值和时钟的硬编码规则
    """

    def __init__(self, npc_config: Dict[str, Any]):
        self.config = npc_config
        self.current_action: Optional[NPCAction] = None
        self.action_start_time: Optional[datetime] = None

    def decide(self,
               current_action: Optional[NPCAction],
               current_hour: int,
               energy_level: float,
               hunger_level: float,
               fatigue_level: float,
               latest_impact_score: int) -> Optional[NPCAction]:
        """
        硬判决逻辑：根据生物钟和惯性值决定是否继续当前行为
        
        Returns:
            NPCAction if 需要改变行为，None if 继续执行L1
        """
        
        # 强制睡眠检查（最高优先）
        if fatigue_level > 0.98:
            return NPCAction.SLEEP
        
        # 强制进食检查
        if hunger_level > 0.9:
            return NPCAction.EAT
        
        # 如果没有当前行为，返回默认作息
        if current_action is None:
            return self._get_default_routine(current_hour)
        
        # 检查事件冲击力是否超过当前行为的惯性
        current_inertia = ACTIVITY_INERTIA.get(current_action, 50)
        
        if latest_impact_score < current_inertia:
            # 冲击力不足以打断当前行为，继续L1
            return None
        
        # 冲击力足够，允许下放到L2
        return "L2_REQUIRED"

    def _get_default_routine(self, current_hour: int) -> NPCAction:
        """根据小时数返回默认作息"""
        # 简化的日程：这里应该从人物卡读取详细日程
        if 22 <= current_hour or current_hour < 6:
            return NPCAction.SLEEP
        elif 6 <= current_hour < 7:
            return NPCAction.EAT
        elif 7 <= current_hour < 12:
            return NPCAction.WORK
        elif 12 <= current_hour < 13:
            return NPCAction.EAT
        elif 13 <= current_hour < 18:
            return NPCAction.WORK
        elif 18 <= current_hour < 19:
            return NPCAction.EAT
        else:
            return NPCAction.REST

    def assess_duration(self, 
                       action_start_time: datetime,
                       current_time: datetime) -> float:
        """评估当前行为的持续时间"""
        if not action_start_time:
            return 0.0
        duration_minutes = (current_time - action_start_time).total_seconds() / 60
        return duration_minutes


class L2FastFilter:
    """
    L2 决策层 - 事件重要性智能快速过滤
    使用高速LLM模式（few tokens）判断事件重要性
    特点：快速判决，仅消耗少量token
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def assess_event_importance(self,
                               event_content: str,
                               npc_personality: Dict[str, Any],
                               max_tokens: int = 50) -> Tuple[bool, float]:
        """
        快速过滤：判断事件是否足够重要以推进L3
        
        Args:
            event_content: 事件描述
            npc_personality: NPC人格特征
            max_tokens: 最大输出token数（保证快速）
        
        Returns:
            (is_important, urgency_score)
        """
        
        prompt = f"""你是{npc_personality.get('name', 'NPC')}，一个{npc_personality.get('profession', '村民')}。
你的性格特征：{json.dumps(npc_personality.get('traits', []))}

刚刚发生了这个事件：
{event_content}

快速判断：这个事件是否会威胁你的安全、改变长期目标或触发强烈情感？
只需回答 YES 或 NO，然后给出紧急度评分（1-10）。

格式：YES/NO, 紧急度: X"""

        try:
            # 使用fast模式加速
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                model="deepseek-chat",
                max_tokens=max_tokens,
                temperature=0.3  # 较低温度保证一致性
            )
            
            # 解析响应
            text = response.strip().lower()
            is_important = "yes" in text
            
            # 提取紧急度分数
            import re
            score_match = re.search(r'紧急度:\s*(\d+)', text)
            urgency = float(score_match.group(1)) / 10 if score_match else 0.5
            
            return is_important, urgency
        
        except Exception as e:
            logger.error(f"L2 Filter error: {e}")
            # 默认认为重要
            return True, 0.5


class L3StrategyPlanning:
    """
    L3 决策层 - 战略蓝图规划
    在启动复杂推理前进行高维思考，生成行动蓝图
    防止ReAct跑题，加快L4执行
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate_strategy_blueprint(self,
                                   event_content: str,
                                   npc_profile: Dict[str, Any],
                                   current_context: Dict[str, Any],
                                   max_tokens: int = 200) -> Dict[str, Any]:
        """
        生成行动蓝图
        
        Returns:
            {
                "ultimate_goal": str,
                "key_steps": List[str],
                "predicted_risks": List[str],
                "resource_needs": List[str],
                "recommended_reasoning_depth": str  # shallow, moderate, deep
            }
        """

        prompt = f"""你是 {npc_profile.get('name', 'NPC')}。

当前情况：
{event_content}

你的核心价值观：{json.dumps(npc_profile.get('values', []))}
当前目标：{current_context.get('primary_goal', '未知')}

请生成一个简洁的行动蓝图：
1. 最终目标（一句话）：
2. 关键步骤（最多3个）：
   - 步骤1
   - 步骤2
   - 步骤3
3. 预期的主要风险：
   - 风险1
   - 风险2

直接回答，不需要额外解释。"""

        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.5
            )
            
            # 解析蓝图
            blueprint = self._parse_blueprint(response, npc_profile)
            return blueprint
        
        except Exception as e:
            logger.error(f"L3 Strategy generation error: {e}")
            return {
                "ultimate_goal": "应对当前事件",
                "key_steps": ["观察局势", "评估选项", "采取行动"],
                "predicted_risks": ["不确定性"],
                "resource_needs": [],
                "recommended_reasoning_depth": "moderate"
            }

    def _parse_blueprint(self,
                        response: str,
                        npc_profile: Dict[str, Any]) -> Dict[str, Any]:
        """解析LLM生成的蓝图"""
        # 简化解析（实际应该更精细）
        lines = response.split('\n')
        
        return {
            "ultimate_goal": lines[0] if lines else "应对事件",
            "key_steps": [l.strip('- ') for l in lines[1:4] if l.strip().startswith('-')],
            "predicted_risks": [l.strip('- ') for l in lines[4:] if l.strip().startswith('-')],
            "resource_needs": [],
            "recommended_reasoning_depth": self._assess_complexity(response)
        }

    @staticmethod
    def _assess_complexity(response: str) -> str:
        """根据蓝图复杂度判断推理深度"""
        # 简化逻辑
        word_count = len(response.split())
        if word_count < 50:
            return "shallow"
        elif word_count < 150:
            return "moderate"
        else:
            return "deep"


class L4ToTReactReasoning:
    """
    L4 决策层 - Tree of Thoughts 增强型 ReAct 推理
    处理复杂决策：分叉、评估、自纠错
    """

    def __init__(self, llm_client, tool_registry):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_iterations = 5

    def solve_with_tot(self,
                       problem: str,
                       blueprint: Dict[str, Any],
                       npc_profile: Dict[str, Any],
                       current_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用Tree of Thoughts进行多路径推理
        
        Returns:
            {
                "chosen_path": int,
                "reasoning_log": List[Dict],
                "final_action": str,
                "success_score": float
            }
        """
        
        # 第一步：生成候选路径
        paths = self._generate_candidate_paths(problem, blueprint, npc_profile)
        
        # 第二步：为每条路径进行沙箱模拟评估
        evaluated_paths = []
        for path_id, path in enumerate(paths):
            simulation_result = self._simulate_path(
                path, 
                npc_profile, 
                current_context
            )
            evaluated_paths.append({
                "path_id": path_id,
                "steps": path["steps"],
                "predicted_outcome": simulation_result["outcome"],
                "success_probability": simulation_result["success_prob"],
                "risk_level": simulation_result["risk_level"]
            })
        
        # 第三步：选择最优路径
        best_path = max(evaluated_paths, 
                       key=lambda x: x["success_probability"])
        
        # 第四步：执行选中路径并收集反馈
        execution_log = self._execute_path_with_feedback(
            best_path,
            npc_profile
        )
        
        return {
            "chosen_path": best_path["path_id"],
            "evaluated_paths_count": len(evaluated_paths),
            "reasoning_log": execution_log,
            "final_action": best_path["steps"][-1] if best_path["steps"] else "无",
            "success_score": best_path["success_probability"]
        }

    def _generate_candidate_paths(self,
                                  problem: str,
                                  blueprint: Dict[str, Any],
                                  npc_profile: Dict[str, Any]) -> List[Dict]:
        """生成2-3条候选路径"""
        
        prompt = f"""你是 {npc_profile.get('name', 'NPC')}，正面临这个问题：
{problem}

行动蓝图：{json.dumps(blueprint, ensure_ascii=False)}

生成2-3种不同的解决方案（每个方案包括具体步骤）。
格式：
方案1：[步骤1] -> [步骤2] -> [步骤3]
方案2：[步骤1] -> [步骤2] -> [步骤3]
...
"""
        
        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7
            )
            
            paths = self._parse_paths(response)
            return paths
        
        except Exception as e:
            logger.error(f"Path generation error: {e}")
            return [{
                "steps": ["采取保守行动"],
                "risk_level": "low"
            }]

    def _parse_paths(self, response: str) -> List[Dict]:
        """解析路径字符串"""
        # 简化实现
        return [
            {"steps": ["采取第一方案"], "risk_level": "medium"},
            {"steps": ["采取第二方案"], "risk_level": "low"}
        ]

    def _simulate_path(self,
                       path: Dict,
                       npc_profile: Dict[str, Any],
                       context: Dict[str, Any]) -> Dict[str, float]:
        """模拟路径执行的后果"""
        # 基于NPC特性和环境进行评估
        return {
            "outcome": "positive",
            "success_prob": 0.7,
            "risk_level": 0.3
        }

    def _execute_path_with_feedback(self,
                                     path: Dict,
                                     npc_profile: Dict[str, Any]) -> List[Dict]:
        """执行路径并收集反馈"""
        return [
            {"step": "执行", "result": "成功", "next_step": "继续"}
        ]


class FourLevelDecisionMaker:
    """
    四级决策系统主控制器
    协调所有四层，管理决策流程
    """

    def __init__(self,
                 npc_config: Dict[str, Any],
                 llm_client,
                 tool_registry,
                 embedding_model=None):
        self.npc_config = npc_config
        
        self.l1 = L1RoutineDecision(npc_config)
        self.l2 = L2FastFilter(llm_client)
        self.l3 = L3StrategyPlanning(llm_client)
        self.l4 = L4ToTReactReasoning(llm_client, tool_registry)
        
        # 决策统计
        self.decision_stats = {
            "l1_decisions": 0,
            "l2_decisions": 0,
            "l3_decisions": 0,
            "l4_decisions": 0
        }

    def make_decision(self,
                      event: Optional[Dict[str, Any]],
                      current_state: Dict[str, Any],
                      latest_impact_score: int) -> Dict[str, Any]:
        """
        多层决策流程
        
        Returns:
            {
                "decision_level": DecisionLevel,
                "action": NPCAction,
                "reasoning": str,
                "confidence": float
            }
        """
        
        # L1：生物钟硬判决
        l1_result = self.l1.decide(
            current_action=current_state.get("current_action"),
            current_hour=current_state.get("current_hour", 12),
            energy_level=current_state.get("energy_level", 0.5),
            hunger_level=current_state.get("hunger_level", 0.3),
            fatigue_level=current_state.get("fatigue_level", 0.2),
            latest_impact_score=latest_impact_score
        )
        
        if l1_result != "L2_REQUIRED" and l1_result is not None:
            self.decision_stats["l1_decisions"] += 1
            return {
                "decision_level": DecisionLevel.L1_ROUTINE,
                "action": l1_result,
                "reasoning": "遵循生物钟作息",
                "confidence": 0.95
            }
        
        # 如果没有事件，返回L1决策
        if event is None:
            self.decision_stats["l1_decisions"] += 1
            return {
                "decision_level": DecisionLevel.L1_ROUTINE,
                "action": self.l1._get_default_routine(
                    current_state.get("current_hour", 12)
                ),
                "reasoning": "无外部事件，遵循日程",
                "confidence": 0.85
            }
        
        # L2：快速重要性过滤
        is_important, urgency = self.l2.assess_event_importance(
            event.get("content", ""),
            self.npc_config
        )
        
        if not is_important:
            self.decision_stats["l2_decisions"] += 1
            return {
                "decision_level": DecisionLevel.L2_FILTER,
                "action": current_state.get("current_action", NPCAction.REST),
                "reasoning": f"事件不重要（紧急度：{urgency}），继续当前行为",
                "confidence": 0.7
            }
        
        # L3：战略蓝图规划
        blueprint = self.l3.generate_strategy_blueprint(
            event.get("content", ""),
            self.npc_config,
            current_state
        )
        
        self.decision_stats["l3_decisions"] += 1
        
        # L4：深度推理（仅在关键情况）
        if urgency > 0.7 or latest_impact_score > 70:
            result = self.l4.solve_with_tot(
                problem=event.get("content", ""),
                blueprint=blueprint,
                npc_profile=self.npc_config,
                current_context=current_state
            )
            
            self.decision_stats["l4_decisions"] += 1
            
            return {
                "decision_level": DecisionLevel.L4_DEEP_REASONING,
                "action": result.get("final_action", NPCAction.REST),
                "reasoning": f"深度推理（路径{result.get('chosen_path')}）",
                "confidence": result.get("success_score", 0.6)
            }
        
        # 返回L3规划的行动
        return {
            "decision_level": DecisionLevel.L3_STRATEGY,
            "action": blueprint.get("key_steps", ["采取行动"])[0],
            "reasoning": blueprint.get("ultimate_goal", ""),
            "confidence": 0.75
        }

    def get_decision_stats(self) -> Dict[str, int]:
        """获取决策统计信息"""
        total = sum(self.decision_stats.values())
        if total == 0:
            return self.decision_stats
        
        return {
            **self.decision_stats,
            "l1_percentage": f"{100 * self.decision_stats['l1_decisions'] / total:.1f}%",
            "l2_percentage": f"{100 * self.decision_stats['l2_decisions'] / total:.1f}%",
            "l3_percentage": f"{100 * self.decision_stats['l3_decisions'] / total:.1f}%",
            "l4_percentage": f"{100 * self.decision_stats['l4_decisions'] / total:.1f}%"
        }
