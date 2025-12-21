"""
RAG记忆检索系统
使用向量化存储和语义搜索实现记忆检索
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class SimpleVectorStore:
    """简单的向量存储（使用关键词匹配，后续可升级为真正的向量数据库）"""
    
    def __init__(self):
        self.memories: Dict[str, Dict[str, Any]] = {}
        self.index: Dict[str, List[str]] = {}  # 关键词 -> 记忆ID列表
    
    def add(self, id: str, content: str, metadata: Dict[str, Any]):
        """添加记忆"""
        # 提取关键词
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
        """搜索记忆"""
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
        
        return [m[1] for m in scored_memories[:top_k]]
    
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
        """删除记忆"""
        if id in self.memories:
            memory = self.memories[id]
            # 从索引中删除
            for keyword in memory["keywords"]:
                if keyword in self.index and id in self.index[keyword]:
                    self.index[keyword].remove(id)
            # 删除记忆
            del self.memories[id]


class RAGMemorySystem:
    """RAG记忆系统（使用向量存储）"""
    
    def __init__(self):
        """初始化RAG记忆系统"""
        self.vector_store = SimpleVectorStore()
        self.memories: Dict[str, Dict[str, Any]] = {}
    
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
        
        # 转换为完整记忆对象
        relevant_memories = []
        for result in results[:top_k]:
            mem_id = result["id"]
            if mem_id in self.memories:
                relevant_memories.append(self.memories[mem_id])
        
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
    
    def get_all_memories(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return list(self.memories.values())

