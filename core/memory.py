"""记忆系统 — 三层（热-温-冷）+ RAG 检索 + 反思提炼

比 Smallville 更复杂：
- 三层分级（热/温/冷）而非单一记忆流
- Insight 反思提炼（事件影响力驱动）
- Episode 情景摘要（时间段聚合）
- FAISS 向量检索（可选，降级为关键词匹配）
"""
import json, logging, os, sqlite3, time, re, hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

try:
    import faiss
    import numpy as np
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False


@dataclass
class Memory:
    """单条记忆"""
    id: str
    timestamp: str
    type: str  # event / dialogue / observation / insight / episode
    content: str
    importance: int = 5  # 1-10
    emotional_weight: int = 0  # -10 ~ +10
    source_npc: str = ""
    related_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    embedding: Optional[Any] = None


class MemorySystem:
    """NPC 记忆系统 — 三层 + RAG + 反思"""

    def __init__(self, npc_name: str, data_dir: str = "npc_storage"):
        self.npc_name = npc_name
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # 热记忆：最近 50 条
        self.hot: List[Memory] = []
        self.hot_limit = 50

        # 温记忆：Insight + Episode（内存 + FAISS）
        self.insights: List[Memory] = []
        self.episodes: List[Memory] = []

        # 事件影响力累积
        self.impact_accumulator = 0
        self.reflect_threshold = 50  # 累积到 50 触发反思

        # FAISS 向量索引
        self._embed_model = None
        self._faiss_index = None
        self._faiss_dim = 768
        self._init_faiss()

        # 冷记忆：SQLite
        self._db_path = os.path.join(data_dir, f"{npc_name}_cold.db")
        self._init_db()

    def _init_faiss(self):
        if FAISS_AVAILABLE and ST_AVAILABLE:
            try:
                model_path = os.path.join(os.path.dirname(__file__), "..", "models", "text2vec-base-chinese")
                if os.path.exists(model_path):
                    self._embed_model = SentenceTransformer(model_path)
                    self._faiss_dim = self._embed_model.get_sentence_embedding_dimension()
                self._faiss_index = faiss.IndexFlatL2(self._faiss_dim)
                logger.info(f"[{self.npc_name}] FAISS 索引初始化，维度={self._faiss_dim}")
            except Exception as e:
                logger.warning(f"[{self.npc_name}] FAISS 初始化失败: {e}，降级为关键词匹配")

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS cold_memory (
                id TEXT PRIMARY KEY, timestamp TEXT, type TEXT, content TEXT,
                importance INTEGER, emotional_weight INTEGER, source_npc TEXT,
                keywords TEXT, related_ids TEXT)""")

    def _embed(self, text: str) -> Optional[Any]:
        if self._embed_model:
            return self._embed_model.encode([text])[0]
        return None

    def _extract_keywords(self, text: str) -> List[str]:
        segments = re.split(r'][，。！？、；：""''（）【\[\s]+', text)
        return [s for s in segments if len(s) >= 2][:10]

    def add(self, content: str, mtype: str = "event", importance: int = 5,
            emotional_weight: int = 0, source_npc: str = "") -> Memory:
        mem = Memory(
            id=hashlib.md5(f"{time.time()}-{content[:20]}".encode()).hexdigest()[:8],
            timestamp=datetime.now().isoformat(),
            type=mtype, content=content, importance=importance,
            emotional_weight=emotional_weight, source_npc=source_npc,
            keywords=self._extract_keywords(content),
            embedding=self._embed(content),
        )
        self.hot.append(mem)
        if len(self.hot) > self.hot_limit:
            old = self.hot.pop(0)
            self._archive_cold(old)
        if self._faiss_index is not None and mem.embedding is not None:
            self._faiss_index.add(np.array([mem.embedding], dtype=np.float32))
        self.impact_accumulator += importance
        return mem

    def _archive_cold(self, mem: Memory):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO cold_memory VALUES (?,?,?,?,?,?,?,?,?)",
                (mem.id, mem.timestamp, mem.type, mem.content,
                 mem.importance, mem.emotional_weight, mem.source_npc,
                 json.dumps(mem.keywords, ensure_ascii=False),
                 json.dumps(mem.related_ids, ensure_ascii=False)),
            )

    def retrieve(self, query: str, top_k: int = 5) -> List[Memory]:
        """RAG 检索 — 向量优先，降级关键词"""
        candidates = self.hot + self.insights + self.episodes
        if not candidates:
            return []

        query_kw = set(self._extract_keywords(query))

        if self._faiss_index is not None and self._embed_model:
            q_vec = self._embed(query)
            if q_vec is not None:
                scores = []
                for i, mem in enumerate(candidates):
                    if mem.embedding is not None:
                        dist = float(np.linalg.norm(np.array(mem.embedding, dtype=np.float32) - np.array(q_vec, dtype=np.float32)))
                        recency = 1.0 / (1.0 + (datetime.now() - datetime.fromisoformat(mem.timestamp)).total_seconds() / 3600)
                        score = mem.importance * 0.4 + (1.0 / (1.0 + dist)) * 0.4 + recency * 0.2
                        scores.append((score, mem))
                scores.sort(key=lambda x: -x[0])
                return [m for _, m in scores[:top_k]]

        # 关键词匹配降级
        scored = []
        for mem in candidates:
            overlap = len(query_kw & set(mem.keywords))
            recency = 1.0 / (1.0 + (datetime.now() - datetime.fromisoformat(mem.timestamp)).total_seconds() / 3600)
            score = mem.importance * 0.3 + overlap * 0.5 + recency * 0.2
            scored.append((score, mem))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:top_k]]

    def should_reflect(self) -> bool:
        return self.impact_accumulator >= self.reflect_threshold

    def add_insight(self, content: str, source_ids: List[str], importance: int = 8):
        insight = Memory(
            id=hashlib.md5(f"insight-{time.time()}".encode()).hexdigest()[:8],
            timestamp=datetime.now().isoformat(), type="insight",
            content=content, importance=importance, emotional_weight=0,
            source_npc=self.npc_name, related_ids=source_ids,
            keywords=self._extract_keywords(content),
            embedding=self._embed(content),
        )
        self.insights.append(insight)
        if len(self.insights) > 100:
            old = self.insights.pop(0)
            self._archive_cold(old)

    def reflect(self, llm_client) -> Optional[str]:
        """反思 — LLM 从近期记忆提炼 Insight"""
        if not self.should_reflect():
            return None
        recent = self.hot[-20:]
        if len(recent) < 3:
            return None
        summary = "\n".join(f"[{m.timestamp[:16]}] {m.content}" for m in recent)
        prompt = f"""你是{self.npc_name}。回顾以下近期经历，提炼一条高维见解（Insight）。
只输出见解本身（一句话），不要解释。

近期经历：
{summary}"""
        result = llm_client.chat([{"role": "user", "content": prompt}], temperature=0.5, max_tokens=100)
        insight_text = result.strip()
        if insight_text and not insight_text.startswith("("):
            self.add_insight(insight_text, [m.id for m in recent])
            self.impact_accumulator = 0
            logger.info(f"[{self.npc_name}] 反思提炼 Insight: {insight_text}")
            return insight_text
        return None

    def get_context(self, query: str, max_items: int = 8) -> str:
        """获取决策上下文 — 检索相关记忆 + 最近记忆 + Insight"""
        retrieved = self.retrieve(query, top_k=max_items)
        parts = []
        if self.insights:
            parts.append("## 见解")
            for ins in self.insights[-3:]:
                parts.append(f"- {ins.content}")
        if retrieved:
            parts.append("\n## 相关记忆")
            for m in retrieved:
                parts.append(f"- [{m.timestamp[:10]}] {m.content[:80]}")
        return "\n".join(parts) if parts else "(无相关记忆)"

    def to_dict(self) -> dict:
        return {
            "hot_count": len(self.hot),
            "insight_count": len(self.insights),
            "episode_count": len(self.episodes),
            "impact_accumulator": self.impact_accumulator,
            "recent": [{"content": m.content[:60], "type": m.type, "importance": m.importance} for m in self.hot[-5:]],
            "insights": [{"content": m.content} for m in self.insights[-3:]],
        }
