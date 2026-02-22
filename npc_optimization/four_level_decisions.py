"""
四级决策混合架构 (4-Level Decision Architecture)
按需分配算力：80%琐事 L1，15%常规 L2-L3，5%关键 L4
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
from core_types import NPCAction, ACTIVITY_INERTIA

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


def map_step_to_action(step_text: str) -> NPCAction:
    """
    将LLM生成的规划步骤文本映射为具体的NPCAction

    Args:
        step_text: 规划步骤文本，如 "先确认情况"、"通知大家"

    Returns:
        对应的NPCAction枚举值
    """
    if not isinstance(step_text, str):
        # 如果已经是NPCAction，直接返回
        if isinstance(step_text, NPCAction):
            return step_text
        return NPCAction.OBSERVE

    step_lower = step_text.lower()

    # 通知/告诉相关 -> 社交行为
    if any(kw in step_lower for kw in ['通知', '告诉', '告知', '呼叫', '喊', '传达', '报告', '汇报']):
        return NPCAction.SOCIALIZE

    # 帮助/救援相关 -> 帮助他人
    if any(kw in step_lower for kw in ['帮助', '救援', '支援', '协助', '救火', '灭火', '救人', '施救']):
        return NPCAction.HELP_OTHERS

    # 确认/观察相关 -> 观察
    if any(kw in step_lower for kw in ['确认', '观察', '查看', '检查', '了解', '查明', '调查', '看看']):
        return NPCAction.OBSERVE

    # 移动/前往相关 -> 旅行
    if any(kw in step_lower for kw in ['前往', '去', '移动', '赶到', '跑向', '走向', '赶往']):
        return NPCAction.TRAVEL

    # 祈祷/祝福相关 -> 祈祷
    if any(kw in step_lower for kw in ['祈祷', '祝福', '祈求', '祷告']):
        return NPCAction.PRAY

    # 思考/考虑相关 -> 思考
    if any(kw in step_lower for kw in ['思考', '考虑', '分析', '判断', '决定']):
        return NPCAction.THINK

    # 休息相关 -> 休息
    if any(kw in step_lower for kw in ['休息', '停下', '等待']):
        return NPCAction.REST

    # 工作相关 -> 工作
    if any(kw in step_lower for kw in ['工作', '干活', '劳动', '打铁', '酿酒']):
        return NPCAction.WORK

    # 组织/领导相关 -> 社交（组织活动）
    if any(kw in step_lower for kw in ['组织', '召集', '领导', '安排', '指挥']):
        return NPCAction.SOCIALIZE

    # 安全/保护相关 -> 帮助他人
    if any(kw in step_lower for kw in ['保护', '安全', '疏散', '撤离']):
        return NPCAction.HELP_OTHERS

    # 默认返回观察
    return NPCAction.OBSERVE


class L1RoutineDecision:
    """
    L1 决策层 - 生理与生物钟硬判决
    处理日常作息：睡眠、吃饭、工作循环等
    特点：零LLM调用，委托BehaviorDecisionTree从人物卡读取作息规则
    """

    def __init__(self, npc_config: Dict[str, Any], behavior_tree=None):
        self.config = npc_config
        self.current_activity: Optional[NPCAction] = None
        self.action_start_time: Optional[datetime] = None
        # 委托BehaviorDecisionTree读取人物卡作息规则（避免硬编码）
        self.behavior_tree = behavior_tree

    def decide(self,
               current_activity: Optional[NPCAction],
               current_hour: int,
               energy_level: float,
               hunger_level: float,
               fatigue_level: float,
               latest_impact_score: int) -> Optional[NPCAction]:
        """
        硬判决逻辑：根据生物钟和惯性值决定是否继续当前行为

        Returns:
            NPCAction if 需要改变行为，None if 继续执行L1，"L2_REQUIRED" if 需要L2
        """

        # 强制睡眠检查（最高优先）
        if fatigue_level > 0.98:
            return NPCAction.SLEEP

        # 强制进食检查
        if hunger_level > 0.9:
            return NPCAction.EAT

        # 如果没有当前行为，返回默认作息
        if current_activity is None:
            return self._get_default_routine(
                current_hour, energy_level, hunger_level, fatigue_level
            )

        # 检查事件冲击力是否超过当前行为的惯性
        current_inertia = ACTIVITY_INERTIA.get(current_activity, 50)

        if latest_impact_score < current_inertia:
            # 冲击力不足以打断当前行为，继续L1
            return None

        # 冲击力足够，允许下放到L2
        return "L2_REQUIRED"

    def _get_default_routine(self, current_hour: int,
                             energy_level: float = 0.5,
                             hunger_level: float = 0.3,
                             fatigue_level: float = 0.2) -> NPCAction:
        """从BehaviorDecisionTree获取默认作息，降级为内置规则"""
        # 优先委托BehaviorDecisionTree（从人物卡读取）
        if self.behavior_tree is not None:
            needs = {
                "hunger": hunger_level,
                "fatigue": fatigue_level,
                "social": 0.0
            }
            # energy_level 在 BehaviorDecisionTree 使用 0-100 整数
            energy_int = int(energy_level * 100)
            tree_action = self.behavior_tree.decide_routine_behavior(
                current_hour=current_hour,
                energy_level=energy_int,
                needs=needs,
                current_task=None
            )
            if tree_action is not None:
                return tree_action

        # 降级：内置简化规则（无人物卡时兜底）
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
    先使用本地规则预过滤，命中规则直接跳过LLM调用；
    仅未命中规则的事件才进入高速LLM判断（50 tokens）。
    """

    # 本地规则：匹配这些关键词的事件直接判为不重要，跳过LLM
    _IGNORE_KEYWORDS = frozenset([
        "天气", "日出", "日落", "黎明", "黄昏", "起风", "下雨",
        "鸟叫", "虫鸣", "云朵", "时间流逝", "太阳", "月亮", "星星"
    ])

    def __init__(self, llm_client):
        self.llm_client = llm_client
        # 记录最近处理的事件类型及时间，用于重复检测
        self._recent_event_types: Dict[str, datetime] = {}
        # 同类型事件冷却时间（分钟），冷却内重复出现直接跳过
        self._cooldown_minutes = 10

    def _is_trivial_by_rules(self, event_content: str, event_type: str = "") -> bool:
        """本地规则预过滤，返回 True 表示该事件为琐事可直接跳过"""
        content_lower = event_content.lower()

        # 规则1：关键词命中忽略列表
        if any(kw in content_lower for kw in self._IGNORE_KEYWORDS):
            return True

        # 规则2：同类型事件在冷却时间内重复出现
        if event_type:
            last_time = self._recent_event_types.get(event_type)
            if last_time is not None:
                elapsed = (datetime.now() - last_time).total_seconds() / 60
                if elapsed < self._cooldown_minutes:
                    return True
            # 更新最近处理时间
            self._recent_event_types[event_type] = datetime.now()

        return False

    def assess_event_importance(self,
                               event_content: str,
                               npc_personality: Dict[str, Any],
                               max_tokens: int = 50,
                               event_type: str = "") -> Tuple[bool, float]:
        """
        快速过滤：判断事件是否足够重要以推进L3

        Returns:
            (is_important, urgency_score)
        """
        # 本地规则预过滤（零LLM调用）
        if self._is_trivial_by_rules(event_content, event_type):
            return False, 0.1

        prompt = f"""你是{npc_personality.get('name', 'NPC')}，一个{npc_personality.get('profession', '村民')}。
你的性格特征：{json.dumps(npc_personality.get('traits', []))}

刚刚发生了这个事件：
{event_content}

快速判断：这个事件是否会威胁你的安全、改变长期目标或触发强烈情感？
只需回答 YES 或 NO，然后给出紧急度评分（1-10）。

格式：YES/NO, 紧急度: X"""

        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                model="deepseek-chat",
                max_tokens=max_tokens,
                temperature=0.3
            )

            text = response.strip().lower()
            is_important = "yes" in text

            import re
            score_match = re.search(r'紧急度:\s*(\d+)', text)
            urgency = float(score_match.group(1)) / 10 if score_match else 0.5

            return is_important, urgency

        except Exception as e:
            logger.error(f"L2 Filter error: {e}")
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
                                   max_tokens: int = 250) -> Dict[str, Any]:
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
        # 获取对话历史和记忆上下文
        dialogue_context = current_context.get('dialogue_history', '')
        recent_memory = current_context.get('recent_memory', '')

        prompt = f"""你是 {npc_profile.get('name', 'NPC')}。

当前情况：
{event_content}

你的核心价值观：{json.dumps(npc_profile.get('values', []), ensure_ascii=False)}
当前目标：{current_context.get('primary_goal', '未知')}
{f"最近对话历史：{chr(10)}{dialogue_context}" if dialogue_context else ""}
{f"相关记忆：{recent_memory}" if recent_memory else ""}

请生成行动蓝图，使用JSON格式返回：
{{
    "ultimate_goal": "最终目标（一句话）",
    "key_steps": ["步骤1", "步骤2", "步骤3"],
    "predicted_risks": ["风险1", "风险2"],
    "resource_needs": ["需要的资源或帮助"],
    "reasoning_depth": "shallow/moderate/deep"
}}

只返回JSON对象，不要其他内容。
"""

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
        import re

        default_blueprint = {
            "ultimate_goal": "应对事件",
            "key_steps": ["观察局势", "评估选项", "采取行动"],
            "predicted_risks": ["不确定性"],
            "resource_needs": [],
            "recommended_reasoning_depth": "moderate"
        }

        try:
            # 清理响应文本
            cleaned = response.strip()

            # 尝试直接解析JSON
            if cleaned.startswith('{'):
                blueprint = json.loads(cleaned)
                return self._validate_blueprint(blueprint)

            # 尝试从文本中提取JSON对象
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                blueprint = json.loads(json_match.group())
                return self._validate_blueprint(blueprint)

            # JSON解析失败，尝试文本解析
            return self._parse_text_blueprint(response)

        except json.JSONDecodeError as e:
            logger.warning(f"蓝图JSON解析失败: {e}，尝试文本解析")
            return self._parse_text_blueprint(response)

    def _validate_blueprint(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """验证和规范化蓝图数据"""
        validated = {
            "ultimate_goal": blueprint.get("ultimate_goal", "应对事件"),
            "key_steps": blueprint.get("key_steps", ["采取行动"]),
            "predicted_risks": blueprint.get("predicted_risks", []),
            "resource_needs": blueprint.get("resource_needs", []),
            "recommended_reasoning_depth": blueprint.get("reasoning_depth",
                                                         blueprint.get("recommended_reasoning_depth", "moderate"))
        }

        # 确保列表类型
        if isinstance(validated["key_steps"], str):
            validated["key_steps"] = [validated["key_steps"]]
        if isinstance(validated["predicted_risks"], str):
            validated["predicted_risks"] = [validated["predicted_risks"]]
        if isinstance(validated["resource_needs"], str):
            validated["resource_needs"] = [validated["resource_needs"]]

        # 限制步骤数量
        validated["key_steps"] = validated["key_steps"][:5]
        validated["predicted_risks"] = validated["predicted_risks"][:3]

        return validated

    def _parse_text_blueprint(self, response: str) -> Dict[str, Any]:
        """解析文本格式的蓝图（降级方案）"""
        import re

        lines = response.strip().split('\n')
        blueprint = {
            "ultimate_goal": "",
            "key_steps": [],
            "predicted_risks": [],
            "resource_needs": [],
            "recommended_reasoning_depth": "moderate"
        }

        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测章节标题
            if '目标' in line or '最终' in line:
                current_section = 'goal'
                # 尝试提取同一行的内容
                match = re.search(r'[：:]\s*(.+)$', line)
                if match:
                    blueprint["ultimate_goal"] = match.group(1).strip()
                continue
            elif '步骤' in line or '关键' in line:
                current_section = 'steps'
                continue
            elif '风险' in line:
                current_section = 'risks'
                continue
            elif '资源' in line or '需要' in line:
                current_section = 'resources'
                continue

            # 提取列表项
            item_match = re.match(r'^[-•·*\d.]+\s*(.+)$', line)
            if item_match:
                item = item_match.group(1).strip()
            else:
                item = line

            if current_section == 'goal' and not blueprint["ultimate_goal"]:
                blueprint["ultimate_goal"] = item
            elif current_section == 'steps':
                blueprint["key_steps"].append(item)
            elif current_section == 'risks':
                blueprint["predicted_risks"].append(item)
            elif current_section == 'resources':
                blueprint["resource_needs"].append(item)

        # 如果没有解析到目标，使用第一行
        if not blueprint["ultimate_goal"] and lines:
            blueprint["ultimate_goal"] = lines[0].strip()

        # 确保至少有一个步骤
        if not blueprint["key_steps"]:
            blueprint["key_steps"] = ["采取行动"]

        # 评估复杂度
        blueprint["recommended_reasoning_depth"] = self._assess_complexity_from_content(blueprint)

        return blueprint

    def _assess_complexity_from_content(self, blueprint: Dict[str, Any]) -> str:
        """根据蓝图内容评估推理深度"""
        steps_count = len(blueprint.get("key_steps", []))
        risks_count = len(blueprint.get("predicted_risks", []))

        total_complexity = steps_count + risks_count

        if total_complexity <= 2:
            return "shallow"
        elif total_complexity <= 5:
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

请生成2-3种不同的解决方案。使用JSON数组格式返回：
[
    {{"path_id": 1, "steps": ["步骤1描述", "步骤2描述", "步骤3描述"], "risk_level": "low/medium/high", "rationale": "选择理由"}},
    {{"path_id": 2, "steps": ["步骤1描述", "步骤2描述"], "risk_level": "low/medium/high", "rationale": "选择理由"}}
]

只返回JSON数组，不要其他内容。
"""

        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
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
        """解析LLM返回的路径JSON"""
        import re

        # 尝试提取JSON数组
        try:
            # 清理响应文本
            cleaned = response.strip()

            # 尝试直接解析
            if cleaned.startswith('['):
                paths = json.loads(cleaned)
                return self._validate_paths(paths)

            # 尝试从文本中提取JSON数组
            json_match = re.search(r'\[[\s\S]*?\]', cleaned)
            if json_match:
                paths = json.loads(json_match.group())
                return self._validate_paths(paths)

            # 如果无法解析JSON，尝试解析文本格式
            return self._parse_text_paths(response)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}，尝试文本解析")
            return self._parse_text_paths(response)

    def _validate_paths(self, paths: List[Dict]) -> List[Dict]:
        """验证和规范化路径数据"""
        validated = []
        for i, path in enumerate(paths):
            validated_path = {
                "path_id": path.get("path_id", i + 1),
                "steps": path.get("steps", ["采取行动"]),
                "risk_level": path.get("risk_level", "medium"),
                "rationale": path.get("rationale", "")
            }
            # 确保steps是列表
            if isinstance(validated_path["steps"], str):
                validated_path["steps"] = [validated_path["steps"]]
            validated.append(validated_path)

        return validated if validated else [{"steps": ["采取保守行动"], "risk_level": "low"}]

    def _parse_text_paths(self, response: str) -> List[Dict]:
        """解析文本格式的路径（降级方案）"""
        import re
        paths = []
        lines = response.strip().split('\n')

        current_path = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 匹配 "方案1：" 或 "方案 1:" 等格式
            path_match = re.match(r'方案\s*(\d+)[：:]\s*(.*)', line)
            if path_match:
                if current_path:
                    paths.append(current_path)
                path_id = int(path_match.group(1))
                content = path_match.group(2)

                # 解析步骤（使用 -> 或 → 分隔）
                steps = re.split(r'\s*[-→>]+\s*', content)
                steps = [s.strip('[] ') for s in steps if s.strip()]

                current_path = {
                    "path_id": path_id,
                    "steps": steps if steps else ["采取行动"],
                    "risk_level": "medium"
                }

        if current_path:
            paths.append(current_path)

        return paths if paths else [{"steps": ["采取保守行动"], "risk_level": "low"}]

    def _simulate_path(self,
                       path: Dict,
                       npc_profile: Dict[str, Any],
                       context: Dict[str, Any]) -> Dict[str, float]:
        """
        模拟路径执行的后果

        基于以下因素计算成功概率和风险：
        1. NPC技能匹配度 (skill_bonus: 0-0.3)
        2. 路径复杂度惩罚 (complexity_penalty: 0-0.2)
        3. 环境风险因素 (env_risk: 0-0.4)
        4. 历史经验加成 (history_bonus: 0-0.2)
        5. 情绪状态影响 (emotion_modifier: -0.1 to 0.1)

        Returns:
            包含outcome, success_prob, risk_level的字典
        """
        # 基础成功概率
        base_prob = 0.5

        # 1. 计算技能匹配度 (0-0.3)
        skill_bonus = self._calculate_skill_match(path, npc_profile)

        # 2. 计算路径复杂度惩罚 (0-0.2)
        steps = path.get("steps", [])
        step_count = len(steps)
        # 每个步骤约 0.03-0.05 惩罚，最大0.2
        complexity_penalty = min(step_count * 0.04, 0.2)

        # 3. 评估环境风险 (0-0.4)
        env_risk = self._assess_environment_risk(context)

        # 4. 检查历史经验加成 (0-0.2)
        history_bonus = self._check_similar_history(path, npc_profile)

        # 5. 获取情绪状态影响 (-0.1 to 0.1)
        emotion_modifier = self._get_emotion_modifier(context)

        # 计算最终成功概率
        success_prob = (base_prob + skill_bonus - complexity_penalty
                        - env_risk + history_bonus + emotion_modifier)

        # 确保 success_prob 在 0.1-0.95 范围内
        success_prob = max(0.1, min(0.95, success_prob))

        # 计算风险等级
        risk_level = env_risk + complexity_penalty * 0.5
        # 确保 risk_level 在 0.0-0.8 范围内
        risk_level = max(0.0, min(0.8, risk_level))

        # 根据成功概率确定结果类型
        if success_prob >= 0.7:
            outcome = "positive"
        elif success_prob >= 0.4:
            outcome = "neutral"
        else:
            outcome = "negative"

        return {
            "outcome": outcome,
            "success_prob": round(success_prob, 3),
            "risk_level": round(risk_level, 3)
        }

    def _calculate_skill_match(self,
                               path: Dict,
                               npc_profile: Dict[str, Any]) -> float:
        """
        计算NPC技能与路径需求的匹配度

        Args:
            path: 包含steps的路径字典
            npc_profile: NPC配置文件

        Returns:
            技能加成值 (0-0.3)
        """
        skill_bonus = 0.0

        # 获取NPC技能列表
        npc_skills = npc_profile.get("skills", [])
        profession = npc_profile.get("profession", "").lower()

        # 如果skills是字典，提取技能名称
        if isinstance(npc_skills, dict):
            npc_skills = list(npc_skills.keys())
        elif isinstance(npc_skills, str):
            npc_skills = [npc_skills]

        # 技能关键词映射
        skill_keywords = {
            "铁匠": ["打铁", "锻造", "火", "灭火", "金属", "修理", "武器"],
            "牧师": ["祈祷", "祝福", "治疗", "安慰", "神圣", "驱邪"],
            "猎人": ["追踪", "狩猎", "观察", "射击", "陷阱", "野外"],
            "医生": ["治疗", "医疗", "诊断", "急救", "药物"],
            "商人": ["交易", "谈判", "说服", "评估", "买卖"],
            "农民": ["耕种", "收割", "养殖", "农活", "种植"],
            "守卫": ["巡逻", "保护", "战斗", "警戒", "追捕"],
            "工匠": ["制作", "修理", "建造", "雕刻"]
        }

        # 获取步骤文本
        steps = path.get("steps", [])
        steps_text = " ".join(str(s) for s in steps).lower()

        # 检查职业技能匹配
        profession_keywords = skill_keywords.get(profession, [])
        for keyword in profession_keywords:
            if keyword in steps_text:
                skill_bonus += 0.1
                break

        # 检查具体技能匹配
        for skill in npc_skills:
            skill_str = str(skill).lower()
            if skill_str in steps_text:
                skill_bonus += 0.1

        # 特殊情况：铁匠处理火灾有额外加成
        if profession == "铁匠" and any(kw in steps_text for kw in ["火", "灭火", "火灾", "救火"]):
            skill_bonus += 0.1

        # 限制最大值为0.3
        return min(skill_bonus, 0.3)

    def _assess_environment_risk(self, context: Dict[str, Any]) -> float:
        """
        评估环境风险因素

        考虑因素：
        - 当前时间（夜间增加风险）
        - 天气条件
        - 危险事件类型
        - 位置危险性

        Args:
            context: 当前上下文信息

        Returns:
            环境风险值 (0-0.4)
        """
        env_risk = 0.0

        # 时间风险：夜间增加风险
        current_hour = context.get("current_hour", 12)
        if current_hour is not None:
            if 22 <= current_hour or current_hour < 6:
                # 深夜
                env_risk += 0.15
            elif 19 <= current_hour < 22 or 6 <= current_hour < 8:
                # 傍晚或清晨
                env_risk += 0.05

        # 天气风险
        weather = context.get("weather", "晴").lower()
        weather_risk_map = {
            "暴风雨": 0.15,
            "暴雨": 0.12,
            "大雨": 0.1,
            "雨": 0.05,
            "雪": 0.08,
            "大雪": 0.12,
            "雾": 0.08,
            "大风": 0.06,
            "晴": 0.0,
            "多云": 0.0
        }
        for weather_type, risk in weather_risk_map.items():
            if weather_type in weather:
                env_risk += risk
                break

        # 事件类型风险
        event_type = context.get("event_type", "").lower()
        dangerous_events = {
            "火灾": 0.2,
            "袭击": 0.25,
            "战斗": 0.2,
            "怪物": 0.25,
            "洪水": 0.15,
            "地震": 0.2,
            "瘟疫": 0.15,
            "盗贼": 0.15,
            "紧急": 0.1
        }
        for event, risk in dangerous_events.items():
            if event in event_type:
                env_risk += risk
                break

        # 位置风险
        location = context.get("current_location", "").lower()
        dangerous_locations = ["森林", "洞穴", "废墟", "矿井", "沼泽", "墓地"]
        if any(loc in location for loc in dangerous_locations):
            env_risk += 0.1

        # 限制最大值为0.4
        return min(env_risk, 0.4)

    def _check_similar_history(self,
                               path: Dict,
                               npc_profile: Dict[str, Any]) -> float:
        """
        检查NPC是否有类似任务的成功历史

        Args:
            path: 当前路径
            npc_profile: NPC配置文件

        Returns:
            历史经验加成 (0-0.2)
        """
        history_bonus = 0.0

        # 获取历史经验记录
        history = npc_profile.get("history", [])
        experiences = npc_profile.get("experiences", [])
        memory = npc_profile.get("memory", {})

        # 合并所有历史来源
        all_history = []
        if isinstance(history, list):
            all_history.extend(history)
        if isinstance(experiences, list):
            all_history.extend(experiences)
        if isinstance(memory, dict):
            past_events = memory.get("past_events", [])
            if isinstance(past_events, list):
                all_history.extend(past_events)

        # 获取当前路径的关键词
        steps = path.get("steps", [])
        steps_text = " ".join(str(s) for s in steps).lower()

        # 提取关键动作词
        action_keywords = ["帮助", "救援", "灭火", "保护", "治疗", "交易",
                          "谈判", "战斗", "逃跑", "通知", "组织"]

        current_actions = [kw for kw in action_keywords if kw in steps_text]

        # 检查历史中是否有类似成功经验
        for record in all_history:
            record_str = str(record).lower()

            # 检查是否是成功经验
            is_success = any(word in record_str for word in ["成功", "完成", "胜利", "解决"])

            if is_success:
                # 检查是否有匹配的动作
                for action in current_actions:
                    if action in record_str:
                        history_bonus += 0.1
                        break

        # 检查技能熟练度
        skills = npc_profile.get("skills", {})
        if isinstance(skills, dict):
            for skill_name, skill_level in skills.items():
                skill_str = str(skill_name).lower()
                if skill_str in steps_text:
                    # 根据技能等级增加加成
                    if isinstance(skill_level, (int, float)):
                        if skill_level >= 80:
                            history_bonus += 0.1
                        elif skill_level >= 50:
                            history_bonus += 0.05

        # 限制最大值为0.2
        return min(history_bonus, 0.2)

    def _get_emotion_modifier(self, context: Dict[str, Any]) -> float:
        """
        获取情绪状态对成功率的影响

        正面情绪增加成功率，负面情绪降低成功率

        Args:
            context: 当前上下文信息

        Returns:
            情绪修正值 (-0.1 to 0.1)
        """
        # 获取当前情绪
        emotion = context.get("emotion", "").lower()
        mood = context.get("mood", "").lower()
        emotional_state = context.get("emotional_state", "").lower()

        # 合并情绪信息
        emotion_text = f"{emotion} {mood} {emotional_state}"

        # 正面情绪映射
        positive_emotions = {
            "平静": 0.05,
            "冷静": 0.05,
            "自信": 0.08,
            "兴奋": 0.06,
            "愉快": 0.05,
            "快乐": 0.05,
            "开心": 0.05,
            "热情": 0.06,
            "专注": 0.08,
            "决心": 0.07,
            "勇敢": 0.08
        }

        # 负面情绪映射
        negative_emotions = {
            "担心": -0.06,
            "焦虑": -0.07,
            "恐惧": -0.08,
            "害怕": -0.08,
            "疲惫": -0.08,
            "疲劳": -0.07,
            "沮丧": -0.06,
            "悲伤": -0.05,
            "愤怒": -0.04,  # 愤怒可能提供动力，惩罚较小
            "慌张": -0.1,
            "绝望": -0.1,
            "困惑": -0.05
        }

        modifier = 0.0

        # 检查正面情绪
        for emotion_name, bonus in positive_emotions.items():
            if emotion_name in emotion_text:
                modifier = max(modifier, bonus)

        # 检查负面情绪（取最大惩罚）
        for emotion_name, penalty in negative_emotions.items():
            if emotion_name in emotion_text:
                modifier = min(modifier, penalty)

        # 确保在 -0.1 到 0.1 范围内
        return max(-0.1, min(0.1, modifier))

    def _execute_path_with_feedback(self,
                                     path: Dict,
                                     npc_profile: Dict[str, Any]) -> List[Dict]:
        """执行路径并收集真实反馈，结果写入决策统计并触发记忆记录"""
        steps = path.get("steps", [])
        results = []

        for step in steps:
            action = step.get("action", "")
            expected = step.get("expected_outcome", "")

            prompt = f"""你是{npc_profile.get('name', 'NPC')}。
你刚刚执行了以下行动：{action}
预期结果：{expected}

请简短评估这个行动是否成功（1-2句话），并给出成功率（0-100）。
格式：[评估内容] 成功率: XX"""

            try:
                response = self.llm_client.call_model(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=80,
                    temperature=0.4
                )
                import re
                score_match = re.search(r'成功率:\s*(\d+)', response)
                success_rate = int(score_match.group(1)) / 100 if score_match else 0.5
                success = success_rate >= 0.5

                results.append({
                    "step": action,
                    "result": response.split("成功率:")[0].strip(),
                    "success": success,
                    "success_rate": success_rate,
                    "next_step": steps[steps.index(step) + 1].get("action", "完成") if steps.index(step) + 1 < len(steps) else "完成"
                })
            except Exception as e:
                logger.warning(f"路径步骤评估失败: {e}")
                results.append({"step": action, "result": "执行", "success": True, "success_rate": 0.5, "next_step": "继续"})

        return results


class FourLevelDecisionMaker:
    """
    四级决策系统主控制器
    协调所有四层，管理决策流程
    支持ReAct工具调用执行决策
    """

    def __init__(self,
                 npc_config: Dict[str, Any],
                 llm_client,
                 tool_registry,
                 unified_tool_registry=None,
                 embedding_model=None,
                 behavior_tree=None):
        self.npc_config = npc_config
        self.llm_client = llm_client

        self.l1 = L1RoutineDecision(npc_config, behavior_tree=behavior_tree)
        self.l2 = L2FastFilter(llm_client)
        self.l3 = L3StrategyPlanning(llm_client)
        self.l4 = L4ToTReactReasoning(llm_client, tool_registry)

        # 统一工具注册表（用于ReAct执行）
        self.unified_tool_registry = unified_tool_registry

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
            current_activity=current_state.get("current_activity"),
            current_hour=current_state.get("current_hour", 12),
            energy_level=current_state.get("energy", 0.5),  # 使用新字段
            hunger_level=current_state.get("hunger", 0.3),  # 使用新字段
            fatigue_level=current_state.get("fatigue", 0.2),  # 使用新字段
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
                    current_state.get("current_hour", 12),
                    energy_level=current_state.get("energy", 0.5),
                    hunger_level=current_state.get("hunger", 0.3),
                    fatigue_level=current_state.get("fatigue", 0.2)
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
                "action": current_state.get("current_activity", NPCAction.REST),
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

            # 将L4的final_action映射为NPCAction
            final_action = result.get("final_action", NPCAction.REST)
            if isinstance(final_action, str):
                final_action = map_step_to_action(final_action)

            return {
                "decision_level": DecisionLevel.L4_DEEP_REASONING,
                "action": final_action,
                "reasoning": f"深度推理（路径{result.get('chosen_path')}）",
                "confidence": result.get("success_score", 0.6)
            }

        # 返回L3规划的行动
        # 获取第一个步骤并映射为NPCAction
        first_step = blueprint.get("key_steps", ["采取行动"])[0]
        mapped_action = map_step_to_action(first_step)

        return {
            "decision_level": DecisionLevel.L3_STRATEGY,
            "action": mapped_action,
            "reasoning": blueprint.get("ultimate_goal", ""),
            "original_step": first_step,  # 保留原始步骤文本用于日志
            "all_steps": blueprint.get("key_steps", []),  # 保留所有步骤
            "confidence": 0.75
        }

    def make_decision_with_react(self,
                                  event: Optional[Dict[str, Any]],
                                  current_state: Dict[str, Any],
                                  latest_impact_score: int,
                                  coordinator_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用ReAct模式进行决策并执行工具调用

        这是make_decision的增强版本，在L3/L4决策后会：
        1. 使用LLM选择合适的工具
        2. 执行工具调用
        3. 返回执行结果

        Args:
            event: 事件信息
            current_state: 当前NPC状态
            latest_impact_score: 事件影响度
            coordinator_context: 来自EventCoordinator的上下文（包含角色分配等）

        Returns:
            包含决策和执行结果的字典
        """
        # 先获取基础决策
        decision = self.make_decision(event, current_state, latest_impact_score)

        # 如果是L1/L2决策，不需要ReAct执行
        if decision["decision_level"] in [DecisionLevel.L1_ROUTINE, DecisionLevel.L2_FILTER]:
            return {
                **decision,
                "tool_executed": False,
                "tool_result": None,
                "react_reasoning": None
            }

        # L3/L4决策需要ReAct执行
        if not self.unified_tool_registry:
            logger.warning("未配置统一工具注册表，跳过ReAct执行")
            return {
                **decision,
                "tool_executed": False,
                "tool_result": None,
                "react_reasoning": "无工具注册表"
            }

        # 使用ReAct选择和执行工具
        react_result = self._react_execute(
            event=event,
            decision=decision,
            current_state=current_state,
            coordinator_context=coordinator_context
        )

        return {
            **decision,
            "tool_executed": react_result.get("executed", False),
            "tool_result": react_result.get("result"),
            "tool_name": react_result.get("tool_name"),
            "react_reasoning": react_result.get("reasoning"),
            "speech_content": react_result.get("speech_content")
        }

    def _react_execute(self,
                       event: Dict[str, Any],
                       decision: Dict[str, Any],
                       current_state: Dict[str, Any],
                       coordinator_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用ReAct模式执行工具调用

        Args:
            event: 事件信息
            decision: 四级决策结果
            current_state: 当前状态
            coordinator_context: 协调器上下文

        Returns:
            工具执行结果
        """
        from .unified_tools import get_unified_tools_prompt, parse_tool_call

        # 构建ReAct提示
        npc_name = self.npc_config.get("name", "NPC")
        profession = self.npc_config.get("profession", "村民")
        location = current_state.get("current_location", "未知")

        # 从协调器获取角色信息
        role = "observer"
        suggested_action = ""
        if coordinator_context:
            role = coordinator_context.get("role", "observer")
            suggested_action = coordinator_context.get("suggested_action", "")

        tools_prompt = get_unified_tools_prompt()

        prompt = f"""你是艾伦谷的NPC：{npc_name}（{profession}）

## 当前情况
- 你的位置：{location}
- 事件：{event.get('content', '无')}
- 事件位置：{event.get('location', '未知')}
- 你的角色：{role}
- 建议行动：{suggested_action}

## 四级决策系统的判断
- 决策级别：{decision.get('decision_level', '未知')}
- 推荐行动：{decision.get('action', '未知')}
- 推理过程：{decision.get('reasoning', '')}

{tools_prompt}

## 任务
根据上述信息，选择一个最合适的工具来执行你的行动。

请严格按照以下JSON格式回复：
```json
{{"tool": "工具名称", "参数1": "值1", "参数2": "值2"}}
```

同时，用一句简短的话描述你的行动（作为你说的话或动作描述）。

**回复格式：**
思考：[你的思考过程]
工具调用：
```json
{{"tool": "...", ...}}
```
行动描述：[你要说的话或做的动作]
"""

        try:
            # 调用LLM选择工具
            response = self.llm_client.generate_response(
                prompt=prompt,
                context={},
                temperature=0.7,
                max_tokens=300
            )

            # 解析工具调用
            tool_call = parse_tool_call(response)

            if not tool_call:
                logger.warning(f"无法解析工具调用: {response[:100]}...")
                return {
                    "executed": False,
                    "reasoning": "无法解析LLM响应中的工具调用",
                    "raw_response": response
                }

            tool_name = tool_call.pop("tool", None)
            if not tool_name:
                return {
                    "executed": False,
                    "reasoning": "工具调用中缺少tool字段"
                }

            # 提取行动描述（说话内容）
            speech_content = None
            if "行动描述：" in response:
                speech_start = response.find("行动描述：") + len("行动描述：")
                speech_content = response[speech_start:].strip().split("\n")[0]

            # 执行工具
            result = self.unified_tool_registry.execute_tool(tool_name, **tool_call)

            logger.info(f"NPC {npc_name} 执行工具 {tool_name}: {result.get('success', False)}")

            return {
                "executed": True,
                "tool_name": tool_name,
                "tool_params": tool_call,
                "result": result,
                "speech_content": speech_content,
                "reasoning": response[:200] if len(response) > 200 else response
            }

        except Exception as e:
            logger.error(f"ReAct执行失败: {e}")
            return {
                "executed": False,
                "reasoning": f"执行错误: {str(e)}"
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
