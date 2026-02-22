#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest 共享 fixtures 配置文件

提供测试所需的共享 fixtures，包括：
- Mock LLM 客户端
- NPC 配置模板
- 世界时钟模拟
- 嵌入模型模拟
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, MagicMock, patch

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Mock 类定义
# ============================================================================

class MockLLMClient:
    """模拟 LLM 客户端，避免真实 API 调用"""

    def __init__(self, default_response: str = "这是一个模拟的 LLM 响应"):
        self.default_response = default_response
        self.call_history: List[Dict[str, Any]] = []
        self.custom_responses: Dict[str, str] = {}

    def set_response(self, keyword: str, response: str):
        """设置特定关键词的自定义响应"""
        self.custom_responses[keyword] = response

    def call_model(self,
                   messages: List[Dict[str, str]],
                   model: str = "deepseek-chat",
                   max_tokens: int = 500,
                   temperature: float = 0.7) -> str:
        """模拟 call_model 方法"""
        # 记录调用历史
        self.call_history.append({
            "messages": messages,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timestamp": datetime.now().isoformat()
        })

        # 获取用户消息
        user_message = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # 检查自定义响应
        for keyword, response in self.custom_responses.items():
            if keyword in user_message:
                return response

        # 根据消息内容返回不同的响应
        if "YES" in user_message or "NO" in user_message:
            return "YES, 紧急度: 7"
        elif "蓝图" in user_message or "blueprint" in user_message.lower():
            return '{"ultimate_goal": "应对事件", "key_steps": ["观察", "行动"], "predicted_risks": ["风险"], "resource_needs": [], "reasoning_depth": "moderate"}'
        elif "路径" in user_message or "path" in user_message.lower():
            return '[{"path_id": 1, "steps": ["步骤1", "步骤2"], "risk_level": "low", "rationale": "安全方案"}]'

        return self.default_response

    def generate_response(self,
                          prompt: str,
                          context: Dict[str, Any] = None,
                          temperature: float = 0.7,
                          max_tokens: int = 500) -> str:
        """模拟 generate_response 方法"""
        return self.call_model(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )


class MockWorldClock:
    """模拟世界时钟"""

    def __init__(self, initial_time: datetime = None):
        self.current_time = initial_time or datetime(2025, 6, 15, 10, 30, 0)

    def get_current_hour(self) -> int:
        return self.current_time.hour

    def get_current_time(self) -> datetime:
        return self.current_time

    def advance_time(self, minutes: int = 30):
        """推进时间"""
        from datetime import timedelta
        self.current_time += timedelta(minutes=minutes)


class MockEmbeddingModel:
    """模拟嵌入模型"""

    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim
        self.encode_calls = 0

    def encode(self, texts: List[str]) -> 'np.ndarray':
        """返回模拟的嵌入向量"""
        import numpy as np
        self.encode_calls += 1
        if isinstance(texts, str):
            texts = [texts]
        # 返回基于文本哈希的伪随机向量（确保相同文本返回相同向量）
        result = []
        for text in texts:
            np.random.seed(hash(text) % (2**32))
            vec = np.random.randn(self.embedding_dim).astype(np.float32)
            # L2 归一化
            vec = vec / np.linalg.norm(vec)
            result.append(vec)
        return np.array(result)

    def get_sentence_embedding_dimension(self) -> int:
        return self.embedding_dim


class MockToolRegistry:
    """模拟工具注册表"""

    def __init__(self):
        self.tools: Dict[str, callable] = {}
        self.execute_history: List[Dict[str, Any]] = []

    def register_tool(self, name: str, func: callable):
        """注册工具"""
        self.tools[name] = func

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        self.execute_history.append({
            "tool_name": tool_name,
            "params": kwargs,
            "timestamp": datetime.now().isoformat()
        })
        return {
            "success": True,
            "result": f"模拟执行 {tool_name}",
            "params": kwargs
        }


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_client():
    """提供 Mock LLM 客户端"""
    return MockLLMClient()


@pytest.fixture
def mock_world_clock():
    """提供 Mock 世界时钟"""
    return MockWorldClock()


@pytest.fixture
def mock_embedding_model():
    """提供 Mock 嵌入模型"""
    return MockEmbeddingModel()


@pytest.fixture
def mock_tool_registry():
    """提供 Mock 工具注册表"""
    return MockToolRegistry()


@pytest.fixture
def sample_npc_config() -> Dict[str, Any]:
    """提供示例 NPC 配置"""
    return {
        "name": "测试铁匠",
        "profession": "铁匠",
        "personality": ["坚韧", "友好", "勤劳"],
        "traits": ["坚韧", "友好", "勤劳"],
        "background": "在村里的铁匠铺工作了二十年",
        "values": ["诚信", "勤劳", "家庭"],
        "skills": {
            "锻造": 85,
            "修理": 70,
            "交易": 50
        },
        "daily_schedule": {
            "6-7": "起床吃早餐",
            "7-12": "在铁匠铺工作",
            "12-13": "午餐",
            "13-18": "继续工作",
            "18-19": "晚餐",
            "19-21": "休息或社交",
            "21-6": "睡觉"
        },
        "relationships": {
            "村长": {"affection": 60, "trust": 70},
            "酒馆老板": {"affection": 50, "trust": 50}
        },
        "history": ["成功修复了村长的宝剑", "帮助灭火救了一家人"],
        "experiences": ["曾在大城市学习锻造技术"],
        "memory": {
            "past_events": ["成功完成了一把精良剑的锻造"]
        }
    }


@pytest.fixture
def sample_npc_state() -> Dict[str, Any]:
    """提供示例 NPC 状态"""
    return {
        "current_activity": None,
        "current_hour": 10,
        "energy_level": 0.8,
        "hunger_level": 0.3,
        "fatigue_level": 0.2,
        "current_location": "铁匠铺",
        "emotion": "平静",
        "mood": "良好",
        "emotional_state": "专注",
        "weather": "晴",
        "dialogue_history": "",
        "recent_memory": "",
        "primary_goal": "完成今天的锻造订单"
    }


@pytest.fixture
def sample_event() -> Dict[str, Any]:
    """提供示例事件"""
    return {
        "content": "铁匠铺着火了！需要紧急帮助灭火！",
        "location": "铁匠铺",
        "type": "fire",
        "event_type": "火灾",
        "importance": 9,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def sample_low_importance_event() -> Dict[str, Any]:
    """提供低重要性事件"""
    return {
        "content": "一只野兔从村口跑过",
        "location": "村口",
        "type": "wildlife",
        "event_type": "普通",
        "importance": 2,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def sample_memories() -> List[Dict[str, Any]]:
    """提供示例记忆列表"""
    return [
        {
            "id": "mem_001",
            "content": "今天在镇广场遇见了老朋友",
            "importance": 7,
            "tags": ["社交", "朋友"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": "mem_002",
            "content": "完成了一把精良的长剑锻造",
            "importance": 8,
            "tags": ["工作", "成就"],
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": "mem_003",
            "content": "帮助邻居修理了农具",
            "importance": 5,
            "tags": ["帮助", "邻居"],
            "timestamp": datetime.now().isoformat()
        }
    ]


@pytest.fixture
def temp_storage_dir(tmp_path):
    """提供临时存储目录"""
    storage_dir = tmp_path / "npc_storage"
    storage_dir.mkdir(exist_ok=True)
    return str(storage_dir)


# ============================================================================
# 辅助函数 Fixtures
# ============================================================================

@pytest.fixture
def patch_transformers():
    """Patch transformers 以模拟不可用状态"""
    with patch.dict('sys.modules', {'transformers': None}):
        yield


@pytest.fixture
def patch_faiss():
    """Patch faiss 以模拟不可用状态"""
    with patch.dict('sys.modules', {'faiss': None}):
        yield


@pytest.fixture
def patch_all_dependencies():
    """Patch 所有可选依赖以测试降级机制"""
    with patch.dict('sys.modules', {
        'transformers': None,
        'faiss': None,
        'torch': None
    }):
        yield
