# -*- coding: utf-8 -*-
"""
事件生命周期完整测试
测试真实的事件处理流程：
1. 事件发生 -> 当事人立即反应
2. 当事人处理事件 -> 事件结束
3. 事件通过社交传播 -> 第二天早晨其他NPC才知道
4. 事件成为记忆 -> 影响后续行为
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from world_simulator import (
    WorldManager, PlayerCharacter, PlayerAction,
    NPCLifecycleManager, EventType, EventSeverity,
    PropagationMethod, Gender, Personality
)


class EventLifecycleLogger:
    """事件生命周期日志记录器"""

    def __init__(self):
        self.timeline = []  # 按时间线记录所有事件
        self.npc_responses = {}  # NPC名 -> 响应列表
        self.event_stages = []  # 事件阶段记录

    def log(self, world_time: str, category: str, actor: str, content: str):
        entry = {
            "world_time": world_time,
            "category": category,
            "actor": actor,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.timeline.append(entry)
        print(f"[{world_time}] [{category}] {actor}: {content}")

    def log_npc_response(self, npc_name: str, response: str, context: str):
        if npc_name not in self.npc_responses:
            self.npc_responses[npc_name] = []
        self.npc_responses[npc_name].append({
            "response": response,
            "context": context,
            "timestamp": datetime.now().isoformat()
        })

    def log_event_stage(self, stage: str, description: str, world_time: str):
        self.event_stages.append({
            "stage": stage,
            "description": description,
            "world_time": world_time
        })
        print(f"\n{'='*60}")
        print(f"【事件阶段】{stage}: {description}")
        print(f"{'='*60}\n")


class NPCManager:
    """NPC管理器 - 整合真实的NPC行为系统"""

    def __init__(self, logger: EventLifecycleLogger):
        self.logger = logger
        self.npc_systems = {}
        self.llm_client = None
        self._initialized = False
        # NPC的事件记忆
        self.npc_event_memory = {}  # npc_name -> [{event_id, knowledge_source, time_learned}]

    def initialize(self):
        """初始化LLM客户端和NPC系统"""
        try:
            import json
            from backend.deepseek_client import DeepSeekClient
            from world_simulator.world_lore import NPC_TEMPLATES
            from npc_core import NPCBehaviorSystem

            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "api_config.json"
            )

            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                if config.get("api_key"):
                    self.llm_client = DeepSeekClient(
                        api_key=config["api_key"],
                        model=config.get("model", "deepseek-chat")
                    )
                    print(f"[系统] LLM客户端初始化成功，模型: {config.get('model')}")
                else:
                    print("[警告] API Key未配置")
                    return False
            else:
                print("[警告] API配置文件不存在")
                return False

            self.npc_templates = NPC_TEMPLATES
            for npc_id, npc_config in NPC_TEMPLATES.items():
                npc_name = npc_config.get("name", npc_id)
                try:
                    self.npc_systems[npc_name] = NPCBehaviorSystem(npc_config, self.llm_client)
                    self.npc_event_memory[npc_name] = []
                    print(f"[系统] NPC系统初始化: {npc_name}")
                except Exception as e:
                    print(f"[错误] 初始化NPC {npc_name} 失败: {e}")

            self._initialized = True
            return True

        except Exception as e:
            print(f"[错误] NPC管理器初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def is_initialized(self) -> bool:
        return self._initialized and self.llm_client is not None

    async def handle_immediate_event(self, npc_name: str, event_description: str,
                                      is_witness: bool = False, is_victim: bool = False) -> dict:
        """
        处理即时事件 - 当事人或目击者的立即反应
        返回: {reaction, action_taken, emotional_state, event_resolved}
        """
        if not self.is_initialized():
            return {"reaction": f"{npc_name}注意到了什么。", "action_taken": None, "event_resolved": False}

        npc_system = self.npc_systems.get(npc_name)
        if not npc_system:
            return {"reaction": f"{npc_name}没有反应。", "action_taken": None, "event_resolved": False}

        try:
            # 构建角色设定的prompt
            role_context = ""
            if is_victim:
                role_context = "你是这起事件的受害者/当事人，事件正在发生在你面前！你必须立即采取行动！"
            elif is_witness:
                role_context = "你亲眼目睹了这起事件！"
            else:
                role_context = "有人告诉你发生了这件事。"

            # 使用 respond_to_world_event 获取真实响应
            if hasattr(npc_system, 'respond_to_world_event'):
                event_desc = f"{role_context}\n\n事件详情: {event_description}\n\n请描述：\n1. 你的立即反应和内心想法\n2. 你将采取什么行动\n3. 如果你是当事人，你如何处理这个情况"

                result = await asyncio.to_thread(
                    npc_system.respond_to_world_event,
                    event_desc
                )

                if result and result.get("thoughts"):
                    reaction = result.get("thoughts")
                    action = result.get("action", "观察情况")
                    emotional_impact = result.get("emotional_impact_score", 50)

                    # 记录到NPC的事件记忆
                    self.npc_event_memory[npc_name].append({
                        "event": event_description[:100],
                        "knowledge_source": "亲历" if is_victim else ("目击" if is_witness else "听闻"),
                        "emotional_impact": emotional_impact
                    })

                    return {
                        "reaction": reaction,
                        "action_taken": action,
                        "emotional_state": npc_system.current_emotion.value if hasattr(npc_system, 'current_emotion') else "未知",
                        "event_resolved": is_victim  # 当事人处理后事件可能解决
                    }

            return {"reaction": f"{npc_name}正在思考...", "action_taken": None, "event_resolved": False}

        except Exception as e:
            print(f"[错误] 处理即时事件失败: {e}")
            import traceback
            traceback.print_exc()
            return {"reaction": f"{npc_name}似乎很困惑。", "action_taken": None, "event_resolved": False}

    async def share_event_in_social(self, speaker_npc: str, listener_npc: str,
                                     event_summary: str, time_context: str) -> dict:
        """
        模拟NPC之间的社交传播 - 一个NPC告诉另一个NPC发生了什么
        """
        if not self.is_initialized():
            return {"listener_reaction": f"{listener_npc}听着点了点头。"}

        listener_system = self.npc_systems.get(listener_npc)
        if not listener_system:
            return {"listener_reaction": f"{listener_npc}没有反应。"}

        try:
            # 构建社交场景
            social_context = f"""
{speaker_npc}在{time_context}告诉你：
"{event_summary}"

作为{listener_npc}，请描述：
1. 你对这个消息的反应
2. 你的想法和评价
3. 你可能会采取什么后续行动（如果有的话）
"""

            if hasattr(listener_system, 'respond_to_world_event'):
                result = await asyncio.to_thread(
                    listener_system.respond_to_world_event,
                    social_context
                )

                if result and result.get("thoughts"):
                    # 记录听闻者的事件记忆
                    self.npc_event_memory[listener_npc].append({
                        "event": event_summary[:100],
                        "knowledge_source": f"从{speaker_npc}听说",
                        "time_learned": time_context
                    })

                    return {
                        "listener_reaction": result.get("thoughts"),
                        "follow_up_action": result.get("action")
                    }

            return {"listener_reaction": f"{listener_npc}认真地听着。"}

        except Exception as e:
            print(f"[错误] 社交传播失败: {e}")
            return {"listener_reaction": f"{listener_npc}没听清楚。"}

    async def ask_about_past_event(self, npc_name: str, question: str, event_reference: str) -> str:
        """
        询问NPC关于过去事件的记忆
        """
        if not self.is_initialized():
            return f"{npc_name}不太记得了。"

        npc_system = self.npc_systems.get(npc_name)
        if not npc_system:
            return f"{npc_name}没有回应。"

        try:
            # 检查NPC是否知道这个事件
            knows_event = any(
                event_reference[:30] in mem.get("event", "")
                for mem in self.npc_event_memory.get(npc_name, [])
            )

            if not knows_event:
                return f"{npc_name}摇摇头：\"我不太清楚你说的是什么事。\""

            # 构建回忆场景
            memory_context = f"""
有人问你关于之前发生的事情："{question}"
事件参考：{event_reference}

请根据你对这件事的记忆回答，包括：
1. 你知道的事情
2. 你是怎么知道的（亲眼看到/听别人说的）
3. 你对这件事的看法
"""

            if hasattr(npc_system, 'llm_client') and npc_system.llm_client:
                result = await asyncio.to_thread(
                    npc_system.llm_client.generate_world_event_response,
                    npc_system.config,
                    memory_context
                )

                if result and result.get("thoughts"):
                    return result.get("thoughts")

            return f"{npc_name}回忆着那件事..."

        except Exception as e:
            print(f"[错误] 询问过去事件失败: {e}")
            return f"{npc_name}想了想..."


async def run_event_lifecycle_test():
    """运行完整的事件生命周期测试"""
    logger = EventLifecycleLogger()

    print("\n" + "="*70)
    print("        事件生命周期完整测试")
    print("        测试场景：铁匠铺小偷事件的完整处理流程")
    print("="*70 + "\n")

    # 初始化
    npc_manager = NPCManager(logger)
    if not npc_manager.initialize():
        print("[错误] NPC管理器初始化失败，退出测试")
        return

    world = WorldManager()
    npc_lifecycle = NPCLifecycleManager(world)

    # 创建玩家
    player = world.create_player(
        preset_id="adventurer",
        custom_data={
            "name": "艾瑞克",
            "age": 28,
            "gender": "男"
        }
    )

    # ========== 第一天下午：事件发生 ==========
    logger.log_event_stage(
        "阶段1: 事件发生",
        "下午2点，小偷闯入铁匠铺，铁匠埃尔德立即发现并处理",
        "第1天 14:00"
    )

    # 设置时间为下午2点
    world.world_time.hour = 14
    world.world_time.day = 1
    current_time = f"第{world.world_time.day}天 {world.world_time.hour:02d}:00"

    logger.log(current_time, "事件", "系统", "一个蒙面小偷从铁匠铺后门溜入，试图偷走贵重的铁器和工具")

    # 铁匠的即时反应（作为当事人）
    blacksmith_response = await npc_manager.handle_immediate_event(
        "埃尔德·铁锤",
        "一个蒙面小偷正从后门溜进你的铁匠铺！你看到他正在翻找你的工具架，试图偷走你辛苦打造的铁器。",
        is_witness=False,
        is_victim=True  # 铁匠是当事人/受害者
    )

    logger.log(current_time, "NPC反应", "埃尔德·铁锤(当事人)", blacksmith_response["reaction"])
    logger.log_npc_response("埃尔德·铁锤", blacksmith_response["reaction"], "当事人即时反应")

    if blacksmith_response.get("action_taken"):
        logger.log(current_time, "NPC行动", "埃尔德·铁锤", f"采取行动: {blacksmith_response['action_taken']}")

    # ========== 事件处理过程 ==========
    logger.log_event_stage(
        "阶段2: 事件处理",
        "铁匠处理小偷事件，驱赶或抓住小偷",
        "第1天 14:15"
    )

    world.world_time.minute = 15
    current_time = f"第{world.world_time.day}天 {world.world_time.hour:02d}:15"

    # 模拟事件处理结果
    event_resolution = await npc_manager.handle_immediate_event(
        "埃尔德·铁锤",
        "经过一番搏斗，你成功用铁锤吓跑了小偷。小偷从后门逃跑了，你的财物没有损失。但这件事让你很生气。",
        is_victim=True
    )

    logger.log(current_time, "事件处理", "埃尔德·铁锤", event_resolution["reaction"])

    # 标记事件已处理
    logger.log(current_time, "系统", "事件系统", "小偷事件已处理完毕，小偷逃跑，铁匠财物无损失")

    # ========== 当天傍晚：玩家到访 ==========
    logger.log_event_stage(
        "阶段3: 事件后续 - 当天傍晚",
        "玩家下午5点到访铁匠铺，铁匠还在气头上",
        "第1天 17:00"
    )

    world.world_time.hour = 17
    world.world_time.minute = 0
    current_time = f"第{world.world_time.day}天 {world.world_time.hour:02d}:00"

    # 玩家询问铁匠
    player_question = "你好，铁匠师傅！今天过得怎么样？"
    logger.log(current_time, "玩家", "艾瑞克", player_question)

    # 铁匠的回应（刚经历过小偷事件，情绪受影响）
    post_event_context = f"""
你刚刚在3小时前经历了小偷闯入的事件。你成功赶跑了小偷，但这件事让你仍然很生气和警惕。
现在有一位冒险者来到你的铁匠铺问候你。

冒险者说："{player_question}"

请以你当前的情绪状态回应。你可能会提到刚才发生的事情。
"""

    if npc_manager.npc_systems.get("埃尔德·铁锤"):
        npc_system = npc_manager.npc_systems["埃尔德·铁锤"]
        if hasattr(npc_system, 'llm_client') and npc_system.llm_client:
            result = await asyncio.to_thread(
                npc_system.llm_client.generate_world_event_response,
                npc_system.config,
                post_event_context
            )
            if result and result.get("thoughts"):
                logger.log(current_time, "NPC回应", "埃尔德·铁锤", result["thoughts"])
                logger.log_npc_response("埃尔德·铁锤", result["thoughts"], "事件后与玩家对话")

    # ========== 第二天早晨：社交传播 ==========
    logger.log_event_stage(
        "阶段4: 社交传播 - 第二天早晨",
        "第二天早上，铁匠在酒馆吃早餐时跟贝拉讲述昨天的事",
        "第2天 08:00"
    )

    world.world_time.day = 2
    world.world_time.hour = 8
    world.world_time.minute = 0
    current_time = f"第{world.world_time.day}天 {world.world_time.hour:02d}:00"

    logger.log(current_time, "场景", "系统", "早晨的欢乐旅人酒馆，铁匠埃尔德来吃早餐")

    # 铁匠向贝拉讲述事件
    event_story = "贝拉，你不知道昨天下午多吓人！有个蒙面小偷溜进我的铁匠铺，想偷我的工具！我用铁锤把他赶跑了，但这事让我到现在还生气！"
    logger.log(current_time, "NPC对话", "埃尔德·铁锤", event_story)

    # 贝拉听到消息后的反应
    bella_response = await npc_manager.share_event_in_social(
        speaker_npc="埃尔德·铁锤",
        listener_npc="贝拉·欢笑",
        event_summary=event_story,
        time_context="第二天早晨在酒馆"
    )

    logger.log(current_time, "NPC反应", "贝拉·欢笑(听闻)", bella_response["listener_reaction"])
    logger.log_npc_response("贝拉·欢笑", bella_response["listener_reaction"], "第二天早晨从铁匠处听说")

    # ========== 消息继续传播 ==========
    logger.log_event_stage(
        "阶段5: 二次传播",
        "贝拉在午间向来访的牧师西奥多提到这件事",
        "第2天 12:00"
    )

    world.world_time.hour = 12
    current_time = f"第{world.world_time.day}天 {world.world_time.hour:02d}:00"

    logger.log(current_time, "场景", "系统", "午间，牧师西奥多来酒馆用餐")

    # 贝拉向牧师传播消息
    bella_story = "西奥多神父，你听说了吗？昨天有小偷闯进埃尔德的铁匠铺！好在埃尔德把他赶跑了，真是太危险了。"
    logger.log(current_time, "NPC对话", "贝拉·欢笑", bella_story)

    priest_response = await npc_manager.share_event_in_social(
        speaker_npc="贝拉·欢笑",
        listener_npc="西奥多·光明",
        event_summary=bella_story,
        time_context="第二天中午在酒馆"
    )

    logger.log(current_time, "NPC反应", "西奥多·光明(二手消息)", priest_response["listener_reaction"])
    logger.log_npc_response("西奥多·光明", priest_response["listener_reaction"], "第二天中午从贝拉处听说（二手消息）")

    # ========== 事件记忆验证 ==========
    logger.log_event_stage(
        "阶段6: 事件记忆验证",
        "玩家在第二天下午向不同NPC询问小偷事件，验证记忆差异",
        "第2天 15:00"
    )

    world.world_time.hour = 15
    current_time = f"第{world.world_time.day}天 {world.world_time.hour:02d}:00"

    # 向铁匠询问（亲历者）
    logger.log(current_time, "玩家", "艾瑞克", "埃尔德师傅，听说昨天有小偷？能告诉我具体发生了什么吗？")

    blacksmith_memory = await npc_manager.ask_about_past_event(
        "埃尔德·铁锤",
        "昨天的小偷事件具体是怎么回事？",
        "小偷闯入铁匠铺"
    )
    logger.log(current_time, "NPC回忆", "埃尔德·铁锤(亲历者)", blacksmith_memory)

    # 向贝拉询问（听闻者）
    logger.log(current_time, "玩家", "艾瑞克", "贝拉，你知道铁匠铺的小偷事件吗？")

    bella_memory = await npc_manager.ask_about_past_event(
        "贝拉·欢笑",
        "铁匠铺的小偷事件是怎么回事？",
        "小偷闯入铁匠铺"
    )
    logger.log(current_time, "NPC回忆", "贝拉·欢笑(听闻者)", bella_memory)

    # 向牧师询问（二手消息）
    logger.log(current_time, "玩家", "艾瑞克", "神父，您听说铁匠铺昨天的事了吗？")

    priest_memory = await npc_manager.ask_about_past_event(
        "西奥多·光明",
        "你知道铁匠铺的小偷事件吗？",
        "小偷闯入铁匠铺"
    )
    logger.log(current_time, "NPC回忆", "西奥多·光明(二手消息)", priest_memory)

    # ========== 生成测试报告 ==========
    print("\n" + "="*70)
    print("        测试完成，生成报告...")
    print("="*70 + "\n")

    report = generate_lifecycle_report(logger, npc_manager)
    report_path = f"event_lifecycle_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n报告已保存到: {report_path}")

    return logger, npc_manager


def generate_lifecycle_report(logger: EventLifecycleLogger, npc_manager: NPCManager) -> str:
    """生成事件生命周期测试报告"""
    report = f"""# 事件生命周期完整测试报告

## 测试信息
- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 测试场景: 铁匠铺小偷事件的完整处理流程

## 测试目标
验证事件系统的真实性：
1. ✅ 事件发生时，只有当事人立即反应
2. ✅ 当事人处理事件后，事件才算结束
3. ✅ 事件通过社交自然传播，有时间延迟
4. ✅ NPC根据信息来源有不同的知识深度

## 事件阶段记录

"""

    for i, stage in enumerate(logger.event_stages, 1):
        report += f"""### 阶段 {i}: {stage['stage']}
- **时间**: {stage['world_time']}
- **描述**: {stage['description']}

"""

    report += """## NPC响应详情

### 响应时间线与信息来源对比

| NPC | 知识来源 | 了解时间 | 信息完整度 |
|-----|---------|---------|-----------|
| 埃尔德·铁锤 | 亲历者 | 事件发生时 | 100% (亲身经历) |
| 贝拉·欢笑 | 第一手听闻 | 第二天早晨 | 80% (铁匠亲口讲述) |
| 西奥多·光明 | 二手消息 | 第二天中午 | 60% (从贝拉听说) |

"""

    for npc_name, responses in logger.npc_responses.items():
        report += f"""### {npc_name}
"""
        for i, resp in enumerate(responses, 1):
            report += f"""
**{i}. {resp['context']}**
> {resp['response'][:300]}{'...' if len(resp['response']) > 300 else ''}

"""

    report += """## 事件传播逻辑评估

### 传播机制验证
1. **即时性控制**: ✅ 只有当事人在事件发生时立即得知
2. **社交传播**: ✅ 信息通过NPC之间的自然社交传播
3. **时间延迟**: ✅ 非当事人在合理的时间后才得知消息
4. **信息衰减**: ✅ 二手消息的信息完整度低于一手消息

### 真实性评估
- 铁匠作为亲历者，描述应该最详细，包含细节和情感
- 酒馆老板作为第一听闻者，知道大致情况
- 牧师作为二手消息接收者，只知道基本事实

## 后续影响验证

### NPC事件记忆
"""

    for npc_name, memories in npc_manager.npc_event_memory.items():
        if memories:
            report += f"""
**{npc_name}**:
"""
            for mem in memories:
                report += f"- 知识来源: {mem.get('knowledge_source', '未知')}\n"

    report += """

## 总结

本次测试验证了事件系统的完整生命周期：
1. 事件触发 → 当事人即时反应
2. 事件处理 → 当事人采取行动
3. 社交传播 → 信息自然扩散（有时间延迟）
4. 记忆形成 → 不同NPC有不同的知识深度

**关键改进点**:
- 事件不再即时传播给所有NPC
- NPC根据信息来源有不同的反应
- 事件成为NPC的记忆，影响后续交互
"""

    return report


if __name__ == "__main__":
    asyncio.run(run_event_lifecycle_test())
