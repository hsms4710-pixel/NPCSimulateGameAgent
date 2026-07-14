"""NPC 子 Agent — 自治心智体

每个 NPC 是一个独立 Agent：
- 自治循环：感知→记忆检索→决策→执行tools→记录记忆→反思
- 可被玩家对话触发
- 自主移动、工作、社交
"""
import json, logging, asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from .memory import MemorySystem
from .decision import DecisionEngine
from .tools import NPCTools

logger = logging.getLogger(__name__)


class NPCAgent:
    """NPC 子 Agent — 有记忆、会决策、能行动的自治体"""

    def __init__(self, name: str, config: dict, world: "WorldManager", llm_client):
        self.name = name
        self.config = config
        self.world = world
        self.llm = llm_client

        self.profession = config.get("profession", "村民")
        self.personality = config.get("personality", {})
        self.background = config.get("background", "")
        self.location = config.get("location", "镇中心广场")
        self.schedule = config.get("schedule", {})

        self.energy = 100
        self.mood = "平静"
        self.current_activity = "空闲"

        # 核心模块
        self.memory = MemorySystem(name, world.data_dir)
        self.tools = NPCTools(name, world)
        self.decision = DecisionEngine(name, llm_client, self.tools, self.memory)

        # 初始记忆
        self.memory.add(f"我是{name}，{self.background[:80]}", "background", importance=8)

        self._dialogue_queue: List[dict] = []

    async def tick(self):
        """世界 tick — NPC 自主行动"""
        world_state = self.world.get_state_for_npc(self.name)

        # 1. 感知：获取可见事件
        events = self.world.events.get_npc_events(self.name, self.location)
        for evt in events:
            self.memory.add(evt.content, "event", importance=evt.importance, source_npc=evt.source_npc)

        # 2. 处理对话队列
        if self._dialogue_queue:
            return await self._handle_dialogue()

        # 3. 决策
        actions = await self.decision.decide_and_act(world_state, self.config, [
            {"content": e.content, "importance": e.importance, "type": e.type,
             "location": e.location, "target_npc": e.target_npc}
            for e in events
        ])

        # 4. 执行
        results = []
        for action in actions[:3]:  # 每 tick 最多 3 个行动
            tool = action.get("tool", "")
            params = action.get("params", {})
            result = self.tools.execute(tool, **params)
            results.append({"tool": tool, "params": params, "result": result})

            if result.get("ok"):
                self.memory.add(f"执行了{tool}: {json.dumps(params, ensure_ascii=False)}", "action", importance=3)
                if tool == "rest":
                    self.energy = min(100, self.energy + 20)
                    self.current_activity = "休息"
                elif tool == "work":
                    self.energy = max(0, self.energy - 10)
                    self.current_activity = "工作"
                elif tool == "move_to":
                    self.location = params.get("location", self.location)
                    self.current_activity = "移动"

        # 5. 反思（异步，避免阻塞）
        if self.memory.should_reflect():
            insight = await asyncio.to_thread(self.memory.reflect, self.llm)
            if insight:
                self.mood = "若有所思"

        return results

    async def _handle_dialogue(self) -> list:
        """处理玩家对话"""
        if not self._dialogue_queue:
            return []
        dlg = self._dialogue_queue.pop(0)
        speaker = dlg["speaker"]
        message = dlg["message"]

        self.memory.add(f"{speaker}说：{message}", "dialogue", importance=7, source_npc=speaker)

        mem_ctx = self.memory.get_context(message, max_items=5)
        prompt = f"""你是{self.name}，{self.profession}，位于{self.location}。
性格：{json.dumps(self.personality, ensure_ascii=False)}
背景：{self.background}

{speaker}对你说：{message}

相关记忆：
{mem_ctx}

以{self.name}的口吻回复（符合性格和背景，自然口语化，1-3句话）："""

        reply = await self.llm.chat_async([
            {"role": "system", "content": f"你是{self.name}，一个{self.profession}。保持角色设定，自然回复。"},
            {"role": "user", "content": prompt}
        ], temperature=0.8, max_tokens=200)

        self.memory.add(f"我回复{speaker}：{reply}", "dialogue", importance=6, source_npc=self.name)
        self.current_activity = "对话"
        return [{"tool": "talk_to", "result": {"reply": reply, "speaker": self.name}}]

    def receive_dialogue(self, speaker: str, message: str):
        """玩家触发对话"""
        self._dialogue_queue.append({"speaker": speaker, "message": message})

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "profession": self.profession,
            "location": self.location,
            "energy": self.energy,
            "mood": self.mood,
            "activity": self.current_activity,
            "memory": self.memory.to_dict(),
        }
