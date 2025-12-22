"""
记忆分层存储系统 - 热-温-冷三层架构
处理 NPC 长期运行中的内存和 I/O 优化
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
from queue import Queue
import logging

logger = logging.getLogger(__name__)

# ━━━ 可选依赖检查 ━━━
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers未安装，使用关键词匹配替代向量搜索")

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("faiss未安装，使用内存向量相似度搜索")


@dataclass
class NPCEventEnhanced:
    """增强的NPC事件记录 - 支持因果链"""
    id: str  # 事件唯一ID
    timestamp: str
    event_type: str  # dialogue, world_event, preset_event, status_change
    content: str
    analysis: Dict[str, Any]
    response: str
    state_before: Dict[str, Any]
    state_after: Dict[str, Any]
    impact_score: int  # 0-100
    resolved: bool = False
    parent_event_id: Optional[str] = None  # 关键：记忆锚点 - 指向因果前驱事件
    related_event_ids: List[str] = field(default_factory=list)  # 相关事件链


@dataclass
class Insight:
    """高维见解 - 从原始事件提炼的知识"""
    id: str
    created_at: str
    source_event_ids: List[str]  # 来源事件
    insight_text: str  # 见解内容
    insight_type: str  # reflection, lesson, realization, emotional_growth
    emotional_weight: int  # -10 到 +10
    relevance_score: float  # 0-1，用于RAG检索排序
    embedding_vector: Optional[List[float]] = None  # 向量化后的嵌入
    keywords: List[str] = field(default_factory=list)  # 关键词标签


@dataclass
class Episode:
    """情景摘要 - 最近24小时的事件集合"""
    id: str
    created_at: str
    time_range: tuple  # (start_time, end_time)
    involved_events: List[str]  # 包含的事件ID
    episode_summary: str  # 摘要文本
    emotional_arc: str  # 情感弧线描述
    key_decisions: List[str]  # 关键决策
    embedding_vector: Optional[List[float]] = None


class HotMemory:
    """
    热记忆层 - 实时内存存储
    不使用压缩，支持快速读写
    存储内容：当前状态、最近5条原始事件、进行中的任务
    """

    def __init__(self, npc_name: str):
        self.npc_name = npc_name
        self.lock = threading.RLock()
        
        # 核心实时数据
        self.current_state: Dict[str, Any] = {}
        self.recent_events: List[NPCEventEnhanced] = []  # 保持最近5条
        self.active_tasks: Dict[str, Any] = {}
        self.thinking_vars: Dict[str, Any] = {}
        
        # 性能指标
        self.last_snapshot_time = datetime.now()
        self.snapshot_interval = 30  # 秒

    def update_state(self, state_delta: Dict[str, Any]):
        """原子性地更新状态"""
        with self.lock:
            self.current_state.update(state_delta)
            self.last_snapshot_time = datetime.now()

    def add_event(self, event: NPCEventEnhanced):
        """添加事件到热记忆（自动维持最近5条）"""
        with self.lock:
            self.recent_events.append(event)
            # 保持最近5条
            if len(self.recent_events) > 5:
                self.recent_events.pop(0)

    def get_snapshot(self) -> Dict[str, Any]:
        """获取热记忆快照"""
        with self.lock:
            return {
                "state": self.current_state.copy(),
                "recent_events": [asdict(e) for e in self.recent_events],
                "active_tasks": self.active_tasks.copy(),
                "thinking_vars": self.thinking_vars.copy(),
                "snapshot_time": datetime.now().isoformat()
            }


class WarmMemory:
    """
    温记忆层 - 向量数据库 (FAISS可选)
    存储经过提炼的见解(Insights)和情景摘要(Episodes)
    支持语义检索(RAG) - 无FAISS时降级为内存搜索
    """
# 约第 116 行，WarmMemory.__init__ 修复后的逻辑
def __init__(self, npc_name: str, embedding_model=None):
    self.npc_name = npc_name
    self.lock = threading.RLock()
    
    # --- 依赖安全性检查 ---
    if embedding_model is None and SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embeddings_ready = True  # 标记模型已就绪
        except Exception as e:
            logger.warning(f"SentenceTransformer加载失败: {e}，将降级为关键词匹配")
            self.embedding_model = None
            self.embeddings_ready = False
    else:
        self.embedding_model = embedding_model
        self.embeddings_ready = True if embedding_model else False

    self.insights: Dict[str, Insight] = {}
    self.episodes: Dict[str, Episode] = {}
    
    # --- 修复后的 FAISS 初始化逻辑 ---
    self.faiss_index = None
    self.index_to_id_map = []
    
    # 只有库可用且模型就绪时才开启向量索引
    if FAISS_AVAILABLE and self.embeddings_ready:
        try:
            # 384 是 all-MiniLM-L6-v2 的维度
            self.faiss_index = faiss.IndexFlatL2(384) 
            logger.info("✅ FAISS 向量索引已成功初始化")
        except Exception as e:
            logger.warning(f"FAISS初始化失败: {e}，将降级为内存向量搜索")

    def add_insight(self, insight: Insight):
        """添加见解"""
        with self.lock:
            if self.embedding_model:
                try:
                    # 生成向量嵌入（仅在模型可用时）
                    insight.embedding_vector = self.embedding_model.encode(
                        insight.insight_text
                    ).tolist()
                except Exception as e:
                    logger.warning(f"向量编码失败: {e}，跳过向量化")
            self.insights[insight.id] = insight

    def add_episode(self, episode: Episode):
        """添加情景摘要"""
        with self.lock:
            if self.embedding_model:
                try:
                    episode.embedding_vector = self.embedding_model.encode(
                        episode.episode_summary
                    ).tolist()
                except Exception as e:
                    logger.warning(f"向量编码失败: {e}，跳过向量化")
            self.episodes[episode.id] = episode

    def search_insights(self, query: str, top_k: int = 5) -> List[Insight]:
        """
        语义搜索见解
        
        降级策略：
        - 有embedding_model + embedding_vector: 向量搜索
        - 无embedding: 关键词匹配
        """
        with self.lock:
            if not self.insights:
                return []
            
            # 尝试向量搜索（若模型和向量可用）
            if self.embedding_model:
                try:
                    query_vector = self.embedding_model.encode(query)
                    ranked = sorted(
                        self.insights.values(),
                        key=lambda x: self._cosine_similarity(
                            query_vector, x.embedding_vector or []
                        ),
                        reverse=True
                    )
                    return ranked[:top_k]
                except Exception as e:
                    logger.warning(f"向量搜索失败: {e}，降级为关键词匹配")
            
            # 降级：关键词匹配
            return self._keyword_search_insights(query, top_k)

    def _keyword_search_insights(self, query: str, top_k: int = 5) -> List[Insight]:
        """降级的关键词搜索"""
        query_keywords = set(query.lower().split())
        
        ranked = sorted(
            self.insights.values(),
            key=lambda x: sum(
                1 for keyword in query_keywords
                if keyword in x.insight_text.lower()
            ),
            reverse=True
        )
        return ranked[:top_k]

    def get_recent_episodes(self, hours: int = 24) -> List[Episode]:
        """获取最近N小时的情景摘要"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent = [
                ep for ep in self.episodes.values()
                if datetime.fromisoformat(ep.created_at) > cutoff_time
            ]
            return sorted(recent, key=lambda x: x.created_at, reverse=True)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """简单的余弦相似度计算"""
        if not a or not b:
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)


class ColdMemory:
    """
    冷记忆层 - SQLite数据库
    存储超过7天的原始NPCEvent记录
    仅在特定场景(年度总结、性格反思)异步加载
    """

    def __init__(self, npc_name: str, storage_dir: str = "npc_storage"):
        self.npc_name = npc_name
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        self.db_path = self.storage_dir / f"{npc_name}_cold_memory.db"
        self.lock = threading.RLock()
        
        self._init_db()

    def _init_db(self):
        """初始化SQLite数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建事件表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT,
                content TEXT,
                analysis TEXT,
                response TEXT,
                state_before TEXT,
                state_after TEXT,
                impact_score INTEGER,
                resolved BOOLEAN,
                parent_event_id TEXT,
                related_event_ids TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 创建索引以加速查询
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON events(timestamp)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type 
            ON events(event_type)
            """)
            
            conn.commit()

    def archive_event(self, event: NPCEventEnhanced):
        """归档事件到冷存储"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO events (
                    id, timestamp, event_type, content, analysis, 
                    response, state_before, state_after, impact_score,
                    resolved, parent_event_id, related_event_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.id,
                    event.timestamp,
                    event.event_type,
                    event.content,
                    json.dumps(event.analysis),
                    event.response,
                    json.dumps(event.state_before),
                    json.dumps(event.state_after),
                    event.impact_score,
                    event.resolved,
                    event.parent_event_id,
                    json.dumps(event.related_event_ids)
                ))
                conn.commit()

    def query_events(self, 
                    start_time: Optional[str] = None,
                    end_time: Optional[str] = None,
                    event_type: Optional[str] = None) -> List[NPCEventEnhanced]:
        """查询冷存储中的事件"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM events WHERE 1=1"
                params = []
                
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time)
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time)
                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)
                
                query += " ORDER BY timestamp DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    event = NPCEventEnhanced(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        event_type=row['event_type'],
                        content=row['content'],
                        analysis=json.loads(row['analysis']),
                        response=row['response'],
                        state_before=json.loads(row['state_before']),
                        state_after=json.loads(row['state_after']),
                        impact_score=row['impact_score'],
                        resolved=bool(row['resolved']),
                        parent_event_id=row['parent_event_id'],
                        related_event_ids=json.loads(row['related_event_ids'])
                    )
                    events.append(event)
                
                return events


class MemoryLayerManager:
    """
    分层记忆管理器
    协调三层存储的数据流、清理、和异步操作
    """

    def __init__(self, 
                 npc_name: str,
                 embedding_model=None,
                 storage_dir: str = "npc_storage",
                 cold_archival_days: int = 7):
        self.npc_name = npc_name
        self.storage_dir = storage_dir
        self.cold_archival_days = cold_archival_days
        
        # 三层存储
        self.hot_memory = HotMemory(npc_name)
        self.warm_memory = WarmMemory(npc_name, embedding_model)
        self.cold_memory = ColdMemory(npc_name, storage_dir)
        
        # 异步队列
        self.archival_queue: Queue = Queue()
        self.reflection_queue: Queue = Queue()
        
        # 后台线程
        self.archival_thread = None
        self.running = False

    def start(self):
        """启动后台处理线程"""
        self.running = True
        self.archival_thread = threading.Thread(
            target=self._archival_worker,
            daemon=True
        )
        self.archival_thread.start()

    def stop(self):
        """停止后台线程"""
        self.running = False
        if self.archival_thread:
            self.archival_thread.join(timeout=5)

    def add_event(self, event: NPCEventEnhanced):
        """添加事件到分层系统"""
        # 添加到热记忆
        self.hot_memory.add_event(event)
        
        # 检查是否需要归档到冷存储
        event_age = datetime.now() - datetime.fromisoformat(event.timestamp)
        if event_age.days >= self.cold_archival_days:
            self.archival_queue.put(event)

    def get_decision_context(self, 
                            max_hot_events: int = 5,
                            max_warm_insights: int = 3) -> Dict[str, Any]:
        """获取决策所需的上下文"""
        return {
            "hot_memory": self.hot_memory.get_snapshot(),
            "warm_insights": [
                asdict(i) for i in self.warm_memory.insights.values()
            ][:max_warm_insights],
            "recent_episodes": [
                asdict(e) for e in self.warm_memory.get_recent_episodes(24)
            ]
        }

    def _archival_worker(self):
        """后台归档工作线程"""
        while self.running:
            try:
                event = self.archival_queue.get(timeout=1)
                self.cold_memory.archive_event(event)
            except:
                pass

    def add_reflection_insight(self, insight: Insight):
        """添加反思得到的见解"""
        self.warm_memory.add_insight(insight)

    def add_episode_summary(self, episode: Episode):
        """添加情景摘要"""
        self.warm_memory.add_episode(episode)

    def query_cold_storage(self,
                          start_time: Optional[str] = None,
                          end_time: Optional[str] = None) -> List[NPCEventEnhanced]:
        """异步查询冷存储（用于年度总结或重大反思）"""
        return self.cold_memory.query_events(start_time, end_time)
