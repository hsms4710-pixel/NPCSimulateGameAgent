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
    """NPC行动枚举（已在 npc_system.py 中定义，此处保留备份）"""
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


class Emotion(Enum):
    """情感状态枚举（已在 npc_system.py 中定义，此处保留备份）"""
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
