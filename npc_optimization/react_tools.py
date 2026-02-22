"""
ReAct工具系统
将NPC行为逻辑映射为工具，Agent可以自主调用
"""

from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json


class ToolType(Enum):
    """工具类型"""
    STATE_CHANGE = "state_change"  # 状态切换
    ACTION_SELECT = "action_select"  # 行为选择
    STATE_UPDATE = "state_update"  # 状态更新
    MEMORY_OPERATION = "memory_operation"  # 记忆操作
    TASK_OPERATION = "task_operation"  # 任务操作


class NPCActionTool:
    """NPC行为工具基类"""
    
    def __init__(self, 
                 name: str,
                 description: str,
                 tool_type: ToolType,
                 parameters: Dict[str, Any],
                 executor: Callable):
        """
        初始化工具
        
        Args:
            name: 工具名称
            description: 工具描述
            tool_type: 工具类型
            parameters: 参数定义（JSON Schema格式）
            executor: 执行函数
        """
        self.name = name
        self.description = description
        self.tool_type = tool_type
        self.parameters = parameters
        self.executor = executor
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于LLM）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        try:
            result = self.executor(**kwargs)
            return {
                "success": True,
                "result": result,
                "tool": self.name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": self.name
            }


class NPCToolRegistry:
    """NPC工具注册表"""
    
    def __init__(self, npc_system):
        """
        初始化工具注册表
        
        Args:
            npc_system: NPC行为系统实例
        """
        self.npc_system = npc_system
        self.tools: Dict[str, NPCActionTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        # 1. 状态切换工具
        self.register_tool(NPCActionTool(
            name="change_activity",
            description="切换NPC当前活动（工作、休息、睡觉、观察等）",
            tool_type=ToolType.STATE_CHANGE,
            parameters={
                "type": "object",
                "properties": {
                    "activity": {
                        "type": "string",
                        "enum": ["工作", "休息", "睡觉", "吃饭", "社交", "观察", "帮助他人", "思考", "祈祷", "学习", "创造"],
                        "description": "要切换到的活动"
                    },
                    "reason": {
                        "type": "string",
                        "description": "切换原因"
                    }
                },
                "required": ["activity"]
            },
            executor=self._change_activity
        ))
        
        # 2. 情绪更新工具
        self.register_tool(NPCActionTool(
            name="update_emotion",
            description="更新NPC情绪状态",
            tool_type=ToolType.STATE_UPDATE,
            parameters={
                "type": "object",
                "properties": {
                    "emotion": {
                        "type": "string",
                        "enum": ["平静", "高兴", "愤怒", "担心", "悲伤", "兴奋", "满足", "沮丧", "疲惫", "狂喜"],
                        "description": "新的情绪状态"
                    },
                    "intensity": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 10,
                        "description": "情绪强度（0-10）"
                    }
                },
                "required": ["emotion"]
            },
            executor=self._update_emotion
        ))
        
        # 3. 创建任务工具
        self.register_tool(NPCActionTool(
            name="create_task",
            description="创建新任务",
            tool_type=ToolType.TASK_OPERATION,
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "任务描述"
                    },
                    "priority": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "任务优先级（0-100）"
                    },
                    "task_type": {
                        "type": "string",
                        "enum": ["short_term", "long_term", "event_response"],
                        "description": "任务类型"
                    },
                    "deadline": {
                        "type": "string",
                        "format": "datetime",
                        "description": "截止时间（可选）"
                    }
                },
                "required": ["description", "priority", "task_type"]
            },
            executor=self._create_task
        ))
        
        # 4. 更新任务进度工具
        self.register_tool(NPCActionTool(
            name="update_task_progress",
            description="更新任务进度",
            tool_type=ToolType.TASK_OPERATION,
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "任务ID（可选，默认当前任务）"
                    },
                    "progress_increase": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "进度增量（0-1）"
                    }
                },
                "required": ["progress_increase"]
            },
            executor=self._update_task_progress
        ))
        
        # 5. 添加记忆工具
        self.register_tool(NPCActionTool(
            name="add_memory",
            description="添加新记忆",
            tool_type=ToolType.MEMORY_OPERATION,
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "记忆内容"
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "重要性（1-10）"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表"
                    }
                },
                "required": ["content", "importance"]
            },
            executor=self._add_memory
        ))
        
        # 6. 搜索记忆工具
        self.register_tool(NPCActionTool(
            name="search_memories",
            description="搜索相关记忆",
            tool_type=ToolType.MEMORY_OPERATION,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询"
                    },
                    "max_results": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                        "description": "最大返回数量"
                    }
                },
                "required": ["query"]
            },
            executor=self._search_memories
        ))
    
    def register_tool(self, tool: NPCActionTool):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具定义（用于LLM）"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具 {tool_name} 不存在"
            }
        
        return self.tools[tool_name].execute(**kwargs)
    
    # 工具执行函数
    def _change_activity(self, activity: str, reason: str = ""):
        """
        切换活动
        
        注意：此工具与行为决策树（硬判决）的优先级关系：
        - 如果行为决策树已经决定切换活动（日常行为），此工具不应该覆盖
        - 此工具主要用于复杂情况下的LLM决策，或紧急任务需要
        - 工具调用前会检查当前是否有高优先级任务，如果有则允许切换
        - 睡眠时只能被优先级 >= 95 的任务唤醒（生死关头）
        """
        from core_types import NPCAction, ACTIVITY_PRIORITY_SLEEP, ACTIVITY_PRIORITY_CRITICAL
        
        activity_map = {
            "工作": NPCAction.WORK,
            "休息": NPCAction.REST,
            "睡觉": NPCAction.SLEEP,
            "吃饭": NPCAction.EAT,
            "社交": NPCAction.SOCIALIZE,
            "观察": NPCAction.OBSERVE,
            "帮助他人": NPCAction.HELP_OTHERS,
            "思考": NPCAction.THINK,
            "祈祷": NPCAction.PRAY,
            "学习": NPCAction.LEARN,
            "创造": NPCAction.CREATE
        }
        
        if activity in activity_map:
            # 特殊保护：睡眠状态只能被生死关头的任务唤醒
            if self.npc_system.current_activity == NPCAction.SLEEP:
                current_task = self.npc_system.persistence.current_task
                if activity != "睡觉":  # 尝试唤醒
                    if not current_task or current_task.priority < ACTIVITY_PRIORITY_CRITICAL:
                        # 不是生死关头，不能唤醒睡眠中的NPC
                        return {
                            "activity": activity,
                            "reason": reason,
                            "note": "NPC正在深度睡眠，无法被中等优先级任务唤醒",
                            "blocked": True
                        }
            
            # 检查是否有高优先级任务，如果有则允许切换
            current_task = self.npc_system.persistence.current_task
            if current_task and current_task.priority >= 80:
                # 高优先级任务，允许工具切换活动
                self.npc_system._change_activity(activity_map[activity])
                return {"activity": activity, "reason": reason, "note": "高优先级任务允许切换"}
            elif current_task and current_task.priority < 50:
                # 低优先级任务，检查是否与日常行为冲突
                # 如果当前活动是日常行为（由行为决策树决定），则不允许工具覆盖
                current_hour = self.npc_system.world_clock.current_time.hour
                needs_dict = {
                    "hunger": self.npc_system.need_system.needs.hunger,
                    "fatigue": self.npc_system.need_system.needs.fatigue,
                    "social": self.npc_system.need_system.needs.social
                }
                routine_action = self.npc_system.behavior_tree.decide_routine_behavior(
                    current_hour=current_hour,
                    energy_level=int(self.npc_system.energy * 100),  # 转换为0-100范围
                    needs=needs_dict,
                    current_task={"priority": current_task.priority, "description": current_task.description}
                )
                
                # 如果行为决策树有明确的日常行为决策，且与工具决策冲突，则不允许
                if routine_action and routine_action == self.npc_system.current_activity:
                    # 日常行为正在执行，不允许工具覆盖（除非是紧急情况）
                    return {"activity": activity, "reason": reason, "note": "日常行为不允许覆盖", "blocked": True}
                else:
                    # 允许切换
                    self.npc_system._change_activity(activity_map[activity])
                    return {"activity": activity, "reason": reason}
            else:
                # 无任务或中等优先级，允许切换
                self.npc_system._change_activity(activity_map[activity])
                return {"activity": activity, "reason": reason}
        else:
            raise ValueError(f"未知活动: {activity}")
    
    def _update_emotion(self, emotion: str, intensity: int = 5):
        """更新情绪"""
        from core_types import Emotion
        emotion_map = {
            "平静": Emotion.CALM,
            "高兴": Emotion.HAPPY,
            "愤怒": Emotion.ANGRY,
            "担心": Emotion.WORRIED,
            "悲伤": Emotion.SAD,
            "兴奋": Emotion.EXCITED,
            "满足": Emotion.CONTENT,
            "沮丧": Emotion.FRUSTRATED,
            "疲惫": Emotion.EXHAUSTED,
            "狂喜": Emotion.ECSTATIC
        }
        
        if emotion in emotion_map:
            self.npc_system.current_emotion = emotion_map[emotion]
            return {"emotion": emotion, "intensity": intensity}
        else:
            raise ValueError(f"未知情绪: {emotion}")
    
    def _create_task(self, description: str, priority: int, task_type: str, deadline: Optional[str] = None):
        """创建任务"""
        task_id = self.npc_system.persistence.create_task(
            description=description,
            task_type=task_type,
            priority=priority,
            deadline=deadline
        )
        
        # 如果是高优先级任务，设置为当前任务
        if priority > 70:
            task = self.npc_system.persistence.tasks[task_id]
            self.npc_system.persistence.set_current_task(task)
        
        return {"task_id": task_id, "description": description}
    
    def _update_task_progress(self, progress_increase: float, task_id: Optional[str] = None):
        """更新任务进度"""
        task = self.npc_system.persistence.current_task
        if not task:
            raise ValueError("没有当前任务")
        
        old_progress = task.progress
        task.progress = min(1.0, task.progress + progress_increase)
        self.npc_system.persistence._save_data()
        
        return {
            "task_id": task.id,
            "old_progress": old_progress,
            "new_progress": task.progress
        }
    
    def _add_memory(self, content: str, importance: int, tags: List[str] = None):
        """添加记忆"""
        self.npc_system.add_memory(
            content=content,
            importance=importance,
            tags=tags or []
        )
        return {"content": content[:50] + "..." if len(content) > 50 else content}
    
    def _search_memories(self, query: str, max_results: int = 5):
        """搜索记忆"""
        if not hasattr(self.npc_system, 'memories'):
            return {"results": []}
        
        memories_dict = [
            {
                "content": m.content,
                "importance": m.importance,
                "tags": m.tags if hasattr(m, 'tags') else []
            }
            for m in self.npc_system.memories
        ]
        
        results = self.npc_system.memory_manager.get_relevant_memories(
            query=query,
            memories=memories_dict,
            top_k=max_results
        )
        
        return {"results": results, "count": len(results)}


class ReActAgent:
    """ReAct风格的Agent（使用工具）"""
    
    def __init__(self, llm_client, tool_registry: NPCToolRegistry):
        """
        初始化ReAct Agent
        
        Args:
            llm_client: LLM客户端
            tool_registry: 工具注册表
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
    
    def think_and_act(self, 
                      situation: str,
                      compressed_context: Dict[str, Any],
                      max_iterations: int = 5,
                      thinking_callback=None) -> Dict[str, Any]:
        """
        思考-行动循环
        
        Args:
            situation: 当前情况
            compressed_context: 压缩后的上下文
            max_iterations: 最大迭代次数
            thinking_callback: 思考过程回调函数（用于GUI显示）
            
        Returns:
            最终决策结果
        """
        observation = ""
        tools_available = self.tool_registry.get_tools()
        
        if thinking_callback:
            thinking_callback("开始思考", f"当前情况: {situation}")
        
        for i in range(max_iterations):
            # 1. 思考阶段
            thought = self._think(situation, observation, compressed_context, tools_available, i)
            
            # 显示思考过程
            if thinking_callback:
                reasoning = thought.get("reasoning", "无")
                if thought.get("tool_call"):
                    tool_name = thought["tool_call"].get("name", "未知工具")
                    thinking_callback(f"思考步骤 {i+1}", f"推理: {reasoning}\n决定调用工具: {tool_name}")
                else:
                    final_decision = thought.get("final_decision", {})
                    action = final_decision.get("action", "未知")
                    reason = final_decision.get("reason", "无")
                    thinking_callback(f"思考步骤 {i+1}", f"推理: {reasoning}\n最终决策: {action} - {reason}")
            
            # 2. 行动阶段（工具调用）
            if thought.get("tool_call"):
                tool_call = thought["tool_call"]
                result = self.tool_registry.execute_tool(
                    tool_call["name"],
                    **tool_call.get("parameters", {})
                )
                observation = f"工具 {tool_call['name']} 执行结果: {result}"
                
                if thinking_callback:
                    thinking_callback("工具执行", f"工具: {tool_call['name']}\n结果: {str(result)[:100]}")
            else:
                # 3. 最终决策
                return thought.get("final_decision", {"action": "休息", "reason": "无决策"})
        
        return {"action": "休息", "reason": "达到最大迭代次数"}
    
    def _think(self, 
               situation: str,
               observation: str,
               compressed_context: Dict[str, Any],
               tools: List[Dict[str, Any]],
               iteration: int) -> Dict[str, Any]:
        """思考阶段"""
        from npc_optimization.prompt_templates import PromptTemplates
        
        context_str = compressed_context.get("formatted", "")
        tools_str = json.dumps(tools, ensure_ascii=False, indent=2)
        
        prompt = f"""你是一个智能NPC Agent，使用ReAct（推理-行动）循环进行决策。

当前情况：{situation}
上次观察：{observation if observation else "无"}

可用工具：
{tools_str}

当前上下文：
{context_str}

请分析情况并决定：
1. 是否需要调用工具？
2. 如果需要，调用哪个工具？参数是什么？
3. 如果不需要，做出最终决策

格式（JSON）：
{{
    "reasoning": "你的推理过程",
    "tool_call": {{"name": "工具名", "parameters": {{}}}},
    "final_decision": {{"action": "行动", "reason": "原因"}}
}}

注意：
- 第{iteration + 1}次迭代（最多5次）
- 如果工具执行成功，可以继续思考下一步
- 如果工具执行失败或不需要工具，做出最终决策
"""
        
        try:
            response = self.llm_client.generate_response(prompt, max_tokens=500)
            
            # 解析JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"final_decision": {"action": "休息", "reason": "无法解析响应"}}
        except Exception as e:
            print(f"ReAct思考失败: {e}")
            return {"final_decision": {"action": "休息", "reason": f"思考错误: {e}"}}

