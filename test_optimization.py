#!/usr/bin/env python3
"""
优化系统测试脚本
测试所有优化模块的功能
"""

import sys
from datetime import datetime
from deepseek_client import DeepSeekClient
from world_lore import NPC_TEMPLATES, WORLD_LORE
from npc_optimization import (
    ContextCompressor,
    BehaviorDecisionTree,
    PromptTemplates,
    MemoryManager,
    RAGMemorySystem,
    NPCToolRegistry
)
from npc_system import NPCBehaviorSystem


def test_context_compressor():
    """测试上下文压缩器"""
    print("\n=== 测试上下文压缩器 ===")
    
    compressor = ContextCompressor(max_tokens=1000)
    npc_config = NPC_TEMPLATES["elder_blacksmith"]
    
    npc_state = {
        "current_activity": "工作",
        "current_emotion": "平静",
        "energy_level": 80,
        "time": "14:00",
        "location": "铁匠铺",
        "needs": {"hunger": 0.3, "fatigue": 0.2, "social": 0.1}
    }
    
    compressed = compressor.compress_context(
        npc_config=npc_config,
        npc_state=npc_state,
        current_task={"description": "完成订单", "priority": 70, "progress": 0.5},
        recent_events=None,
        relevant_memories=None
    )
    
    formatted = compressor.format_compressed_context(compressed)
    print(f"压缩后上下文长度: {len(formatted)} 字符")
    print(f"压缩后上下文:\n{formatted[:200]}...")
    
    return True


def test_behavior_decision_tree():
    """测试行为决策树"""
    print("\n=== 测试行为决策树 ===")
    
    npc_config = NPC_TEMPLATES["elder_blacksmith"]
    tree = BehaviorDecisionTree(npc_config)
    
    # 测试不同时间的行为决策
    test_cases = [
        (22, 50, {"hunger": 0.3, "fatigue": 0.8, "social": 0.2}, None),  # 睡觉时间
        (7, 80, {"hunger": 0.7, "fatigue": 0.2, "social": 0.1}, None),   # 吃饭时间
        (14, 70, {"hunger": 0.3, "fatigue": 0.3, "social": 0.2}, None),  # 工作时间
    ]
    
    for hour, energy, needs, task in test_cases:
        action = tree.decide_routine_behavior(hour, energy, needs, task)
        print(f"时间{hour:02d}:00 | 能量{energy} | 需求{needs} -> {action.value if action else '需要LLM决策'}")
    
    return True


def test_memory_manager():
    """测试记忆管理器"""
    print("\n=== 测试记忆管理器 ===")
    
    manager = MemoryManager()
    
    # 创建测试记忆
    memories = [
        {
            "id": "mem1",
            "content": "今天完成了一个重要的订单",
            "importance": 8,
            "tags": ["工作", "订单"],
            "timestamp": (datetime.now() - timedelta(days=0.5)).isoformat()
        },
        {
            "id": "mem2",
            "content": "早上吃了早餐",
            "importance": 3,
            "tags": ["日常"],
            "timestamp": (datetime.now() - timedelta(days=2)).isoformat()
        }
    ]
    
    cleanup_result = manager.cleanup_memories(memories)
    print(f"清理结果: 保留{len(cleanup_result['kept'])}个，压缩{len(cleanup_result['compressed'])}个")
    
    return True


def test_rag_memory():
    """测试RAG记忆系统"""
    print("\n=== 测试RAG记忆系统 ===")
    
    rag = RAGMemorySystem()
    
    # 添加测试记忆
    rag.add_memory("mem1", "今天完成了一个重要的订单", importance=8, tags=["工作"])
    rag.add_memory("mem2", "早上吃了早餐", importance=3, tags=["日常"])
    rag.add_memory("mem3", "遇到了老朋友", importance=6, tags=["社交"])
    
    # 搜索相关记忆
    results = rag.search_relevant_memories("订单", top_k=3)
    print(f"搜索'订单'找到{len(results)}个相关记忆")
    for r in results:
        print(f"  - {r['content'][:50]}...")
    
    return True


def test_integration():
    """测试系统集成"""
    print("\n=== 测试系统集成 ===")
    
    try:
        client = DeepSeekClient("sk-your_deepseek_api_key_here")
        npc_config = NPC_TEMPLATES["elder_blacksmith"]
        
        npc = NPCBehaviorSystem(npc_config, client)
        
        # 检查优化模块是否已加载
        assert hasattr(npc, 'context_compressor'), "上下文压缩器未加载"
        assert hasattr(npc, 'behavior_tree'), "行为决策树未加载"
        assert hasattr(npc, 'memory_manager'), "记忆管理器未加载"
        assert hasattr(npc, 'rag_memory'), "RAG记忆系统未加载"
        assert hasattr(npc, 'tool_registry'), "工具注册表未加载"
        
        print("所有优化模块已加载")
        print(f"工具数量: {len(npc.tool_registry.get_tools())}")
        
        return True
    except Exception as e:
        print(f"集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("NPC系统优化测试")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("上下文压缩器", test_context_compressor()))
    results.append(("行为决策树", test_behavior_decision_tree()))
    results.append(("记忆管理器", test_memory_manager()))
    results.append(("RAG记忆系统", test_rag_memory()))
    results.append(("系统集成", test_integration()))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        status = "通过" if result else "失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n所有测试通过！")
        return 0
    else:
        print("\n部分测试失败")
        return 1


if __name__ == "__main__":
    from datetime import timedelta
    sys.exit(main())

