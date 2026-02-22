# -*- coding: utf-8 -*-
"""
艾伦谷世界观设定
Eldoria Valley - A Medieval Fantasy Village World

该模块现在作为 data/ 目录配置的包装器，
提供对旧代码的向后兼容性。
"""

from data import get_data_loader, WORLD_LORE, NPC_TEMPLATES, ENVIRONMENTAL_EVENTS

# 重新导出以保持向后兼容
__all__ = [
    'WORLD_LORE',
    'NPC_TEMPLATES',
    'ENVIRONMENTAL_EVENTS',
    'BEHAVIOR_WEIGHTS',
    'get_world_lore',
    'get_npc_templates',
    'get_environmental_events',
    'get_behavior_weights',
]


def get_world_lore():
    """获取世界设定"""
    loader = get_data_loader()
    return loader.get_world_settings()


def get_npc_templates():
    """获取NPC模板"""
    loader = get_data_loader()
    return loader.get_npc_templates()


def get_environmental_events():
    """获取环境事件"""
    loader = get_data_loader()
    events = loader.get_events()
    return {
        'weather': events.get('weather', []),
        'seasons': events.get('seasons', []),
        'town_events': [e['name'] for e in events.get('town_events', [])],
        'personal_events': [e['name'] for e in events.get('personal_events', [])]
    }


def get_behavior_weights():
    """获取行为权重配置"""
    loader = get_data_loader()
    return loader.get_behavior_weights()


# 行为决策权重系统（默认值，如果配置文件不存在则使用）
BEHAVIOR_WEIGHTS = {
    "work_priority": {
        "high": ["工作时间严格遵守", "职业技能优先"],
        "medium": ["工作与个人时间平衡", "偶尔偷懒"],
        "low": ["工作可有可无", "追求个人兴趣"]
    },

    "social_interaction": {
        "high": ["主动社交", "乐于助人", "喜欢聚会"],
        "medium": ["选择性社交", "维持必要关系"],
        "low": ["独来独往", "避免不必要接触"]
    },

    "goal_orientation": {
        "high": ["目标驱动", "长期规划", "自律"],
        "medium": ["适度规划", "平衡短期享乐"],
        "low": ["随遇而安", "享受当下"]
    },

    "emotional_response": {
        "high": ["情绪化表达", "易受影响"],
        "medium": ["适度表达", "理性控制"],
        "low": ["情绪稳定", "内敛"]
    }
}
