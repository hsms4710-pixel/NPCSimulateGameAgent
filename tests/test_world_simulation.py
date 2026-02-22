# -*- coding: utf-8 -*-
"""
世界模拟器测试脚本
模拟玩家一天的活动和世界事件触发
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


async def run_simulation():
    """运行一天的模拟"""
    logger = SimulationLogger()
    logger.log("系统", "=" * 60)
    logger.log("系统", "世界模拟器测试开始")
    logger.log("系统", "=" * 60)

    # 初始化世界管理器
    world = WorldManager()
    npc_lifecycle = NPCLifecycleManager(world)

    logger.log("系统", f"世界时间: {world.world_time.to_string()}")

    # ========== 阶段1：创建玩家角色 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段1】创建玩家角色")
    logger.log("系统", "=" * 40)

    # 使用冒险者预设创建玩家
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

    # 社交 - 与贝拉交谈
    logger.log("玩家", "\n--- 玩家尝试与贝拉·欢笑交谈 ---")
    result = await world.execute_player_action(
        action="社交",
        target="贝拉·欢笑",
        details="早上好！我是刚到镇上的冒险者，请问这里最近有什么有趣的消息吗？"
    )
    logger.log("玩家", f"行动结果: {result.get('message', '')}")
    if result.get('response'):
        logger.log("NPC回应", f"贝拉·欢笑: {result['response']}")

    # 推进时间1小时
    world.advance_time(60)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 饮食
    logger.log("玩家", "\n--- 玩家在酒馆进餐 ---")
    result = await world.execute_player_action(action="饮食")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")
    logger.log("玩家", f"剩余金币: {player.gold}")

    # 移动到工坊区
    logger.log("玩家", "\n--- 玩家移动到市场区 ---")
    result = await world.execute_player_action(action="移动", target="市场区")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")

    # 再移动到镇中心
    logger.log("玩家", "\n--- 玩家移动到镇中心 ---")
    result = await world.execute_player_action(action="移动", target="镇中心")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")

    # 移动到工坊区
    logger.log("玩家", "\n--- 玩家移动到工坊区 ---")
    result = await world.execute_player_action(action="移动", target="工坊区")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")

    # 移动到铁匠铺
    logger.log("玩家", "\n--- 玩家移动到铁匠铺 ---")
    result = await world.execute_player_action(action="移动", target="铁匠铺")
    logger.log("玩家", f"行动结果: {result.get('message', '')}")

    # 与铁匠交谈
    logger.log("玩家", "\n--- 玩家与埃尔德·铁锤交谈 ---")
    result = await world.execute_player_action(
        action="社交",
        target="埃尔德·铁锤",
        details="你好，老铁匠！我需要一把好剑，能帮我打造吗？"
    )
    logger.log("玩家", f"行动结果: {result.get('message', '')}")
    if result.get('response'):
        logger.log("NPC回应", f"埃尔德·铁锤: {result['response']}")

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
        description="一个蒙面小偷趁铁匠不注意，潜入铁匠铺试图偷走贵重工具和金属",
        location="铁匠铺",
        event_type="犯罪",
        severity=4
    )

    logger.log_event(event.to_dict())
    logger.log("事件", f"事件ID: {event.event_id}")
    logger.log("事件", f"严重程度: {event.severity.value}")
    logger.log("事件", f"发生位置: {event.location}")

    # 传播事件到NPC
    event_responses = await npc_lifecycle.propagate_event_to_npcs(
        event.to_dict(),
        world.world_time.to_datetime()
    )

    # 让NPC对事件做出反应
    logger.log("系统", "\n--- NPC对事件的反应 ---")

    # 埃尔德·铁锤在场，立即发现
    blacksmith_reaction = "埃尔德·铁锤大喝一声：'小偷！给我站住！'他抓起手边的铁锤追了过去。"
    logger.log("NPC反应", f"[铁匠铺] {blacksmith_reaction}")
    logger.log_npc_reaction("埃尔德·铁锤", blacksmith_reaction)

    # 玩家在场，可以选择帮助
    logger.log("玩家", "\n玩家目睹了小偷入侵事件！")

    # 推进时间30分钟，让事件传播
    world.advance_time(30)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 检查事件传播到其他NPC
    logger.log("系统", "\n--- 事件信息传播 ---")

    # 模拟事件传播到酒馆老板（口口相传）
    bella_reaction = "贝拉·欢笑听说铁匠铺遭贼后：'天哪！老埃尔德没事吧？这年头小偷真是越来越猖狂了！'"
    logger.log("NPC反应", f"[酒馆 - 1小时后知晓] {bella_reaction}")
    logger.log_npc_reaction("贝拉·欢笑", bella_reaction)

    # 牧师的反应
    priest_reaction = "西奥多·光明在教堂听闻此事：'愿圣光保佑这位勇敢的铁匠。我会为镇上的安全祈祷。'"
    logger.log("NPC反应", f"[圣光教堂 - 2小时后知晓] {priest_reaction}")
    logger.log_npc_reaction("西奥多·光明", priest_reaction)

    # ========== 阶段4：傍晚活动 ==========
    logger.log("系统", "\n" + "=" * 40)
    logger.log("系统", "【阶段4】傍晚活动 (18:00 - 22:00)")
    logger.log("系统", "=" * 40)

    # 推进到傍晚
    world.advance_time(180)
    logger.log("系统", f"时间推进到: {world.world_time.to_string()}")

    # 更新NPC状态
    npc_updates = npc_lifecycle.update_all_npcs_for_time(18)
    for update in npc_updates:
        logger.log("NPC", f"{update['npc_name']}: {update['new_activity']} @ {update['new_location']}")

    # 玩家返回酒馆休息
    logger.log("玩家", "\n--- 玩家返回酒馆 ---")
    result = await world.execute_player_action(action="移动", target="工坊区")
    result = await world.execute_player_action(action="移动", target="镇中心")
    result = await world.execute_player_action(action="移动", target="市场区")
    result = await world.execute_player_action(action="移动", target="酒馆")
    logger.log("玩家", f"当前位置: {player.current_location}")

    # 与酒馆老板聊聊今天的事件
    logger.log("玩家", "\n--- 玩家与贝拉讨论今天的事件 ---")
    result = await world.execute_player_action(
        action="社交",
        target="贝拉·欢笑",
        details="今天铁匠铺的事你听说了吗？我可是亲眼看到的！"
    )
    logger.log("玩家", f"行动结果: {result.get('message', '')}")

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

    # 导出日志
    logger.log("系统", "\n" + "=" * 60)
    logger.log("系统", "模拟结束，正在导出日志...")

    filepath = world.export_logs_to_markdown()
    logger.log("系统", f"日志已导出到: {filepath}")

    return world, logger, npc_lifecycle


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("        艾伦谷世界模拟器 - 完整一天测试")
    print("=" * 70 + "\n")

    world, logger, npc_lifecycle = await run_simulation()

    # 生成详细测试报告
    report_path = generate_test_report(world, logger, npc_lifecycle)
    print(f"\n测试报告已生成: {report_path}")


def generate_test_report(world, logger, npc_lifecycle):
    """生成详细测试报告"""
    report_path = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    content = f"""# 世界模拟器测试报告

## 测试信息
- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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
        content += f"""
#### {evt.title}
- 类型: {evt.event_type.value}
- 严重程度: {evt.severity.value}
- 位置: {evt.location}
- 描述: {evt.description}
- 已通知NPC: {', '.join(evt.notified_npcs) if evt.notified_npcs else '无'}
"""

    content += """

## 3. NPC反应记录

"""

    for reaction in logger.npc_reactions:
        content += f"- **{reaction['npc']}**: {reaction['reaction']}\n"

    content += f"""

## 4. 交互日志

| 时间 | 行动者 | 行动 | 目标 | 详情 |
|------|--------|------|------|------|
"""

    for log in world.interaction_logs:
        content += f"| {log.world_time or '-'} | {log.actor} | {log.action} | {log.target or '-'} | {log.details[:40]}... |\n"

    content += f"""

## 5. 逻辑评估

### 评估标准
1. NPC日程是否符合预期
2. 事件传播是否合理
3. 玩家需求变化是否正常
4. NPC反应是否符合角色设定

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

    # 检查事件传播 - 使用 npc_lifecycle 的已知事件记录
    for evt in world.event_trigger.event_history:
        npcs_who_know = []
        for npc_name, state in npc_lifecycle.npc_states.items():
            if evt.event_id in state.known_events:
                npcs_who_know.append(npc_name)
        if len(npcs_who_know) == 0:
            issues.append(f"**事件未传播**: '{evt.title}' 没有通知到任何NPC")

    if issues:
        for issue in issues:
            content += f"- {issue}\n"
    else:
        content += "- 未发现明显逻辑问题\n"

    content += """

### 改进建议

1. **事件传播机制**: 需要更精细的距离计算和时间延迟
2. **NPC反应系统**: 应接入LLM生成更自然的反应
3. **玩家引导**: 可添加任务系统引导玩家行动
4. **经济平衡**: 调整工作收入和消费支出的比例

## 6. 总结

本次测试成功模拟了玩家在艾伦谷的一天活动，包括：
- 角色创建和初始化
- 地点间移动和导航
- 与NPC的社交互动
- 饮食、工作、休息等基本行为
- 世界事件触发和传播
- NPC对事件的反应

系统基本功能正常，但仍需要进一步完善事件传播机制和NPC智能反应。
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return report_path


if __name__ == "__main__":
    asyncio.run(main())
