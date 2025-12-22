"""
项目常量定义
统一管理 Enum 和其他常量，避免散落在各个模块中
"""

from enum import Enum


class ReasoningMode(Enum):
    """推理模式枚举"""
    NORMAL = "normal"           # 正常推理
    DEEP = "deep"              # 深度思考
    EMOTIONAL = "emotional"    # 情感驱动
    STRATEGIC = "strategic"    # 战略思考
    REACTIVE = "reactive"      # 反应式决策


class NPCAction(Enum):
    """NPC行动枚举 - 统一定义所有可能的行为"""
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
            "移动": "你正在移动。你的回应应该匆忙、简短。"
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
            "移动": "你正在移动，回应应该匆忙简短"
        }
        return descriptions.get(self.value, "你可以正常回应")


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


# 任务相关常量
TASK_MIN_PROGRESS_STEP = 0.05  # 最小任务进度步长（5%）
TASK_PROGRESS_CHECK_INTERVAL = 30  # 任务进度检查间隔（分钟）
TASK_LLM_RECHECK_THRESHOLD = 0.2  # 任务进度 LLM 重新评估阈值（20% 时重新评估）

# 活动优先级（用于冲突检查）
ACTIVITY_PRIORITY_CRITICAL = 100   # 紧急（如救人）
ACTIVITY_PRIORITY_IMPORTANT = 50   # 重要（如工作、学习）
ACTIVITY_PRIORITY_NORMAL = 20      # 正常（如吃饭、社交）
ACTIVITY_PRIORITY_LOW = 5          # 低优先级（如休息、思考）
ACTIVITY_PRIORITY_SLEEP = 0        # 睡眠（最低，不可打扰）

# 状态检查阈值
ENERGY_CRITICAL_THRESHOLD = 0.2    # 能量紧急值（20%）
HUNGER_CRITICAL_THRESHOLD = 0.9    # 饥饿紧急值（90%）
FATIGUE_CRITICAL_THRESHOLD = 0.95  # 疲劳紧急值（95%）
SLEEP_FORCED_THRESHOLD = 0.98      # 强制睡眠阈值（98%）
# L1 决策层 - 活动惯性值（0-100，越高越难被打断）
ACTIVITY_INERTIA = {
    NPCAction.SLEEP: 95,       # 睡眠最难被打断
    NPCAction.EAT: 85,         # 吃饭生存性强，不易被打断
    NPCAction.WORK: 65,        # 工作相对专注
    NPCAction.REST: 50,        # 休息容易被打扰
    NPCAction.SOCIALIZE: 30,   # 社交最容易被打扰
    NPCAction.TRAVEL: 45,      # 移动中等
    NPCAction.THINK: 35,       # 思考中等
    NPCAction.PRAY: 70,        # 祈祷较难被打扰
    NPCAction.LEARN: 55,       # 学习中等专注
    NPCAction.CREATE: 65,      # 创造相对专注
    NPCAction.OBSERVE: 40,     # 观察中等
    NPCAction.HELP_OTHERS: 60  # 帮助他人中等
}