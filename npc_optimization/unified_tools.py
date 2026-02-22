"""
统一NPC工具定义

整合 react_tools.py 和 npc_agent.py 中的工具定义，
提供一套完整的NPC行为工具供ReAct Agent调用。

工具分类：
1. 移动类：move_to, flee
2. 交流类：speak, notify_others, alert
3. 行动类：help_action, observe, work
4. 状态类：change_activity, update_emotion
5. 记忆类：add_memory, search_memories
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """工具分类"""
    MOVEMENT = "movement"        # 移动类
    COMMUNICATION = "communication"  # 交流类
    ACTION = "action"            # 行动类
    STATE = "state"              # 状态类
    MEMORY = "memory"            # 记忆类


@dataclass
class UnifiedTool:
    """统一工具定义"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]  # JSON Schema格式
    required_params: List[str]
    examples: List[Dict[str, Any]]  # 示例调用

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于LLM提示）"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": self.parameters,
            "required": self.required_params,
            "examples": self.examples
        }

    def to_llm_format(self) -> str:
        """转换为LLM可读的格式"""
        params_str = ", ".join([
            f"{k}: {v.get('type', 'any')}"
            for k, v in self.parameters.items()
        ])
        example_str = json.dumps(self.examples[0], ensure_ascii=False) if self.examples else "{}"
        return f"- {self.name}({params_str}): {self.description}\n  示例: {example_str}"


# ============== 统一工具定义 ==============

UNIFIED_TOOLS: List[UnifiedTool] = [
    # ========== 移动类工具 ==========
    UnifiedTool(
        name="move_to",
        description="移动到指定位置。用于前往某地点、赶往事件现场或撤离危险区域。",
        category=ToolCategory.MOVEMENT,
        parameters={
            "destination": {
                "type": "string",
                "description": "目标位置名称（如：教堂、中心广场、铁匠铺）"
            },
            "urgency": {
                "type": "string",
                "enum": ["normal", "fast", "emergency"],
                "description": "紧急程度：normal=正常步行，fast=快走，emergency=紧急奔跑"
            },
            "reason": {
                "type": "string",
                "description": "移动原因"
            }
        },
        required_params=["destination"],
        examples=[
            {"tool": "move_to", "destination": "教堂", "urgency": "emergency", "reason": "教堂起火，前去救援"},
            {"tool": "move_to", "destination": "酒馆", "urgency": "normal", "reason": "下班后去喝一杯"}
        ]
    ),

    UnifiedTool(
        name="flee",
        description="逃离当前位置到安全地点。用于紧急危险情况。",
        category=ToolCategory.MOVEMENT,
        parameters={
            "destination": {
                "type": "string",
                "description": "逃往的安全位置"
            },
            "reason": {
                "type": "string",
                "description": "逃跑原因"
            }
        },
        required_params=["destination"],
        examples=[
            {"tool": "flee", "destination": "中心广场", "reason": "建筑物倒塌，需要撤离"}
        ]
    ),

    # ========== 交流类工具 ==========
    UnifiedTool(
        name="speak",
        description="说话或与他人对话。可以对特定人物说话，也可以自言自语或向周围人喊话。",
        category=ToolCategory.COMMUNICATION,
        parameters={
            "content": {
                "type": "string",
                "description": "说话的内容"
            },
            "target": {
                "type": "string",
                "description": "对话目标：具体人名、'nearby'（附近的人）、'self'（自言自语）"
            },
            "emotion": {
                "type": "string",
                "enum": ["calm", "excited", "worried", "scared", "angry", "sad", "happy"],
                "description": "说话时的情绪"
            },
            "volume": {
                "type": "string",
                "enum": ["whisper", "normal", "loud", "shout"],
                "description": "音量：whisper=低语，normal=正常，loud=大声，shout=喊叫"
            }
        },
        required_params=["content"],
        examples=[
            {"tool": "speak", "content": "教堂着火了！快来帮忙！", "target": "nearby", "emotion": "scared", "volume": "shout"},
            {"tool": "speak", "content": "今天的铁件打得不错", "target": "self", "emotion": "happy", "volume": "normal"}
        ]
    ),

    UnifiedTool(
        name="notify_others",
        description="通知其他NPC关于某个事件或信息。消息会通过消息总线传播。",
        category=ToolCategory.COMMUNICATION,
        parameters={
            "message": {
                "type": "string",
                "description": "要传达的消息内容"
            },
            "targets": {
                "type": "string",
                "description": "通知目标：'nearby'（附近的人）、'all'（所有人）、具体人名列表"
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "消息优先级"
            }
        },
        required_params=["message"],
        examples=[
            {"tool": "notify_others", "message": "教堂发生火灾，需要救援！", "targets": "all", "priority": "urgent"},
            {"tool": "notify_others", "message": "今晚酒馆有特价啤酒", "targets": "nearby", "priority": "low"}
        ]
    ),

    UnifiedTool(
        name="alert",
        description="发出警报，警告他人注意危险。比notify_others更紧急。",
        category=ToolCategory.COMMUNICATION,
        parameters={
            "danger_type": {
                "type": "string",
                "description": "危险类型（火灾、攻击、洪水等）"
            },
            "location": {
                "type": "string",
                "description": "危险发生的位置"
            },
            "action_required": {
                "type": "string",
                "description": "建议的行动（撤离、躲避、集合等）"
            }
        },
        required_params=["danger_type", "location"],
        examples=[
            {"tool": "alert", "danger_type": "火灾", "location": "教堂", "action_required": "携带水桶前往救援"}
        ]
    ),

    # ========== 行动类工具 ==========
    UnifiedTool(
        name="help_action",
        description="帮助他人或参与救援行动。",
        category=ToolCategory.ACTION,
        parameters={
            "target": {
                "type": "string",
                "description": "帮助的目标（人名、事件、位置）"
            },
            "action": {
                "type": "string",
                "description": "具体的帮助行动"
            },
            "use_skill": {
                "type": "string",
                "description": "使用的技能（可选，如铁匠技能、医疗技能）"
            }
        },
        required_params=["target", "action"],
        examples=[
            {"tool": "help_action", "target": "教堂火灾", "action": "用水桶灭火", "use_skill": "铁匠的力量"},
            {"tool": "help_action", "target": "受伤的村民", "action": "进行急救", "use_skill": "基础医疗"}
        ]
    ),

    UnifiedTool(
        name="observe",
        description="观察周围情况或特定目标。用于收集信息、评估局势。",
        category=ToolCategory.ACTION,
        parameters={
            "target": {
                "type": "string",
                "description": "观察目标：具体对象、'surroundings'（周围环境）、事件名称"
            },
            "focus": {
                "type": "string",
                "description": "关注重点（可选）"
            },
            "duration_minutes": {
                "type": "number",
                "description": "观察持续时间（分钟）"
            }
        },
        required_params=["target"],
        examples=[
            {"tool": "observe", "target": "教堂火势", "focus": "火势大小和蔓延方向", "duration_minutes": 5},
            {"tool": "observe", "target": "surroundings", "focus": "有无可疑人物", "duration_minutes": 10}
        ]
    ),

    UnifiedTool(
        name="work",
        description="进行工作相关活动。根据NPC职业执行不同的工作内容。",
        category=ToolCategory.ACTION,
        parameters={
            "activity": {
                "type": "string",
                "description": "具体工作活动（打铁、酿酒、耕种、祈祷等）"
            },
            "duration_minutes": {
                "type": "number",
                "description": "工作持续时间（分钟）"
            },
            "intensity": {
                "type": "string",
                "enum": ["light", "normal", "heavy"],
                "description": "工作强度"
            }
        },
        required_params=["activity"],
        examples=[
            {"tool": "work", "activity": "打造铁剑", "duration_minutes": 60, "intensity": "heavy"},
            {"tool": "work", "activity": "为村民祈福", "duration_minutes": 30, "intensity": "light"}
        ]
    ),

    # ========== 状态类工具 ==========
    UnifiedTool(
        name="change_activity",
        description="切换当前活动状态。",
        category=ToolCategory.STATE,
        parameters={
            "activity": {
                "type": "string",
                "enum": ["工作", "休息", "睡觉", "吃饭", "社交", "观察", "帮助他人", "思考", "祈祷", "学习", "旅行"],
                "description": "要切换到的活动"
            },
            "reason": {
                "type": "string",
                "description": "切换原因"
            }
        },
        required_params=["activity"],
        examples=[
            {"tool": "change_activity", "activity": "帮助他人", "reason": "教堂起火，需要救援"},
            {"tool": "change_activity", "activity": "休息", "reason": "工作了一整天，需要休息"}
        ]
    ),

    UnifiedTool(
        name="update_emotion",
        description="更新当前情绪状态。",
        category=ToolCategory.STATE,
        parameters={
            "emotion": {
                "type": "string",
                "enum": ["happy", "sad", "angry", "scared", "worried", "calm", "excited", "tired"],
                "description": "新的情绪状态"
            },
            "intensity": {
                "type": "number",
                "minimum": 1,
                "maximum": 10,
                "description": "情绪强度（1-10）"
            },
            "cause": {
                "type": "string",
                "description": "情绪变化原因"
            }
        },
        required_params=["emotion"],
        examples=[
            {"tool": "update_emotion", "emotion": "worried", "intensity": 8, "cause": "听说教堂起火了"}
        ]
    ),

    UnifiedTool(
        name="continue_current",
        description="继续当前活动，不做改变。用于决定维持现状时。",
        category=ToolCategory.STATE,
        parameters={
            "reason": {
                "type": "string",
                "description": "继续当前活动的原因"
            }
        },
        required_params=[],
        examples=[
            {"tool": "continue_current", "reason": "事件与我无关，继续工作"}
        ]
    ),

    # ========== 记忆类工具 ==========
    UnifiedTool(
        name="add_memory",
        description="添加新记忆。用于记住重要事件、对话或观察。",
        category=ToolCategory.MEMORY,
        parameters={
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
            },
            "related_npcs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "相关NPC列表"
            }
        },
        required_params=["content", "importance"],
        examples=[
            {"tool": "add_memory", "content": "教堂在第1天发生火灾，牧师西奥多组织救援", "importance": 9, "tags": ["火灾", "教堂"], "related_npcs": ["牧师西奥多"]}
        ]
    ),

    UnifiedTool(
        name="search_memories",
        description="搜索相关记忆。用于回忆过去的事件或信息。",
        category=ToolCategory.MEMORY,
        parameters={
            "query": {
                "type": "string",
                "description": "搜索关键词或问题"
            },
            "max_results": {
                "type": "number",
                "description": "最大返回数量"
            }
        },
        required_params=["query"],
        examples=[
            {"tool": "search_memories", "query": "关于教堂的记忆", "max_results": 5}
        ]
    ),

    # ========== 经济类工具（B3）==========
    UnifiedTool(
        name="trade_item",
        description="与商人或NPC进行物品交易（买入或卖出）。触发经济系统结算，更新双方背包和金币。",
        category=ToolCategory.ACTION,
        parameters={
            "action": {
                "type": "string",
                "enum": ["buy", "sell"],
                "description": "交易类型：buy=买入，sell=卖出"
            },
            "item_id": {
                "type": "string",
                "description": "物品ID（如：iron_sword, herb_basic）"
            },
            "target_npc": {
                "type": "string",
                "description": "交易对象NPC名称"
            },
            "quantity": {
                "type": "integer",
                "description": "数量，默认1"
            }
        },
        required_params=["action", "item_id", "target_npc"],
        examples=[
            {"tool": "trade_item", "action": "buy", "item_id": "iron_sword", "target_npc": "雷纳德·行商", "quantity": 1},
            {"tool": "trade_item", "action": "sell", "item_id": "herb_basic", "target_npc": "玛格丽特·花语", "quantity": 3}
        ]
    ),
]


class UnifiedToolRegistry:
    """
    统一工具注册表

    管理所有可用工具，提供工具查询、执行等功能。
    """

    def __init__(self, npc_system=None):
        """
        初始化工具注册表

        Args:
            npc_system: NPC行为系统实例（用于执行工具）
        """
        self.npc_system = npc_system
        self.tools: Dict[str, UnifiedTool] = {}
        self.executors: Dict[str, Callable] = {}

        # 注册所有统一工具
        for tool in UNIFIED_TOOLS:
            self.tools[tool.name] = tool

        # 如果有npc_system，绑定执行器
        if npc_system:
            self._bind_executors()

    def _bind_executors(self):
        """绑定工具执行器到npc_system的方法"""
        if not self.npc_system:
            return

        # 移动类
        self.executors["move_to"] = self._execute_move_to
        self.executors["flee"] = self._execute_flee

        # 交流类
        self.executors["speak"] = self._execute_speak
        self.executors["notify_others"] = self._execute_notify_others
        self.executors["alert"] = self._execute_alert

        # 行动类
        self.executors["help_action"] = self._execute_help_action
        self.executors["observe"] = self._execute_observe
        self.executors["work"] = self._execute_work

        # 状态类
        self.executors["change_activity"] = self._execute_change_activity
        self.executors["update_emotion"] = self._execute_update_emotion
        self.executors["continue_current"] = self._execute_continue_current

        # 记忆类
        self.executors["add_memory"] = self._execute_add_memory
        self.executors["search_memories"] = self._execute_search_memories

        # 经济类（B3）
        self.executors["trade_item"] = self._execute_trade_item

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具定义（用于LLM）"""
        return [tool.to_dict() for tool in self.tools.values()]

    def get_tools_by_category(self, category: ToolCategory) -> List[Dict[str, Any]]:
        """按分类获取工具"""
        return [
            tool.to_dict()
            for tool in self.tools.values()
            if tool.category == category
        ]

    def get_tools_for_prompt(self) -> str:
        """获取用于LLM提示的工具描述"""
        lines = ["可用工具："]
        for category in ToolCategory:
            category_tools = [t for t in self.tools.values() if t.category == category]
            if category_tools:
                lines.append(f"\n## {category.value.upper()}")
                for tool in category_tools:
                    lines.append(tool.to_llm_format())
        return "\n".join(lines)

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            执行结果
        """
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 不存在"
            }

        if tool_name not in self.executors:
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 没有绑定执行器"
            }

        try:
            result = self.executors[tool_name](**kwargs)
            return {
                "success": True,
                "tool": tool_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {e}")
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e)
            }

    # ========== 工具执行器实现 ==========

    def _execute_move_to(self, destination: str, urgency: str = "normal", reason: str = "") -> Dict:
        """执行移动"""
        from core_types import NPCAction

        # 调用npc_system的move_to方法
        if hasattr(self.npc_system, 'move_to'):
            success = self.npc_system.move_to(destination)
        else:
            success = False

        return {
            "action": "move_to",
            "destination": destination,
            "urgency": urgency,
            "reason": reason,
            "success": success,
            "message": f"开始前往{destination}" if success else f"无法前往{destination}"
        }

    def _execute_flee(self, destination: str, reason: str = "") -> Dict:
        """执行逃跑"""
        return self._execute_move_to(destination, urgency="emergency", reason=reason)

    def _execute_speak(self, content: str, target: str = "nearby",
                       emotion: str = "calm", volume: str = "normal") -> Dict:
        """执行说话"""
        from npc_optimization.message_bus import MessageType, MessagePriority

        # 使用消息总线广播
        if hasattr(self.npc_system, 'broadcast_to_nearby'):
            priority = MessagePriority.HIGH if volume == "shout" else MessagePriority.NORMAL
            self.npc_system.broadcast_to_nearby(
                message_content=content,
                message_type=MessageType.NPC_SPEECH,
                priority=priority
            )

        return {
            "action": "speak",
            "content": content,
            "target": target,
            "emotion": emotion,
            "volume": volume,
            "success": True
        }

    def _execute_notify_others(self, message: str, targets: str = "nearby",
                                priority: str = "normal") -> Dict:
        """执行通知他人"""
        from npc_optimization.message_bus import MessageType, MessagePriority

        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT
        }

        if hasattr(self.npc_system, 'broadcast_to_nearby'):
            self.npc_system.broadcast_to_nearby(
                message_content=message,
                message_type=MessageType.GOSSIP,
                priority=priority_map.get(priority, MessagePriority.NORMAL)
            )

        return {
            "action": "notify_others",
            "message": message,
            "targets": targets,
            "priority": priority,
            "success": True
        }

    def _execute_alert(self, danger_type: str, location: str,
                       action_required: str = "") -> Dict:
        """执行警报"""
        alert_message = f"警报！{location}发生{danger_type}！{action_required}"
        return self._execute_notify_others(alert_message, targets="all", priority="urgent")

    def _execute_help_action(self, target: str, action: str,
                              use_skill: str = "") -> Dict:
        """执行帮助行动"""
        from core_types import NPCAction

        # 切换到帮助他人状态
        if hasattr(self.npc_system, '_change_activity'):
            self.npc_system._change_activity(NPCAction.HELP_OTHERS)

        return {
            "action": "help_action",
            "target": target,
            "help_action": action,
            "skill_used": use_skill,
            "success": True,
            "message": f"正在{action}"
        }

    def _execute_observe(self, target: str, focus: str = "",
                          duration_minutes: int = 5) -> Dict:
        """执行观察"""
        from core_types import NPCAction

        if hasattr(self.npc_system, '_change_activity'):
            self.npc_system._change_activity(NPCAction.OBSERVE)

        return {
            "action": "observe",
            "target": target,
            "focus": focus,
            "duration_minutes": duration_minutes,
            "success": True,
            "message": f"正在观察{target}"
        }

    def _execute_work(self, activity: str, duration_minutes: int = 60,
                       intensity: str = "normal") -> Dict:
        """执行工作"""
        from core_types import NPCAction

        if hasattr(self.npc_system, '_change_activity'):
            self.npc_system._change_activity(NPCAction.WORK)

        return {
            "action": "work",
            "activity": activity,
            "duration_minutes": duration_minutes,
            "intensity": intensity,
            "success": True,
            "message": f"正在{activity}"
        }

    def _execute_change_activity(self, activity: str, reason: str = "") -> Dict:
        """执行切换活动"""
        from core_types import NPCAction

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
            "旅行": NPCAction.TRAVEL,
        }

        npc_action = activity_map.get(activity)
        if npc_action and hasattr(self.npc_system, '_change_activity'):
            self.npc_system._change_activity(npc_action)
            return {
                "action": "change_activity",
                "activity": activity,
                "reason": reason,
                "success": True
            }
        else:
            return {
                "action": "change_activity",
                "activity": activity,
                "reason": reason,
                "success": False,
                "error": f"未知活动类型: {activity}"
            }

    def _execute_update_emotion(self, emotion: str, intensity: int = 5,
                                 cause: str = "") -> Dict:
        """执行更新情绪"""
        from core_types import Emotion

        emotion_map = {
            "happy": Emotion.HAPPY,
            "sad": Emotion.SAD,
            "angry": Emotion.ANGRY,
            "scared": Emotion.ANXIOUS,
            "worried": Emotion.ANXIOUS,
            "calm": Emotion.CALM,
            "excited": Emotion.EXCITED,
            "tired": Emotion.TIRED,
        }

        npc_emotion = emotion_map.get(emotion)
        if npc_emotion and hasattr(self.npc_system, 'current_emotion'):
            self.npc_system.current_emotion = npc_emotion

        return {
            "action": "update_emotion",
            "emotion": emotion,
            "intensity": intensity,
            "cause": cause,
            "success": True
        }

    def _execute_continue_current(self, reason: str = "") -> Dict:
        """执行继续当前活动"""
        current_activity = getattr(self.npc_system, 'current_activity', None)
        return {
            "action": "continue_current",
            "current_activity": current_activity.value if current_activity else "unknown",
            "reason": reason,
            "success": True,
            "message": "继续当前活动"
        }

    def _execute_add_memory(self, content: str, importance: int,
                             tags: List[str] = None,
                             related_npcs: List[str] = None) -> Dict:
        """执行添加记忆"""
        if hasattr(self.npc_system, 'memory_manager'):
            self.npc_system.memory_manager.add_memory(
                content=content,
                importance=importance,
                tags=tags or [],
                related_npcs=related_npcs or []
            )
            return {
                "action": "add_memory",
                "content": content,
                "importance": importance,
                "success": True
            }
        return {
            "action": "add_memory",
            "success": False,
            "error": "记忆管理器不可用"
        }

    def _execute_search_memories(self, query: str, max_results: int = 5) -> Dict:
        """执行搜索记忆"""
        if hasattr(self.npc_system, 'rag_memory'):
            results = self.npc_system.rag_memory.search(query, top_k=max_results)
            return {
                "action": "search_memories",
                "query": query,
                "results": results,
                "success": True
            }
        return {
            "action": "search_memories",
            "success": False,
            "error": "RAG记忆系统不可用"
        }

    def _execute_trade_item(self, action: str, item_id: str, target_npc: str, quantity: int = 1) -> Dict:
        """执行物品交易（B3：接入EconomySystem）"""
        try:
            from world_simulator.economy_system import EconomySystem
            eco = EconomySystem()
            buyer_name = self.npc_system.npc_name
            if action == "buy":
                result = eco.market_system.buy_item(
                    buyer=buyer_name, seller=target_npc,
                    item_id=item_id, quantity=quantity
                )
            else:
                result = eco.market_system.sell_item(
                    seller=buyer_name, buyer=target_npc,
                    item_id=item_id, quantity=quantity
                )
            # 关系更新：交易后好感+1，信任+2
            if hasattr(self.npc_system, '_update_relationship'):
                self.npc_system._update_relationship(
                    target=target_npc, affection_delta=1, trust_delta=2,
                    content=f"与{target_npc}完成了{action}交易: {item_id}x{quantity}"
                )
            return {
                "action": "trade_item",
                "trade_action": action,
                "item_id": item_id,
                "target_npc": target_npc,
                "quantity": quantity,
                "success": bool(result),
                "result": result if isinstance(result, dict) else {}
            }
        except Exception as e:
            logger.error(f"trade_item 执行失败: {e}")
            return {"action": "trade_item", "success": False, "error": str(e)}


def get_unified_tools_prompt() -> str:
    """获取统一工具的提示文本"""
    registry = UnifiedToolRegistry()
    return registry.get_tools_for_prompt()


def parse_tool_call(response_text: str) -> Optional[Dict[str, Any]]:
    """
    从LLM响应中解析工具调用

    Args:
        response_text: LLM响应文本

    Returns:
        解析出的工具调用，或None
    """
    import re

    # 尝试从JSON代码块中提取
    json_pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(json_pattern, response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试直接解析JSON对象
    json_obj_pattern = r'\{[^{}]*"tool"[^{}]*\}'
    match = re.search(json_obj_pattern, response_text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None
