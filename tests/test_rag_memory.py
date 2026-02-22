#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rag_memory.py - RAG 记忆系统测试

测试内容：
1. Text2VecEmbedding 加载和编码
2. FAISSVectorStore 添加和搜索
3. RAGMemorySystem 完整流程
4. 降级机制（模拟依赖不可用）

使用 pytest 框架，配合 conftest.py 中的共享 fixtures
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import numpy as np

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Text2VecEmbedding 测试
# ============================================================================

class TestText2VecEmbedding:
    """测试 Text2Vec 嵌入模型"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.rag_memory import Text2VecEmbedding
        assert Text2VecEmbedding is not None

    def test_init_without_model_raises_error(self):
        """测试在模型不存在时抛出错误"""
        from npc_optimization.rag_memory import Text2VecEmbedding, TRANSFORMERS_AVAILABLE

        if not TRANSFORMERS_AVAILABLE:
            pytest.skip("transformers 未安装，跳过此测试")

        with pytest.raises(FileNotFoundError):
            Text2VecEmbedding(model_path="./nonexistent_model")

    def test_mock_embedding_model_encode(self, mock_embedding_model):
        """使用 Mock 测试编码功能"""
        # 使用 conftest 中的 mock_embedding_model
        texts = ["你好世界", "今天天气真好"]
        embeddings = mock_embedding_model.encode(texts)

        assert embeddings.shape == (2, 768)
        assert mock_embedding_model.encode_calls == 1

    def test_mock_embedding_model_single_text(self, mock_embedding_model):
        """测试单文本编码"""
        text = "单个文本测试"
        embedding = mock_embedding_model.encode([text])

        assert embedding.shape == (1, 768)

    def test_mock_embedding_model_same_text_same_vector(self, mock_embedding_model):
        """测试相同文本返回相同向量"""
        text = "测试文本"
        embedding1 = mock_embedding_model.encode([text])
        embedding2 = mock_embedding_model.encode([text])

        np.testing.assert_array_almost_equal(embedding1, embedding2)

    def test_mock_embedding_dimension(self, mock_embedding_model):
        """测试嵌入维度"""
        assert mock_embedding_model.embedding_dim == 768
        assert mock_embedding_model.get_sentence_embedding_dimension() == 768


# ============================================================================
# FAISSVectorStore 测试
# ============================================================================

class TestFAISSVectorStore:
    """测试 FAISS 向量存储"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.rag_memory import FAISSVectorStore
        assert FAISSVectorStore is not None

    def test_init_fallback_mode(self):
        """测试降级模式初始化"""
        from npc_optimization.rag_memory import FAISSVectorStore

        # 使用不存在的模型路径触发降级
        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 验证降级到关键词模式
        assert hasattr(store, 'use_faiss')
        assert hasattr(store, 'memories')

    def test_add_simple_fallback(self):
        """测试降级模式下的添加功能"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 添加记忆
        store.add(
            id="mem_001",
            content="今天在铁匠铺工作",
            metadata={"importance": 7, "tags": ["工作"]}
        )

        assert len(store) >= 1

    def test_search_simple_fallback(self):
        """测试降级模式下的搜索功能"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 添加一些记忆
        store.add("mem_001", "今天在铁匠铺工作，锻造了一把剑", {"importance": 7})
        store.add("mem_002", "和村长讨论了村子的防御问题", {"importance": 8})
        store.add("mem_003", "帮助农夫修理了锄头", {"importance": 5})

        # 搜索
        results = store.search("铁匠铺 锻造", top_k=3)

        assert isinstance(results, list)
        # 应该能找到相关记忆
        if results:
            assert "id" in results[0]
            assert "content" in results[0]
            assert "similarity_score" in results[0]

    def test_delete_simple_fallback(self):
        """测试降级模式下的删除功能"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        store.add("mem_001", "测试记忆", {"importance": 5})
        initial_len = len(store)

        store.delete("mem_001")

        assert len(store) == initial_len - 1

    def test_extract_keywords(self):
        """测试关键词提取"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")
        keywords = store._extract_keywords("今天在铁匠铺工作，锻造了一把精良的剑")

        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_match_filter_exact(self):
        """测试精确过滤匹配"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        metadata = {"type": "event", "importance": 7}
        filter_dict = {"type": "event"}

        assert store._match_filter(metadata, filter_dict) is True

        filter_dict_mismatch = {"type": "dialogue"}
        assert store._match_filter(metadata, filter_dict_mismatch) is False

    def test_match_filter_range(self):
        """测试范围过滤匹配"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        metadata = {"importance": 7}

        # 测试 $gte
        filter_gte = {"importance": {"$gte": 5}}
        assert store._match_filter(metadata, filter_gte) is True

        filter_gte_fail = {"importance": {"$gte": 8}}
        assert store._match_filter(metadata, filter_gte_fail) is False

        # 测试 $lte
        filter_lte = {"importance": {"$lte": 10}}
        assert store._match_filter(metadata, filter_lte) is True

        filter_lte_fail = {"importance": {"$lte": 5}}
        assert store._match_filter(metadata, filter_lte_fail) is False


class TestFAISSVectorStoreWithMock:
    """使用 Mock 模型测试 FAISS 向量存储"""

    @pytest.fixture
    def mock_faiss_store(self, mock_embedding_model):
        """创建带 Mock 模型的向量存储"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")
        store.use_faiss = True
        store.model = mock_embedding_model
        store.embedding_dim = 768

        # 模拟 FAISS 索引
        store.index = MagicMock()
        store.index.add = MagicMock()
        store.index.search = MagicMock(return_value=(
            np.array([[0.1, 0.2, 0.3]]),
            np.array([[0, 1, 2]])
        ))

        store.memories = {}
        store.id_to_index = {}
        store.index_counter = 0

        return store

    def test_add_with_mock_model(self, mock_faiss_store):
        """测试使用 Mock 模型添加记忆"""
        mock_faiss_store.add(
            id="mem_001",
            content="今天锻造了一把精良的剑",
            metadata={"importance": 8}
        )

        assert "mem_001" in mock_faiss_store.id_to_index
        assert mock_faiss_store.index_counter == 1


# ============================================================================
# RAGMemorySystem 测试
# ============================================================================

class TestRAGMemorySystem:
    """测试 RAG 记忆系统"""

    def test_import_class(self):
        """测试类可以导入"""
        from npc_optimization.rag_memory import RAGMemorySystem
        assert RAGMemorySystem is not None

    def test_init(self):
        """测试初始化"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        assert hasattr(rag, 'vector_store')
        assert hasattr(rag, 'memories')
        assert hasattr(rag, 'stats')

    def test_add_memory(self):
        """测试添加记忆"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        rag.add_memory(
            memory_id="mem_001",
            content="今天在镇广场遇见了老朋友",
            importance=7,
            tags=["社交", "朋友"]
        )

        assert "mem_001" in rag.memories
        assert rag.stats["total_memories"] == 1

    def test_add_multiple_memories(self, sample_memories):
        """测试添加多条记忆"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        for mem in sample_memories:
            rag.add_memory(
                memory_id=mem["id"],
                content=mem["content"],
                importance=mem["importance"],
                tags=mem["tags"]
            )

        assert rag.stats["total_memories"] == len(sample_memories)

    def test_search_relevant_memories(self, sample_memories):
        """测试搜索相关记忆"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        for mem in sample_memories:
            rag.add_memory(
                memory_id=mem["id"],
                content=mem["content"],
                importance=mem["importance"],
                tags=mem["tags"]
            )

        results = rag.search_relevant_memories("镇广场", top_k=3)

        assert isinstance(results, list)
        assert rag.stats["search_count"] == 1

    def test_search_with_min_importance(self, sample_memories):
        """测试带最小重要性的搜索"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        for mem in sample_memories:
            rag.add_memory(
                memory_id=mem["id"],
                content=mem["content"],
                importance=mem["importance"],
                tags=mem["tags"]
            )

        # 搜索重要性 >= 7 的记忆
        results = rag.search_relevant_memories(
            "工作",
            top_k=5,
            min_importance=7
        )

        assert isinstance(results, list)
        # 所有结果的重要性都应该 >= 7
        for result in results:
            assert result.get("importance", 0) >= 7

    def test_search_with_context(self, sample_memories):
        """测试带上下文的搜索"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        for mem in sample_memories:
            rag.add_memory(
                memory_id=mem["id"],
                content=mem["content"],
                importance=mem["importance"],
                tags=mem["tags"]
            )

        results = rag.search_with_context(
            query="锻造",
            current_task={"description": "完成锻造订单", "type": "work"},
            time_context={"hour": 14},
            top_k=3
        )

        assert isinstance(results, list)

    def test_delete_memory(self):
        """测试删除记忆"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        rag.add_memory("mem_001", "测试记忆", importance=5)
        assert rag.stats["total_memories"] == 1

        rag.delete_memory("mem_001")
        assert "mem_001" not in rag.memories
        assert rag.stats["total_memories"] == 0

    def test_get_all_memories(self, sample_memories):
        """测试获取所有记忆"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        for mem in sample_memories:
            rag.add_memory(
                memory_id=mem["id"],
                content=mem["content"],
                importance=mem["importance"],
                tags=mem["tags"]
            )

        all_memories = rag.get_all_memories()

        assert len(all_memories) == len(sample_memories)

    def test_get_stats(self, sample_memories):
        """测试获取统计信息"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        for mem in sample_memories:
            rag.add_memory(
                memory_id=mem["id"],
                content=mem["content"],
                importance=mem["importance"]
            )

        rag.search_relevant_memories("测试", top_k=3)

        stats = rag.get_stats()

        assert "total_memories" in stats
        assert "search_count" in stats
        assert "avg_similarity" in stats
        assert "use_faiss" in stats
        assert "vector_store_type" in stats

        assert stats["total_memories"] == len(sample_memories)
        assert stats["search_count"] == 1


# ============================================================================
# 降级机制测试
# ============================================================================

class TestDegradationMechanism:
    """测试降级机制"""

    def test_faiss_not_available_fallback(self):
        """测试 FAISS 不可用时的降级"""
        from npc_optimization.rag_memory import FAISSVectorStore

        # 使用不存在的模型路径触发降级
        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 应该降级到关键词模式
        assert store.use_faiss is False

    def test_keyword_search_works_without_faiss(self):
        """测试关键词搜索在没有 FAISS 时正常工作"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 添加记忆
        store.add("mem_001", "铁匠铺着火了", {"importance": 9})
        store.add("mem_002", "村庄很平静", {"importance": 3})
        store.add("mem_003", "铁匠正在锻造", {"importance": 6})

        # 搜索应该能工作
        results = store.search("铁匠", top_k=3)

        assert isinstance(results, list)

    def test_rag_system_works_in_fallback_mode(self):
        """测试 RAG 系统在降级模式下正常工作"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        # 添加记忆
        rag.add_memory("mem_001", "今天很忙", importance=5)
        rag.add_memory("mem_002", "完成了锻造工作", importance=7)

        # 搜索应该能工作
        results = rag.search_relevant_memories("锻造", top_k=2)

        assert isinstance(results, list)

    def test_keyword_extraction_without_jieba(self):
        """测试没有 jieba 时的关键词提取"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 即使没有 jieba，也应该能提取关键词
        keywords = store._extract_keywords("今天天气真好，适合锻造")

        assert isinstance(keywords, list)

    def test_calculate_keyword_score(self):
        """测试关键词匹配分数计算"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        query_kw = ["铁匠", "锻造", "剑"]
        memory_kw = ["铁匠", "锻造", "工作"]

        score = store._calculate_keyword_score(query_kw, memory_kw)

        assert 0.0 <= score <= 1.0
        assert score > 0  # 应该有匹配

    def test_calculate_keyword_score_empty(self):
        """测试空关键词的分数计算"""
        from npc_optimization.rag_memory import FAISSVectorStore

        store = FAISSVectorStore(model_path="./nonexistent_model")

        # 空查询关键词
        score1 = store._calculate_keyword_score([], ["铁匠"])
        assert score1 == 0.0

        # 空记忆关键词
        score2 = store._calculate_keyword_score(["铁匠"], [])
        assert score2 == 0.0


# ============================================================================
# 边界条件测试
# ============================================================================

class TestBoundaryConditions:
    """边界条件测试"""

    def test_add_empty_content(self):
        """测试添加空内容"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()
        rag.add_memory("mem_001", "", importance=1)

        assert "mem_001" in rag.memories

    def test_search_empty_query(self):
        """测试空查询"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()
        rag.add_memory("mem_001", "测试记忆", importance=5)

        results = rag.search_relevant_memories("", top_k=3)

        assert isinstance(results, list)

    def test_search_no_results(self):
        """测试无结果搜索"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()
        rag.add_memory("mem_001", "今天很忙", importance=5)

        results = rag.search_relevant_memories("完全不相关的查询xyz", top_k=3)

        assert isinstance(results, list)

    def test_delete_nonexistent_memory(self):
        """测试删除不存在的记忆"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        # 不应该抛出异常
        rag.delete_memory("nonexistent_id")

    def test_importance_boundary_values(self):
        """测试重要性边界值"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()

        # 最小重要性
        rag.add_memory("mem_001", "不重要的记忆", importance=1)
        # 最大重要性
        rag.add_memory("mem_002", "非常重要的记忆", importance=10)

        assert rag.memories["mem_001"]["importance"] == 1
        assert rag.memories["mem_002"]["importance"] == 10

    def test_top_k_larger_than_memories(self):
        """测试 top_k 大于记忆数量"""
        from npc_optimization.rag_memory import RAGMemorySystem

        rag = RAGMemorySystem()
        rag.add_memory("mem_001", "唯一的记忆", importance=5)

        # 请求 10 条，但只有 1 条
        results = rag.search_relevant_memories("记忆", top_k=10)

        assert len(results) <= 1


# ============================================================================
# 兼容性测试
# ============================================================================

class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_simple_vector_store_alias(self):
        """测试 SimpleVectorStore 别名"""
        from npc_optimization.rag_memory import SimpleVectorStore, FAISSVectorStore

        assert SimpleVectorStore is FAISSVectorStore

    def test_embeddings_available_flag(self):
        """测试 EMBEDDINGS_AVAILABLE 标志"""
        from npc_optimization.rag_memory import EMBEDDINGS_AVAILABLE, TRANSFORMERS_AVAILABLE

        assert EMBEDDINGS_AVAILABLE == TRANSFORMERS_AVAILABLE
