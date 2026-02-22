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
    from .rag_memory import Text2VecEmbedding, TRANSFORMERS_AVAILABLE
    TEXT2VEC_AVAILABLE = TRANSFORMERS_AVAILABLE
except ImportError:
    TEXT2VEC_AVAILABLE = False
    logger.warning("Text2VecEmbedding不可用，使用关键词匹配替代向量搜索")

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

    def __init__(self, npc_name: str, embedding_model=None,
                 model_path: str = "./models/text2vec-base-chinese"):
        self.npc_name = npc_name
        self.lock = threading.RLock()

        # --- 依赖安全性检查 ---
        if embedding_model is None and TEXT2VEC_AVAILABLE:
            try:
                self.embedding_model = Text2VecEmbedding(model_path)
                self.embeddings_ready = True  # 标记模型已就绪
                self.embedding_dim = self.embedding_model.embedding_dim  # 768
                logger.info(f"Text2VecEmbedding加载成功，向量维度: {self.embedding_dim}")
            except Exception as e:
                logger.warning(f"Text2VecEmbedding加载失败: {e}，将降级为关键词匹配")
                self.embedding_model = None
                self.embeddings_ready = False
                self.embedding_dim = 768  # 默认维度
        else:
            self.embedding_model = embedding_model
            self.embeddings_ready = True if embedding_model else False
            # 获取传入模型的维度
            if embedding_model and hasattr(embedding_model, 'embedding_dim'):
                self.embedding_dim = embedding_model.embedding_dim
            elif embedding_model and hasattr(embedding_model, 'get_sentence_embedding_dimension'):
                self.embedding_dim = embedding_model.get_sentence_embedding_dimension()
            else:
                self.embedding_dim = 768  # 默认维度

        self.insights: Dict[str, Insight] = {}
        self.episodes: Dict[str, Episode] = {}

        # --- FAISS 初始化逻辑 ---
        self.faiss_index = None
        self.index_to_id_map = []

        # 只有库可用且模型就绪时才开启向量索引
        if FAISS_AVAILABLE and self.embeddings_ready:
            try:
                # 使用 Text2Vec 的维度 (768)
                self.faiss_index = faiss.IndexFlatL2(self.embedding_dim)
                logger.info(f"FAISS 向量索引已成功初始化，维度: {self.embedding_dim}")
            except Exception as e:
                logger.warning(f"FAISS初始化失败: {e}，将降级为内存向量搜索")

    def add_insight(self, insight: Insight):
        """添加见解"""
        with self.lock:
            if self.embedding_model:
                try:
                    # 生成向量嵌入（仅在模型可用时）
                    # Text2VecEmbedding.encode 接受列表并返回 numpy 数组
                    embedding = self.embedding_model.encode([insight.insight_text])
                    insight.embedding_vector = embedding[0].tolist()
                except Exception as e:
                    logger.warning(f"向量编码失败: {e}，跳过向量化")
            self.insights[insight.id] = insight

    def add_episode(self, episode: Episode):
        """添加情景摘要"""
        with self.lock:
            if self.embedding_model:
                try:
                    # Text2VecEmbedding.encode 接受列表并返回 numpy 数组
                    embedding = self.embedding_model.encode([episode.episode_summary])
                    episode.embedding_vector = embedding[0].tolist()
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
                    # Text2VecEmbedding.encode 接受列表并返回 numpy 数组
                    query_vector = self.embedding_model.encode([query])[0].tolist()
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

            # 创建见解表（温记忆持久化）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                source_event_ids TEXT,
                insight_text TEXT,
                insight_type TEXT,
                emotional_weight INTEGER,
                relevance_score REAL,
                keywords TEXT
            )
            """)

            # 创建情景摘要表（温记忆持久化）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                time_range TEXT,
                involved_events TEXT,
                episode_summary TEXT,
                emotional_arc TEXT,
                key_decisions TEXT
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
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_insight_created
            ON insights(created_at)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_created
            ON episodes(created_at)
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

    def persist_insight(self, insight: Insight):
        """将见解持久化到SQLite（INSERT OR REPLACE）"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO insights (
                    id, created_at, source_event_ids, insight_text,
                    insight_type, emotional_weight, relevance_score, keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    insight.id,
                    insight.created_at,
                    json.dumps(insight.source_event_ids),
                    insight.insight_text,
                    insight.insight_type,
                    insight.emotional_weight,
                    insight.relevance_score,
                    json.dumps(insight.keywords)
                ))
                conn.commit()

    def persist_episode(self, episode: Episode):
        """将情景摘要持久化到SQLite（INSERT OR REPLACE）"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO episodes (
                    id, created_at, time_range, involved_events,
                    episode_summary, emotional_arc, key_decisions
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.id,
                    episode.created_at,
                    json.dumps(list(episode.time_range)),
                    json.dumps(episode.involved_events),
                    episode.episode_summary,
                    episode.emotional_arc,
                    json.dumps(episode.key_decisions)
                ))
                conn.commit()

    def load_insights(self, limit: int = 100) -> List[Insight]:
        """从SQLite加载最近的见解"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM insights ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                insights = []
                for row in rows:
                    try:
                        insight = Insight(
                            id=row['id'],
                            created_at=row['created_at'],
                            source_event_ids=json.loads(row['source_event_ids'] or '[]'),
                            insight_text=row['insight_text'] or '',
                            insight_type=row['insight_type'] or 'reflection',
                            emotional_weight=row['emotional_weight'] or 0,
                            relevance_score=row['relevance_score'] or 0.5,
                            keywords=json.loads(row['keywords'] or '[]')
                        )
                        insights.append(insight)
                    except Exception:
                        pass
                return insights

    def load_episodes(self, limit: int = 50) -> List[Episode]:
        """从SQLite加载最近的情景摘要"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                episodes = []
                for row in rows:
                    try:
                        time_range_list = json.loads(row['time_range'] or '["", ""]')
                        episode = Episode(
                            id=row['id'],
                            created_at=row['created_at'],
                            time_range=tuple(time_range_list),
                            involved_events=json.loads(row['involved_events'] or '[]'),
                            episode_summary=row['episode_summary'] or '',
                            emotional_arc=row['emotional_arc'] or '',
                            key_decisions=json.loads(row['key_decisions'] or '[]')
                        )
                        episodes.append(episode)
                    except Exception:
                        pass
                return episodes


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
        """启动后台处理线程，并从SQLite加载历史温记忆"""
        if self.running:
            return
        self.running = True
        self.archival_thread = threading.Thread(
            target=self._archival_worker,
            daemon=True,
            name=f"MemoryArchival-{self.npc_name}"
        )
        self.archival_thread.start()
        logger.info(f"[{self.npc_name}] 记忆归档后台线程已启动")

        # 从SQLite恢复温记忆（Insight/Episode）
        self._restore_warm_memory()

    def stop(self):
        """停止后台线程"""
        self.running = False
        if self.archival_thread:
            self.archival_thread.join(timeout=5)

    # 热记忆事件数量触发归档的阈值
    HOT_MEMORY_ARCHIVAL_THRESHOLD = 50

    def add_event(self, event: NPCEventEnhanced):
        """添加事件到分层系统"""
        # 添加到热记忆
        self.hot_memory.add_event(event)

        # 基于热记忆容量触发冷归档：当事件总数超过阈值时，将最老一批事件入队
        with self.hot_memory.lock:
            all_events = self.hot_memory.recent_events.copy()

        if len(all_events) >= self.HOT_MEMORY_ARCHIVAL_THRESHOLD:
            # 将超出阈值部分的最老事件提交归档
            overflow = all_events[: len(all_events) - self.HOT_MEMORY_ARCHIVAL_THRESHOLD]
            for old_event in overflow:
                self.archival_queue.put(old_event)

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

    def _restore_warm_memory(self):
        """从SQLite加载历史Insight/Episode到温记忆"""
        try:
            insights = self.cold_memory.load_insights(limit=100)
            for insight in insights:
                self.warm_memory.insights[insight.id] = insight
            logger.info(f"[{self.npc_name}] 从SQLite恢复 {len(insights)} 条见解到温记忆")
        except Exception as e:
            logger.warning(f"[{self.npc_name}] 恢复Insight失败: {e}")

        try:
            episodes = self.cold_memory.load_episodes(limit=50)
            for episode in episodes:
                self.warm_memory.episodes[episode.id] = episode
            logger.info(f"[{self.npc_name}] 从SQLite恢复 {len(episodes)} 条情景摘要到温记忆")
        except Exception as e:
            logger.warning(f"[{self.npc_name}] 恢复Episode失败: {e}")

    def add_reflection_insight(self, insight: Insight):
        """添加反思得到的见解，并持久化到SQLite"""
        self.warm_memory.add_insight(insight)
        try:
            self.cold_memory.persist_insight(insight)
        except Exception as e:
            logger.warning(f"[{self.npc_name}] Insight持久化失败: {e}")

    def add_episode_summary(self, episode: Episode):
        """添加情景摘要，并持久化到SQLite"""
        self.warm_memory.add_episode(episode)
        try:
            self.cold_memory.persist_episode(episode)
        except Exception as e:
            logger.warning(f"[{self.npc_name}] Episode持久化失败: {e}")

    def query_cold_storage(self,
                          start_time: Optional[str] = None,
                          end_time: Optional[str] = None) -> List[NPCEventEnhanced]:
        """异步查询冷存储（用于年度总结或重大反思）"""
        return self.cold_memory.query_events(start_time, end_time)
