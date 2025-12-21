#!/usr/bin/env python3
"""
完整系统测试
测试所有优化功能在实际运行中的表现
"""

import sys
import time
from datetime import datetime, timedelta
from deepseek_client import DeepSeekClient
from world_lore import NPC_TEMPLATES
from npc_system import NPCBehaviorSystem
from world_clock import get_world_clock, reset_world_clock


def test_full_system():
    """完整系统测试"""
    print("=" * 60)
    print("NPC系统完整测试")
    print("=" * 60)
    
    # 初始化
    print("\n1. 初始化系统...")
    client = DeepSeekClient("sk-your_deepseek_api_key_here")
    npc_config = NPC_TEMPLATES["elder_blacksmith"]
    
    # 重置世界时钟
    reset_world_clock(datetime(2025, 12, 6, 8, 0, 0))
    world_clock = get_world_clock()
    world_clock.start()
    
    try:
        npc = NPCBehaviorSystem(npc_config, client)
        print("系统初始化成功")
        print(f"  - 上下文压缩器: {'已加载' if hasattr(npc, 'context_compressor') else '未加载'}")
        print(f"  - 行为决策树: {'已加载' if hasattr(npc, 'behavior_tree') else '未加载'}")
        print(f"  - 记忆管理器: {'已加载' if hasattr(npc, 'memory_manager') else '未加载'}")
        print(f"  - RAG记忆系统: {'已加载' if hasattr(npc, 'rag_memory') else '未加载'}")
        print(f"  - 工具注册表: {'已加载' if hasattr(npc, 'tool_registry') else '未加载'}")
        print(f"  - 工具数量: {len(npc.tool_registry.get_tools())}")
        
        # 测试2: 行为决策树
        print("\n2. 测试行为决策树...")
        current_hour = world_clock.current_time.hour
        needs = {
            "hunger": 0.3,
            "fatigue": 0.2,
            "social": 0.1
        }
        action = npc.behavior_tree.decide_routine_behavior(
            current_hour=current_hour,
            energy_level=80,
            needs=needs,
            current_task=None
        )
        print(f"  当前时间: {current_hour}:00")
        print(f"  决策结果: {action.value if action else '需要LLM决策'}")
        
        # 测试3: 上下文压缩
        print("\n3. 测试上下文压缩...")
        npc_state = {
            "current_activity": npc.current_activity.value if npc.current_activity else "空闲",
            "current_emotion": npc.current_emotion.value,
            "energy_level": npc.energy_level,
            "time": world_clock.current_time.strftime("%H:%M"),
            "location": npc.current_location,
            "needs": {
                "hunger": npc.need_system.needs.hunger,
                "fatigue": npc.need_system.needs.fatigue,
                "social": npc.need_system.needs.social
            }
        }
        compressed = npc.context_compressor.compress_context(
            npc_config=npc_config,
            npc_state=npc_state,
            current_task=None,
            recent_events=None,
            relevant_memories=None
        )
        formatted = npc.context_compressor.format_compressed_context(compressed)
        print(f"  压缩后长度: {len(formatted)} 字符")
        print(f"  包含世界观: {'是' if '艾伦谷' in formatted or '中世纪' in formatted else '否'}")
        print(f"  包含性格: {'是' if any(trait in formatted for trait in npc_config['personality']['traits']) else '否'}")
        
        # 测试4: 创建任务并测试进度更新
        print("\n4. 测试任务进度更新...")
        task_id = npc.persistence.create_task(
            description="测试任务：完成一个简单的订单",
            task_type="event_response",
            priority=75
        )
        task = npc.persistence.tasks[task_id]
        npc.persistence.set_current_task(task)
        npc.current_activity = npc.current_activity.__class__.OBSERVE  # 切换到观察
        
        old_progress = task.progress
        npc._update_task_progress(0.1)  # 模拟0.1小时
        new_progress = task.progress
        
        print(f"  任务进度: {old_progress*100:.1f}% -> {new_progress*100:.1f}%")
        print(f"  进度更新: {'成功' if new_progress > old_progress else '失败'}")
        
        # 测试5: RAG记忆检索
        print("\n5. 测试RAG记忆检索...")
        npc.add_memory("今天完成了一个重要的订单", importance=8, tags=["工作", "订单"])
        npc.add_memory("早上吃了早餐", importance=3, tags=["日常"])
        
        results = npc.rag_memory.search_relevant_memories("订单", top_k=3)
        print(f"  搜索'订单'找到 {len(results)} 个相关记忆")
        for r in results:
            print(f"    - {r['content'][:40]}...")
        
        # 测试6: 时间推进
        print("\n6. 测试时间推进...")
        old_time = world_clock.current_time
        world_clock.advance_time(1.0)  # 前进1小时
        npc.update_time(world_clock.current_time)
        new_time = world_clock.current_time
        
        print(f"  时间: {old_time.strftime('%H:%M')} -> {new_time.strftime('%H:%M')}")
        print(f"  活动: {npc.current_activity.value if npc.current_activity else '无'}")
        
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_full_system()
    sys.exit(0 if success else 1)

