"""
NPC Agent 系统 - 基于ReAct模式的NPC行为决策
类似于LLM Agent调用工具的模式，NPC通过思考决定调用哪个行为接口

注意：此模块定义了ReAct Agent专用的类型，与core_types中的类型用途不同：
- AgentActionType: Agent可执行的行为类型（对应工具调用）
- AgentAction: Agent行为动作数据（包含参数）
- AgentNPCState: Agent视角的NPC状态（简化版）
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class AgentActionType(Enum):
    """Agent可执行的行为类型（对应ReAct工具）"""
    MOVE = "move"                    # 移动到某个位置
    SPEAK = "speak"                  # 说话/对话
    WORK = "work"                    # 进行工作相关活动
    HELP = "help"                    # 帮助他人（紧急事件）
    OBSERVE = "observe"              # 观察/关注事件
    FLEE = "flee"                    # 逃跑/避难
    ALERT = "alert"                  # 警告他人
    CONTINUE = "continue"            # 继续当前活动
    REST = "rest"                    # 休息
    SOCIALIZE = "socialize"          # 社交活动


# 向后兼容别名
ActionType = AgentActionType


@dataclass
class AgentAction:
    """Agent行为动作数据"""
    action_type: AgentActionType
    target: Optional[str] = None     # 目标位置/人物
    content: Optional[str] = None    # 说话内容/行为描述
    priority: int = 5                # 优先级 1-10，10最高
    duration_minutes: int = 15       # 预计持续时间（分钟）
    reason: str = ""                 # 行为原因（思考过程）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "content": self.content,
            "priority": self.priority,
            "duration_minutes": self.duration_minutes,
            "reason": self.reason
        }


# 向后兼容别名
NPCAction = AgentAction


@dataclass
class AgentNPCState:
    """Agent视角的NPC状态（简化版）"""
    name: str
    location: str
    profession: str
    current_activity: str
    energy: float = 1.0              # 体力 0-1
    mood: str = "normal"             # 情绪: happy, normal, worried, scared, angry
    current_goal: Optional[str] = None  # 当前目标
    pending_actions: List[AgentAction] = field(default_factory=list)
    action_history: List[Dict] = field(default_factory=list)  # 最近行为历史

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "profession": self.profession,
            "current_activity": self.current_activity,
            "energy": self.energy,
            "mood": self.mood,
            "current_goal": self.current_goal,
            "pending_actions": [a.to_dict() for a in self.pending_actions],
            "action_history": self.action_history[-5:]  # 最近5条
        }


# 向后兼容别名
NPCState = AgentNPCState


# NPC行为工具定义（供LLM理解和调用）
NPC_TOOLS = [
    {
        "name": "move",
        "description": "移动到指定位置。用于前往某个地点，如救火、逃跑、工作等。",
        "parameters": {
            "destination": "目标位置名称（如：教堂、酒馆、铁匠铺等）",
            "reason": "移动的原因",
            "urgency": "紧急程度：normal（普通）、urgent（紧急）、emergency（非常紧急）"
        },
        "example": '{"tool": "move", "destination": "教堂", "reason": "听说教堂起火了，要去帮忙救火", "urgency": "emergency"}'
    },
    {
        "name": "speak",
        "description": "发表言论或与他人对话。用于表达想法、警告他人、求助等。",
        "parameters": {
            "content": "说话的内容",
            "target": "说话对象（可选，不填则是自言自语或对周围所有人说）",
            "emotion": "说话时的情绪：calm（平静）、worried（担忧）、scared（害怕）、angry（愤怒）、excited（激动）"
        },
        "example": '{"tool": "speak", "content": "天哪，教堂着火了！大家快来帮忙！", "emotion": "scared"}'
    },
    {
        "name": "work",
        "description": "进行与职业相关的工作活动。",
        "parameters": {
            "activity": "具体的工作内容",
            "duration": "预计持续时间（分钟）"
        },
        "example": '{"tool": "work", "activity": "打铁锻造武器", "duration": 60}'
    },
    {
        "name": "help",
        "description": "帮助处理紧急事件或协助他人。",
        "parameters": {
            "target": "帮助的对象或事件",
            "action": "具体帮助行为"
        },
        "example": '{"tool": "help", "target": "教堂火灾", "action": "提水救火"}'
    },
    {
        "name": "observe",
        "description": "观察周围情况或特定事件，收集信息。",
        "parameters": {
            "target": "观察的目标",
            "reason": "观察的原因"
        },
        "example": '{"tool": "observe", "target": "教堂方向", "reason": "看看火势如何"}'
    },
    {
        "name": "alert",
        "description": "向他人发出警告或通知重要消息。",
        "parameters": {
            "message": "警告/通知的内容",
            "targets": "通知的对象（可以是all表示所有人）"
        },
        "example": '{"tool": "alert", "message": "教堂起火了！需要帮助！", "targets": "all"}'
    },
    {
        "name": "flee",
        "description": "逃离危险区域到安全地点。",
        "parameters": {
            "destination": "逃往的安全地点",
            "reason": "逃跑的原因"
        },
        "example": '{"tool": "flee", "destination": "村庄大门", "reason": "火势太大，需要撤离"}'
    },
    {
        "name": "continue",
        "description": "继续当前正在进行的活动，不做改变。",
        "parameters": {
            "reason": "继续当前活动的原因"
        },
        "example": '{"tool": "continue", "reason": "这件事与我无关，继续做我的事"}'
    }
]


class NPCAgentManager:
    """NPC Agent 管理器 - 管理所有NPC的状态和行为决策"""

    def __init__(self):
        self.npc_states: Dict[str, NPCState] = {}
        self.world_events: List[Dict[str, Any]] = []  # 活动中的世界事件
        self.location_adjacency = {
            "村庄大门": ["镇中心", "森林边缘"],
            "镇中心": ["村庄大门", "酒馆", "市场区", "教堂"],
            "酒馆": ["镇中心", "市场区"],
            "市场区": ["镇中心", "酒馆", "铁匠铺"],
            "铁匠铺": ["市场区", "工坊区"],
            "教堂": ["镇中心", "农田"],
            "工坊区": ["铁匠铺", "农田"],
            "农田": ["教堂", "工坊区", "森林边缘"],
            "森林边缘": ["村庄大门", "农田"]
        }
        self._init_default_npcs()

    def _init_default_npcs(self):
        """初始化默认NPC状态"""
        default_npcs = [
            NPCState("埃尔德·铁锤", "铁匠铺", "铁匠", "打铁"),
            NPCState("贝拉·欢笑", "酒馆", "酒馆老板娘", "打扫酒馆"),
            NPCState("西奥多·光明", "教堂", "牧师", "祈祷"),
            NPCState("玛格丽特·花语", "市场区", "花商", "整理花束"),
            NPCState("汉斯·巧手", "工坊区", "工匠", "制作工具"),
            NPCState("老农托马斯", "农田", "农夫", "耕作"),
        ]
        for npc in default_npcs:
            self.npc_states[npc.name] = npc

    def get_npc_state(self, npc_name: str) -> Optional[NPCState]:
        """获取NPC状态"""
        return self.npc_states.get(npc_name)

    def update_npc_location(self, npc_name: str, new_location: str, activity: str = None):
        """更新NPC位置"""
        if npc_name in self.npc_states:
            self.npc_states[npc_name].location = new_location
            if activity:
                self.npc_states[npc_name].current_activity = activity
            logger.info(f"NPC {npc_name} 移动到 {new_location}")

    def update_npc_activity(self, npc_name: str, activity: str, mood: str = None):
        """更新NPC活动状态"""
        if npc_name in self.npc_states:
            self.npc_states[npc_name].current_activity = activity
            if mood:
                self.npc_states[npc_name].mood = mood

    def add_action_to_history(self, npc_name: str, action: NPCAction):
        """添加行为到历史记录"""
        if npc_name in self.npc_states:
            self.npc_states[npc_name].action_history.append({
                "action": action.to_dict(),
                "timestamp": datetime.now().isoformat()
            })
            # 保留最近10条
            if len(self.npc_states[npc_name].action_history) > 10:
                self.npc_states[npc_name].action_history = \
                    self.npc_states[npc_name].action_history[-10:]

    def calculate_distance(self, loc1: str, loc2: str) -> int:
        """计算两个地点之间的距离（BFS）"""
        if loc1 == loc2:
            return 0

        visited = {loc1}
        queue = [(loc1, 0)]

        while queue:
            current, dist = queue.pop(0)
            for neighbor in self.location_adjacency.get(current, []):
                if neighbor == loc2:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return 999  # 不可达

    def get_path_to_location(self, from_loc: str, to_loc: str) -> List[str]:
        """获取从一个位置到另一个位置的路径"""
        if from_loc == to_loc:
            return [from_loc]

        visited = {from_loc}
        queue = [(from_loc, [from_loc])]

        while queue:
            current, path = queue.pop(0)
            for neighbor in self.location_adjacency.get(current, []):
                if neighbor == to_loc:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []  # 不可达

    def get_npcs_at_location(self, location: str) -> List[str]:
        """获取某位置的所有NPC"""
        return [name for name, state in self.npc_states.items()
                if state.location == location]

    def get_all_npc_states(self) -> Dict[str, Dict]:
        """获取所有NPC状态"""
        return {name: state.to_dict() for name, state in self.npc_states.items()}


def build_react_prompt(
    npc_name: str,
    npc_profile: Dict[str, str],
    npc_state: NPCState,
    event_context: Dict[str, Any],
    available_tools: List[Dict] = NPC_TOOLS
) -> str:
    """
    构建ReAct风格的提示词，让LLM决定NPC应该采取什么行动
    """

    # 构建工具描述
    tools_desc = "\n".join([
        f"- **{tool['name']}**: {tool['description']}\n  示例: {tool['example']}"
        for tool in available_tools
    ])

    # 事件信息
    event_info = event_context.get("event", {})
    event_content = event_info.get("content", "无特殊事件")
    event_location = event_info.get("location", "未知")
    event_phase = event_info.get("phase_description", "")

    # 距离信息
    distance = event_context.get("distance", 0)
    distance_desc = {
        0: "事件就在你眼前发生",
        1: "事件发生在相邻区域，你能听到动静",
        2: "事件发生在较远的地方，你听到了传言",
    }.get(distance, "事件发生在很远的地方")

    prompt = f"""你是艾伦谷世界中的NPC：{npc_name}

## 角色信息
- 职业：{npc_profile.get('profession', '村民')}
- 性格：{npc_profile.get('personality', '友好')}
- 背景：{npc_profile.get('background', '艾伦谷的居民')}
- 说话风格：{npc_profile.get('speaking_style', '朴实自然')}

## 当前状态
- 你的位置：{npc_state.location}
- 当前活动：{npc_state.current_activity}
- 当前情绪：{npc_state.mood}
- 体力状态：{int(npc_state.energy * 100)}%

## 正在发生的事件
- 事件内容：{event_content}
- 事件位置：{event_location}
- 事件阶段：{event_phase}
- 与你的距离：{distance_desc}

## 可用的行动工具
{tools_desc}

## 任务
请根据你的角色特点和当前情况，思考并决定要采取什么行动。

请按以下格式回复：

**思考过程：**
[分析当前情况，考虑你的角色会如何反应]

**决定的行动：**
```json
{{"tool": "工具名称", ...其他参数}}
```

**行动说明：**
[用1-2句话，以角色的口吻描述这个行动，或说出角色会说的话]

重要提示：
1. 如果是紧急事件（如火灾、攻击），相关职业的NPC应该优先响应
2. 牧师对教堂事件应该反应强烈
3. 考虑NPC之间的合作可能性
4. 不要做出不符合角色身份的行动
"""

    return prompt


def parse_react_response(response_text: str) -> Dict[str, Any]:
    """
    解析LLM的ReAct响应，提取行动信息
    """
    result = {
        "thinking": "",
        "action": None,
        "description": "",
        "raw_response": response_text
    }

    try:
        # 提取思考过程
        if "**思考过程：**" in response_text:
            thinking_start = response_text.find("**思考过程：**") + len("**思考过程：**")
            thinking_end = response_text.find("**决定的行动：**")
            if thinking_end > thinking_start:
                result["thinking"] = response_text[thinking_start:thinking_end].strip()

        # 提取JSON行动
        json_start = response_text.find("```json")
        if json_start != -1:
            json_start = response_text.find("{", json_start)
            json_end = response_text.find("}", json_start) + 1
            if json_end > json_start:
                json_str = response_text[json_start:json_end]
                result["action"] = json.loads(json_str)

        # 提取行动说明
        if "**行动说明：**" in response_text:
            desc_start = response_text.find("**行动说明：**") + len("**行动说明：**")
            result["description"] = response_text[desc_start:].strip()
            # 清理可能的多余内容
            if "\n\n" in result["description"]:
                result["description"] = result["description"].split("\n\n")[0]

    except Exception as e:
        logger.error(f"解析ReAct响应失败: {e}")

    return result


def create_action_from_tool_call(tool_call: Dict[str, Any]) -> NPCAction:
    """
    从工具调用创建NPCAction对象
    """
    tool_name = tool_call.get("tool", "continue")

    action_type_map = {
        "move": ActionType.MOVE,
        "speak": ActionType.SPEAK,
        "work": ActionType.WORK,
        "help": ActionType.HELP,
        "observe": ActionType.OBSERVE,
        "alert": ActionType.ALERT,
        "flee": ActionType.FLEE,
        "continue": ActionType.CONTINUE,
    }

    action_type = action_type_map.get(tool_name, ActionType.CONTINUE)

    # 根据不同工具类型设置参数
    if tool_name == "move":
        return NPCAction(
            action_type=action_type,
            target=tool_call.get("destination"),
            content=tool_call.get("reason", ""),
            priority=9 if tool_call.get("urgency") == "emergency" else 7,
            duration_minutes=5,  # 移动时间
            reason=tool_call.get("reason", "")
        )
    elif tool_name == "speak":
        return NPCAction(
            action_type=action_type,
            target=tool_call.get("target"),
            content=tool_call.get("content", ""),
            priority=5,
            duration_minutes=1,
            reason=f"情绪: {tool_call.get('emotion', 'calm')}"
        )
    elif tool_name == "help":
        return NPCAction(
            action_type=action_type,
            target=tool_call.get("target"),
            content=tool_call.get("action", "帮助"),
            priority=10,
            duration_minutes=30,
            reason="紧急救援"
        )
    elif tool_name == "alert":
        return NPCAction(
            action_type=action_type,
            target=tool_call.get("targets", "all"),
            content=tool_call.get("message", ""),
            priority=8,
            duration_minutes=2,
            reason="发出警报"
        )
    elif tool_name == "flee":
        return NPCAction(
            action_type=action_type,
            target=tool_call.get("destination"),
            content=tool_call.get("reason", ""),
            priority=10,
            duration_minutes=3,
            reason="逃离危险"
        )
    elif tool_name == "work":
        return NPCAction(
            action_type=action_type,
            content=tool_call.get("activity", "工作"),
            priority=4,
            duration_minutes=tool_call.get("duration", 60),
            reason="进行日常工作"
        )
    elif tool_name == "observe":
        return NPCAction(
            action_type=action_type,
            target=tool_call.get("target"),
            content=tool_call.get("reason", ""),
            priority=3,
            duration_minutes=5,
            reason="观察情况"
        )
    else:
        return NPCAction(
            action_type=ActionType.CONTINUE,
            content=tool_call.get("reason", "继续当前活动"),
            priority=1,
            duration_minutes=15,
            reason=tool_call.get("reason", "")
        )


# 全局NPC Agent管理器实例
npc_agent_manager = NPCAgentManager()
