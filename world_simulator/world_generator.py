# -*- coding: utf-8 -*-
"""
世界生成器
==========

支持通过LLM动态生成完整的游戏世界：
- 世界背景和设定
- 地图和位置
- 初始NPC（非核心化）
- 世界规则和职业

用户可以：
1. 输入简短描述，LLM生成完整世界
2. 使用预设模板快速创建
3. 完全自定义每个细节
"""

import json
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
import random

logger = logging.getLogger(__name__)


# ==================== 世界模板 ====================

class WorldTheme(Enum):
    """世界主题模板"""
    MEDIEVAL_FANTASY = "medieval_fantasy"     # 中世纪奇幻
    EASTERN_MARTIAL = "eastern_martial"       # 东方武侠
    STEAMPUNK = "steampunk"                   # 蒸汽朋克
    POST_APOCALYPTIC = "post_apocalyptic"     # 末日废土
    MODERN_URBAN = "modern_urban"             # 现代都市
    PIRATE_AGE = "pirate_age"                 # 大航海时代
    CUSTOM = "custom"                         # 自定义


THEME_TEMPLATES = {
    WorldTheme.MEDIEVAL_FANTASY: {
        "name_style": "欧洲中世纪风格",
        "races": ["人类", "精灵", "矮人", "半身人"],
        "professions": ["铁匠", "酒馆老板", "牧师", "农夫", "商人", "猎人", "法师", "骑士"],
        "location_types": ["酒馆", "铁匠铺", "教堂", "市场", "城堡", "森林", "农田", "矿洞"],
        "setting_hints": "魔法存在，有神明信仰，封建社会结构"
    },
    WorldTheme.EASTERN_MARTIAL: {
        "name_style": "中国古风",
        "races": ["人类"],
        "professions": ["铁匠", "掌柜", "道士", "农夫", "商贩", "猎户", "侠客", "郎中"],
        "location_types": ["客栈", "铁匠铺", "道观", "集市", "武馆", "山林", "田地", "药铺"],
        "setting_hints": "武功秘籍，江湖门派，皇权与江湖"
    },
    WorldTheme.STEAMPUNK: {
        "name_style": "维多利亚时代风格",
        "races": ["人类", "机械人"],
        "professions": ["工程师", "酒吧老板", "医生", "工人", "商人", "发明家", "侦探", "飞艇驾驶员"],
        "location_types": ["酒吧", "工坊", "医院", "工厂", "飞艇港", "钟楼", "实验室"],
        "setting_hints": "蒸汽科技，齿轮机械，工业革命"
    },
    WorldTheme.POST_APOCALYPTIC: {
        "name_style": "废土风格",
        "races": ["人类", "变异人"],
        "professions": ["工匠", "酒保", "医疗兵", "拾荒者", "商人", "猎人", "雇佣兵", "机械师"],
        "location_types": ["酒吧", "修理站", "诊所", "废墟", "交易站", "避难所", "荒野"],
        "setting_hints": "资源匮乏，辐射危险，生存至上"
    },
}


# ==================== 数据结构 ====================

@dataclass
class WorldConfig:
    """世界配置"""
    # 基础信息
    world_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    world_name: str = ""
    world_description: str = ""
    theme: str = "medieval_fantasy"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 种族和职业
    races: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    professions: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 时间系统
    time_system: Dict[str, Any] = field(default_factory=lambda: {
        "hours_per_day": 24,
        "time_periods": {
            "dawn": {"start": 5, "end": 6, "description": "黎明"},
            "early_morning": {"start": 6, "end": 8, "description": "清晨"},
            "morning": {"start": 8, "end": 12, "description": "上午"},
            "noon": {"start": 12, "end": 14, "description": "中午"},
            "afternoon": {"start": 14, "end": 18, "description": "下午"},
            "evening": {"start": 18, "end": 20, "description": "傍晚"},
            "night": {"start": 20, "end": 23, "description": "夜晚"},
            "late_night": {"start": 23, "end": 5, "description": "深夜"}
        }
    })

    # 世界规则
    rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocationConfig:
    """位置配置"""
    location_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    location_type: str = "public"  # workplace, social, religious, commercial, residential, wilderness
    description: str = ""
    owner: Optional[str] = None
    connected_to: List[str] = field(default_factory=list)
    activities_available: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NPCTemplate:
    """NPC模板（用于生成）"""
    npc_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    race: str = "人类"
    profession: str = ""
    age: int = 30
    gender: str = "男性"

    # 性格
    personality_traits: List[str] = field(default_factory=list)
    temperament: str = "sanguine"  # sanguine, choleric, melancholic, phlegmatic
    moral_alignment: str = "neutral"
    speech_style: str = ""

    # 背景
    background: str = ""
    default_location: str = ""

    # 关系（名字 -> 关系描述）
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 目标
    short_term_goals: List[str] = field(default_factory=list)
    long_term_goals: List[str] = field(default_factory=list)

    # 技能
    skills: Dict[str, int] = field(default_factory=dict)

    # 日程（时段 -> 活动）
    daily_schedule: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # 初始记忆
    initial_memories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==================== 世界生成器 ====================

class WorldGenerator:
    """
    世界生成器

    通过LLM或模板生成完整的游戏世界
    """

    # LLM提示词模板
    WORLD_GENERATION_PROMPT = """你是一个世界构建大师。请根据用户的描述创建一个详细的游戏世界设定。

## 用户描述
{user_description}

## 世界主题
{theme}

## 请生成以下内容（JSON格式）

```json
{{
    "world_name": "世界/地区名称",
    "world_description": "100-200字的世界背景描述，包含历史、特色、氛围",
    "races": {{
        "race_id": {{"name": "种族名", "traits": ["特征1", "特征2"]}}
    }},
    "professions": {{
        "profession_id": {{
            "name": "职业名",
            "workplace": "工作地点",
            "work_hours": "8:00-18:00",
            "skills": ["技能1", "技能2"],
            "social_status": "社会地位描述"
        }}
    }},
    "locations": [
        {{
            "name": "地点名",
            "type": "workplace/social/religious/commercial/residential/wilderness",
            "description": "地点描述",
            "connected_to": ["连接的其他地点"],
            "activities": ["可进行的活动"]
        }}
    ],
    "world_rules": {{
        "magic_level": "none/low/medium/high",
        "technology_level": "primitive/medieval/industrial/modern",
        "danger_level": "safe/moderate/dangerous",
        "special_rules": ["特殊规则1", "特殊规则2"]
    }}
}}
```

请确保：
1. 地点之间有合理的连接关系
2. 职业与地点匹配
3. 世界观自洽
4. 符合所选主题的风格"""

    NPC_GENERATION_PROMPT = """你是一个角色设计大师。请为以下世界创建一个NPC。

## 世界背景
{world_description}

## 已有地点
{locations}

## 已有NPC（避免重复）
{existing_npcs}

## NPC要求
- 职业: {profession}
- 工作地点: {workplace}
- 性别要求: {gender_requirement}
- 特殊要求: {special_requirements}

## 请生成NPC（JSON格式）

```json
{{
    "name": "符合世界观的名字",
    "race": "种族",
    "profession": "{profession}",
    "age": 年龄数字,
    "gender": "{gender_hint}",
    "personality": {{
        "traits": ["性格特征1", "性格特征2", "性格特征3", "性格特征4"],
        "temperament": "sanguine/choleric/melancholic/phlegmatic",
        "moral_alignment": "lawful_good/neutral_good/chaotic_good/lawful_neutral/neutral/chaotic_neutral/lawful_evil/neutral_evil/chaotic_evil",
        "speech_style": "说话风格描述"
    }},
    "background": "50-100字的背景故事",
    "default_location": "默认所在地点",
    "goals": {{
        "short_term": ["短期目标1", "短期目标2"],
        "long_term": ["长期目标1", "长期目标2"]
    }},
    "skills": {{
        "技能1": 技能等级(0-100),
        "技能2": 技能等级
    }},
    "initial_memories": [
        "重要记忆1",
        "重要记忆2"
    ],
    "daily_schedule": {{
        "dawn": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "early_morning": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "morning": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "noon": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "afternoon": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "evening": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "night": {{"activity": "活动", "location": "地点", "description": "描述"}},
        "late_night": {{"activity": "活动", "location": "地点", "description": "描述"}}
    }}
}}
```

请确保NPC性格鲜明，背景故事与世界观契合。严格遵守性别要求。"""

    def __init__(self, llm_client=None, data_dir: str = "data"):
        self.llm_client = llm_client
        self.data_dir = data_dir

        # 生成的数据
        self.world_config: Optional[WorldConfig] = None
        self.locations: Dict[str, LocationConfig] = {}
        self.npcs: Dict[str, NPCTemplate] = {}

    async def generate_world(
        self,
        user_description: str,
        theme: WorldTheme = WorldTheme.MEDIEVAL_FANTASY,
        npc_count: int = 5
    ) -> Tuple[WorldConfig, Dict[str, LocationConfig], Dict[str, NPCTemplate]]:
        """
        生成完整世界

        Args:
            user_description: 用户对世界的描述
            theme: 世界主题
            npc_count: 初始NPC数量

        Returns:
            (世界配置, 位置字典, NPC字典)
        """
        logger.info(f"开始生成世界: theme={theme.value}, npc_count={npc_count}")

        # 1. 生成世界基础设定
        self.world_config = await self._generate_world_base(user_description, theme)

        # 2. 生成位置
        self.locations = await self._generate_locations(self.world_config)

        # 3. 生成NPC
        self.npcs = await self._generate_npcs(
            self.world_config,
            self.locations,
            npc_count
        )

        # 4. 建立NPC关系
        await self._generate_relationships()

        logger.info(f"世界生成完成: {self.world_config.world_name}, "
                   f"{len(self.locations)} 个位置, {len(self.npcs)} 个NPC")

        return self.world_config, self.locations, self.npcs

    async def _generate_world_base(
        self,
        user_description: str,
        theme: WorldTheme
    ) -> WorldConfig:
        """生成世界基础设定"""
        if not self.llm_client:
            # 无LLM时使用模板
            return self._create_template_world(theme, user_description)

        template = THEME_TEMPLATES.get(theme, THEME_TEMPLATES[WorldTheme.MEDIEVAL_FANTASY])

        prompt = self.WORLD_GENERATION_PROMPT.format(
            user_description=user_description,
            theme=f"{theme.value} - {template['setting_hints']}"
        )

        try:
            response = await asyncio.to_thread(
                self.llm_client.generate_response,
                prompt=prompt,
                context={},
                temperature=0.8,
                max_tokens=2000,
                timeout=90  # 世界生成需要更长时间
            )

            # 解析JSON
            data = self._parse_json_response(response)

            config = WorldConfig(
                world_name=data.get("world_name", "未命名世界"),
                world_description=data.get("world_description", ""),
                theme=theme.value,
                races=data.get("races", {}),
                professions=data.get("professions", {}),
                rules=data.get("world_rules", {})
            )

            # 临时保存位置数据（稍后转换）
            config.rules["_raw_locations"] = data.get("locations", [])

            return config

        except Exception as e:
            logger.warning(f"LLM生成世界失败: {e}, 使用模板")
            return self._create_template_world(theme, user_description)

    def _create_template_world(self, theme: WorldTheme, description: str) -> WorldConfig:
        """使用模板创建世界"""
        template = THEME_TEMPLATES.get(theme, THEME_TEMPLATES[WorldTheme.MEDIEVAL_FANTASY])

        # 生成默认职业
        professions = {}
        for prof in template["professions"]:
            prof_id = prof.lower().replace(" ", "_")
            professions[prof_id] = {
                "name": prof,
                "workplace": "未指定",
                "work_hours": "8:00-18:00",
                "skills": [],
                "social_status": "普通"
            }

        # 生成默认种族
        races = {}
        for race in template["races"]:
            race_id = race.lower()
            races[race_id] = {
                "name": race,
                "traits": ["普通"]
            }

        return WorldConfig(
            world_name=f"新世界_{datetime.now().strftime('%m%d')}",
            world_description=description or f"一个{template['name_style']}的世界",
            theme=theme.value,
            races=races,
            professions=professions
        )

    async def _generate_locations(self, world_config: WorldConfig) -> Dict[str, LocationConfig]:
        """生成位置"""
        locations = {}

        # 如果有LLM生成的原始数据
        raw_locations = world_config.rules.pop("_raw_locations", [])

        if raw_locations:
            for loc_data in raw_locations:
                loc = LocationConfig(
                    name=loc_data.get("name", "未命名地点"),
                    location_type=loc_data.get("type", "public"),
                    description=loc_data.get("description", ""),
                    connected_to=loc_data.get("connected_to", []),
                    activities_available=loc_data.get("activities", [])
                )
                locations[loc.name] = loc
        else:
            # 使用模板生成默认位置
            theme = WorldTheme(world_config.theme) if world_config.theme else WorldTheme.MEDIEVAL_FANTASY
            template = THEME_TEMPLATES.get(theme, THEME_TEMPLATES[WorldTheme.MEDIEVAL_FANTASY])

            # 创建中心广场
            center = LocationConfig(
                name="中心广场",
                location_type="public",
                description="人们聚集和交流的中心地带",
                connected_to=[],
                activities_available=["社交", "观察", "休息"]
            )
            locations["中心广场"] = center

            # 根据模板创建其他位置
            for loc_type in template["location_types"][:6]:  # 最多6个
                loc = LocationConfig(
                    name=loc_type,
                    location_type=self._infer_location_type(loc_type),
                    description=f"{world_config.world_name}的{loc_type}",
                    connected_to=["中心广场"],
                    activities_available=["工作", "交谈"] if "铺" in loc_type or "坊" in loc_type else ["休息", "社交"]
                )
                locations[loc_type] = loc
                center.connected_to.append(loc_type)

        return locations

    def _infer_location_type(self, name: str) -> str:
        """推断位置类型"""
        if any(x in name for x in ["铺", "坊", "店", "工厂", "矿"]):
            return "workplace"
        if any(x in name for x in ["酒", "馆", "客栈", "酒吧"]):
            return "social"
        if any(x in name for x in ["教堂", "寺", "庙", "道观"]):
            return "religious"
        if any(x in name for x in ["市场", "集市", "交易"]):
            return "commercial"
        if any(x in name for x in ["住宅", "民居", "家"]):
            return "residential"
        if any(x in name for x in ["森林", "山", "野", "荒"]):
            return "wilderness"
        return "public"

    async def _generate_npcs(
        self,
        world_config: WorldConfig,
        locations: Dict[str, LocationConfig],
        count: int
    ) -> Dict[str, NPCTemplate]:
        """生成NPC"""
        npcs = {}

        # 确定要生成的职业
        professions = list(world_config.professions.keys())
        if not professions:
            professions = ["铁匠", "酒馆老板", "商人", "农夫", "猎人"]

        # 为每个职业分配位置
        profession_locations = {}
        for prof_id, prof_data in world_config.professions.items():
            workplace = prof_data.get("workplace", "中心广场")
            # 找到匹配的位置
            for loc_name in locations:
                if workplace in loc_name or loc_name in workplace:
                    profession_locations[prof_id] = loc_name
                    break
            if prof_id not in profession_locations:
                profession_locations[prof_id] = list(locations.keys())[0] if locations else "中心广场"

        # 生成NPC
        for i in range(min(count, len(professions))):
            prof_id = professions[i % len(professions)]
            prof_data = world_config.professions.get(prof_id, {"name": prof_id})
            workplace = profession_locations.get(prof_id, "中心广场")

            npc = await self._generate_single_npc(
                world_config,
                locations,
                list(npcs.values()),
                prof_data.get("name", prof_id),
                workplace
            )

            if npc:
                npcs[npc.npc_id] = npc

        return npcs

    async def _generate_single_npc(
        self,
        world_config: WorldConfig,
        locations: Dict[str, LocationConfig],
        existing_npcs: List[NPCTemplate],
        profession: str,
        workplace: str,
        special_requirements: str = "",
        forced_gender: str = None
    ) -> Optional[NPCTemplate]:
        """生成单个NPC"""
        # 确定性别要求（交替生成以保持多样性）
        if forced_gender:
            gender = forced_gender
            gender_requirement = f"必须是{gender}"
        else:
            # 统计已有NPC的性别分布
            male_count = sum(1 for npc in existing_npcs if npc.gender in ["男性", "男"])
            female_count = sum(1 for npc in existing_npcs if npc.gender in ["女性", "女"])
            # 选择较少的性别
            if male_count > female_count:
                gender = "女性"
                gender_requirement = "需要女性角色以平衡性别比例"
            elif female_count > male_count:
                gender = "男性"
                gender_requirement = "需要男性角色以平衡性别比例"
            else:
                # 相等时随机选择
                gender = random.choice(["男性", "女性"])
                gender_requirement = "自由选择"

        if self.llm_client:
            try:
                existing_names = [npc.name for npc in existing_npcs]
                location_names = list(locations.keys())

                prompt = self.NPC_GENERATION_PROMPT.format(
                    world_description=world_config.world_description,
                    locations=", ".join(location_names),
                    existing_npcs=", ".join(existing_names) if existing_names else "无",
                    profession=profession,
                    workplace=workplace,
                    gender_requirement=gender_requirement,
                    gender_hint=gender,
                    special_requirements=special_requirements or "无"
                )

                response = await asyncio.to_thread(
                    self.llm_client.generate_response,
                    prompt=prompt,
                    context={},
                    temperature=0.9,
                    max_tokens=1500,
                    timeout=90  # NPC生成需要更长时间
                )

                data = self._parse_json_response(response)
                npc = self._dict_to_npc_template(data, profession, workplace)
                # 如果LLM没有遵守性别要求，强制覆盖
                if forced_gender and npc and npc.gender != forced_gender:
                    npc.gender = forced_gender
                return npc

            except Exception as e:
                logger.warning(f"LLM生成NPC失败: {e}")

        # 回退到模板生成
        return self._create_template_npc(world_config, profession, workplace, existing_npcs, gender)

    def _create_template_npc(
        self,
        world_config: WorldConfig,
        profession: str,
        workplace: str,
        existing_npcs: List[NPCTemplate],
        gender: str = None
    ) -> NPCTemplate:
        """使用模板创建NPC"""
        # 生成名字
        existing_names = {npc.name for npc in existing_npcs}
        name = self._generate_unique_name(world_config.theme, existing_names)

        # 随机属性
        traits = random.sample(
            ["勤劳", "善良", "固执", "聪明", "热情", "冷静", "幽默", "严肃", "好奇", "谨慎"],
            k=4
        )
        temperaments = ["sanguine", "choleric", "melancholic", "phlegmatic"]

        races = list(world_config.races.keys())
        race = random.choice(races) if races else "人类"
        race_name = world_config.races.get(race, {}).get("name", race)

        # 使用传入的性别或随机选择
        npc_gender = gender if gender else random.choice(["男性", "女性"])

        return NPCTemplate(
            name=name,
            race=race_name,
            profession=profession,
            age=random.randint(25, 60),
            gender=npc_gender,
            personality_traits=traits,
            temperament=random.choice(temperaments),
            moral_alignment="neutral",
            speech_style="普通",
            background=f"{name}是{world_config.world_name}的一名{profession}，在{workplace}工作。",
            default_location=workplace,
            short_term_goals=[f"做好{profession}的工作"],
            long_term_goals=[f"成为{world_config.world_name}最好的{profession}"],
            skills={profession: random.randint(60, 90)},
            initial_memories=[f"在{world_config.world_name}生活多年"],
            daily_schedule=self._create_default_schedule(workplace)
        )

    def _generate_unique_name(self, theme: str, existing: set) -> str:
        """生成唯一名字"""
        # 根据主题选择名字风格
        if theme == "eastern_martial":
            surnames = ["李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
            given_names = ["明", "华", "强", "伟", "芳", "娟", "秀", "英", "志", "文"]
        else:
            surnames = ["艾", "贝", "卡", "德", "埃", "弗", "格", "海", "伊", "杰"]
            given_names = ["尔德", "拉", "克", "斯", "娜", "莉", "恩", "特", "森", "伦"]

        for _ in range(100):
            name = random.choice(surnames) + random.choice(given_names)
            if theme != "eastern_martial":
                name = random.choice(surnames) + random.choice(given_names) + "·" + random.choice(given_names)
            if name not in existing:
                return name

        return f"无名者_{uuid.uuid4().hex[:4]}"

    def _create_default_schedule(self, workplace: str) -> Dict[str, Dict[str, str]]:
        """创建默认日程"""
        return {
            "dawn": {"activity": "起床", "location": workplace, "description": "起床准备"},
            "early_morning": {"activity": "吃饭", "location": workplace, "description": "吃早餐"},
            "morning": {"activity": "工作", "location": workplace, "description": "开始工作"},
            "noon": {"activity": "吃饭", "location": workplace, "description": "午餐时间"},
            "afternoon": {"activity": "工作", "location": workplace, "description": "继续工作"},
            "evening": {"activity": "休息", "location": workplace, "description": "结束工作"},
            "night": {"activity": "社交", "location": workplace, "description": "休闲时间"},
            "late_night": {"activity": "睡觉", "location": workplace, "description": "休息"}
        }

    async def _generate_relationships(self):
        """生成NPC之间的关系"""
        npc_list = list(self.npcs.values())
        if len(npc_list) < 2:
            return

        relationship_types = ["朋友", "同事", "邻居", "熟人", "老友"]

        for i, npc in enumerate(npc_list):
            # 每个NPC与1-3个其他NPC建立关系
            num_relations = min(random.randint(1, 3), len(npc_list) - 1)
            others = [n for n in npc_list if n.npc_id != npc.npc_id]
            random.shuffle(others)

            for other in others[:num_relations]:
                if other.name not in npc.relationships:
                    rel_type = random.choice(relationship_types)
                    affection = random.randint(40, 80)
                    npc.relationships[other.name] = {
                        "type": rel_type,
                        "affection": affection,
                        "description": f"{npc.name}和{other.name}是{rel_type}"
                    }

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON"""
        # 尝试找到JSON块
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            return json.loads(json_str)

        raise ValueError("无法解析JSON响应")

    def _dict_to_npc_template(self, data: Dict[str, Any], profession: str, workplace: str) -> NPCTemplate:
        """将字典转换为NPCTemplate"""
        personality = data.get("personality", {})
        goals = data.get("goals", {})

        return NPCTemplate(
            name=data.get("name", "未命名"),
            race=data.get("race", "人类"),
            profession=data.get("profession", profession),
            age=data.get("age", 30),
            gender=data.get("gender", "男性"),
            personality_traits=personality.get("traits", []),
            temperament=personality.get("temperament", "sanguine"),
            moral_alignment=personality.get("moral_alignment", "neutral"),
            speech_style=personality.get("speech_style", "普通"),
            background=data.get("background", ""),
            default_location=data.get("default_location", workplace),
            short_term_goals=goals.get("short_term", []),
            long_term_goals=goals.get("long_term", []),
            skills=data.get("skills", {}),
            initial_memories=data.get("initial_memories", []),
            daily_schedule=data.get("daily_schedule", self._create_default_schedule(workplace))
        )

    # ==================== 保存和加载 ====================

    def save_world(self, world_name: str = None) -> str:
        """
        保存世界到文件

        Returns:
            保存的世界目录路径
        """
        if not self.world_config:
            raise ValueError("没有可保存的世界")

        world_name = world_name or self.world_config.world_name
        safe_name = "".join(c for c in world_name if c.isalnum() or c in "_ -")
        world_dir = os.path.join(self.data_dir, "worlds", safe_name)
        os.makedirs(world_dir, exist_ok=True)

        # 保存世界配置
        with open(os.path.join(world_dir, "world_settings.json"), 'w', encoding='utf-8') as f:
            json.dump(self.world_config.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存位置
        locations_data = {name: loc.to_dict() for name, loc in self.locations.items()}
        with open(os.path.join(world_dir, "locations.json"), 'w', encoding='utf-8') as f:
            json.dump({"locations": locations_data}, f, ensure_ascii=False, indent=2)

        # 保存NPC
        npcs_dir = os.path.join(world_dir, "npcs")
        os.makedirs(npcs_dir, exist_ok=True)
        for npc_id, npc in self.npcs.items():
            npc_file = os.path.join(npcs_dir, f"{npc.name}.json")
            with open(npc_file, 'w', encoding='utf-8') as f:
                json.dump(npc.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存世界索引
        index = {
            "world_id": self.world_config.world_id,
            "world_name": world_name,
            "created_at": self.world_config.created_at,
            "theme": self.world_config.theme,
            "location_count": len(self.locations),
            "npc_count": len(self.npcs),
            "npc_names": [npc.name for npc in self.npcs.values()]
        }
        with open(os.path.join(world_dir, "index.json"), 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        logger.info(f"世界已保存到: {world_dir}")
        return world_dir

    @classmethod
    def load_world(cls, world_dir: str, llm_client=None) -> 'WorldGenerator':
        """加载已保存的世界"""
        generator = cls(llm_client=llm_client)

        # 加载世界配置
        with open(os.path.join(world_dir, "world_settings.json"), 'r', encoding='utf-8') as f:
            data = json.load(f)
            generator.world_config = WorldConfig(**data)

        # 加载位置
        with open(os.path.join(world_dir, "locations.json"), 'r', encoding='utf-8') as f:
            data = json.load(f)
            for name, loc_data in data.get("locations", {}).items():
                generator.locations[name] = LocationConfig(**loc_data)

        # 加载NPC
        npcs_dir = os.path.join(world_dir, "npcs")
        if os.path.exists(npcs_dir):
            for filename in os.listdir(npcs_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(npcs_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        npc = NPCTemplate(**data)
                        generator.npcs[npc.npc_id] = npc

        logger.info(f"加载世界: {generator.world_config.world_name}")
        return generator

    @classmethod
    def list_saved_worlds(cls, data_dir: str = "data") -> List[Dict[str, Any]]:
        """列出所有已保存的世界"""
        worlds = []
        worlds_dir = os.path.join(data_dir, "worlds")

        if not os.path.exists(worlds_dir):
            return worlds

        for name in os.listdir(worlds_dir):
            world_path = os.path.join(worlds_dir, name)
            index_file = os.path.join(world_path, "index.json")
            if os.path.exists(index_file):
                with open(index_file, 'r', encoding='utf-8') as f:
                    world_data = json.load(f)
                    # 添加前端需要的字段
                    world_data['dir_name'] = name
                    world_data['modified_time'] = os.path.getmtime(index_file)
                    worlds.append(world_data)

        return worlds


# ==================== 便捷函数 ====================

async def create_world(
    description: str = "",
    theme: str = "medieval_fantasy",
    npc_count: int = 5,
    llm_client=None
) -> WorldGenerator:
    """
    快速创建世界

    Args:
        description: 世界描述（可选）
        theme: 主题 (medieval_fantasy/eastern_martial/steampunk/post_apocalyptic)
        npc_count: 初始NPC数量
        llm_client: LLM客户端（可选）

    Returns:
        WorldGenerator实例
    """
    generator = WorldGenerator(llm_client=llm_client)

    try:
        theme_enum = WorldTheme(theme)
    except ValueError:
        theme_enum = WorldTheme.MEDIEVAL_FANTASY

    await generator.generate_world(
        user_description=description or "一个有趣的世界",
        theme=theme_enum,
        npc_count=npc_count
    )

    return generator


__all__ = [
    'WorldGenerator',
    'WorldConfig',
    'LocationConfig',
    'NPCTemplate',
    'WorldTheme',
    'THEME_TEMPLATES',
    'create_world',
]
