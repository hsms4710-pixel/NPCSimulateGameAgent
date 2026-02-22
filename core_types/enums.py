# -*- coding: utf-8 -*-
"""
统一枚举定义
===========

集中管理所有枚举类型，避免多处重复定义导致的不一致问题。

包含：
- NPCAction: NPC行为枚举（合并了NPCActivity）
- Emotion: 情感状态枚举
- ReasoningMode: 推理模式枚举
- AgentState: Agent状态枚举
- MessageType: 消息类型枚举（合并两个版本）
- MessagePriority: 消息优先级枚举
- EventPriority: 事件优先级枚举
- NPCRole: NPC角色枚举
- MemoryType: 记忆类型枚举
- TaskStatus: 任务状态枚举
"""

from enum import Enum, IntEnum


class NPCAction(Enum):
    """
    NPC行动枚举 - 统一定义所有可能的行为

    合并了原有的 NPCAction (constants.py) 和 NPCActivity (npc_lifecycle.py)
    """
    # 基础活动
    WORK = "工作"
    REST = "休息"
    EAT = "吃饭"
    SLEEP = "睡觉"
    SOCIALIZE = "社交"
    TRAVEL = "移动"
    THINK = "思考"
    PRAY = "祈祷"
    LEARN = "学习"
    CREATE = "创造"
    OBSERVE = "观察"
    HELP_OTHERS = "帮助他人"

    # 扩展活动 (来自 NPCActivity)
    WAKING_UP = "起床"
    IDLE = "空闲"

    @property
    def ai_instruction(self) -> str:
        """获取AI指令版本的活动约束"""
        instructions = {
            "睡觉": """重要：你正在深度睡眠中，除非发生极端紧急情况（如房子着火、有人生命危险），否则你不会醒来。
                如果有人试图叫醒你，你的回应应该是模糊的、睡意朦胧的，表示你不想被打扰，继续睡觉。
                不要表现出清醒或警觉的状态。""",
            "工作": "你正在专注工作。你的回应应该显示你正在忙于工作，可能有些不耐烦被打断。",
            "休息": "你正在休息。你的回应应该平静、放松，愿意进行简短对话。",
            "社交": "你正在社交。你的回应应该友好、开放，愿意进行对话。",
            "观察": "你正在观察周围环境。你的回应应该警惕、小心。",
            "帮助他人": "你正在帮助别人。你的回应应该显示出关心和责任感。",
            "吃饭": "你正在吃饭。你的回应应该显示出你正在用餐，可能有些匆忙。",
            "祈祷": "你正在祈祷。你的回应应该虔诚、平静。",
            "学习": "你正在学习。你的回应应该专注、认真。",
            "思考": "你正在思考。你的回应应该深沉、专注。",
            "创造": "你正在创造。你的回应应该富有灵感、专注。",
            "移动": "你正在移动。你的回应应该匆忙、简短。",
            "起床": "你刚刚醒来，还有些迷糊。你的回应应该带有睡意。",
            "空闲": "你当前没有特定活动。你可以自由选择下一步行动。"
        }
        return instructions.get(self.value, "")

    @property
    def ui_description(self) -> str:
        """获取UI显示版本的活动约束"""
        descriptions = {
            "睡觉": "你正在睡觉，只能给出迷糊的、睡意朦胧的回应，除非发生极端紧急情况",
            "工作": "你正在专注工作，回应应该显示出你正在忙碌，可能有些不耐烦",
            "休息": "你正在休息，回应应该平静、放松",
            "社交": "你正在社交，回应应该友好、开放",
            "观察": "你正在观察周围环境，回应应该警惕、小心",
            "帮助他人": "你正在帮助别人，回应应该显示出关心和责任感",
            "吃饭": "你正在吃饭，回应应该显示出用餐状态",
            "祈祷": "你正在祈祷，回应应该虔诚平静",
            "学习": "你正在学习，回应应该专注认真",
            "思考": "你正在思考，回应应该深沉专注",
            "创造": "你正在创造，回应应该富有灵感",
            "移动": "你正在移动，回应应该匆忙简短",
            "起床": "你刚刚醒来，带有睡意",
            "空闲": "你当前没有特定活动"
        }
        return descriptions.get(self.value, "你可以正常回应")

    @property
    def inertia(self) -> int:
        """获取活动惯性值（0-100，越高越难被打断）"""
        inertia_map = {
            "睡觉": 95,
            "吃饭": 85,
            "工作": 65,
            "休息": 50,
            "社交": 30,
            "移动": 45,
            "思考": 35,
            "祈祷": 70,
            "学习": 55,
            "创造": 65,
            "观察": 40,
            "帮助他人": 60,
            "起床": 40,
            "空闲": 10
        }
        return inertia_map.get(self.value, 30)


class Emotion(Enum):
    """情感状态枚举 - 统一定义所有可能的情感状态"""
    ECSTATIC = "狂喜"
    HAPPY = "高兴"
    CONTENT = "满足"
    CALM = "平静"
    WORRIED = "担心"
    SAD = "悲伤"
    ANGRY = "愤怒"
    FRUSTRATED = "沮丧"
    EXHAUSTED = "疲惫"
    EXCITED = "兴奋"
    ANXIOUS = "焦虑"
    FEARFUL = "恐惧"
    CURIOUS = "好奇"
    CONFUSED = "困惑"
    GRATEFUL = "感激"


class ReasoningMode(Enum):
    """推理模式枚举"""
    FAST = "快速"          # 快速推理
    NORMAL = "正常"        # 正常推理
    DEEP = "深度"          # 深度思考
    EXHAUSTIVE = "详尽"    # 详尽推理
    EMOTIONAL = "情感"     # 情感驱动
    STRATEGIC = "战略"     # 战略思考
    REACTIVE = "反应"      # 反应式决策


class AgentState(Enum):
    """Agent状态枚举"""
    IDLE = "空闲"          # 空闲
    RUNNING = "运行中"      # 运行中
    PAUSED = "已暂停"       # 已暂停
    STOPPED = "已停止"      # 已停止
    ERROR = "错误"          # 错误状态


class MessageType(Enum):
    """
    消息类型枚举

    合并了:
    - message_bus.py 中的 MessageType
    - world_event_manager.py 中的 MessageType
    """
    # 世界事件
    WORLD_EVENT = "世界事件"       # 全局世界事件
    ZONE_EVENT = "区域事件"        # 区域事件
    SPATIAL_EVENT = "空间事件"     # 空间事件（有范围衰减）

    # NPC通信
    NPC_SPEECH = "NPC说话"         # NPC说话（可被其他NPC听到）
    NPC_ACTION = "NPC行为"         # NPC行为（可被其他NPC观察到）
    NPC_EMOTION = "NPC情绪"        # NPC情绪变化

    # 社交交互
    GREETING = "打招呼"            # 打招呼
    CONVERSATION = "对话"          # 对话
    GOSSIP = "传闻"                # 传闻/八卦
    REQUEST = "请求"               # 请求帮助
    RESPONSE = "回应"              # 回应
    SOCIAL_UPDATE = "社交更新"     # 社交关系更新

    # 观察与紧急
    OBSERVATION = "观察"           # 观察到的事件
    EMERGENCY = "紧急"             # 紧急事件（无范围限制）

    # 系统消息
    TIME_CHANGE = "时间变化"       # 时间变化
    WEATHER_CHANGE = "天气变化"    # 天气变化


class MessagePriority(IntEnum):
    """
    消息优先级枚举

    使用 IntEnum 便于比较和排序
    """
    LOW = 0        # 低优先级
    NORMAL = 1     # 普通优先级
    HIGH = 2       # 高优先级
    URGENT = 3     # 紧急优先级
    CRITICAL = 4   # 危急优先级


class EventPriority(IntEnum):
    """
    事件优先级枚举

    与 MessagePriority 值域统一
    """
    LOW = 1        # 低优先级
    MEDIUM = 2     # 中等优先级
    HIGH = 3       # 高优先级
    CRITICAL = 4   # 危急（生死攸关）


class NPCRole(Enum):
    """NPC在事件中的角色"""
    RESCUER = "rescuer"         # 救援者：直接参与救援
    HELPER = "helper"           # 帮助者：协助救援
    ALERTER = "alerter"         # 通知者：负责通知他人
    OBSERVER = "observer"       # 观察者：关注事件
    EVACUEE = "evacuee"         # 撤离者：需要撤离
    VICTIM = "victim"           # 受害者：事件受害者
    PARTICIPANT = "participant" # 参与者：一般参与
    UNAFFECTED = "unaffected"   # 不受影响


class MemoryType(Enum):
    """记忆类型枚举"""
    GENERAL = "一般"          # 一般记忆
    DIALOGUE = "对话"         # 对话记忆
    EVENT = "事件"            # 事件记忆
    OBSERVATION = "观察"      # 观察记忆
    EMOTIONAL = "情感"        # 情感记忆
    KNOWLEDGE = "知识"        # 知识记忆
    RELATIONSHIP = "关系"     # 关系记忆
    SKILL = "技能"            # 技能记忆


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "待处理"        # 待处理
    ACTIVE = "进行中"         # 进行中
    COMPLETED = "已完成"      # 已完成
    FAILED = "失败"           # 失败
    PAUSED = "已暂停"         # 已暂停
    CANCELLED = "已取消"      # 已取消


# ==================== 兼容性别名 ====================
# 为了向后兼容，提供旧名称的别名

# NPCActivity 别名 (来自 npc_lifecycle.py)
NPCActivity = NPCAction

# 活动惯性映射 (来自 constants.py ACTIVITY_INERTIA)
ACTIVITY_INERTIA = {action: action.inertia for action in NPCAction}

# 活动优先级常量 (来自 constants.py)
ACTIVITY_PRIORITY_CRITICAL = 100
ACTIVITY_PRIORITY_IMPORTANT = 50
ACTIVITY_PRIORITY_NORMAL = 20
ACTIVITY_PRIORITY_LOW = 5
ACTIVITY_PRIORITY_SLEEP = 0

# 状态检查阈值 (来自 constants.py)
ENERGY_CRITICAL_THRESHOLD = 0.2
HUNGER_CRITICAL_THRESHOLD = 0.9
FATIGUE_CRITICAL_THRESHOLD = 0.95
SLEEP_FORCED_THRESHOLD = 0.98

# 任务相关常量 (来自 constants.py)
TASK_MIN_PROGRESS_STEP = 0.05
TASK_PROGRESS_CHECK_INTERVAL = 30
TASK_LLM_RECHECK_THRESHOLD = 0.2
