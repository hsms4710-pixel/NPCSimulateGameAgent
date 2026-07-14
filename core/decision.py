"""决策系统 — L1-L4 四级决策，按事件冲击力分配算力

L1 日常(80%): 日程表驱动，无LLM
L2 过滤(15%): 语义匹配，判断是否需要关注
L3 规划(4%):  LLM 生成行动步骤
L4 深度(1%):  LLM ReAct 深度推理
"""
import json, logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class DecisionLevel(Enum):
    L1_ROUTINE = 1
    L2_FILTER = 2
    L3_STRATEGY = 3
    L4_DEEP = 4


def classify_impact(importance: int) -> DecisionLevel:
    if importance <= 3:
        return DecisionLevel.L1_ROUTINE
    elif importance <= 6:
        return DecisionLevel.L2_FILTER
    elif importance <= 8:
        return DecisionLevel.L3_STRATEGY
    else:
        return DecisionLevel.L4_DEEP


class DecisionEngine:
    """NPC 决策引擎 — 按需分配算力"""

    def __init__(self, npc_name: str, llm_client, tools, memory):
        self.npc_name = npc_name
        self.llm = llm_client
        self.tools = tools
        self.memory = memory

    async def decide_and_act(self, world_state: dict, npc_config: dict, events: list) -> List[dict]:
        """决策并执行 — 返回 action 列表"""
        if not events:
            return self._l1_routine(world_state, npc_config)

        max_impact = max(e.get("importance", 3) for e in events)
        level = classify_impact(max_impact)

        if level == DecisionLevel.L1_ROUTINE:
            return self._l1_routine(world_state, npc_config)
        elif level == DecisionLevel.L2_FILTER:
            return self._l2_filter(world_state, npc_config, events)
        elif level == DecisionLevel.L3_STRATEGY:
            return await self._l3_strategy(world_state, npc_config, events)
        else:
            return await self._l4_deep(world_state, npc_config, events)

    def _l1_routine(self, world: dict, npc: dict) -> List[dict]:
        """L1 日常 — 日程表驱动"""
        hour = world.get("hour", 8)
        schedule = npc.get("schedule", {})
        if hour < 6:
            action = "rest"
        elif hour < 12:
            action = schedule.get("morning", "work")
        elif hour < 18:
            action = schedule.get("afternoon", "work")
        else:
            action = schedule.get("evening", "rest")

        if action in ("rest", "休息"):
            return [{"tool": "rest"}]
        return [{"tool": "work"}]

    def _l2_filter(self, world: dict, npc: dict, events: list) -> List[dict]:
        """L2 过滤 — 判断事件是否需要关注"""
        relevant = [e for e in events if e.get("importance", 0) >= 4]
        if not relevant:
            return self._l1_routine(world, npc)

        loc = world.get("my_location", "")
        for e in relevant:
            e_loc = e.get("location", "")
            if e_loc == loc or e.get("target_npc") == self.npc_name:
                return [{"tool": "observe"}]
        return self._l1_routine(world, npc)

    async def _l3_strategy(self, world: dict, npc: dict, events: list) -> List[dict]:
        """L3 规划 — LLM 生成行动步骤"""
        mem_ctx = self.memory.get_context(json.dumps(events, ensure_ascii=False)[:200])
        tool_desc = self.tools.get_tool_prompt()

        prompt = f"""你是{self.npc_name}，职业{npc.get('profession','')}，位于{world.get('my_location','')}。
当前时间：第{world.get('day',1)}天 {world.get('hour',8):02d}:00

发生的事件：
{json.dumps(events, ensure_ascii=False, indent=2)}

你的记忆：
{mem_ctx}

{tool_desc}

选择1-2个行动回应当前情况。输出JSON：
{{"actions": [{{"tool": "工具名", "params": {{}}}}]}}

只输出JSON，不要解释。"""

        result = await self.llm.chat_json_async(
            "你是一个NPC行为决策器。根据情境选择最合适的行动。只输出JSON。",
            prompt, temperature=0.4
        )
        actions = result.get("actions", [])
        if not actions:
            return self._l1_routine(world, npc)
        return actions

    async def _l4_deep(self, world: dict, npc: dict, events: list) -> List[dict]:
        """L4 深度推理 — LLM ReAct"""
        mem_ctx = self.memory.get_context(json.dumps(events, ensure_ascii=False)[:300])
        tool_desc = self.tools.get_tool_prompt()

        prompt = f"""你是{self.npc_name}，职业{npc.get('profession','')}，性格{json.dumps(npc.get('personality',{}), ensure_ascii=False)}。
位于{world.get('my_location','')}，时间第{world.get('day',1)}天{world.get('hour',8):02d}:00。

重大事件：
{json.dumps(events, ensure_ascii=False, indent=2)}

你的记忆与见解：
{mem_ctx}

{tool_desc}

仔细思考后选择行动。考虑你的性格、过去经历和当前情境。
输出JSON：{{"reasoning": "简短思考", "actions": [{{"tool": "工具名", "params": {{}}}}]}}"""

        result = await self.llm.chat_json_async(
            "你是一个有深度心智的NPC。根据性格、记忆和情境做出合理决策。只输出JSON。",
            prompt, temperature=0.7
        )
        actions = result.get("actions", [])
        if not actions:
            return self._l1_routine(world, npc)
        return actions
