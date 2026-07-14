"""NPC Tools — Agent 可调用的能力

每个 NPC 子 Agent 通过 tools 操控世界：
move_to / trade / talk_to / observe / work / rest / accept_quest
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {"name": "move_to", "description": "移动到指定地点", "params": {"location": "目标地点名"}},
    {"name": "talk_to", "description": "与某个NPC对话", "params": {"target": "目标NPC名", "message": "要说的话"}},
    {"name": "trade", "description": "与NPC交易物品", "params": {"target": "目标NPC名", "item": "物品名", "action": "buy或sell"}},
    {"name": "observe", "description": "观察当前地点的环境和NPC", "params": {}},
    {"name": "work", "description": "执行当前职业的工作", "params": {}},
    {"name": "rest", "description": "休息恢复精力", "params": {}},
    {"name": "accept_quest", "description": "接受一个任务", "params": {"quest_id": "任务ID"}},
]


class NPCTools:
    """NPC 的工具集 — 通过 world 引用操控世界"""

    def __init__(self, npc_name: str, world: "WorldManager"):
        self.npc_name = npc_name
        self.world = world

    def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        fn = getattr(self, f"tool_{tool_name}", None)
        if not fn:
            return {"ok": False, "error": f"未知工具: {tool_name}"}
        try:
            result = fn(**kwargs)
            return {"ok": True, **result} if isinstance(result, dict) else {"ok": True, "result": result}
        except Exception as e:
            logger.error(f"[{self.npc_name}] tool_{tool_name} 失败: {e}")
            return {"ok": False, "error": str(e)}

    def tool_move_to(self, location: str) -> dict:
        loc = self.world.locations.get(location)
        if not loc:
            return {"ok": False, "error": f"未知地点: {location}"}
        old = self.world.get_npc_location(self.npc_name)
        self.world.set_npc_location(self.npc_name, location)
        self.world.add_event(f"{self.npc_name}从{old}来到了{location}", "move", location=location)
        return {"from": old, "to": location, "description": loc.get("description", "")}

    def tool_talk_to(self, target: str, message: str) -> dict:
        target_loc = self.world.get_npc_location(target)
        my_loc = self.world.get_npc_location(self.npc_name)
        if target_loc != my_loc:
            return {"ok": False, "error": f"{target}不在{my_loc}，在{target_loc}"}
        self.world.add_dialogue(self.npc_name, target, message)
        self.world.add_event(f"{self.npc_name}对{target}说：{message[:50]}", "dialogue", location=my_loc)
        return {"target": target, "message": message}

    def tool_trade(self, target: str, item: str, action: str = "buy") -> dict:
        result = self.world.economy.trade(self.npc_name, target, item, action)
        if result.get("ok"):
            self.world.add_event(f"{self.npc_name}向{target}{action}了{item}", "trade", location=self.world.get_npc_location(self.npc_name))
        return result

    def tool_observe(self) -> dict:
        loc = self.world.get_npc_location(self.npc_name)
        loc_info = self.world.locations.get(loc, {})
        npcs_here = [n for n, l in self.world.npc_locations.items() if l == loc and n != self.npc_name]
        return {
            "location": loc,
            "description": loc_info.get("description", ""),
            "npcs_here": npcs_here,
            "services": loc_info.get("services", []),
            "time": self.world.get_time_str(),
        }

    def tool_work(self) -> dict:
        loc = self.world.get_npc_location(self.npc_name)
        npc = self.world.npc_configs.get(self.npc_name, {})
        profession = npc.get("profession", "村民")
        self.world.add_event(f"{self.npc_name}开始做{profession}的工作", "work", location=loc)
        return {"profession": profession, "location": loc}

    def tool_rest(self) -> dict:
        self.world.add_event(f"{self.npc_name}正在休息", "rest", location=self.world.get_npc_location(self.npc_name))
        return {"ok": True}

    def tool_accept_quest(self, quest_id: str) -> dict:
        quest = self.world.quests.get(quest_id)
        if not quest:
            return {"ok": False, "error": f"任务{quest_id}不存在"}
        if quest.get("status") != "available":
            return {"ok": False, "error": "任务不可接"}
        quest["status"] = "active"
        quest["accepted_by"] = self.npc_name
        self.world.add_event(f"{self.npc_name}接受了任务：{quest.get('title', quest_id)}", "quest")
        return {"quest": quest}

    def get_tool_prompt(self) -> str:
        """生成 tools 描述供 LLM 决策使用"""
        lines = ["你可以执行以下操作:"]
        for t in TOOL_DEFINITIONS:
            params = ", ".join(f"{k}={v}" for k, v in t["params"].items()) if t["params"] else ""
            lines.append(f"- {t['name']}({params}): {t['description']}")
        return "\n".join(lines)
