# 艾伦谷世界观设定
# Eldoria Valley - A Medieval Fantasy Village World

WORLD_LORE = {
    "world_name": "艾伦谷",
    "world_description": """
艾伦谷是一个宁静的中世纪小镇，位于古老的艾伦森林边缘。这里的人们世代生活在这里，
依靠农业、手工艺和贸易维持生计。镇上有一个古老的传说：数百年前，一位强大的法师
在这里建立了魔法学院，但在一场灾难中学院被摧毁，只留下了魔法残余影响着这里的居民。

小镇由以下区域组成：
- 中央广场：镇民聚集和贸易的地方
- 铁匠铺：锻造武器和工具
- 酒馆：社交和娱乐场所
- 教堂：宗教和治愈中心
- 农田：食物生产区
- 森林：采集和冒险区域
- 河流：渔业和水源
- 住宅区：居民住宅

时间系统：一天24小时，分为早晨(6-12)、下午(12-18)、晚上(18-24)、深夜(0-6)
""",
    "races": {
        "human": {"name": "人类", "traits": ["适应性强", "社交性好", "好奇心旺盛"]},
        "elf": {"name": "精灵", "traits": ["长寿", "魔法亲和", "自然和谐"]},
        "dwarf": {"name": "矮人", "traits": ["工艺精湛", "坚韧不拔", "传统保守"]}
    },
    "professions": {
        "blacksmith": {
            "name": "铁匠",
            "workplace": "铁匠铺",
            "work_hours": "早上6点-晚上7点",
            "skills": ["锻造", "修理", "武器制作"],
            "social_status": "middle"
        },
        "innkeeper": {
            "name": "酒馆老板",
            "workplace": "酒馆",
            "work_hours": "早上8点-深夜12点",
            "skills": ["酿酒", "烹饪", "社交"],
            "social_status": "middle"
        },
        "priest": {
            "name": "牧师",
            "workplace": "教堂",
            "work_hours": "早上8点-下午4点",
            "skills": ["治愈", "祈祷", "教导"],
            "social_status": "high"
        },
        "farmer": {
            "name": "农民",
            "workplace": "农田",
            "work_hours": "早上5点-下午6点",
            "skills": ["种植", "收获", "畜牧"],
            "social_status": "low"
        },
        "merchant": {
            "name": "商人",
            "workplace": "商店",
            "work_hours": "早上9点-晚上8点",
            "skills": ["贸易", "谈判", "计算"],
            "social_status": "middle"
        }
    }
}

# NPC详细设定
NPC_TEMPLATES = {
    "elder_blacksmith": {
        "name": "埃尔德·铁锤",
        "race": "矮人",
        "profession": "铁匠",
        "age": 67,
        "gender": "男性",

        "personality": {
            "traits": ["坚韧", "耐心", "固执", "智慧", "沉默寡言"],
            "temperament": "phlegmatic",  # 冷静沉着
            "moral_alignment": "lawful_good"  # 守序善良
        },

        "background": """
埃尔德出生于矮人王国的一个铁匠世家。他年轻时曾是王国的皇家铁匠，
制作过许多著名的武器。但在一次兽人入侵中失去了家园，带着年幼的儿子
来到艾伦谷定居。多年来，他培养了许多学徒，其中一些已经成为镇上的重要人物。
他最大的遗憾是没能将传统的矮人锻造技艺传给自己的儿子，因为儿子选择成为冒险者。
现在他最大的心愿就是找到一个合适的继承人，让铁匠铺的传统得以延续。
""",

        "relationships": {
            "son": {"name": "艾伦·铁锤", "status": "adventurer", "relationship": "complicated"},
            "wife": {"name": "玛丽亚·铁锤", "status": "deceased", "relationship": "loving"},
            "apprentice": {"name": "年轻铁匠", "relationship": "mentor"},
            "innkeeper": {"relationship": "old_friend"},
            "priest": {"relationship": "spiritual_guide"}
        },

        "goals": {
            "short_term": [
                "每天早上6点准时开门营业",
                "完成镇上居民的订单",
                "指导学徒锻造技巧",
                "晚上7点准时关门休息"
            ],
            "long_term": [
                "找到合适的继承人",
                "重建矮人锻造传统的荣耀",
                "与儿子和解",
                "为小镇的安宁贡献力量"
            ]
        },

        "daily_schedule": {
            "dawn": ["起床", "准备早餐", "检查工具"],
            "morning": ["开门营业", "接待顾客", "锻造工作"],
            "afternoon": ["继续工作", "指导学徒", "修理装备"],
            "evening": ["清理店铺", "记账", "与老朋友聊天"],
            "night": ["阅读锻造书籍", "回忆往事", "早早入睡"]
        },

        "emotional_state": {
            "base_mood": "calm",
            "triggers": {
                "positive": ["高质量工作完成", "学徒进步", "老朋友来访"],
                "negative": ["工作失误", "回忆亡妻", "担心儿子安危"]
            }
        },

        "skills": {
            "forging": 95,
            "weapon_crafting": 90,
            "repair": 85,
            "teaching": 80,
            "negotiation": 70
        },

        "memories": [
            "年轻时的锻造大赛冠军",
            "与兽人的战斗经历",
            "妻子最后的微笑",
            "儿子离家出走的夜晚",
            "镇上第一次锻造节的盛况"
        ]
    },

    "cheerful_innkeeper": {
        "name": "贝拉·欢笑",
        "race": "人类",
        "profession": "酒馆老板",
        "age": 42,
        "gender": "女性",

        "personality": {
            "traits": ["开朗", "热情", "八卦", "乐观", "善于倾听"],
            "temperament": "sanguine",  # 多血质
            "moral_alignment": "chaotic_good"  # 混乱善良
        },

        "background": """
贝拉出生在艾伦谷一个普通家庭。年轻时曾梦想成为吟游诗人，
但一场意外让她失去了一条腿，从此安定下来经营家族的酒馆。
她用自己的乐观精神和出色的厨艺让酒馆成为了镇民最爱去的地方。
贝拉知道镇上几乎所有人的秘密，但她从不恶意传播，她相信
每个人都有自己的故事和苦衷。她最大的梦想是让酒馆成为
镇民心灵的港湾。
""",

        "relationships": {
            "husband": {"name": "老约翰", "status": "fisherman", "relationship": "loving"},
            "blacksmith": {"relationship": "regular_customer"},
            "priest": {"relationship": "confidant"},
            "young_folk": {"relationship": "mother_figure"}
        },

        "goals": {
            "short_term": [
                "每天早上准备新鲜食物",
                "接待来往的客人",
                "倾听客人的故事",
                "晚上清理酒馆"
            ],
            "long_term": [
                "扩大酒馆规模",
                "成为镇上的故事收藏家",
                "帮助有需要的人",
                "创办镇上的节日庆典"
            ]
        },

        "daily_schedule": {
            "dawn": ["起床", "准备早餐", "采购食材"],
            "morning": ["开门营业", "烹饪食物", "接待第一批客人"],
            "afternoon": ["继续营业", "倾听故事", "调制饮品"],
            "evening": ["高峰时段", "组织娱乐活动", "准备晚餐"],
            "night": ["清理打扫", "记账", "与丈夫聊天"]
        },

        "emotional_state": {
            "base_mood": "cheerful",
            "triggers": {
                "positive": ["客人满意的笑容", "有趣的故事", "节日庆典"],
                "negative": ["客人冲突", "食材短缺", "身体不适"]
            }
        },

        "skills": {
            "cooking": 90,
            "brewing": 85,
            "storytelling": 80,
            "conflict_resolution": 75,
            "business_management": 70
        },

        "memories": [
            "失去腿的意外事故",
            "第一次独立经营酒馆",
            "镇上最热闹的节日",
            "帮助困难居民的故事",
            "与丈夫的相遇"
        ]
    },

    "wise_priest": {
        "name": "西奥多·光明",
        "race": "人类",
        "profession": "牧师",
        "age": 58,
        "gender": "男性",

        "personality": {
            "traits": ["智慧", "慈祥", "公正", "耐心", "神秘"],
            "temperament": "melancholic",  # 抑郁质
            "moral_alignment": "lawful_good"  # 守序善良
        },

        "background": """
西奥多出生于一个贵族家庭，但选择放弃世俗生活成为神职人员。
他曾在王国首都的神学院学习多年，精通古老的典籍和魔法。
来到艾伦谷后，他发现这里的人们虽然贫穷但心灵纯净。
他致力于帮助镇民解决各种问题，从疾病治疗到心灵安慰。
他知道一些关于小镇古老传说的秘密，但他选择在适当的时候分享。
""",

        "relationships": {
            "blacksmith": {"relationship": "spiritual_guide"},
            "innkeeper": {"relationship": "confidant"},
            "villagers": {"relationship": "shepherd"},
            "mysterious_stranger": {"relationship": "intrigued"}
        },

        "goals": {
            "short_term": [
                "早上祈祷仪式",
                "接待求助者",
                "治疗病人",
                "下午冥想"
            ],
            "long_term": [
                "守护小镇的和平",
                "发掘古老传说的真相",
                "培养下一代神职人员",
                "建立社区互助体系"
            ]
        },

        "daily_schedule": {
            "dawn": ["晨祷", "冥想", "准备教堂"],
            "morning": ["开门迎客", "治疗工作", "倾听忏悔"],
            "afternoon": ["继续工作", "研究典籍", "社区活动"],
            "evening": ["晚祷", "记录日记", "反思一天"],
            "night": ["阅读古老典籍", "冥想", "安然入睡"]
        },

        "emotional_state": {
            "base_mood": "serene",
            "triggers": {
                "positive": ["帮助他人成功", "发现知识", "和谐社区"],
                "negative": ["无法帮助的痛苦", "社区冲突", "古老传说的阴影"]
            }
        },

        "skills": {
            "healing": 90,
            "divination": 85,
            "counseling": 80,
            "ancient_knowledge": 95,
            "mediation": 75
        },

        "memories": [
            "神学院的学习时光",
            "第一次治愈奇迹",
            "小镇的古老传说",
            "帮助困难村民的经历",
            "与神秘力量的邂逅"
        ]
    }
}

# 行为决策权重系统
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

# 环境事件系统
ENVIRONMENTAL_EVENTS = {
    "weather": ["sunny", "rainy", "cloudy", "stormy", "snowy"],
    "seasons": ["spring", "summer", "autumn", "winter"],
    "town_events": [
        "market_day", "festival", "wedding", "funeral",
        "visitor_arrival", "theft_incident", "healing_request"
    ],
    "personal_events": [
        "birthday", "anniversary", "health_issue", "family_visit",
        "opportunity_knock", "crisis_moment", "achievement"
    ]
}
