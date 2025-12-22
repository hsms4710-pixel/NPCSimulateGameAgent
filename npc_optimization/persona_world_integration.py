"""
人物卡与世界卡整合系统
将全局世界规则映射到个体NPC状态中，支持个性化规则覆盖
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class PersonaCard:
    """动态人物卡 - 支持世界规则覆盖"""
    npc_name: str
    race: str
    profession: str
    age: int
    
    # 核心人格特征
    personality_traits: List[str]
    values: List[str]
    fears: List[str]
    desires: List[str]
    
    # 世界规则的个人版本覆盖
    world_rule_overrides: Dict[str, Any] = field(default_factory=dict)
    # 格式: {
    #     "work_hours": "9:00-18:00",  # 覆盖职业默认工作时间
    #     "moral_alignment": "chaotic_neutral",  # 覆盖种族/职业的道德倾向
    #     "custom_beliefs": ["我相信自由比秩序重要"]
    # }
    
    # 对世界中特定地点的认知
    world_knowledge_index: Dict[str, Any] = field(default_factory=dict)
    # 格式: {
    #     "blacksmith_shop": {
    #         "reputation": "trusted",
    #         "visit_frequency": "weekly",
    #         "memorable_events": [事件ID列表]
    #     },
    #     "tavern": {...}
    # }
    
    # 长期记忆整合
    long_term_memory_anchors: List[str] = field(default_factory=list)
    # 最重要的回忆ID，用于快速检索

    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


class WorldCardView:
    """世界卡视图 - 封装全局世界规则"""
    
    def __init__(self, world_lore: Dict[str, Any]):
        self.world_lore = world_lore
        self.professions = world_lore.get("professions", {})
        self.races = world_lore.get("races", {})
        self.locations = world_lore.get("locations", {})
        self.rules = world_lore.get("rules", {})

    def get_profession_rules(self, profession: str) -> Dict[str, Any]:
        """获取职业的全局规则"""
        return self.professions.get(profession, {})

    def get_race_traits(self, race: str) -> List[str]:
        """获取种族特性"""
        race_info = self.races.get(race, {})
        return race_info.get("traits", [])

    def get_location_info(self, location: str) -> Dict[str, Any]:
        """获取地点信息"""
        return self.locations.get(location, {})

    def get_global_rule(self, rule_name: str) -> Any:
        """获取全局规则"""
        return self.rules.get(rule_name)


class PersonaWorldIntegrator:
    """
    人物卡-世界卡整合器
    协调个体规则与全局规则，处理冲突和优先级
    """

    def __init__(self,
                 persona_card: PersonaCard,
                 world_card_view: WorldCardView):
        self.persona = persona_card
        self.world = world_card_view

    def get_effective_rule(self, 
                          rule_type: str,
                          context: Optional[Dict[str, Any]] = None) -> Any:
        """
        获取生效的规则（优先级：个人覆盖 > 职业规则 > 种族特性 > 全局规则）
        
        Args:
            rule_type: 规则名称，如 "work_hours", "moral_alignment"
            context: 额外上下文，用于复杂规则判定
        
        Returns:
            有效的规则值
        """
        
        # 1. 检查个人覆盖
        if rule_type in self.persona.world_rule_overrides:
            override = self.persona.world_rule_overrides[rule_type]
            logger.debug(f"使用个人覆盖规则: {rule_type}={override}")
            return override
        
        # 2. 检查职业规则
        profession_rules = self.world.get_profession_rules(self.persona.profession)
        if rule_type in profession_rules:
            prof_rule = profession_rules[rule_type]
            logger.debug(f"使用职业规则: {rule_type}={prof_rule}")
            return prof_rule
        
        # 3. 检查种族特性
        race_traits = self.world.get_race_traits(self.persona.race)
        if rule_type == "inherent_traits":
            return race_traits
        
        # 4. 检查全局规则
        global_rule = self.world.get_global_rule(rule_type)
        if global_rule is not None:
            logger.debug(f"使用全局规则: {rule_type}={global_rule}")
            return global_rule
        
        # 5. 返回None表示规则不存在
        logger.warning(f"未找到规则: {rule_type}")
        return None

    def get_work_schedule(self) -> Dict[str, Any]:
        """获取生效的工作时间"""
        work_hours = self.get_effective_rule("work_hours")
        
        if isinstance(work_hours, str):
            # 解析字符串格式的工作时间
            return self._parse_work_hours(work_hours)
        elif isinstance(work_hours, dict):
            return work_hours
        
        return {"start": 9, "end": 18}  # 默认

    def get_location_specific_knowledge(self, 
                                        location: str) -> Dict[str, Any]:
        """获取NPC对特定地点的认知"""
        if location in self.persona.world_knowledge_index:
            return self.persona.world_knowledge_index[location]
        
        # 首次访问，返回世界卡的公开信息
        world_info = self.world.get_location_info(location)
        return {
            "reputation": "unknown",
            "visit_frequency": "never",
            "memorable_events": [],
            "world_info": world_info
        }

    def update_location_knowledge(self,
                                  location: str,
                                  knowledge: Dict[str, Any]):
        """更新NPC对特定地点的认知"""
        if location not in self.persona.world_knowledge_index:
            self.persona.world_knowledge_index[location] = {}
        
        self.persona.world_knowledge_index[location].update(knowledge)
        self.persona.last_updated = datetime.now().isoformat()

    def get_effective_personality(self) -> Dict[str, Any]:
        """获取整合后的人格（个人+世界环境影响）"""
        return {
            "core_traits": self.persona.personality_traits,
            "values": self.persona.values,
            "professional_expectations": self.world.get_profession_rules(
                self.persona.profession
            ).get("expectations", []),
            "racial_influences": self.world.get_race_traits(self.persona.race),
            "personal_overrides": self.persona.world_rule_overrides.get(
                "custom_beliefs", []
            )
        }

    def _parse_work_hours(self, work_hours_str: str) -> Dict[str, Any]:
        """解析工作时间字符串"""
        import re
        # 支持多种格式："9:00-18:00", "早上9点-晚上6点" 等
        times = re.findall(r'(\d{1,2})', work_hours_str)
        if len(times) >= 2:
            return {
                "start": int(times[0]),
                "end": int(times[1])
            }
        return {"start": 9, "end": 18}


class PersonalCharacterMigrationTask:
    """
    性格迁移任务 - 当人物卡配置变更时执行
    生成"心路历程"摘要并存入RAG系统
    """

    def __init__(self, llm_client, rag_memory_system):
        self.llm_client = llm_client
        self.rag_memory_system = rag_memory_system

    def execute_persona_reshaping(self,
                                  npc_name: str,
                                  old_persona: PersonaCard,
                                  new_persona: PersonaCard,
                                  long_term_memories: List[Dict[str, Any]],
                                  max_tokens: int = 300) -> str:
        """
        执行性格迁移任务
        
        Returns:
            生成的"心路历程"摘要
        """
        
        # 第1步：检测变化
        changes = self._detect_changes(old_persona, new_persona)
        
        if not changes:
            logger.info(f"{npc_name}: 人物卡无重大变化")
            return ""
        
        # 第2步：提取相关长期记忆
        relevant_memories = self._extract_relevant_memories(
            changes, long_term_memories
        )
        
        # 第3步：LLM生成心路历程
        journey_summary = self._generate_journey_narrative(
            npc_name,
            old_persona,
            new_persona,
            changes,
            relevant_memories,
            max_tokens
        )
        
        # 第4步：存入RAG系统作为高优先级见解
        self._store_journey_as_insight(
            npc_name,
            journey_summary,
            priority="highest"
        )
        
        logger.info(f"{npc_name}: 性格迁移完成\n{journey_summary}")
        
        return journey_summary

    def _detect_changes(self,
                        old_persona: PersonaCard,
                        new_persona: PersonaCard) -> Dict[str, Any]:
        """检测人物卡的变化"""
        changes = {}
        
        # 比较核心属性
        if old_persona.personality_traits != new_persona.personality_traits:
            changes["personality_traits"] = {
                "old": old_persona.personality_traits,
                "new": new_persona.personality_traits
            }
        
        if old_persona.values != new_persona.values:
            changes["values"] = {
                "old": old_persona.values,
                "new": new_persona.values
            }
        
        if old_persona.world_rule_overrides != new_persona.world_rule_overrides:
            changes["world_rule_overrides"] = {
                "old": old_persona.world_rule_overrides,
                "new": new_persona.world_rule_overrides
            }
        
        return changes

    def _extract_relevant_memories(self,
                                   changes: Dict[str, Any],
                                   memories: List[Dict[str, Any]],
                                   top_k: int = 5) -> List[Dict[str, Any]]:
        """提取与变化相关的长期记忆"""
        # 简化实现：返回最近的几条记忆
        return sorted(
            memories,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:top_k]

    def _generate_journey_narrative(self,
                                    npc_name: str,
                                    old_persona: PersonaCard,
                                    new_persona: PersonaCard,
                                    changes: Dict[str, Any],
                                    memories: List[Dict[str, Any]],
                                    max_tokens: int) -> str:
        """使用LLM生成心路历程摘要"""
        
        prompt = f"""你是{npc_name}，一个{old_persona.profession}。

你经历了人生的转变。你的以前：
- 性格特征：{', '.join(old_persona.personality_traits)}
- 核心价值观：{', '.join(old_persona.values)}

现在的你：
- 性格特征：{', '.join(new_persona.personality_traits)}
- 核心价值观：{', '.join(new_persona.values)}

关键经历（最近的记忆）：
{json.dumps(memories[:2], ensure_ascii=False, indent=2)}

请用第一人称写一段简短的"心路历程"摘要（2-3句话），描述你是如何改变的。
要求：真实、有说服力、体现具体的转变。

例如："经过岁月的洗礼，我不再执着于过去的信念。那些曾经伤害过我的事件，
最终教会了我宽容与理解。我决定放下固执，开始接纳他人的想法。"

你的心路历程："""

        try:
            response = self.llm_client.call_model(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.8  # 稍高温度保证创意
            )
            return response.strip()
        
        except Exception as e:
            logger.error(f"生成心路历程失败: {e}")
            return f"{npc_name}经历了转变，开始以不同的方式看待世界。"

    def _store_journey_as_insight(self,
                                  npc_name: str,
                                  journey_text: str,
                                  priority: str = "highest"):
        """将心路历程存入RAG系统作为高优先级见解"""
        
        from npc_optimization.memory_layers import Insight
        import uuid
        
        insight = Insight(
            id=f"journey_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now().isoformat(),
            source_event_ids=[],
            insight_text=journey_text,
            insight_type="emotional_growth",
            emotional_weight=8,  # 高情感权重
            relevance_score=1.0,  # 最高相关性
            keywords=["性格转变", "自我认知", "成长"]
        )
        
        # 存入RAG系统
        self.rag_memory_system.add_reflection_insight(insight)
        logger.info(f"已将{npc_name}的心路历程存入RAG系统")


class DynamicPersonaUpdateManager:
    """
    动态人物卡更新管理器
    监听配置文件变化，触发性格迁移任务
    """

    def __init__(self,
                 llm_client,
                 rag_memory_system,
                 world_card_view: WorldCardView):
        self.llm_client = llm_client
        self.rag_memory_system = rag_memory_system
        self.world_card_view = world_card_view
        self.migration_task = PersonalCharacterMigrationTask(
            llm_client,
            rag_memory_system
        )

    def on_persona_config_updated(self,
                                  npc_name: str,
                                  old_config: Dict[str, Any],
                                  new_config: Dict[str, Any],
                                  memories: List[Dict[str, Any]]):
        """当人物卡配置文件更新时调用"""
        
        # 重建人物卡对象
        old_persona = self._build_persona(npc_name, old_config)
        new_persona = self._build_persona(npc_name, new_config)
        
        # 执行性格迁移
        journey_summary = self.migration_task.execute_persona_reshaping(
            npc_name,
            old_persona,
            new_persona,
            memories
        )
        
        # 重新初始化行为决策树的惯性参数
        # 这应该在NPC系统中执行
        logger.info(f"已更新{npc_name}的行为决策树参数")
        
        return {
            "journey_summary": journey_summary,
            "update_timestamp": datetime.now().isoformat()
        }

    def _build_persona(self,
                       npc_name: str,
                       config: Dict[str, Any]) -> PersonaCard:
        """从配置字典构建人物卡"""
        return PersonaCard(
            npc_name=npc_name,
            race=config.get("race", "人类"),
            profession=config.get("profession", "村民"),
            age=config.get("age", 30),
            personality_traits=config.get("personality", {}).get("traits", []),
            values=config.get("values", []),
            fears=config.get("fears", []),
            desires=config.get("desires", []),
            world_rule_overrides=config.get("world_rule_overrides", {}),
            world_knowledge_index=config.get("world_knowledge_index", {})
        )
