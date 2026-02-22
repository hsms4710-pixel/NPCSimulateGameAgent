"""
RAG 记忆检索系统 (Retrieval-Augmented Generation Memory System)
===============================================================

本模块实现了基于向量检索的语义记忆系统，是 MRAG (Memory-RAG) 架构的核心组件。

核心功能:
---------
1. 语义嵌入: 使用 Text2Vec 中文模型将文本转换为 768 维向量
2. 向量检索: 使用 FAISS 实现高效的相似度搜索
3. 记忆管理: 支持添加、搜索、删除记忆，带元数据过滤

架构层次:
---------
┌─────────────────────────────────────────────────────────────┐
│                    RAGMemorySystem                          │
│                  (高级 API，业务逻辑)                        │
├─────────────────────────────────────────────────────────────┤
│                    FAISSVectorStore                         │
│                (向量存储，FAISS 索引管理)                    │
├─────────────────────────────────────────────────────────────┤
│                   Text2VecEmbedding                         │
│              (中文语义嵌入，768维向量)                       │
└─────────────────────────────────────────────────────────────┘

依赖:
-----
- 必需: numpy
- 可选: faiss-cpu, transformers, torch, jieba

使用示例:
---------
>>> from npc_optimization.rag_memory import RAGMemorySystem
>>> rag = RAGMemorySystem()
>>> rag.add_memory("m1", "铁匠铺着火了", importance=8)
>>> results = rag.search_relevant_memories("火灾事件", top_k=3)

模型下载:
---------
HF_ENDPOINT=https://hf-mirror.com python -c "
from huggingface_hub import snapshot_download
snapshot_download('shibing624/text2vec-base-chinese', local_dir='./models/text2vec-base-chinese')
"
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
import numpy as np
import uuid

# 导入统一接口
from interfaces import BaseMemorySystem, MemorySearchResult

logger = logging.getLogger(__name__)

# ============================================================================
# 依赖检测
# ============================================================================

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.info("FAISS 未安装，将使用关键词匹配作为降级方案")

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.info("jieba 未安装，中文分词将使用简单字符分割")

try:
    import torch
    from transformers import AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.info("transformers 未安装，Text2Vec 模型不可用")


# ============================================================================
# Text2Vec 嵌入模型
# ============================================================================

class Text2VecEmbedding:
    """
    Text2Vec 中文句嵌入模型封装

    使用 shibing624/text2vec-base-chinese 模型，专门为中文语义相似度优化。
    采用 Mean Pooling + L2 归一化策略生成定长向量。

    技术规格:
    ---------
    - 向量维度: 768
    - 最大序列长度: 512 tokens
    - 语义精度: ~90%+ (在标准中文相似度测试集上)

    Attributes:
        tokenizer: BERT 分词器
        model: BERT 编码器模型
        embedding_dim: 输出向量维度 (768)
    """

    def __init__(self, model_path: str = "./models/text2vec-base-chinese"):
        """
        初始化 Text2Vec 中文嵌入模型

        Args:
            model_path: 本地模型路径，需要包含 config.json 和 pytorch_model.bin

        Raises:
            FileNotFoundError: 模型文件不存在时抛出，附带下载命令
        """
        import os
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"模型未找到: {model_path}\n"
                f"请运行以下命令下载模型:\n"
                f"  HF_ENDPOINT=https://hf-mirror.com python -c \"\n"
                f"  from huggingface_hub import snapshot_download\n"
                f"  snapshot_download('shibing624/text2vec-base-chinese', "
                f"local_dir='./models/text2vec-base-chinese')\""
            )

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        self.model.eval()  # 设置为推理模式
        self.embedding_dim = 768

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        将文本编码为语义向量

        使用 Mean Pooling 策略: 对所有 token 的隐藏状态取平均，
        比直接使用 [CLS] token 更稳定。

        Args:
            texts: 文本列表或单个字符串

        Returns:
            np.ndarray: 形状为 (len(texts), 768) 的 L2 归一化向量数组
        """
        if isinstance(texts, str):
            texts = [texts]

        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            return_tensors='pt',
            max_length=512
        )

        # 编码
        with torch.no_grad():
            outputs = self.model(**inputs)
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state

            # Mean Pooling: 对非 padding token 取平均
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(
                token_embeddings.size()
            ).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embeddings = (sum_embeddings / sum_mask).numpy()

        # L2 归一化，使余弦相似度计算更简单
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.maximum(norms, 1e-9)

        return embeddings

    def get_sentence_embedding_dimension(self) -> int:
        """返回嵌入向量维度 (兼容 SentenceTransformer 接口)"""
        return self.embedding_dim


# ============================================================================
# FAISS 向量存储
# ============================================================================

class FAISSVectorStore:
    """
    FAISS 向量存储引擎

    使用 Facebook AI 的 FAISS 库实现高效的向量相似度搜索。
    支持 GPU 加速和自动降级到关键词匹配。

    工作模式:
    ---------
    1. FAISS 模式 (默认): 使用 Text2Vec 嵌入 + FAISS 索引
    2. 降级模式: 当 FAISS/transformers 不可用时，使用关键词匹配

    Attributes:
        use_faiss: 是否使用 FAISS 向量检索
        model: Text2VecEmbedding 实例
        embedding_dim: 向量维度
        index: FAISS 索引对象
        memories: 记忆存储字典
        id_to_index: 记忆ID到向量索引的映射
    """

    def __init__(self, model_path: str = "./models/text2vec-base-chinese",
                 use_gpu: bool = False):
        """
        初始化 FAISS 向量存储

        Args:
            model_path: Text2Vec 模型路径
            use_gpu: 是否使用 GPU 加速 (需要 faiss-gpu)
        """
        self.use_faiss = False
        self.model = None
        self.embedding_dim = 0

        # 尝试初始化嵌入模型
        if FAISS_AVAILABLE and TRANSFORMERS_AVAILABLE:
            try:
                self.model = Text2VecEmbedding(model_path)
                self.embedding_dim = self.model.embedding_dim
                self.use_faiss = True
                logger.info(f"Text2Vec 模型加载成功，向量维度: {self.embedding_dim}")
            except Exception as e:
                logger.warning(f"Text2Vec 模型初始化失败: {e}，降级到关键词匹配")
                self._init_simple_store()
                return
        else:
            missing = []
            if not FAISS_AVAILABLE:
                missing.append("faiss")
            if not TRANSFORMERS_AVAILABLE:
                missing.append("transformers")
            logger.warning(f"缺少依赖 {missing}，降级到关键词匹配")
            self._init_simple_store()
            return

        # 创建 FAISS 索引 (使用 L2 距离)
        self.index = faiss.IndexFlatL2(self.embedding_dim)

        # GPU 加速 (可选)
        if use_gpu:
            try:
                res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
                logger.info("FAISS GPU 加速已启用")
            except Exception as e:
                logger.debug(f"GPU 加速不可用: {e}")

        # 记忆存储
        self.memories: Dict[int, Dict[str, Any]] = {}
        self.id_to_index: Dict[str, int] = {}
        self.index_counter = 0

    def _init_simple_store(self):
        """初始化简单关键词存储 (降级方案)"""
        self.use_faiss = False
        self.memories: Dict[str, Dict[str, Any]] = {}
        self.keyword_index: Dict[str, List[str]] = {}

    def add(self, id: str, content: str, metadata: Dict[str, Any]):
        """
        添加记忆到向量存储

        Args:
            id: 记忆唯一标识符
            content: 记忆文本内容
            metadata: 元数据字典 (如 importance, tags, timestamp)
        """
        if not self.use_faiss:
            self._add_simple(id, content, metadata)
            return

        # 生成嵌入向量
        embedding = self.model.encode([content])[0].astype(np.float32)
        embedding = embedding.reshape(1, -1)

        # 添加到 FAISS 索引
        self.index.add(embedding)

        # 记录映射关系
        vector_idx = self.index_counter
        self.id_to_index[id] = vector_idx
        self.memories[vector_idx] = {
            "id": id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding[0]
        }
        self.index_counter += 1

    def _add_simple(self, id: str, content: str, metadata: Dict[str, Any]):
        """添加到简单关键词存储"""
        keywords = self._extract_keywords(content)

        self.memories[id] = {
            "id": id,
            "content": content,
            "metadata": metadata,
            "keywords": keywords
        }

        # 更新关键词索引
        for keyword in keywords:
            if keyword not in self.keyword_index:
                self.keyword_index[keyword] = []
            if id not in self.keyword_index[keyword]:
                self.keyword_index[keyword].append(id)

    def search(self, query: str, top_k: int = 5,
               filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        搜索相关记忆

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_dict: 元数据过滤条件，支持 $gte, $lte 范围查询

        Returns:
            记忆列表，每个包含 id, content, metadata, similarity_score
        """
        if not self.use_faiss:
            return self._search_simple(query, top_k, filter_dict)

        # 生成查询向量
        query_embedding = self.model.encode([query])[0].astype(np.float32)
        query_embedding = query_embedding.reshape(1, -1)

        # FAISS 搜索 (返回 L2 距离，越小越相似)
        search_k = min(top_k * 3, max(len(self.memories), 1))
        distances, indices = self.index.search(query_embedding, search_k)

        # 构建结果
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < 0 or idx not in self.memories:
                continue

            memory = self.memories[idx]

            # 应用过滤器
            if filter_dict and not self._match_filter(memory["metadata"], filter_dict):
                continue

            # L2 距离转换为相似度 (0-1 范围)
            similarity = 1.0 / (1.0 + float(distance))

            result = {
                "id": memory["id"],
                "content": memory["content"],
                "metadata": memory["metadata"],
                "similarity_score": similarity
            }
            results.append(result)

        # 按相似度排序
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def _search_simple(self, query: str, top_k: int = 5,
                       filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """简单关键词匹配搜索"""
        query_keywords = self._extract_keywords(query)

        scored_memories = []
        for mem_id, memory in self.memories.items():
            # 应用过滤器
            if filter_dict and not self._match_filter(memory["metadata"], filter_dict):
                continue

            # 计算关键词匹配分数
            score = self._calculate_keyword_score(query_keywords, memory["keywords"])
            if score > 0:
                scored_memories.append((score, memory))

        # 排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # 构建结果
        results = []
        for score, memory in scored_memories[:top_k]:
            results.append({
                "id": memory["id"],
                "content": memory["content"],
                "metadata": memory["metadata"],
                "similarity_score": min(score, 1.0)
            })

        return results

    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取文本关键词

        优先使用 jieba 分词，降级使用简单规则分割。
        """
        # 中文停用词
        stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "他",
            "她", "它", "们", "把", "被", "让", "给", "从", "向", "对",
            "但", "而", "或", "如果", "因为", "所以", "虽然", "但是", "可以",
            "什么", "怎么", "为什么", "哪", "哪里", "谁", "多少", "几",
            "这个", "那个", "这些", "那些", "已经", "正在", "将要", "曾经"
        }

        if JIEBA_AVAILABLE:
            words = list(jieba.cut(text, cut_all=False))
            keywords = [
                w.strip() for w in words
                if len(w.strip()) > 1
                and w.strip() not in stop_words
                and any('\u4e00' <= c <= '\u9fff' or c.isalnum() for c in w)
            ]
        else:
            # 降级：简单分割
            import re
            segments = re.split(r'[，。！？、；：""''（）【】\[\]\s]+', text)
            keywords = []
            for seg in segments:
                seg = seg.strip()
                if len(seg) >= 2 and seg not in stop_words:
                    if len(seg) > 4:
                        for i in range(0, len(seg) - 1, 2):
                            word = seg[i:i+2]
                            if word not in stop_words:
                                keywords.append(word)
                    else:
                        keywords.append(seg)

        # 去重并限制数量
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:15]

    def _calculate_keyword_score(self, query_kw: List[str],
                                  memory_kw: List[str]) -> float:
        """计算关键词匹配分数 (Jaccard 相似度)"""
        if not query_kw or not memory_kw:
            return 0.0
        matches = len(set(query_kw) & set(memory_kw))
        return matches / max(len(query_kw), len(memory_kw))

    def _match_filter(self, metadata: Dict[str, Any],
                      filter_dict: Dict[str, Any]) -> bool:
        """
        匹配元数据过滤条件

        支持:
            - 精确匹配: {"type": "event"}
            - 范围查询: {"importance": {"$gte": 5, "$lte": 10}}
        """
        for key, condition in filter_dict.items():
            if key not in metadata:
                continue
            value = metadata[key]

            if isinstance(condition, dict):
                if "$gte" in condition and value < condition["$gte"]:
                    return False
                if "$lte" in condition and value > condition["$lte"]:
                    return False
            elif value != condition:
                return False
        return True

    def delete(self, id: str):
        """
        删除记忆

        注意: FAISS 不支持真正删除，这里只是从映射中移除。
        如需重建索引，请创建新的 FAISSVectorStore 实例。
        """
        if not self.use_faiss:
            self._delete_simple(id)
            return

        if id in self.id_to_index:
            idx = self.id_to_index[id]
            if idx in self.memories:
                del self.memories[idx]
            del self.id_to_index[id]

    def _delete_simple(self, id: str):
        """从简单存储中删除"""
        if id in self.memories:
            memory = self.memories[id]
            for keyword in memory.get("keywords", []):
                if keyword in self.keyword_index and id in self.keyword_index[keyword]:
                    self.keyword_index[keyword].remove(id)
            del self.memories[id]

    def __len__(self) -> int:
        """返回存储的记忆数量"""
        return len(self.memories)


# ============================================================================
# RAG 记忆系统 (高级 API)
# ============================================================================

class RAGMemorySystem(BaseMemorySystem):
    """
    RAG 记忆系统 - 高级业务接口

    继承自 BaseMemorySystem，实现统一的记忆接口协议。
    封装 FAISSVectorStore，提供面向业务的记忆管理功能。
    支持带上下文的智能检索 (MRAG 模式)。

    功能特点:
    ---------
    1. 记忆管理: 添加/删除/查询记忆
    2. 重要性过滤: 按 importance 字段过滤低优先级记忆
    3. 上下文增强: 结合当前任务和时间上下文优化查询
    4. 统计追踪: 记录搜索次数、平均相似度等指标

    Attributes:
        vector_store: FAISSVectorStore 实例
        memories: 完整记忆存储 (包含业务字段)
        stats: 统计信息字典
    """

    def __init__(self, model_path: str = "./models/text2vec-base-chinese"):
        """
        初始化 RAG 记忆系统

        Args:
            model_path: Text2Vec 模型路径
        """
        self.vector_store = FAISSVectorStore(model_path=model_path)
        self.memories: Dict[str, Dict[str, Any]] = {}

        # 统计信息
        self.stats = {
            "total_memories": 0,
            "search_count": 0,
            "avg_similarity": 0.0,
            "use_faiss": self.vector_store.use_faiss
        }

    # ========================================================================
    # 接口标准方法实现 (MemoryInterface)
    # ========================================================================

    def add_memory(
        self,
        content: str,
        importance: int = 5,
        memory_type: str = "一般",
        tags: Optional[List[str]] = None,
        emotional_impact: int = 0,
        related_npcs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # 兼容旧接口的参数
        memory_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        添加记忆 (实现 MemoryInterface)

        Args:
            content: 记忆文本内容
            importance: 重要性 (1-10)，默认5
            memory_type: 记忆类型，默认"一般"
            tags: 标签列表
            emotional_impact: 情感影响 -10到+10，默认0
            related_npcs: 相关NPC名称列表
            metadata: 额外元数据
            memory_id: 唯一标识符（兼容旧接口）
            timestamp: 时间戳，默认为当前时间

        Returns:
            str: 新记忆的ID
        """
        # 生成或使用提供的ID
        mem_id = memory_id or f"mem_{uuid.uuid4().hex[:8]}"

        # 合并元数据
        full_metadata = {
            "importance": importance,
            "memory_type": memory_type,
            "tags": tags or [],
            "emotional_impact": emotional_impact,
            "related_npcs": related_npcs or [],
            "timestamp": (timestamp or datetime.now()).isoformat()
        }
        if metadata:
            full_metadata.update(metadata)

        # 存储到向量库
        self.vector_store.add(mem_id, content, full_metadata)

        # 存储完整记忆
        self.memories[mem_id] = {
            "id": mem_id,
            "content": content,
            "importance": importance,
            "memory_type": memory_type,
            "tags": tags or [],
            "emotional_impact": emotional_impact,
            "related_npcs": related_npcs or [],
            "timestamp": timestamp or datetime.now(),
            "metadata": metadata or {}
        }

        self.stats["total_memories"] += 1
        return mem_id

    def search_memories(
        self,
        query: str,
        top_k: int = 5,
        memory_types: Optional[List[str]] = None,
        min_importance: int = 0,
        time_range: Optional[tuple] = None,
        tags: Optional[List[str]] = None
    ) -> List[MemorySearchResult]:
        """
        搜索相关记忆 (实现 MemoryInterface)

        Args:
            query: 搜索查询
            top_k: 返回结果数量，默认5
            memory_types: 限定记忆类型
            min_importance: 最低重要性
            time_range: 时间范围 (start_datetime, end_datetime)
            tags: 必须包含的标签

        Returns:
            List[MemorySearchResult]: 搜索结果列表
        """
        # 构建过滤条件
        filter_dict = {}
        if min_importance > 0:
            filter_dict["importance"] = {"$gte": min_importance}

        # 向量搜索
        results = self.vector_store.search(
            query,
            top_k=top_k * 2,
            filter_dict=filter_dict if filter_dict else None
        )

        # 更新统计
        if results:
            similarities = [r.get("similarity_score", 0.5) for r in results]
            self.stats["avg_similarity"] = sum(similarities) / len(similarities)
        self.stats["search_count"] += 1

        # 转换为 MemorySearchResult 对象
        search_results = []
        for result in results[:top_k]:
            mem_id = result["id"]
            if mem_id not in self.memories:
                continue

            memory = self.memories[mem_id]

            # 应用内存类型过滤
            if memory_types:
                mem_type = memory.get("memory_type", "一般")
                if mem_type not in memory_types:
                    continue

            # 应用标签过滤
            if tags:
                mem_tags = memory.get("tags", [])
                if not any(t in mem_tags for t in tags):
                    continue

            # 应用时间范围过滤
            if time_range:
                mem_time = memory.get("timestamp")
                if mem_time:
                    if isinstance(mem_time, str):
                        mem_time = datetime.fromisoformat(mem_time)
                    start_time, end_time = time_range
                    if not (start_time <= mem_time <= end_time):
                        continue

            # 创建结果对象
            timestamp = memory.get("timestamp", datetime.now())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            search_result = MemorySearchResult(
                memory_id=mem_id,
                content=memory.get("content", ""),
                relevance_score=result.get("similarity_score", 0.5),
                importance=memory.get("importance", 5),
                memory_type=memory.get("memory_type", "一般"),
                timestamp=timestamp,
                tags=memory.get("tags", []),
                metadata=memory.get("metadata", {})
            )
            search_results.append(search_result)

        return search_results

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单条记忆 (实现 MemoryInterface)

        Args:
            memory_id: 记忆ID

        Returns:
            Optional[Dict]: 记忆内容
        """
        return self.memories.get(memory_id)

    def get_recent_memories(
        self,
        count: int = 10,
        memory_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取最近的记忆 (实现 MemoryInterface)

        Args:
            count: 返回数量
            memory_types: 限定记忆类型

        Returns:
            List[Dict]: 最近记忆列表
        """
        all_memories = list(self.memories.values())

        # 类型过滤
        if memory_types:
            all_memories = [
                m for m in all_memories
                if m.get("memory_type", "一般") in memory_types
            ]

        # 按时间排序
        def get_timestamp(m):
            ts = m.get("timestamp")
            if ts is None:
                return datetime.min
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts)
                except:
                    return datetime.min
            return ts

        all_memories.sort(key=get_timestamp, reverse=True)

        return all_memories[:count]

    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆 (覆盖 BaseMemorySystem)

        Args:
            memory_id: 记忆ID

        Returns:
            bool: 是否删除成功
        """
        if memory_id not in self.memories:
            return False

        self.vector_store.delete(memory_id)
        del self.memories[memory_id]
        self.stats["total_memories"] -= 1
        return True

    # ========================================================================
    # 原有方法 (保持向后兼容)
    # ========================================================================

    def search_relevant_memories(self,
                                  query: str,
                                  top_k: int = 5,
                                  min_importance: int = 1) -> List[Dict[str, Any]]:
        """
        搜索相关记忆

        Args:
            query: 查询文本
            top_k: 返回数量
            min_importance: 最小重要性阈值

        Returns:
            记忆列表，按相似度降序排列
        """
        # 向量搜索
        results = self.vector_store.search(
            query,
            top_k=top_k * 2,
            filter_dict={"importance": {"$gte": min_importance}} if min_importance > 1 else None
        )

        # 更新统计
        if results:
            similarities = [r.get("similarity_score", 0.5) for r in results]
            self.stats["avg_similarity"] = sum(similarities) / len(similarities)
        self.stats["search_count"] += 1

        # 转换为完整记忆对象
        relevant = []
        for result in results[:top_k]:
            mem_id = result["id"]
            if mem_id in self.memories:
                memory = self.memories[mem_id].copy()
                memory["relevance_score"] = result.get("similarity_score", 0.5)
                relevant.append(memory)

        return relevant

    def search_with_context(self,
                            query: str,
                            current_task: Optional[Dict[str, Any]] = None,
                            time_context: Optional[Dict[str, Any]] = None,
                            top_k: int = 5) -> List[Dict[str, Any]]:
        """
        带上下文的记忆检索 (MRAG 模式)

        根据当前任务和时间上下文增强查询，提高检索相关性。

        Args:
            query: 原始查询
            current_task: 当前任务 {"description": "...", "type": "..."}
            time_context: 时间上下文 {"hour": 14, "day": "Monday"}
            top_k: 返回数量

        Returns:
            增强检索后的相关记忆列表
        """
        enhanced_query = query

        # 添加任务关键词
        if current_task:
            task_desc = current_task.get("description", "")
            if task_desc:
                enhanced_query += " " + task_desc[:50]

        # 添加时间关键词
        if time_context and "hour" in time_context:
            hour = time_context["hour"]
            time_keywords = {
                (6, 12): "早晨",
                (12, 18): "下午",
                (18, 22): "晚上"
            }
            for (start, end), keyword in time_keywords.items():
                if start <= hour < end:
                    enhanced_query += " " + keyword
                    break
            else:
                enhanced_query += " 深夜"

        return self.search_relevant_memories(enhanced_query, top_k=top_k)

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return list(self.memories.values())

    def get_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息

        Returns:
            包含 total_memories, search_count, avg_similarity, use_faiss 的字典
        """
        return {
            "total_memories": self.stats["total_memories"],
            "search_count": self.stats["search_count"],
            "avg_similarity": round(self.stats["avg_similarity"], 3),
            "use_faiss": self.stats["use_faiss"],
            "vector_store_type": "FAISS + Text2Vec" if self.stats["use_faiss"] else "关键词匹配"
        }

    # ========================================================================
    # 记忆压缩与遗忘机制
    # ========================================================================

    def compress_similar_memories(self, similarity_threshold: float = 0.85) -> Dict[str, int]:
        """
        压缩相似记忆

        找出相似度超过阈值的记忆对，将它们合并为一个摘要记忆。
        保留重要性更高的记忆，删除冗余记忆。

        Args:
            similarity_threshold: 相似度阈值 (0.0-1.0)，默认0.85

        Returns:
            压缩统计: {"merged": 合并的记忆组数, "removed": 删除的冗余记忆数}

        Raises:
            ValueError: 当阈值不在有效范围内时
        """
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError(f"相似度阈值必须在 0.0-1.0 范围内，当前值: {similarity_threshold}")

        merged_count = 0
        removed_count = 0

        if len(self.memories) < 2:
            return {"merged": 0, "removed": 0}

        try:
            # 获取所有记忆ID列表
            memory_ids = list(self.memories.keys())
            processed_ids = set()
            groups_to_merge: List[List[str]] = []

            # 找出相似记忆对
            for i, mem_id in enumerate(memory_ids):
                if mem_id in processed_ids:
                    continue

                memory = self.memories.get(mem_id)
                if not memory:
                    continue

                similar_group = [mem_id]
                content = memory.get("content", "")

                # 搜索与当前记忆相似的其他记忆
                search_results = self.vector_store.search(content, top_k=len(self.memories))

                for result in search_results:
                    result_id = result.get("id")
                    similarity = result.get("similarity_score", 0)

                    if (result_id and
                        result_id != mem_id and
                        result_id not in processed_ids and
                        similarity >= similarity_threshold):
                        similar_group.append(result_id)
                        processed_ids.add(result_id)

                if len(similar_group) > 1:
                    groups_to_merge.append(similar_group)
                    processed_ids.add(mem_id)

            # 合并每个相似组
            for group in groups_to_merge:
                new_id = self._merge_memories(group)
                if new_id:
                    merged_count += 1
                    removed_count += len(group) - 1  # 减1因为合并后保留了一个新记忆

            logger.info(f"记忆压缩完成: 合并 {merged_count} 组，删除 {removed_count} 条冗余记忆")

        except Exception as e:
            logger.error(f"记忆压缩过程中发生错误: {e}")
            raise

        return {"merged": merged_count, "removed": removed_count}

    def _merge_memories(self, memory_ids: List[str]) -> Optional[str]:
        """
        合并多条记忆为一条摘要记忆

        Args:
            memory_ids: 要合并的记忆ID列表

        Returns:
            合并后新记忆的ID，失败时返回None
        """
        if not memory_ids or len(memory_ids) < 2:
            return None

        try:
            memories_to_merge = []
            max_importance = 0
            all_tags = set()
            earliest_timestamp = None

            for mem_id in memory_ids:
                memory = self.memories.get(mem_id)
                if memory:
                    memories_to_merge.append(memory)
                    importance = memory.get("importance", 5)
                    max_importance = max(max_importance, importance)
                    all_tags.update(memory.get("tags", []))

                    timestamp = memory.get("timestamp")
                    if timestamp:
                        if earliest_timestamp is None or timestamp < earliest_timestamp:
                            earliest_timestamp = timestamp

            if len(memories_to_merge) < 2:
                return None

            # 按重要性排序，保留最重要的内容在前
            memories_to_merge.sort(key=lambda m: m.get("importance", 0), reverse=True)

            # 创建摘要内容
            contents = [m.get("content", "") for m in memories_to_merge]
            # 使用最重要的记忆作为主体，附加其他记忆的关键信息
            primary_content = contents[0]
            secondary_contents = contents[1:]

            # 生成摘要：主要内容 + 补充信息
            merged_content = primary_content
            if secondary_contents:
                supplements = "; ".join([c[:50] for c in secondary_contents if c])
                if supplements:
                    merged_content = f"{primary_content} [补充: {supplements}]"

            # 生成新ID
            new_id = f"merged_{uuid.uuid4().hex[:8]}"

            # 删除原记忆
            for mem_id in memory_ids:
                self.delete_memory(mem_id)

            # 添加合并后的记忆
            self.add_memory(
                memory_id=new_id,
                content=merged_content,
                importance=max_importance,
                tags=list(all_tags),
                timestamp=earliest_timestamp or datetime.now()
            )

            logger.debug(f"合并 {len(memory_ids)} 条记忆为新记忆: {new_id}")
            return new_id

        except Exception as e:
            logger.error(f"合并记忆失败: {e}")
            return None

    def apply_forgetting(self, decay_factor: float = 0.95, min_importance: float = 1.0) -> int:
        """
        应用遗忘衰减机制

        对重要性低于5的记忆应用衰减因子，删除重要性低于最小阈值的记忆。
        这模拟了人类记忆的自然遗忘过程。

        Args:
            decay_factor: 衰减因子 (0.0-1.0)，默认0.95
            min_importance: 最小重要性阈值，低于此值的记忆将被删除

        Returns:
            被删除的记忆数量

        Raises:
            ValueError: 当参数不在有效范围内时
        """
        if not 0.0 <= decay_factor <= 1.0:
            raise ValueError(f"衰减因子必须在 0.0-1.0 范围内，当前值: {decay_factor}")

        if min_importance < 0:
            raise ValueError(f"最小重要性必须为非负数，当前值: {min_importance}")

        deleted_count = 0
        memories_to_delete = []

        try:
            # 遍历所有记忆，应用衰减
            for mem_id, memory in list(self.memories.items()):
                current_importance = memory.get("importance", 5)

                # 只对重要性 < 5 的记忆应用衰减
                if current_importance < 5:
                    new_importance = current_importance * decay_factor

                    # 检查是否低于最小阈值
                    if new_importance < min_importance:
                        memories_to_delete.append(mem_id)
                    else:
                        # 更新重要性
                        memory["importance"] = new_importance

            # 删除低于阈值的记忆
            for mem_id in memories_to_delete:
                self.delete_memory(mem_id)
                deleted_count += 1

            logger.info(f"遗忘衰减完成: 衰减因子={decay_factor}, 删除 {deleted_count} 条记忆")

        except Exception as e:
            logger.error(f"遗忘衰减过程中发生错误: {e}")
            raise

        return deleted_count

    def _calculate_memory_age(self, memory: Dict[str, Any]) -> float:
        """
        计算记忆的年龄（小时）

        Args:
            memory: 记忆字典

        Returns:
            记忆年龄（小时），如果无法计算则返回0.0
        """
        try:
            timestamp = memory.get("timestamp")
            if timestamp is None:
                return 0.0

            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            if isinstance(timestamp, datetime):
                age = datetime.now() - timestamp
                return age.total_seconds() / 3600.0  # 转换为小时

            return 0.0

        except Exception as e:
            logger.debug(f"计算记忆年龄失败: {e}")
            return 0.0

    def _get_emotion_keywords(self, emotion: str) -> List[str]:
        """
        获取情绪相关的关键词列表

        Args:
            emotion: 情绪类型 (如 "悲伤", "愤怒", "快乐" 等)

        Returns:
            与该情绪相关的关键词列表
        """
        emotion_keyword_map = {
            # 负面情绪
            "悲伤": ["失去", "失败", "离开", "死亡", "痛苦", "悲痛", "哭泣", "遗憾", "孤独", "伤心"],
            "愤怒": ["背叛", "欺骗", "侮辱", "不公", "愤怒", "攻击", "争吵", "仇恨", "报复", "冲突"],
            "恐惧": ["危险", "威胁", "死亡", "黑暗", "未知", "恐怖", "害怕", "逃跑", "灾难", "失控"],
            "焦虑": ["担心", "紧张", "不确定", "压力", "期限", "失败", "评判", "未来", "等待", "风险"],
            "失望": ["失败", "期望", "落空", "背叛", "不满", "遗憾", "无奈", "失信", "破灭", "受挫"],

            # 正面情绪
            "快乐": ["成功", "胜利", "获得", "庆祝", "满足", "开心", "欢笑", "幸福", "奖励", "认可"],
            "兴奋": ["惊喜", "期待", "冒险", "发现", "新奇", "突破", "激动", "机会", "开始", "希望"],
            "感激": ["帮助", "支持", "礼物", "友谊", "救援", "恩惠", "慷慨", "理解", "包容", "关怀"],
            "爱": ["亲密", "关心", "保护", "陪伴", "信任", "承诺", "依恋", "温暖", "家人", "朋友"],
            "平静": ["安宁", "和谐", "休息", "自然", "放松", "接受", "平衡", "宁静", "稳定", "秩序"],

            # 中性/混合情绪
            "惊讶": ["意外", "突然", "发现", "揭露", "转变", "异常", "不寻常", "新", "变化", "震惊"],
            "困惑": ["不解", "矛盾", "复杂", "迷惑", "问题", "疑问", "混乱", "选择", "两难", "模糊"],
            "怀旧": ["过去", "童年", "回忆", "曾经", "老朋友", "故乡", "传统", "往事", "岁月", "怀念"],
        }

        # 转换为小写并查找
        emotion_lower = emotion.lower().strip()
        keywords = emotion_keyword_map.get(emotion_lower, [])

        # 如果没有精确匹配，尝试模糊匹配
        if not keywords:
            for key, values in emotion_keyword_map.items():
                if emotion_lower in key or key in emotion_lower:
                    keywords = values
                    break

        # 如果仍然没有找到，返回通用关键词
        if not keywords:
            keywords = ["重要", "关注", "记忆", "经历", "事件"]

        return keywords

    def apply_emotional_weight(self, query: str, emotion: str) -> List[Dict[str, Any]]:
        """
        根据当前情绪调整搜索结果的权重

        根据情绪状态，增强与该情绪相关的记忆的权重。
        例如：悲伤时，与"失去""失败"相关的记忆权重增加。

        Args:
            query: 搜索查询文本
            emotion: 当前情绪状态 (如 "悲伤", "愤怒", "快乐" 等)

        Returns:
            调整权重后的搜索结果列表，每个结果包含 original_score 和 adjusted_score

        Raises:
            ValueError: 当查询为空时
        """
        if not query or not query.strip():
            raise ValueError("查询文本不能为空")

        try:
            # 获取情绪相关关键词
            emotion_keywords = self._get_emotion_keywords(emotion)

            # 执行基础搜索
            base_results = self.search_relevant_memories(query, top_k=20)

            if not base_results:
                return []

            adjusted_results = []
            for result in base_results:
                original_score = result.get("relevance_score", 0.5)
                content = result.get("content", "").lower()

                # 计算情绪关键词匹配度
                emotion_match_count = sum(1 for kw in emotion_keywords if kw in content)
                emotion_boost = 1.0 + (emotion_match_count * 0.1)  # 每匹配一个关键词增加10%

                # 限制最大增益为50%
                emotion_boost = min(emotion_boost, 1.5)

                adjusted_score = original_score * emotion_boost

                result_copy = result.copy()
                result_copy["original_score"] = original_score
                result_copy["adjusted_score"] = min(adjusted_score, 1.0)  # 确保不超过1.0
                result_copy["emotion_boost"] = emotion_boost
                result_copy["relevance_score"] = result_copy["adjusted_score"]

                adjusted_results.append(result_copy)

            # 按调整后的分数重新排序
            adjusted_results.sort(key=lambda x: x["adjusted_score"], reverse=True)

            logger.debug(f"情感着色完成: 情绪={emotion}, 结果数={len(adjusted_results)}")

            return adjusted_results

        except Exception as e:
            logger.error(f"情感着色搜索失败: {e}")
            raise

    def maintenance(self, compress: bool = True, forget: bool = True,
                   similarity_threshold: float = 0.85,
                   decay_factor: float = 0.95,
                   min_importance: float = 1.0) -> Dict[str, Any]:
        """
        执行记忆维护操作

        组合调用记忆压缩和遗忘衰减机制，提供完整的维护报告。

        Args:
            compress: 是否执行记忆压缩，默认True
            forget: 是否执行遗忘衰减，默认True
            similarity_threshold: 压缩时的相似度阈值
            decay_factor: 遗忘衰减因子
            min_importance: 遗忘的最小重要性阈值

        Returns:
            完整的维护报告字典，包含:
            - before_count: 维护前记忆总数
            - after_count: 维护后记忆总数
            - compression: 压缩统计 (如果执行)
            - forgetting: 遗忘统计 (如果执行)
            - duration_ms: 维护耗时（毫秒）
        """
        import time
        start_time = time.time()

        report = {
            "before_count": len(self.memories),
            "after_count": 0,
            "compression": None,
            "forgetting": None,
            "duration_ms": 0,
            "errors": []
        }

        try:
            # 执行压缩
            if compress:
                try:
                    compression_result = self.compress_similar_memories(similarity_threshold)
                    report["compression"] = compression_result
                except Exception as e:
                    error_msg = f"压缩失败: {str(e)}"
                    report["errors"].append(error_msg)
                    logger.error(error_msg)

            # 执行遗忘
            if forget:
                try:
                    forget_result = self.apply_forgetting(decay_factor, min_importance)
                    report["forgetting"] = {"deleted": forget_result}
                except Exception as e:
                    error_msg = f"遗忘失败: {str(e)}"
                    report["errors"].append(error_msg)
                    logger.error(error_msg)

        finally:
            end_time = time.time()
            report["after_count"] = len(self.memories)
            report["duration_ms"] = round((end_time - start_time) * 1000, 2)

        # 生成摘要
        total_removed = 0
        if report["compression"]:
            total_removed += report["compression"].get("removed", 0)
        if report["forgetting"]:
            total_removed += report["forgetting"].get("deleted", 0)

        report["summary"] = {
            "total_removed": total_removed,
            "reduction_percentage": round(
                (1 - report["after_count"] / max(report["before_count"], 1)) * 100, 2
            ) if report["before_count"] > 0 else 0
        }

        logger.info(
            f"记忆维护完成: {report['before_count']} -> {report['after_count']} "
            f"(减少 {report['summary']['reduction_percentage']}%), "
            f"耗时 {report['duration_ms']}ms"
        )

        return report

    def search_with_context_enhanced(self, query: str,
                                     context: Optional[Dict[str, Any]] = None,
                                     top_k: int = 5) -> List[Dict[str, Any]]:
        """
        支持上下文增强的智能搜索

        根据上下文信息（情绪、时间等）优化搜索结果。

        Args:
            query: 搜索查询文本
            context: 上下文信息字典，可包含:
                - emotion: 当前情绪状态
                - timestamp: 参考时间点
                - time_range_hours: 时间范围（小时）
                - current_task: 当前任务信息
            top_k: 返回结果数量

        Returns:
            上下文增强后的搜索结果列表

        Examples:
            >>> rag.search_with_context_enhanced(
            ...     "铁匠铺的事情",
            ...     context={"emotion": "悲伤", "time_range_hours": 24},
            ...     top_k=5
            ... )
        """
        if not query or not query.strip():
            raise ValueError("查询文本不能为空")

        context = context or {}

        try:
            # 检查是否有情绪信息
            emotion = context.get("emotion")
            if emotion:
                results = self.apply_emotional_weight(query, emotion)
            else:
                results = self.search_relevant_memories(query, top_k=top_k * 2)

            # 检查是否有时间信息
            reference_time = context.get("timestamp")
            time_range_hours = context.get("time_range_hours")

            if reference_time or time_range_hours:
                results = self._apply_time_weighting(
                    results,
                    reference_time=reference_time,
                    time_range_hours=time_range_hours
                )

            # 检查是否有任务上下文
            current_task = context.get("current_task")
            if current_task:
                results = self._apply_task_weighting(results, current_task)

            # 按最终分数排序并返回top_k
            results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"上下文增强搜索失败: {e}")
            # 降级到普通搜索
            return self.search_relevant_memories(query, top_k=top_k)

    def _apply_time_weighting(self, results: List[Dict[str, Any]],
                               reference_time: Optional[datetime] = None,
                               time_range_hours: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        应用时间权重调整

        优先返回时间相近的记忆。

        Args:
            results: 搜索结果列表
            reference_time: 参考时间点，默认为当前时间
            time_range_hours: 优先的时间范围（小时）

        Returns:
            调整后的结果列表
        """
        if not reference_time:
            reference_time = datetime.now()

        if not time_range_hours:
            time_range_hours = 24.0  # 默认24小时

        for result in results:
            memory_id = result.get("id")
            memory = self.memories.get(memory_id, {})
            age_hours = self._calculate_memory_age(memory)

            # 计算时间接近度 (在时间范围内的记忆获得加分)
            if age_hours <= time_range_hours:
                # 越近的记忆分数越高
                time_factor = 1.0 + (1.0 - age_hours / time_range_hours) * 0.3
            else:
                # 超出范围的记忆略微降权
                time_factor = max(0.7, 1.0 - (age_hours - time_range_hours) / (time_range_hours * 10))

            current_score = result.get("relevance_score", 0.5)
            result["time_factor"] = time_factor
            result["relevance_score"] = min(current_score * time_factor, 1.0)

        return results

    def _apply_task_weighting(self, results: List[Dict[str, Any]],
                               current_task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        应用任务相关性权重调整

        根据当前任务信息调整记忆的相关性权重。

        Args:
            results: 搜索结果列表
            current_task: 当前任务信息 {"description": "...", "type": "...", "keywords": [...]}

        Returns:
            调整后的结果列表
        """
        task_description = current_task.get("description", "")
        task_type = current_task.get("type", "")
        task_keywords = current_task.get("keywords", [])

        # 提取任务关键词
        if not task_keywords and task_description:
            task_keywords = self.vector_store._extract_keywords(task_description)

        for result in results:
            content = result.get("content", "").lower()

            # 计算任务相关度
            task_match = 0
            for keyword in task_keywords:
                if keyword.lower() in content:
                    task_match += 1

            # 任务类型匹配
            tags = result.get("tags", [])
            type_match = 1.2 if task_type and task_type in tags else 1.0

            # 计算任务加成
            if task_keywords:
                keyword_factor = 1.0 + (task_match / len(task_keywords)) * 0.2
            else:
                keyword_factor = 1.0

            task_factor = keyword_factor * type_match

            current_score = result.get("relevance_score", 0.5)
            result["task_factor"] = task_factor
            result["relevance_score"] = min(current_score * task_factor, 1.0)

        return results


# ============================================================================
# 向后兼容性
# ============================================================================

# 保持旧版 API 兼容
SimpleVectorStore = FAISSVectorStore
EMBEDDINGS_AVAILABLE = TRANSFORMERS_AVAILABLE
