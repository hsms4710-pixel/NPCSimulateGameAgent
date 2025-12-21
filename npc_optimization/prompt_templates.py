"""
Prompt模板
设计精简但保留世界观和NPC性格的prompt
"""

from typing import Dict, Any, Optional
from .context_compressor import ContextCompressor


class PromptTemplates:
    """Prompt模板管理器"""
    
    def __init__(self, world_lore: Optional[Dict[str, Any]] = None):
        """
        初始化Prompt模板
        
        Args:
            world_lore: 世界观设定（可选）
        """
        self.world_lore = world_lore or {}
        self.compressor = ContextCompressor()
    
    def get_task_progress_prompt(self, 
                                compressed_context: Dict[str, Any],
                                task_description: str,
                                time_passed: float) -> str:
        """
        获取任务进度决策的prompt
        
        Args:
            compressed_context: 压缩后的上下文
            task_description: 任务描述
            time_passed: 经过的时间（小时）
            
        Returns:
            格式化的prompt
        """
        # 格式化压缩上下文
        context_str = self.compressor.format_compressed_context(compressed_context)
        
        # 世界观设定（精简）
        world_context = self._get_world_context()
        
        prompt = f"""你是一个智能NPC决策系统，位于{world_context}。

{context_str}

当前任务：{task_description}
经过时间：{time_passed:.2f}小时

请分析：
1. 当前活动是否适合推进这个任务？
2. 根据任务类型、优先级、当前活动、能量水平等因素，任务进度应该增加多少？
3. 考虑NPC的性格和职业特点

请用JSON格式回复：
{{
    "reasoning": "你的推理过程（简要）",
    "progress_increase": 0.0-1.0之间的浮点数,
    "should_continue": true/false
}}

注意：
- 如果当前活动不适合任务，进度增量应该很小（0.0-0.05）
- 如果当前活动非常适合任务，进度增量可以较大（0.05-0.20）
- 考虑任务优先级：高优先级任务应该推进更快
- 考虑能量水平：能量低时推进速度应该减慢
- 保持角色一致性：决策应符合NPC的性格和背景
"""
        return prompt
    
    def get_behavior_decision_prompt(self,
                                    compressed_context: Dict[str, Any],
                                    situation: str) -> str:
        """
        获取行为决策的prompt
        
        Args:
            compressed_context: 压缩后的上下文
            situation: 当前情况描述
            
        Returns:
            格式化的prompt
        """
        context_str = self.compressor.format_compressed_context(compressed_context)
        world_context = self._get_world_context()
        
        prompt = f"""你是一个智能NPC，位于{world_context}。

{context_str}

当前情况：{situation}

请决定：
1. 应该采取什么行动？
2. 为什么选择这个行动？
3. 这个行动是否符合你的性格和背景？

可用行动：工作、休息、睡觉、吃饭、社交、观察、帮助他人、思考、祈祷、学习、创造

请用JSON格式回复：
{{
    "action": "行动名称",
    "reasoning": "选择原因（简要）",
    "emotion_change": "情绪变化（如有）"
}}

注意：
- 保持角色一致性
- 考虑当前状态和需求
- 行动应该符合世界观设定
"""
        return prompt
    
    def get_event_response_prompt(self,
                                  compressed_context: Dict[str, Any],
                                  event_content: str,
                                  event_type: str) -> str:
        """
        获取事件响应的prompt
        
        Args:
            compressed_context: 压缩后的上下文
            event_content: 事件内容
            event_type: 事件类型
            
        Returns:
            格式化的prompt
        """
        context_str = self.compressor.format_compressed_context(compressed_context)
        world_context = self._get_world_context()
        
        prompt = f"""你是一个智能NPC，位于{world_context}。

{context_str}

发生事件：{event_content}
事件类型：{event_type}

请分析：
1. 这个事件对你的影响是什么？
2. 你应该如何回应？
3. 是否需要改变当前状态或创建新任务？

请用JSON格式回复：
{{
    "response": "你的回应内容",
    "reasoning": "回应理由（简要）",
    "state_change": "rest/activity/none",
    "emotion_change": "calm/angry/fearful/happy/sad/none",
    "create_task": true/false,
    "task_description": "如果需要创建任务，这里填写",
    "task_priority": 1-100
}}

注意：
- 回应应该符合你的性格和背景
- 考虑当前状态（正在做什么）
- 保持世界观一致性
"""
        return prompt
    
    def _get_world_context(self) -> str:
        """获取世界观上下文（精简）"""
        if self.world_lore:
            world_name = self.world_lore.get("world_name", "艾伦谷")
            world_desc = self.world_lore.get("world_description", "")
            # 只取前100字
            if len(world_desc) > 100:
                world_desc = world_desc[:100] + "..."
            return f"{world_name}（{world_desc}）"
        return "艾伦谷（一个宁静的中世纪小镇）"

