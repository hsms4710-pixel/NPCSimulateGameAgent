"""
RAG记忆检索系统
使用向量化存储和语义搜索实现记忆检索
支持 FAISS 向量数据库和 sentence-transformers 语义嵌入
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False


class FAISSVectorStore:
    """FAISS 向量存储（使用语义嵌入，支持句子级别的语义相似性匹配）"""
    
    def __init__(self, model_name: Optional[str] = "all-MiniLM-L6-v2", use_gpu: bool = False):
        """
        初始化 FAISS 向量存储
        
        Args:
            model_name: 预训练嵌入模型名称（默认使用轻量级MiniLM模型，None时降级到关键词匹配）
            use_gpu: 是否使用GPU（需要faiss-gpu安装）
        """
        # 如果明确指定None，或依赖库不可用，降级到简单存储
        self.use_faiss = (model_name is not None) and FAISS_AVAILABLE and EMBEDDINGS_AVAILABLE
        
        if not self.use_faiss:
            # 降级到简单关键词匹配
            self._init_simple_store()
            return
        
        # 初始化语义嵌入模型
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        # 创建 FAISS 索引（使用 L2 距离）
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # 如果使用 GPU
        if use_gpu:
            try:
                res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
            except:
                pass  # GPU 不可用，使用 CPU
        
        # 记忆存储
        self.memories: Dict[int, Dict[str, Any]] = {}
        self.id_to_index: Dict[str, int] = {}  # 记忆ID -> 向量索引
        self.index_counter = 0
        
    def _init_simple_store(self):
        """降级到简单关键词匹配存储"""
        self.use_faiss = False
        self.memories: Dict[str, Dict[str, Any]] = {}
        self.index: Dict[str, List[str]] = {}  # 关键词 -> 记忆ID列表
    
    def add(self, id: str, content: str, metadata: Dict[str, Any]):
        """添加记忆"""
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
        """简单关键词存储的添加方法"""
        keywords = self._extract_keywords(content)
        
        self.memories[id] = {
            "id": id,
            "content": content,
            "metadata": metadata,
            "keywords": keywords
        }
        
        # 更新索引
        for keyword in keywords:
            if keyword not in self.index:
                self.index[keyword] = []
            if id not in self.index[keyword]:
                self.index[keyword].append(id)
    
    def search(self, query: str, top_k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            query: 查询文本
            top_k: 返回数量
            filter_dict: 元数据过滤条件
            
        Returns:
            相关记忆列表，每个包含原始内容和相似度分数
        """
        if not self.use_faiss:
            return self._search_simple(query, top_k, filter_dict)
        
        # 生成查询嵌入
        query_embedding = self.model.encode([query])[0].astype(np.float32)
        query_embedding = query_embedding.reshape(1, -1)
        
        # FAISS 搜索（返回距离，越小越相似）
        distances, indices = self.index.search(query_embedding, min(top_k * 3, len(self.memories)))
        
        # 转换距离为相似度分数（归一化）
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx not in self.memories:
                continue
            
            memory = self.memories[idx]
            
            # 应用过滤器
            if filter_dict and not self._match_filter(memory["metadata"], filter_dict):
                continue
            
            # 转换距离为相似度（L2距离越小，相似度越高）
            similarity = 1.0 / (1.0 + float(distance))
            
            memory_copy = memory.copy()
            memory_copy["similarity_score"] = similarity
            results.append(memory_copy)
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return results[:top_k]
    
    def _search_simple(self, query: str, top_k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """简单关键词存储的搜索方法"""
        query_keywords = self._extract_keywords(query)
        
        # 计算相关性分数
        scored_memories = []
        for mem_id, memory in self.memories.items():
            # 应用过滤器
            if filter_dict:
                metadata = memory["metadata"]
                if not self._match_filter(metadata, filter_dict):
                    continue
            
            # 计算关键词匹配分数
            score = self._calculate_score(query_keywords, memory["keywords"])
            
            if score > 0:
                scored_memories.append((score, memory))
        
        # 按分数排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        result = [m[1] for m in scored_memories[:top_k]]
        # 添加相似度分数字段以保持一致性
        for r in result:
            if "similarity_score" not in r:
                r["similarity_score"] = 0.5
        
        return result
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简单实现）"""
        # 中文停用词
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        
        # 简单分词（实际应该使用jieba等）
        words = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符
                words.append(char)
        
        # 过滤停用词和单字
        keywords = [w for w in words if w not in stop_words and len(w) > 0]
        
        return keywords[:10]  # 最多10个关键词
    
    def _calculate_score(self, query_keywords: List[str], memory_keywords: List[str]) -> float:
        """计算相关性分数"""
        if not query_keywords or not memory_keywords:
            return 0.0
        
        # 计算交集
        matches = len(set(query_keywords) & set(memory_keywords))
        
        # 归一化分数
        score = matches / max(len(query_keywords), len(memory_keywords))
        
        return score
    
    def _match_filter(self, metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        """匹配过滤器"""
        for key, condition in filter_dict.items():
            if key in metadata:
                value = metadata[key]
                if isinstance(condition, dict):
                    # 支持范围查询
                    if "$gte" in condition:
                        if value < condition["$gte"]:
                            return False
                    if "$lte" in condition:
                        if value > condition["$lte"]:
                            return False
                else:
                    if value != condition:
                        return False
        return True
    
    def delete(self, id: str):
        """删除记忆（FAISS不支持直接删除，标记为无效）"""
        if not self.use_faiss:
            self._delete_simple(id)
            return
        
        if id in self.id_to_index:
            idx = self.id_to_index[id]
            # 标记为已删除（设置为空）
            if idx in self.memories:
                del self.memories[idx]
            del self.id_to_index[id]
    
    def _delete_simple(self, id: str):
        """简单存储的删除方法"""
        if id in self.memories:
            memory = self.memories[id]
            # 从索引中删除
            for keyword in memory["keywords"]:
                if keyword in self.index and id in self.index[keyword]:
                    self.index[keyword].remove(id)
            # 删除记忆
            del self.memories[id]


# 保持向后兼容性
class SimpleVectorStore(FAISSVectorStore):
    """向后兼容性类，继承自FAISSVectorStore"""
    def __init__(self):
        """初始化简单向量存储（不使用嵌入）"""
        super().__init__(model_name=None)


class RAGMemorySystem:
    """RAG记忆系统（使用FAISS向量存储）"""
    
    def __init__(self, use_embeddings: bool = True, model_name: str = "all-MiniLM-L6-v2"):
        """
        初始化RAG记忆系统
        
        Args:
            use_embeddings: 是否使用语义嵌入（需要sentence-transformers和faiss）
            model_name: 嵌入模型名称
        """
        self.vector_store = FAISSVectorStore(model_name=model_name) if use_embeddings else SimpleVectorStore()
        self.memories: Dict[str, Dict[str, Any]] = {}
        
        # 统计信息
        self.stats = {
            "total_memories": 0,
            "search_count": 0,
            "avg_similarity": 0.0,
            "embeddings_used": use_embeddings and FAISS_AVAILABLE and EMBEDDINGS_AVAILABLE
        }
    
    def add_memory(self, 
                   memory_id: str,
                   content: str,
                   importance: int = 5,
                   tags: List[str] = None,
                   timestamp: Optional[datetime] = None):
        """
        添加记忆并向量化
        
        Args:
            memory_id: 记忆ID
            content: 记忆内容
            importance: 重要性（1-10）
            tags: 标签列表
            timestamp: 时间戳
        """
        metadata = {
            "importance": importance,
            "tags": tags or [],
            "timestamp": timestamp.isoformat() if timestamp else datetime.now().isoformat()
        }
        
        # 存储到向量库
        self.vector_store.add(memory_id, content, metadata)
        
        # 存储完整记忆
        self.memories[memory_id] = {
            "id": memory_id,
            "content": content,
            "importance": importance,
            "tags": tags or [],
            "timestamp": timestamp or datetime.now()
        }
        
        self.stats["total_memories"] += 1
    
    def search_relevant_memories(self, 
                                query: str,
                                top_k: int = 5,
                                min_importance: int = 3) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回数量
            min_importance: 最小重要性
            
        Returns:
            相关记忆列表
        """
        # 使用向量搜索
        results = self.vector_store.search(
            query,
            top_k=top_k * 2,  # 多取一些，然后过滤
            filter_dict={"importance": {"$gte": min_importance}}
        )
        
        # 收集相似度统计
        if results:
            similarities = [r.get("similarity_score", 0.5) for r in results]
            if similarities:
                self.stats["avg_similarity"] = sum(similarities) / len(similarities)
        
        self.stats["search_count"] += 1
        
        # 转换为完整记忆对象
        relevant_memories = []
        for result in results[:top_k]:
            mem_id = result["id"]
            if mem_id in self.memories:
                memory = self.memories[mem_id].copy()
                memory["relevance_score"] = result.get("similarity_score", 0.5)
                relevant_memories.append(memory)
        
        return relevant_memories
    
    def search_with_context(self,
                           query: str,
                           current_task: Optional[Dict[str, Any]] = None,
                           time_context: Optional[Dict[str, Any]] = None,
                           top_k: int = 5) -> List[Dict[str, Any]]:
        """
        带上下文的记忆检索（MRAG）
        
        Args:
            query: 查询文本
            current_task: 当前任务
            time_context: 时间上下文
            top_k: 返回数量
            
        Returns:
            相关记忆列表
        """
        # 构建增强查询
        enhanced_query = query
        
        if current_task:
            # 添加任务相关关键词
            task_desc = current_task.get("description", "")
            enhanced_query += " " + task_desc[:50]
        
        if time_context:
            # 添加时间相关关键词
            time_keywords = []
            if "hour" in time_context:
                hour = time_context["hour"]
                if 6 <= hour < 12:
                    time_keywords.append("早晨")
                elif 12 <= hour < 18:
                    time_keywords.append("下午")
                elif 18 <= hour < 22:
                    time_keywords.append("晚上")
                else:
                    time_keywords.append("深夜")
            enhanced_query += " " + " ".join(time_keywords)
        
        # 执行搜索
        return self.search_relevant_memories(enhanced_query, top_k=top_k)
    
    def delete_memory(self, memory_id: str):
        """删除记忆"""
        self.vector_store.delete(memory_id)
        if memory_id in self.memories:
            del self.memories[memory_id]
            self.stats["total_memories"] -= 1
    
    def get_all_memories(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return list(self.memories.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取RAG系统统计信息"""
        return {
            "total_memories": self.stats["total_memories"],
            "search_count": self.stats["search_count"],
            "avg_similarity": round(self.stats["avg_similarity"], 3),
            "embeddings_used": self.stats["embeddings_used"],
            "vector_store_type": "FAISS" if self.stats["embeddings_used"] else "SimpleVectorStore"
        }
