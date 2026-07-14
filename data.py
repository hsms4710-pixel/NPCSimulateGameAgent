# -*- coding: utf-8 -*-
"""
统一世界数据源 — 所有世界设定的唯一来源
包含：世界位置、NPC模板、环境事件、经济系统配置
"""

# ========== 世界位置 ==========
WORLD_LORE = {
    "name": "银溪镇",
    "description": "一个位于边境的中世纪奇幻小镇，因银色溪流穿过而得名",
}

WORLD_LOCATIONS = {
    "镇中心广场": {
        "type": "公共区域",
        "description": "银溪镇的中心广场，喷泉旁立着锻造者艾隆的铜像",
        "npcs": [],
        "connections": ["铁匠铺", "银溪旅店", "锻造者圣堂", "市场摊位", "镇公所"],
        "services": ["休息", "社交"],
        "position": [0, 0],
    },
    "铁匠铺": {
        "type": "工业区",
        "description": "托林·石砧的铁匠铺，炉火通明，锤声不断",
        "npcs": ["托林·石砧"],
        "connections": ["镇中心广场"],
        "services": ["工作", "购物"],
        "owner": "托林·石砧",
        "position": [25, 5],
    },
    "银溪旅店": {
        "type": "商业区",
        "description": "艾尔莎·溪光经营的百年旅店，镇上最热闹的社交场所",
        "npcs": ["艾尔莎·溪光", "马库斯·晨星"],
        "connections": ["镇中心广场"],
        "services": ["饮食", "社交", "休息"],
        "owner": "艾尔莎·溪光",
        "position": [-25, 5],
    },
    "锻造者圣堂": {
        "type": "宗教区",
        "description": "供奉锻造者艾隆的圣堂，塞拉斯·铁砧主持于此",
        "npcs": ["塞拉斯·铁砧"],
        "connections": ["镇中心广场"],
        "services": ["休息", "社交"],
        "owner": "塞拉斯·铁砧",
        "position": [0, -25],
    },
    "林边小屋": {
        "type": "居民区",
        "description": "伊莱雅·暮影的草药师小屋，位于镇外森林边缘",
        "npcs": ["伊莱雅·暮影"],
        "connections": ["镇中心广场"],
        "services": ["购物", "社交"],
        "owner": "伊莱雅·暮影",
        "position": [-30, -20],
    },
    "镇公所": {
        "type": "公共区域",
        "description": "哈罗德·铁橡办公的镇公所，也是治安中心",
        "npcs": ["哈罗德·铁橡"],
        "connections": ["镇中心广场", "镇门哨塔"],
        "services": ["社交"],
        "owner": "哈罗德·铁橡",
        "position": [10, 15],
    },
    "镇门哨塔": {
        "type": "防御区",
        "description": "格雷戈尔·风锤驻守的镇门哨塔，俯瞰进出要道",
        "npcs": ["格雷戈尔·风锤"],
        "connections": ["镇公所"],
        "services": ["社交"],
        "owner": "格雷戈尔·风锤",
        "position": [20, 30],
    },
    "花语面包房": {
        "type": "商业区",
        "description": "莉莉安·花语的面包房，每天清晨飘出麦香",
        "npcs": ["莉莉安·花语"],
        "connections": ["镇中心广场"],
        "services": ["饮食", "购物"],
        "owner": "莉莉安·花语",
        "position": [-15, 10],
    },
    "月华裁缝铺": {
        "type": "商业区",
        "description": "伊莎贝拉·月华的裁缝铺，陈列着精美织物",
        "npcs": ["伊莎贝拉·月华"],
        "connections": ["镇中心广场"],
        "services": ["购物"],
        "owner": "伊莎贝拉·月华",
        "position": [-10, -10],
    },
    "市场摊位": {
        "type": "商业区",
        "description": "镇中心旁的露天市场，旅商和本地人交易之所",
        "npcs": [],
        "connections": ["镇中心广场"],
        "services": ["购物", "社交"],
        "position": [5, -5],
    },
}

# ========== NPC 模板 ==========
NPC_TEMPLATES = {
    "托林·石砧": {
        "name": "托林·石砧",
        "profession": "铁匠",
        "personality": {"openness": 0.4, "conscientiousness": 0.9, "extraversion": 0.3, "agreeableness": 0.6, "neuroticism": 0.4},
        "background": "银溪镇第三代铁匠，祖父是首批拓荒者。二十年前父亲在西森林寻找矿石时丧生，自此独自撑起铺子。父亲留下的半本银溪秘铁笔记是他最深藏的秘密。",
        "location": "铁匠铺",
        "schedule": {"morning": "打铁", "afternoon": "接待客人", "evening": "去旅店喝酒"},
    },
    "艾尔莎·溪光": {
        "name": "艾尔莎·溪光",
        "profession": "旅店老板",
        "personality": {"openness": 0.7, "conscientiousness": 0.7, "extraversion": 0.8, "agreeableness": 0.6, "neuroticism": 0.5},
        "background": "继承了家族百年银溪旅店。二十年前丈夫在山区收购毛皮时失踪，此后独自撑起旅店。她熟知镇上每户人家的秘密。",
        "location": "银溪旅店",
        "schedule": {"morning": "准备酒菜", "afternoon": "接待客人", "evening": "听诗人弹琴"},
    },
    "塞拉斯·铁砧": {
        "name": "塞拉斯·铁砧",
        "profession": "祭司",
        "personality": {"openness": 0.5, "conscientiousness": 0.8, "extraversion": 0.4, "agreeableness": 0.7, "neuroticism": 0.3},
        "background": "年轻时是石匠学徒，三十年前修缮圣堂时被石块砸中，昏迷中见到锻造者艾隆的幻象，苏醒后成为祭司。二十年来是圣堂首席祭司。",
        "location": "锻造者圣堂",
        "schedule": {"morning": "晨祷", "afternoon": "接待信徒", "evening": "研读经文"},
    },
    "伊莱雅·暮影": {
        "name": "伊莱雅·暮影",
        "profession": "草药师",
        "personality": {"openness": 0.8, "conscientiousness": 0.6, "extraversion": 0.3, "agreeableness": 0.6, "neuroticism": 0.4},
        "background": "来自迷雾山脉的古老精灵聚落。五十年前族人因魔法失衡被迫迁徙，她选择留在人类世界。被银溪镇的宁静吸引，以草药师身份融入镇民生活。",
        "location": "林边小屋",
        "schedule": {"morning": "采集药草", "afternoon": "研磨药剂", "evening": "观察星象"},
    },
    "哈罗德·铁橡": {
        "name": "哈罗德·铁橡",
        "profession": "镇长",
        "personality": {"openness": 0.4, "conscientiousness": 0.9, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.6},
        "background": "年轻时是商队护卫，三十年前回到故乡成为治安官，十五年前兼任镇长。坚信秩序与传统是小镇安宁的基石。与塞拉斯是表亲但关系微妙。",
        "location": "镇公所",
        "schedule": {"morning": "处理公务", "afternoon": "巡视镇子", "evening": "听取汇报"},
    },
    "格雷戈尔·风锤": {
        "name": "格雷戈尔·风锤",
        "profession": "卫队长",
        "personality": {"openness": 0.3, "conscientiousness": 0.8, "extraversion": 0.5, "agreeableness": 0.4, "neuroticism": 0.5},
        "background": "从南方边境退役的佣兵，十年前流落至银溪镇被哈罗德收留。凭借战斗经验重组了镇卫队。对伊莱雅的精灵身份始终警惕。",
        "location": "镇门哨塔",
        "schedule": {"morning": "训练卫兵", "afternoon": "巡逻", "evening": "值守哨塔"},
    },
    "莉莉安·花语": {
        "name": "莉莉安·花语",
        "profession": "面包师",
        "personality": {"openness": 0.7, "conscientiousness": 0.6, "extraversion": 0.9, "agreeableness": 0.8, "neuroticism": 0.3},
        "background": "银溪镇本地人，从母亲那里继承了烘焙手艺。她的面包房是镇上最受欢迎的聚会场所。与艾尔莎是多年闺蜜，旅店的面包全由她供应。",
        "location": "花语面包房",
        "schedule": {"morning": "烘焙面包", "afternoon": "售卖糕点", "evening": "去旅店聊天"},
    },
    "马库斯·晨星": {
        "name": "马库斯·晨星",
        "profession": "吟游诗人",
        "personality": {"openness": 0.9, "conscientiousness": 0.4, "extraversion": 0.8, "agreeableness": 0.7, "neuroticism": 0.4},
        "background": "来自南方大城的流浪吟游诗人，三年前来到银溪镇后留在银溪旅店。收集各地传说和故事，用琴声和诗歌换取食宿。对伊莱雅的精灵身份充满好奇。",
        "location": "银溪旅店",
        "schedule": {"morning": "收集故事", "afternoon": "创作歌谣", "evening": "弹琴表演"},
    },
    "伊莎贝拉·月华": {
        "name": "伊莎贝拉·月华",
        "profession": "裁缝",
        "personality": {"openness": 0.6, "conscientiousness": 0.8, "extraversion": 0.4, "agreeableness": 0.7, "neuroticism": 0.4},
        "background": "从北方城市搬来的裁缝，五年前因失败婚姻来到银溪镇重新开始。与伊莱雅关系友好，经常从精灵女士那里获取天然染料灵感。",
        "location": "月华裁缝铺",
        "schedule": {"morning": "整理布料", "afternoon": "缝制衣物", "evening": "研究染料"},
    },
}

# ========== 环境事件 ==========
ENVIRONMENTAL_EVENTS = {
    "weather": ["晴天", "阴天", "小雨", "大风", "雾气弥漫"],
    "seasons": ["春", "夏", "秋", "冬"],
    "town_events": ["集市日", "节日庆典", "旅行商人到访", "锻造者祈福仪式"],
    "personal_events": ["偶遇友人", "发现新事物", "回忆往事", "听到传闻"],
}

# ========== 经济系统配置 ==========
ECONOMY_CONFIG = {
    "currency": "银币",
    "initial_player_gold": 50,
    "items": {
        "面包": {"price": 2, "type": "food", "effect": {"hunger": -20}},
        "麦酒": {"price": 5, "type": "drink", "effect": {"hunger": -10, "mood": 10}},
        "铁器": {"price": 30, "type": "tool", "effect": {}},
        "草药": {"price": 8, "type": "medicine", "effect": {"health": 15}},
        "衣物": {"price": 20, "type": "clothing", "effect": {"mood": 5}},
    },
}


class DataLoader:
    """统一数据加载器"""

    def get_world_settings(self):
        return WORLD_LORE

    def get_world_locations(self):
        return WORLD_LOCATIONS

    def get_npc_templates(self):
        return NPC_TEMPLATES

    def get_events(self):
        return {
            "weather": [{"name": w} for w in ENVIRONMENTAL_EVENTS["weather"]],
            "seasons": [{"name": s} for s in ENVIRONMENTAL_EVENTS["seasons"]],
            "town_events": [{"name": e, "description": ""} for e in ENVIRONMENTAL_EVENTS["town_events"]],
            "personal_events": [{"name": e, "description": ""} for e in ENVIRONMENTAL_EVENTS["personal_events"]],
        }

    def get_behavior_weights(self):
        return {
            "work_priority": {"high": ["工作时间严格遵守"], "medium": ["工作与个人时间平衡"], "low": ["追求个人兴趣"]},
            "social_interaction": {"high": ["主动社交"], "medium": ["选择性社交"], "low": ["独来独往"]},
            "goal_orientation": {"high": ["目标驱动"], "medium": ["适度规划"], "low": ["随遇而安"]},
            "emotional_response": {"high": ["情绪化表达"], "medium": ["适度表达"], "low": ["情绪稳定"]},
        }

    def get_all_npcs(self):
        result = {}
        for name, tpl in NPC_TEMPLATES.items():
            result[name] = {
                "name": name,
                "profession": tpl.get("profession", ""),
                "personality": tpl.get("personality", {}),
                "background": tpl.get("background", ""),
                "location": tpl.get("location", ""),
                "daily_schedule": tpl.get("schedule", {}),
            }
        return result

    def get_economy_config(self):
        return ECONOMY_CONFIG


def get_data_loader():
    return DataLoader()
