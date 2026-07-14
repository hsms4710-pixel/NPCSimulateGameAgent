"""世界管理器 — 位置/时间/NPC/玩家/经济/任务 + Tick循环"""
import json, logging, os, asyncio, random
from typing import Dict, Any, Optional, List
from datetime import datetime

from .events import EventSystem
from .economy import EconomySystem

logger = logging.getLogger(__name__)


class WorldManager:
    def __init__(self, data_dir: str = "npc_storage"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # 加载数据
        from data import get_data_loader
        loader = get_data_loader()
        self.locations: Dict = loader.get_world_locations()
        self.npc_configs: Dict = loader.get_npc_templates()

        # 时间
        self.day = 1
        self.hour = 8
        self.minute = 0
        self.time_running = True

        # 系统
        self.events = EventSystem()
        self.economy = EconomySystem()
        self.npc_agents: Dict[str, Any] = {}
        self.npc_locations: Dict[str, str] = {}

        # 玩家
        self.player: Optional[dict] = None

        # 任务
        self.quests: Dict[str, dict] = {}
        self._init_quests()

        # NPC Agent 实例（延迟创建）
        self._llm = None

    def init_npcs(self, llm_client):
        from .npc_agent import NPCAgent
        self._llm = llm_client
        for name, config in self.npc_configs.items():
            loc = config.get("location", "镇中心广场")
            self.npc_locations[name] = loc
            self.economy.init_entity(name, gold=random.randint(30, 80))
            # 初始物品
            if config.get("profession") in ("铁匠", "面包师"):
                self.economy.give_item(name, config.get("profession") == "铁匠" and "铁器" or "面包", 5)
            elif config.get("profession") == "草药师":
                self.economy.give_item(name, "草药", 5)
            elif config.get("profession") == "裁缝":
                self.economy.give_item(name, "衣物", 3)
            self.npc_agents[name] = NPCAgent(name, config, self, llm_client)
            logger.info(f"NPC Agent 创建: {name} @ {loc}")

        # 初始社交关系
        for n1 in self.npc_agents:
            for n2 in self.npc_agents:
                if n1 < n2 and random.random() < 0.3:
                    self.events.register_relationship(n1, n2)

    def _init_quests(self):
        self.quests = {
            "q1": {"title": "铁匠的矿石", "desc": "托林需要一批矿石来打造武器", "type": "fetch",
                   "target": "矿石", "target_npc": "托林·石砧", "reward_gold": 20, "status": "available"},
            "q2": {"title": "旅店的消息", "desc": "艾尔莎想打听一个失踪商人的消息", "type": "talk",
                   "target_npc": "马库斯·晨星", "reward_gold": 15, "status": "available"},
            "q3": {"title": "草药配送", "desc": "伊莱雅需要把草药送到镇公所", "type": "deliver",
                   "target": "草药", "target_npc": "哈罗德·铁橡", "reward_gold": 10, "status": "available"},
        }

    def get_npc_location(self, name: str) -> str:
        return self.npc_locations.get(name, "镇中心广场")

    def set_npc_location(self, name: str, location: str):
        self.npc_locations[name] = location
        if name in self.npc_agents:
            self.npc_agents[name].location = location

    def get_time_str(self) -> str:
        return f"第{self.day}天 {self.hour:02d}:{self.minute:02d}"

    def advance_time(self, minutes: int = 30):
        self.minute += minutes
        while self.minute >= 60:
            self.minute -= 60
            self.hour += 1
            if self.hour >= 24:
                self.hour = 0
                self.day += 1

    def add_event(self, content: str, etype: str = "custom", location: str = "",
                  importance: int = 3, source_npc: str = "", target_npc: str = ""):
        return self.events.add_event(content, etype, location, importance, source_npc, target_npc)

    def add_dialogue(self, speaker: str, target: str, message: str):
        self.events.register_relationship(speaker, target)
        if target in self.npc_agents:
            self.npc_agents[target].receive_dialogue(speaker, message)

    def get_state_for_npc(self, name: str) -> dict:
        return {
            "day": self.day, "hour": self.hour, "minute": self.minute,
            "my_location": self.get_npc_location(name),
            "npcs_here": [n for n, l in self.npc_locations.items()
                           if l == self.get_npc_location(name) and n != name],
        }

    def create_player(self, name: str, profession: str = "旅行者") -> dict:
        self.player = {"name": name, "profession": profession, "location": "镇中心广场",
                       "gold": 50, "inventory": {}}
        self.economy.init_entity(name, 50)
        self.add_event(f"{name}来到了银溪镇", "custom", location="镇中心广场", importance=5)
        return self.player

    async def tick(self):
        """世界 tick — 推进时间 + 所有 NPC 并行自主行动"""
        self.advance_time(30)
        names = list(self.npc_agents.keys())
        tasks = [agent.tick() for agent in self.npc_agents.values()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        npc_updates = {}
        for name, result in zip(names, results_list):
            if isinstance(result, Exception):
                logger.error(f"NPC {name} tick 失败: {result}")
                npc_updates[name] = {"error": str(result)}
            else:
                agent = self.npc_agents[name]
                npc_updates[name] = {"actions": len(result), "activity": agent.current_activity,
                                     "location": agent.location, "mood": agent.mood}
        return npc_updates

    def get_world_state(self) -> dict:
        return {
            "time": {"day": self.day, "hour": self.hour, "minute": self.minute, "display": self.get_time_str()},
            "player": self.player,
            "locations": {name: {**info, "npcs": [n for n, l in self.npc_locations.items() if l == name]}
                          for name, info in self.locations.items()},
            "npcs": {name: agent.to_dict() for name, agent in self.npc_agents.items()},
            "quests": self.quests,
            "events": self.events.to_dict(),
            "economy": self.economy.to_dict(),
        }
