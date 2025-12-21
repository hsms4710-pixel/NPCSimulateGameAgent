"""
React Agent推理引擎
实现step-by-step的推理机制，用于复杂事件分析
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json

from deepseek_client import DeepSeekClient


class ReasoningMode(Enum):
    """推理模式"""
    FAST = "fast"          # 快速推理，1-2步
    NORMAL = "normal"      # 标准推理，3-5步
    DEEP = "deep"          # 深度推理，5-10步
    EXHAUSTIVE = "exhaustive"  # 穷尽推理，10+步


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_number: int
    thought: str          # 当前思考
    action: str          # 采取的行动
    observation: str     # 观察结果
    next_thought: str    # 下一思考方向
    confidence: float    # 置信度 0-1
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_number': self.step_number,
            'thought': self.thought,
            'action': self.action,
            'observation': self.observation,
            'next_thought': self.next_thought,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ReasoningResult:
    """推理结果"""
    final_answer: str
    reasoning_chain: List[ReasoningStep]
    total_steps: int
    total_confidence: float
    reasoning_time: float
    conclusion: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'final_answer': self.final_answer,
            'reasoning_chain': [step.to_dict() for step in self.reasoning_chain],
            'total_steps': self.total_steps,
            'total_confidence': self.total_confidence,
            'reasoning_time': self.reasoning_time,
            'conclusion': self.conclusion
        }


class ReactAgent:
    """React Agent推理引擎"""

    def __init__(self, deepseek_client: DeepSeekClient):
        self.llm_client = deepseek_client

    def reason_about_event(self,
                          npc_config: Dict[str, Any],
                          current_state: Dict[str, Any],
                          event_content: str,
                          event_type: str,
                          mode: ReasoningMode = ReasoningMode.NORMAL,
                          max_steps: Optional[int] = None) -> ReasoningResult:
        """
        对事件进行React Agent推理

        Args:
            npc_config: NPC配置
            current_state: 当前状态
            event_content: 事件内容
            event_type: 事件类型
            mode: 推理模式
            max_steps: 最大推理步数

        Returns:
            ReasoningResult: 推理结果
        """
        start_time = datetime.now()

        # 根据模式设置默认步数
        if max_steps is None:
            mode_steps = {
                ReasoningMode.FAST: 2,
                ReasoningMode.NORMAL: 5,
                ReasoningMode.DEEP: 8,
                ReasoningMode.EXHAUSTIVE: 15
            }
            max_steps = mode_steps.get(mode, 5)

        # 初始化推理链
        reasoning_chain = []

        # 第一步：观察事件
        initial_observation = self._initial_event_analysis(npc_config, current_state, event_content, event_type)
        initial_step = ReasoningStep(
            step_number=1,
            thought="观察到新事件发生",
            action="分析事件内容和影响",
            observation=initial_observation,
            next_thought="评估事件的潜在影响和我的反应",
            confidence=0.8,
            timestamp=datetime.now()
        )
        reasoning_chain.append(initial_step)

        # 后续推理步骤
        current_thought = initial_step.next_thought
        total_confidence = initial_step.confidence

        for step in range(2, max_steps + 1):
            # 生成下一步推理
            next_step = self._generate_reasoning_step(
                npc_config, current_state, event_content, event_type,
                reasoning_chain, current_thought, step
            )

            if next_step is None:
                break

            reasoning_chain.append(next_step)
            current_thought = next_step.next_thought
            total_confidence = (total_confidence + next_step.confidence) / 2

            # 检查是否达到结论
            if self._is_conclusion_reached(next_step):
                break

        # 生成最终结论
        final_answer = self._generate_final_answer(npc_config, current_state, reasoning_chain)
        conclusion = self._generate_conclusion(reasoning_chain)

        reasoning_time = (datetime.now() - start_time).total_seconds()

        return ReasoningResult(
            final_answer=final_answer,
            reasoning_chain=reasoning_chain,
            total_steps=len(reasoning_chain),
            total_confidence=total_confidence,
            reasoning_time=reasoning_time,
            conclusion=conclusion
        )

    def _initial_event_analysis(self, npc_config: Dict[str, Any],
                               current_state: Dict[str, Any],
                               event_content: str, event_type: str) -> str:
        """初始事件分析"""
        prompt = f"""
你是一个{ npc_config['name'] }，{ npc_config['profession'] }。

当前状态：
- 活动：{current_state.get('current_task', '无')}
- 情感：{current_state.get('emotion', '平静')}
- 能量：{current_state.get('energy', 100)}
- 时间：{current_state.get('time', '未知')}

观察到事件：{event_content}
事件类型：{event_type}

请分析这个事件的初步影响：
1. 事件对我的直接影响
2. 我的当前状态是否允许我做出反应
3. 这是否需要立即关注

请用简洁的语言描述你的观察。
"""

        try:
            response = self.llm_client.generate_response(prompt)
            return response.strip()
        except Exception as e:
            return f"事件分析失败: {e}"

    def _generate_reasoning_step(self, npc_config: Dict[str, Any],
                                current_state: Dict[str, Any],
                                event_content: str, event_type: str,
                                reasoning_chain: List[ReasoningStep],
                                current_thought: str, step_number: int) -> Optional[ReasoningStep]:
        """生成推理步骤"""
        # 构建推理历史
        history_text = "\n".join([
            f"步骤{step.step_number}: {step.thought} -> {step.action} -> {step.observation}"
            for step in reasoning_chain[-3:]  # 只保留最近3步
        ])

        prompt = f"""
你是一个{ npc_config['name'] }，{ npc_config['profession'] }。

当前推理状态：
当前思考：{current_thought}

推理历史：
{history_text}

事件：{event_content}
事件类型：{event_type}

当前状态：
- 活动：{current_state.get('current_task', '无')}
- 情感：{current_state.get('emotion', '平静')}
- 能量：{current_state.get('energy', 100)}

请进行第{step_number}步推理：

1. 基于当前思考，分析情况
2. 决定下一步行动（继续分析、寻求信息、做出决定等）
3. 评估置信度（0-1之间）

请用JSON格式回复：
{{
    "thought": "你的当前思考",
    "action": "采取的行动",
    "observation": "行动的结果或观察",
    "next_thought": "下一思考方向",
    "confidence": 0.8,
    "should_continue": true
}}
"""

        try:
            response = self.llm_client.generate_response(prompt)
            result = json.loads(response)

            if not result.get('should_continue', True):
                return None

            return ReasoningStep(
                step_number=step_number,
                thought=result['thought'],
                action=result['action'],
                observation=result['observation'],
                next_thought=result['next_thought'],
                confidence=min(1.0, max(0.0, result.get('confidence', 0.5))),
                timestamp=datetime.now()
            )

        except Exception as e:
            # 如果解析失败，返回None表示推理结束
            return None

    def _is_conclusion_reached(self, step: ReasoningStep) -> bool:
        """检查是否达到结论"""
        conclusion_keywords = ['决定', '结论', '行动', '反应', '处理']
        thought_lower = step.thought.lower()

        return any(keyword in thought_lower for keyword in conclusion_keywords)

    def _generate_final_answer(self, npc_config: Dict[str, Any],
                              current_state: Dict[str, Any],
                              reasoning_chain: List[ReasoningStep]) -> str:
        """生成最终答案"""
        last_step = reasoning_chain[-1] if reasoning_chain else None

        if last_step and '决定' in last_step.thought:
            return last_step.next_thought

        # 如果没有明确的决定，基于推理链生成答案
        prompt = f"""
基于以下推理链，为{ npc_config['name'] }生成对事件的最终反应：

推理过程：
{chr(10).join([f"{step.step_number}. {step.thought} -> {step.action}" for step in reasoning_chain])}

当前状态：
- 活动：{current_state.get('current_task', '无')}
- 情感：{current_state.get('emotion', '平静')}

请生成一个具体的反应或行动决定。
"""

        try:
            response = self.llm_client.generate_response(prompt)
            return response.strip()
        except Exception as e:
            return f"反应生成失败: {e}"

    def _generate_conclusion(self, reasoning_chain: List[ReasoningStep]) -> str:
        """生成结论总结"""
        if not reasoning_chain:
            return "推理失败"

        total_steps = len(reasoning_chain)
        avg_confidence = sum(step.confidence for step in reasoning_chain) / total_steps

        if avg_confidence > 0.8:
            confidence_level = "高"
        elif avg_confidence > 0.6:
            confidence_level = "中等"
        else:
            confidence_level = "低"

        return f"经过{total_steps}步推理，置信度{confidence_level}({avg_confidence:.2f})"


class EventAnalyzer:
    """事件分析器 - 使用React Agent进行复杂事件分析"""

    def __init__(self, react_agent: ReactAgent):
        self.react_agent = react_agent

    def analyze_event_impact(self, npc_config: Dict[str, Any],
                           current_state: Dict[str, Any],
                           event_content: str,
                           event_type: str,
                           reasoning_mode: ReasoningMode = ReasoningMode.NORMAL) -> Dict[str, Any]:
        """
        使用React Agent分析事件影响

        Args:
            npc_config: NPC配置
            current_state: 当前状态
            event_content: 事件内容
            event_type: 事件类型
            reasoning_mode: 推理模式

        Returns:
            包含影响分析和推理链的字典
        """
        # 使用React Agent进行推理
        reasoning_result = self.react_agent.reason_about_event(
            npc_config, current_state, event_content, event_type, reasoning_mode
        )

        # 基于推理结果计算影响度
        impact_score = self._calculate_impact_from_reasoning(reasoning_result)

        return {
            'impact_score': impact_score,
            'should_respond': impact_score > 30,  # 影响度阈值
            'should_change_state': impact_score > 50,  # 状态变化阈值
            'reasoning_result': reasoning_result.to_dict(),
            'reasoning_steps': reasoning_result.total_steps,
            'confidence': reasoning_result.total_confidence,
            'response_strategy': self._extract_response_strategy(reasoning_result)
        }

    def _calculate_impact_from_reasoning(self, reasoning_result: ReasoningResult) -> int:
        """从推理结果计算影响度"""
        base_impact = 20  # 基础影响度

        # 基于推理步数调整影响度
        step_bonus = min(30, reasoning_result.total_steps * 3)

        # 基于置信度调整影响度
        confidence_bonus = int(reasoning_result.total_confidence * 20)

        # 基于内容分析调整影响度
        content_bonus = self._analyze_reasoning_content(reasoning_result)

        total_impact = base_impact + step_bonus + confidence_bonus + content_bonus
        return min(100, max(0, total_impact))

    def _analyze_reasoning_content(self, reasoning_result: ReasoningResult) -> int:
        """分析推理内容的影响度"""
        bonus = 0

        # 检查推理链中的关键内容
        for step in reasoning_result.reasoning_chain:
            content = (step.thought + step.action + step.observation).lower()

            # 威胁相关
            if any(word in content for word in ['危险', '威胁', '攻击', '伤害', '紧急']):
                bonus += 15

            # 个人相关
            if any(word in content for word in ['我', '自己', '个人', '安全']):
                bonus += 10

            # 社会相关
            if any(word in content for word in ['他人', '帮助', '社会', '关系']):
                bonus += 8

            # 经济相关
            if any(word in content for word in ['财产', '金钱', '损失', '价值']):
                bonus += 8

        return min(30, bonus)

    def _extract_response_strategy(self, reasoning_result: ReasoningResult) -> str:
        """从推理结果提取响应策略"""
        if not reasoning_result.reasoning_chain:
            return "无响应"

        last_step = reasoning_result.reasoning_chain[-1]

        # 基于最终思考判断响应策略
        thought = last_step.thought.lower()

        if '立即' in thought or '马上' in thought:
            return "立即响应"
        elif '观察' in thought or '监视' in thought:
            return "观察等待"
        elif '逃跑' in thought or '躲避' in thought:
            return "回避策略"
        elif '对抗' in thought or '战斗' in thought:
            return "对抗策略"
        elif '帮助' in thought or '援助' in thought:
            return "援助策略"
        elif '忽略' in thought or '无视' in thought:
            return "忽略策略"
        else:
            return "一般响应"
