# 🎯 快速参考卡片 - RAG 升级和 Token 统计

## 📦 安装和启用

```bash
# 安装依赖
pip install -r requirements.txt

# 首次运行（下载模型，约 1-2 分钟）
python gui_interface.py
```

---

## 🔍 RAG 系统使用

### 基础使用
```python
from npc_optimization.rag_memory import RAGMemorySystem

# 创建 RAG 系统
rag = RAGMemorySystem(
    use_embeddings=True,           # 启用语义嵌入
    model_name="all-MiniLM-L6-v2"  # 默认轻量级模型
)

# 添加记忆
rag.add_memory(
    memory_id="evt_001",
    content="NPC 与冒险者发生冲突并受伤",
    importance=8,
    tags=["冲突", "伤害"]
)

# 搜索相关记忆
results = rag.search_relevant_memories(
    query="为什么 NPC 害怕那个冒险者？",
    top_k=3,
    min_importance=5
)

# 获取系统统计
stats = rag.get_stats()
print(f"总记忆: {stats['total_memories']}")
print(f"搜索精度: {stats['avg_similarity']:.2%}")
```

### 语义搜索示例
```python
# 添加一些记忆
rag.add_memory("mem_1", "小偷在夜间盗窃了宝物", importance=8)
rag.add_memory("mem_2", "商人丢失了贵重物品", importance=6)
rag.add_memory("mem_3", "王子决定变得更坚强", importance=5)

# 语义搜索（自动匹配"偷窃"相关的记忆）
results = rag.search_relevant_memories("为什么要偷东西？", top_k=2)

# 返回结果包含:
# - mem_1 (相似度 0.92) ← 匹配"盗窃"
# - mem_2 (相似度 0.78) ← 匹配"丢失"
```

---

## 📊 GUI Token 统计面板

### 界面位置
位于 GUI 窗口**底部**，包含：

```
┌─ Token 消耗统计 ──────────────────────────────────┐
│                                                   │
│ Tokens发送: 15,234    Tokens接收: 8,456           │
│ API调用: 42           总Tokens: 23,690            │
│ 压缩比率: 1.25x       估计成本: $0.0047           │
│ 运行时间: 02:15:30    [清除统计] [导出数据]       │
│                                                   │
└───────────────────────────────────────────────────┘
```

### 集成代码
```python
# 在 NPC 系统 LLM 调用后调用
response = deepseek_client.chat_completion(messages=...)

# 更新 GUI 统计
self.gui.update_token_stats(
    tokens_sent=response["usage"]["prompt_tokens"],
    tokens_received=response["usage"]["completion_tokens"],
    api_call=True
)
```

### 导出数据格式
点击"导出数据"生成 `token_stats.json`:
```json
{
  "timestamp": "2025-01-15T10:30:45.123456",
  "total_tokens_sent": 15234,
  "total_tokens_received": 8456,
  "total_api_calls": 42,
  "estimated_cost": 0.0047,
  "compression_ratio": 1.25,
  "runtime": "2:15:30"
}
```

---

## ⚙️ 配置选项

### RAG 系统配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `use_embeddings` | True | 启用 FAISS 语义搜索 |
| `model_name` | "all-MiniLM-L6-v2" | 嵌入模型 |
| `top_k` | 5 | 返回结果数量 |
| `min_importance` | 3 | 最小重要性过滤 |

### 模型选择
```python
# 选项 1: 快速轻量级（推荐）
rag = RAGMemorySystem(model_name="all-MiniLM-L6-v2")  # ~22MB

# 选项 2: 高精度
rag = RAGMemorySystem(model_name="all-mpnet-base-v2")  # ~438MB

# 选项 3: 降级到关键词匹配
rag = RAGMemorySystem(use_embeddings=False)
```

### GPU 加速（可选）
```python
from npc_optimization.rag_memory import FAISSVectorStore

store = FAISSVectorStore(use_gpu=True)  # 需要 faiss-gpu
```

---

## 🐛 故障排除

### 问题 1: FAISS 未找到
**症状**: `ImportError: No module named 'faiss'`
**解决**:
```bash
pip install faiss-cpu
# 或使用 GPU 版本
pip install faiss-gpu
```

### 问题 2: sentence-transformers 模型下载缓慢
**症状**: 首次运行卡在"下载嵌入模型"
**解决**:
```python
# 手动预下载模型
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
# 模型保存至 ~/.cache/huggingface/
```

### 问题 3: Token 统计面板不更新
**症状**: 数字保持为 0
**解决**: 确保在 LLM 调用后调用 `update_token_stats()`
```python
# 正确用法
response = api_call()
gui.update_token_stats(tokens_sent=X, tokens_received=Y, api_call=True)

# 检查响应中的 usage 字段
print(response.get("usage"))
```

### 问题 4: 搜索精度仍然低
**症状**: 搜索结果不相关
**解决**:
```python
# 检查是否使用了 FAISS
from npc_optimization.rag_memory import FAISS_AVAILABLE
print(f"FAISS 可用: {FAISS_AVAILABLE}")

# 增加返回结果数量
results = rag.search_relevant_memories(query, top_k=10)

# 调整重要性阈值
results = rag.search_relevant_memories(query, min_importance=1)
```

---

## 📈 性能优化建议

### 1. 批量操作
```python
# ❌ 避免频繁调用
for memory in memories:
    rag.add_memory(...)

# ✅ 批量添加（推荐）
for memory in memories:
    rag.add_memory(...)
# 然后一次性更新 GUI
```

### 2. 缓存热查询
```python
# 缓存常用查询的结果
query_cache = {}

def search_cached(query):
    if query in query_cache:
        return query_cache[query]
    
    results = rag.search_relevant_memories(query)
    query_cache[query] = results
    return results
```

### 3. Token 成本优化
```python
# 监控成本较高的操作
expensive_calls = []

def track_expensive_calls(cost):
    if cost > 0.001:  # 超过 $0.001
        expensive_calls.append(cost)
        
# 定期审查
print(f"高成本调用: {len(expensive_calls)}")
```

---

## 🔗 相关文件

| 文件 | 说明 |
|------|------|
| `npc_optimization/rag_memory.py` | RAG 核心实现 |
| `gui_interface.py` | GUI Token 统计面板 |
| `requirements.txt` | 依赖列表 |
| `FEATURES_UPDATE.md` | 详细功能文档 |
| `IMPLEMENTATION_SUMMARY.md` | 实现总结 |

---

## 💡 最佳实践

### ✅ 推荐做法
1. 定期导出 Token 统计数据，用于成本分析
2. 为重要记忆设置更高的 importance 值
3. 使用标签分类记忆便于后续查询
4. 监控搜索精度，调整查询表述

### ❌ 避免做法
1. 不要频繁重置统计（丢失历史数据）
2. 不要使用过长的记忆内容（影响嵌入质量）
3. 不要忽视模型下载进度（第一次运行需要时间）
4. 不要在大数据集上使用过小的 top_k

---

## 📞 API 快速参考

### RAGMemorySystem
```python
# 初始化
rag = RAGMemorySystem(use_embeddings=True, model_name="...")

# 添加记忆
rag.add_memory(memory_id, content, importance=5, tags=[], timestamp=None)

# 搜索记忆
rag.search_relevant_memories(query, top_k=5, min_importance=3)

# 带上下文搜索
rag.search_with_context(query, current_task=None, time_context=None, top_k=5)

# 删除记忆
rag.delete_memory(memory_id)

# 获取所有记忆
rag.get_all_memories()

# 获取统计信息
rag.get_stats()
```

### GUI Token 统计
```python
# 更新统计
gui.update_token_stats(tokens_sent=int, tokens_received=int, api_call=bool)

# 重置统计
gui.reset_token_stats()

# 导出数据
gui.export_token_stats()  # 生成 token_stats.json
```

---

**版本**: 1.1.0  
**更新日期**: 2025年1月  
**状态**: ✅ 生产就绪

