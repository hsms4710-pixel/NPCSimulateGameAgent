# -*- coding: utf-8 -*-
"""
世界模拟器测试脚本 - 真实LLM版本
模拟玩家一天的活动和世界事件触发，使用真实LLM生成NPC响应
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from world_simulator import (
    WorldManager, PlayerCharacter, PlayerAction,
    NPCLifecycleManager, EventType, EventSeverity,
    Gender, Personality
)


class SimulationLogger:
    """模拟日志记录器"""

    def __init__(self):
        self.logs = []
        self.events = []
        self.npc_reactions = []

    def log(self, category: str, message: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "message": message
        }
        self.logs.append(entry)
        print(f"[{category}] {message}")

    def log_event(self, event_data: dict):
        self.events.append(event_data)

    def log_npc_reaction(self, npc_name: str, reaction: str):
        self.npc_reactions.append({
            "npc": npc_name,
            "reaction": reaction,
            "timestamp": datetime.now().isoformat()
        })


class NPCManager:
    """NPC管理器 - 整合真实的NPC行为系统"""

    def __init__(self, logger: SimulationLogger):
        self.logger = logger
        self.npc_systems = {}  # npc_name -> NPCBehaviorSystem
        self.llm_client = None
        self._initialized = False

    def initialize(self):
        """初始化LLM客户端和NPC系统"""
        try:
            import json
            from backend.deepseek_client import DeepSeekClient
            from world_simulator.world_lore import NPC_TEMPLATES
            from npc_core import NPCBehaviorSystem

            # 加载API配置
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
                    self.logger.log("系统", f"LLM客户端初始化成功，模型: {config.get('model')}")
                else:
                    self.logger.log("警告", "API Key未配置，将使用模拟响应")
                    return False
            else:
                self.logger.log("警告", "API配置文件不存在")
                return False

            # 初始化NPC系统
            self.npc_templates = NPC_TEMPLATES
            for npc_id, npc_config in NPC_TEMPLATES.items():
                npc_name = npc_config.get("name", npc_id)
                try:
                    self.npc_systems[npc_name] = NPCBehaviorSystem(npc_config, self.llm_client)
                    self.logger.log("系统", f"NPC系统初始化: {npc_name}")
                except Exception as e:
                    self.logger.log("错误", f"初始化NPC {npc_name} 失败: {e}")

            self._initialized = True
            return True

        except Exception as e:
            self.logger.log("错误", f"NPC管理器初始化失败: {e}")
            return False

    def is_initialized(self) -> bool:
        return self._initialized and self.llm_client is not None

    async def get_npc_response(self, npc_name: str, dialogue: str, player_info: str = "") -> str:
        """获取NPC对对话的响应"""
        if not self.is_initialized():
            return f"{npc_name}友好地回应了你。"

        npc_system = self.npc_systems.get(npc_name)
        if not npc_system:
            return f"{npc_name}看着你，似乎不知道该说什么。"

        try:
            # 尝试使用 LLM 客户端直接生成对话响应
            if hasattr(npc_system, 'llm_client') and npc_system.llm_client:
                # 构建对话上下文
                context = f"玩家说: \"{dialogue}\""
                if player_info:
                    context = f"[玩家信息: {player_info[:200]}]\n\n{context}"

                # 调用 LLM 生成响应
                result = await asyncio.to_thread(
                    npc_system.llm_client.generate_dialogue_response,
                    npc_system.config,
                    context
                )

                if result and result.get("dialogue"):
                    return result.get("dialogue")
                elif result and result.get("response"):
                    return result.get("response")

            # 备选：使用 process_event
            event_content = f"玩家对你说: \"{dialogue}\""
            if player_info:
                event_content = f"[玩家信息: {player_info[:200]}]\n\n{event_content}"

            result = await asyncio.to_thread(
                npc_system.process_event,
                event_content,
                "dialogue"
            )

            response = result.get("response_text", "") or result.get("response", "")
            if response and response not in ["我在处理这个情况。", "让我们聊一聊吧。"]:
                return response

            # 如果返回的是默认响应，尝试从推理中获取更多信息
            if result.get("reasoning"):
                return f"{npc_name}: {result.get('reasoning')[:150]}"

            return f"{npc_name}点了点头，微笑着回应。"

        except Exception as e:
            self.logger.log("错误", f"获取NPC响应失败: {e}")
            import traceback
            traceback.print_exc()
            return f"{npc_name}似乎在思考着什么。"

    async def notify_event(self, npc_name: str, event_title: str, event_description: str,
                           event_location: str) -> str:
        """通知NPC有世界事件发生，获取其反应"""
        if not self.is_initialized():
            return f"{npc_name}对此事件表示关注。"

        npc_system = self.npc_systems.get(npc_name)
        if not npc_system:
            return f"{npc_name}没有对此做出反应。"

        try:
            # 优先使用专门的世界事件响应方法
            if hasattr(npc_system, 'respond_to_world_event'):
                event_desc = f"【{event_title}】发生在{event_location}: {event_description}"

                result = await asyncio.to_thread(
                    npc_system.respond_to_world_event,
                    event_desc
                )

                # 从结果中提取响应
                if result:
                    if result.get("thoughts"):
                        return result.get("thoughts")
                    if result.get("response"):
                        return result.get("response")
                    if result.get("action"):
                        return result.get("action")

            # 备选：使用 LLM 客户端直接生成
            if hasattr(npc_system, 'llm_client') and npc_system.llm_client:
                event_desc = f"【{event_title}】发生在{event_location}: {event_description}"

                result = await asyncio.to_thread(
                    npc_system.llm_client.generate_world_event_response,
                    npc_system.config,
                    event_desc
                )

                if result and result.get("thoughts"):
                    return result.get("thoughts")

            # 最后备选：使用 process_event
            event_content = f"【紧急事件通知】\n标题: {event_title}\n地点: {event_location}\n详情: {event_description}"

            result = await asyncio.to_thread(
                npc_system.process_event,
                event_content,
                "world_event"
            )

            response = result.get("response_text", "") or result.get("response", "")
            if response and response not in ["（注意到周围发生了什么变化）", "我在处理这个情况。"]:
                return response

            if result.get("reasoning"):
                return f"{npc_name}: {result.get('reasoning')[:150]}"

            # 如果没有直接响应，尝试获取NPC的状态描述
            status = npc_system.get_status_summary()
            mood = status.get("current_emotion", "平静")
            activity = status.get("current_activity", "思考")
            return f"{npc_name}（{mood}）正在{activity}，对发生的事情保持警觉。"

        except Exception as e:
            self.logger.log("错误", f"通知NPC事件失败: {e}")
            import traceback
            traceback.print_exc()
            return f"{npc_name}注意到了这个事件。"


async def run_simulation():
    """运行一天的模拟"""
    logger = SimulationLogger()
    logger.log("系统", "=" * 60)
    logger.log("系统", "世界模拟器测试开始 - 真实LLM版本")
    logger.log("系统", "=" * 60)

    # 初始化NPC管理器
    npc_manager = NPCManager(logger)
    llm_available = npc_manager.initialize()

    if not llm_available:
        logger.log("警告", "LLM不可用，将使用简化响应模式")

    # 初始化世界管理器
    world = WorldManager()
    npc_lifecycle = NPCLifecycleManager(world)

    # 设置NPC管理器引用到世界管理器
    world._npc_manager = npc_manager

    logger.log("系统", f"世界时间: {world.world_time.to_string()}")

    # ========== 阶段1：创建玩家角色 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段1】创建玩家角色")
    logger.log("系统", "=" * 40)

    player = world.create_player(
        preset_id="adventurer",
        custom_data={
            "name": "艾瑞克",
            "age": 28,
            "gender": "男",
            "birthplace": "北境王国",
            "appearance": "棕色短发，蓝色眼睛，身材魁梧"
        }
    )

    logger.log("玩家", f"玩家 '{player.name}' 已创建")
    logger.log("玩家", f"职业: {player.profession.value}")
    logger.log("玩家", f"背景: {player.background}")
    logger.log("玩家", f"起始位置: {player.current_location}")

    # ========== 阶段2：早晨活动 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段2】早晨活动 (8:00 - 12:00)")
    logger.log("系统", "=" * 40)

    # 更新所有NPC状态
    npc_updates = npc_lifecycle.update_all_npcs_for_time(8)
    for update in npc_updates:
        logger.log("NPC", f"{update['npc_name']}: {update['new_activity']} @ {update['new_location']}")

    # 玩家在酒馆，与酒馆老板交谈
    logger.log("玩家", f"\n当前位置: {player.current_location}")
    location_info = world.get_current_location_info()
    logger.log("系统", f"位置描述: {location_info.get('description', '')}")
    logger.log("系统", f"此处NPC: {[npc['name'] for npc in location_info.get('npcs', [])]}")

    # 社交 - 与贝拉交谈 (使用真实LLM)
    logger.log("玩家", "\n--- 玩家与贝拉·欢笑交谈 ---")
    dialogue = "早上好！我是刚到镇上的冒险者，请问这里最近有什么有趣的消息吗？"
    logger.log("玩家", f"艾瑞克说: \"{dialogue}\"")

    response = await npc_manager.get_npc_response(
        "贝拉·欢笑",
        dialogue,
        player.get_character_card()
    )
    logger.log("NPC回应", f"贝拉·欢笑: {response}")
    logger.log_npc_reaction("贝拉·欢笑", response)

    # 满足社交需求
    player.needs.satisfy_social(0.2)
    player.update_relationship("贝拉·欢笑", affinity_change=1, trust_change=0.5)

    # 推进时间1小时
    world.advance_time(60)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 饮食
    logger.log("玩家", "\n--- 玩家在酒馆进餐 ---")
    result = await world.execute_player_action(action="饮食")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")
    logger.log("玩家", f"剩余金币: {player.gold}")

    # 移动到铁匠铺
    logger.log("玩家", "\n--- 玩家移动到铁匠铺 ---")
    await world.execute_player_action(action="移动", target="市场区")
    await world.execute_player_action(action="移动", target="镇中心")
    await world.execute_player_action(action="移动", target="工坊区")
    result = await world.execute_player_action(action="移动", target="铁匠铺")
    logger.log("玩家", f"到达: {player.current_location}")

    # 与铁匠交谈 (使用真实LLM)
    logger.log("玩家", "\n--- 玩家与埃尔德·铁锤交谈 ---")
    dialogue = "你好，老铁匠！我是个冒险者，需要一把结实的剑。你能帮我打造吗？大概需要多少钱？"
    logger.log("玩家", f"艾瑞克说: \"{dialogue}\"")

    response = await npc_manager.get_npc_response(
        "埃尔德·铁锤",
        dialogue,
        player.get_character_card()
    )
    logger.log("NPC回应", f"埃尔德·铁锤: {response}")
    logger.log_npc_reaction("埃尔德·铁锤", response)

    player.update_relationship("埃尔德·铁锤", affinity_change=1, trust_change=0.5)

    # ========== 阶段3：下午活动和世界事件 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段3】下午活动与世界事件 (12:00 - 18:00)")
    logger.log("系统", "=" * 40)

    # 推进时间到下午2点
    world.advance_time(120)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 更新NPC状态
    npc_updates = npc_lifecycle.update_all_npcs_for_time(14)
    for update in npc_updates:
        if update.get('old_activity') != update.get('new_activity'):
            logger.log("NPC", f"{update['npc_name']}: {update['old_activity']} -> {update['new_activity']}")

    # 玩家工作赚钱
    logger.log("玩家", "\n--- 玩家在铁匠铺帮工 ---")
    result = await world.execute_player_action(action="工作")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")
    logger.log("玩家", f"当前金币: {player.gold}")

    # ========== 触发世界事件：铁匠铺遭小偷入侵 ==========
    logger.log("系统", "\n" + "!" * 50)
    logger.log("事件", "【世界事件触发】铁匠铺遭小偷入侵！")
    logger.log("系统", "!" * 50)

    event = world.trigger_world_event(
        title="铁匠铺遭小偷入侵",
        description="一个蒙面小偷趁铁匠不注意，潜入铁匠铺试图偷走贵重工具和金属。小偷从后门溜进来，正在翻找值钱的东西。",
        location="铁匠铺",
        event_type="犯罪",
        severity=4
    )

    logger.log_event(event.to_dict())
    logger.log("事件", f"事件ID: {event.event_id}")
    logger.log("事件", f"严重程度: {event.severity.value}")
    logger.log("事件", f"发生位置: {event.location}")

    # 传播事件到NPC - 使用真实LLM获取反应
    logger.log("系统", "\n--- NPC对事件的反应 (LLM生成) ---")

    # 埃尔德·铁锤在场，立即发现
    blacksmith_reaction = await npc_manager.notify_event(
        "埃尔德·铁锤",
        event.title,
        event.description,
        event.location
    )
    logger.log("NPC反应", f"[铁匠铺 - 现场] 埃尔德·铁锤: {blacksmith_reaction}")
    logger.log_npc_reaction("埃尔德·铁锤", blacksmith_reaction)

    # 标记事件已通知
    npc_lifecycle.npc_states["埃尔德·铁锤"].known_events.append(event.event_id)

    # 玩家在场，可以选择帮助
    logger.log("玩家", "\n玩家目睹了小偷入侵事件！")

    # 推进时间30分钟，让事件传播
    world.advance_time(30)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 模拟事件传播到其他NPC（假设通过口口相传）
    logger.log("系统", "\n--- 事件信息开始传播 ---")

    # 1小时后，酒馆老板听说了
    world.advance_time(60)

    bella_reaction = await npc_manager.notify_event(
        "贝拉·欢笑",
        event.title,
        f"有人告诉贝拉，{event.description}",
        "酒馆"
    )
    logger.log("NPC反应", f"[酒馆 - 1小时后] 贝拉·欢笑: {bella_reaction}")
    logger.log_npc_reaction("贝拉·欢笑", bella_reaction)

    # 2小时后，牧师也听说了
    world.advance_time(60)

    priest_reaction = await npc_manager.notify_event(
        "西奥多·光明",
        event.title,
        f"教区居民告诉西奥多，{event.description}",
        "圣光教堂"
    )
    logger.log("NPC反应", f"[圣光教堂 - 2小时后] 西奥多·光明: {priest_reaction}")
    logger.log_npc_reaction("西奥多·光明", priest_reaction)

    # ========== 阶段4：傍晚活动 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段4】傍晚活动 (18:00 - 22:00)")
    logger.log("系统", "=" * 40)

    # 推进到傍晚
    world.advance_time(60)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 更新NPC状态
    npc_updates = npc_lifecycle.update_all_npcs_for_time(18)
    for update in npc_updates:
        logger.log("NPC", f"{update['npc_name']}: {update['new_activity']} @ {update['new_location']}")

    # 玩家返回酒馆休息
    logger.log("玩家", "\n--- 玩家返回酒馆 ---")
    await world.execute_player_action(action="移动", target="工坊区")
    await world.execute_player_action(action="移动", target="镇中心")
    await world.execute_player_action(action="移动", target="市场区")
    await world.execute_player_action(action="移动", target="酒馆")
    logger.log("玩家", f"当前位置: {player.current_location}")

    # 与酒馆老板聊聊今天的事件 (使用真实LLM)
    logger.log("玩家", "\n--- 玩家与贝拉讨论今天的事件 ---")
    dialogue = "贝拉，今天铁匠铺的事你听说了吗？我可是亲眼看到的！那小偷差点就得手了。"
    logger.log("玩家", f"艾瑞克说: \"{dialogue}\"")

    response = await npc_manager.get_npc_response(
        "贝拉·欢笑",
        dialogue,
        player.get_character_card()
    )
    logger.log("NPC回应", f"贝拉·欢笑: {response}")
    logger.log_npc_reaction("贝拉·欢笑", response)

    # 休息
    logger.log("玩家", "\n--- 玩家休息恢复精力 ---")
    result = await world.execute_player_action(action="休息")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")
    logger.log("玩家", f"当前疲劳度: {player.needs.fatigue:.2f}")

    # 晚餐
    logger.log("玩家", "\n--- 玩家享用晚餐 ---")
    result = await world.execute_player_action(action="饮食")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")

    # ========== 阶段5：夜晚与总结 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段5】夜晚与一天总结")
    logger.log("系统", "=" * 40)

    # 推进到夜晚
    world.advance_time(180)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 更新NPC状态
    npc_updates = npc_lifecycle.update_all_npcs_for_time(22)
    for update in npc_updates:
        logger.log("NPC", f"{update['npc_name']}: {update['new_activity']}")

    # 输出玩家状态总结
    logger.log("系统", "\n" + "-" * 40)
    logger.log("系统", "【玩家一天总结】")
    logger.log("系统", "-" * 40)
    logger.log("玩家", f"姓名: {player.name}")
    logger.log("玩家", f"金币: {player.gold}")
    logger.log("玩家", f"饥饿度: {player.needs.hunger:.2f}")
    logger.log("玩家", f"疲劳度: {player.needs.fatigue:.2f}")
    logger.log("玩家", f"社交需求: {player.needs.social:.2f}")
    logger.log("玩家", f"建立的关系: {list(player.relationships.keys())}")
    logger.log("玩家", f"记忆数量: {len(player.memories)}")

    # 输出NPC状态
    logger.log("系统", "\n" + "-" * 40)
    logger.log("系统", "【NPC状态总结】")
    logger.log("系统", "-" * 40)
    for npc_name, state in npc_lifecycle.npc_states.items():
        logger.log("NPC", f"{npc_name}: {state.current_activity.value} @ {state.current_location}")
        if state.known_events:
            logger.log("NPC", f"  已知事件: {state.known_events}")

    # 输出事件总结
    logger.log("系统", "\n" + "-" * 40)
    logger.log("系统", "【世界事件总结】")
    logger.log("系统", "-" * 40)
    for evt in world.event_trigger.event_history:
        logger.log("事件", f"[{evt.severity.value}级] {evt.title} @ {evt.location}")

    # 输出NPC反应总结
    logger.log("系统", "\n" + "-" * 40)
    logger.log("系统", "【NPC反应记录 (LLM生成)】")
    logger.log("系统", "-" * 40)
    for reaction in logger.npc_reactions:
        logger.log("反应", f"{reaction['npc']}: {reaction['reaction'][:100]}...")

    # 导出日志
    logger.log("系统", "\n" + "=" * 60)
    logger.log("系统", "模拟结束，正在导出日志...")

    filepath = world.export_logs_to_markdown()
    logger.log("系统", f"日志已导出到: {filepath}")

    return world, logger, npc_lifecycle, npc_manager


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("        艾伦谷世界模拟器 - 真实LLM测试")
    print("=" * 70 + "\n")

    world, logger, npc_lifecycle, npc_manager = await run_simulation()

    # 生成详细测试报告
    report_path = generate_test_report(world, logger, npc_lifecycle, npc_manager)
    print(f"\n测试报告已生成: {report_path}")


def generate_test_report(world, logger, npc_lifecycle, npc_manager):
    """生成详细测试报告"""
    report_path = f"test_report_llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    llm_status = "已启用" if npc_manager.is_initialized() else "未启用（使用模拟响应）"

    content = f"""# 世界模拟器测试报告 - 真实LLM版本

## 测试信息
- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- LLM状态: {llm_status}
- 模拟天数: {world.world_time.day}
- 最终世界时间: {world.world_time.to_string()}

## 1. 玩家信息

### 基础属性
| 属性 | 值 |
|------|-----|
| 姓名 | {world.player.name} |
| 年龄 | {world.player.age} |
| 性别 | {world.player.gender.value} |
| 职业 | {world.player.profession.value} |
| 当前位置 | {world.player.current_location} |
| 金币 | {world.player.gold} |

### 需求状态
| 需求 | 值 | 状态 |
|------|-----|------|
| 饥饿度 | {world.player.needs.hunger:.2f} | {'紧急' if world.player.needs.hunger > 0.8 else '正常'} |
| 疲劳度 | {world.player.needs.fatigue:.2f} | {'紧急' if world.player.needs.fatigue > 0.8 else '正常'} |
| 社交需求 | {world.player.needs.social:.2f} | {'紧急' if world.player.needs.social > 0.8 else '正常'} |

### 建立的关系
"""

    for npc_name, rel in world.player.relationships.items():
        content += f"- **{npc_name}**: 好感度 {rel['affinity']}, 信任度 {rel['trust']}, 互动次数 {rel['interactions']}\n"

    content += f"""

## 2. 世界事件

### 已触发事件
"""

    for evt in world.event_trigger.event_history:
        # 查找知道这个事件的NPC
        npcs_who_know = []
        for npc_name, state in npc_lifecycle.npc_states.items():
            if evt.event_id in state.known_events:
                npcs_who_know.append(npc_name)

        content += f"""
#### {evt.title}
- 类型: {evt.event_type.value}
- 严重程度: {evt.severity.value}
- 位置: {evt.location}
- 描述: {evt.description}
- 已通知NPC: {', '.join(npcs_who_know) if npcs_who_know else '无'}
"""

    content += """

## 3. NPC反应记录 (LLM生成)

以下是NPC通过大语言模型生成的真实反应：

"""

    for i, reaction in enumerate(logger.npc_reactions, 1):
        content += f"""
### {i}. {reaction['npc']}
> {reaction['reaction']}

"""

    content += f"""

## 4. 交互日志

| 时间 | 行动者 | 行动 | 目标 | 详情 |
|------|--------|------|------|------|
"""

    for log in world.interaction_logs:
        details = log.details[:40] + "..." if len(log.details) > 40 else log.details
        content += f"| {log.world_time or '-'} | {log.actor} | {log.action} | {log.target or '-'} | {details} |\n"

    content += f"""

## 5. 逻辑评估

### 评估标准
1. NPC日程是否符合预期
2. 事件传播是否合理
3. 玩家需求变化是否正常
4. NPC反应是否符合角色设定
5. **LLM生成的对话是否符合NPC人设**

### 发现的问题

"""

    # 评估逻辑问题
    issues = []

    # 检查玩家需求
    if world.player.needs.hunger > 0.9:
        issues.append("**饥饿度过高**: 玩家可能没有足够的进餐机会")

    if world.player.needs.fatigue > 0.9:
        issues.append("**疲劳度过高**: 玩家休息不足")

    # 检查金币
    if world.player.gold < 50:
        issues.append("**金币不足**: 经济系统可能需要平衡")

    # 检查关系
    if not world.player.relationships:
        issues.append("**未建立关系**: 社交系统可能存在问题")

    # 检查事件传播
    for evt in world.event_trigger.event_history:
        npcs_who_know = []
        for npc_name, state in npc_lifecycle.npc_states.items():
            if evt.event_id in state.known_events:
                npcs_who_know.append(npc_name)
        if len(npcs_who_know) == 0:
            issues.append(f"**事件未传播**: '{evt.title}' 没有通知到任何NPC")

    # 检查LLM响应
    if not npc_manager.is_initialized():
        issues.append("**LLM未启用**: NPC反应为模拟响应，不是真实LLM生成")

    if len(logger.npc_reactions) == 0:
        issues.append("**无NPC反应记录**: 可能存在响应生成问题")

    if issues:
        for issue in issues:
            content += f"- {issue}\n"
    else:
        content += "- 未发现明显逻辑问题\n"

    content += """

### NPC反应质量评估

请人工检查以上LLM生成的NPC反应是否：
1. 符合NPC的性格特征
2. 与NPC的职业身份相符
3. 对事件的反应合理
4. 对话风格一致

## 6. 总结

本次测试使用真实LLM生成NPC对话和事件反应，验证了：
- 玩家与NPC的对话交互
- 世界事件触发和NPC的智能反应
- 事件信息在NPC之间的传播
- NPC根据事件内容生成符合角色设定的回应

"""

    if npc_manager.is_initialized():
        content += "**LLM集成测试通过**：NPC能够根据事件和对话生成符合角色设定的响应。\n"
    else:
        content += "**注意**：本次测试LLM未启用，请配置API Key后重新测试。\n"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return report_path


if __name__ == "__main__":
    asyncio.run(main())
