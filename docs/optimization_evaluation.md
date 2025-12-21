# NPC系统优化方案评估

## 概述
本文档评估针对单NPC系统的优化方案，重点关注token消耗优化、记忆管理、决策效率等方面。

---

## 1. 上下文压缩减少Token消耗 ⭐⭐⭐⭐⭐

### 当前问题
- 每次LLM调用都包含完整的NPC配置、状态、历史
- 重复发送大量静态信息（性格、背景等）
- 事件历史完整传递，token消耗大

### 优化方案
**分层上下文策略：**
```
Level 1: 核心状态（必需，每次发送）
  - 当前活动、情绪、能量
  - 当前任务（简化描述）
  - 时间、位置

Level 2: 动态状态（按需发送）
  - 最近3个重要事件
  - 当前需求状态
  - 相关关系变化

Level 3: 静态配置（首次或变化时发送）
  - 性格特征（摘要）
  - 职业背景（摘要）
  - 长期目标（摘要）

Level 4: 历史记忆（RAG检索，按相关性）
  - 通过向量搜索获取相关记忆
  - 只返回top-k相关记忆
```

### 实现建议
```python
class ContextCompressor:
    """上下文压缩器"""
    
    def compress_context(self, npc_context, max_tokens=1000):
        """压缩上下文到指定token数"""
        # 1. 提取核心状态（~200 tokens）
        core = self._extract_core_state(npc_context)
        
        # 2. 摘要静态配置（~300 tokens）
        static_summary = self._summarize_static_config(npc_context)
        
        # 3. 检索相关记忆（~400 tokens）
        relevant_memories = self._retrieve_relevant_memories(
            npc_context.current_task,
            top_k=5
        )
        
        # 4. 最近事件摘要（~100 tokens）
        recent_events = self._summarize_recent_events(
            npc_context.event_history[-5:]
        )
        
        return {
            "core": core,
            "static": static_summary,
            "memories": relevant_memories,
            "events": recent_events
        }
```

### 预期效果
- **Token减少**: 60-70%
- **成本降低**: 每次调用从~2000 tokens降至~600-800 tokens
- **响应速度**: 提升20-30%

### 优先级：高 ⭐⭐⭐⭐⭐

---

## 2. 记忆管理（摘要、时间清理、缩减） ⭐⭐⭐⭐⭐

### 当前问题
- 事件历史无限增长
- 所有记忆同等重要
- 没有记忆压缩机制

### 优化方案

#### 2.1 情景摘要
```python
class MemorySummarizer:
    """记忆摘要系统"""
    
    def summarize_episode(self, events: List[NPCEvent], 
                         time_window: timedelta) -> str:
        """将一段时间内的事件摘要为情景"""
        # 使用LLM生成摘要
        prompt = f"""
        将以下事件摘要为一个连贯的情景描述：
        {self._format_events(events)}
        
        要求：
        1. 保留关键信息（人物、地点、结果）
        2. 合并相似事件
        3. 突出重要转折点
        4. 控制在100字以内
        """
        return llm.summarize(prompt)
    
    def create_episode(self, events: List[NPCEvent]) -> Episode:
        """创建情景对象"""
        return Episode(
            summary=self.summarize_episode(events),
            start_time=events[0].timestamp,
            end_time=events[-1].timestamp,
            importance=self._calculate_importance(events),
            key_events=[e.id for e in events if e.impact_score > 70]
        )
```

#### 2.2 时间清理策略
```python
class MemoryManager:
    """记忆管理器"""
    
    CLEANUP_RULES = {
        "daily": {
            "age_days": 1,
            "keep_importance": 7,  # 保留重要性>=7的记忆
            "compress_others": True
        },
        "weekly": {
            "age_days": 7,
            "keep_importance": 5,
            "compress_others": True
        },
        "monthly": {
            "age_days": 30,
            "keep_importance": 3,
            "compress_to_episodes": True  # 压缩为情景
        }
    }
    
    def cleanup_memories(self):
        """定期清理记忆"""
        now = datetime.now()
        
        # 每日清理：删除低重要性旧记忆
        for memory in self.memories:
            age = (now - memory.timestamp).days
            
            if age > 1 and memory.importance < 7:
                # 压缩为摘要
                self._compress_memory(memory)
            
            if age > 7 and memory.importance < 5:
                # 合并到情景
                self._merge_to_episode(memory)
            
            if age > 30 and memory.importance < 3:
                # 删除或归档
                self._archive_memory(memory)
```

#### 2.3 记忆缩减
```python
def _compress_memory(self, memory: Memory) -> CompressedMemory:
    """压缩单个记忆"""
    if len(memory.content) > 200:
        # 使用LLM压缩
        compressed = llm.compress(
            f"压缩以下记忆，保留关键信息：{memory.content}",
            target_length=100
        )
        return CompressedMemory(
            original_id=memory.id,
            compressed_content=compressed,
            importance=memory.importance,
            timestamp=memory.timestamp
        )
    return memory
```

### 预期效果
- **存储减少**: 70-80%
- **检索速度**: 提升50%
- **记忆质量**: 保留重要信息，删除冗余

### 优先级：高 ⭐⭐⭐⭐⭐

---

## 3. 硬编码简单逻辑（日常行为） ⭐⭐⭐⭐

### 当前问题
- 日常行为（吃饭、睡觉）也调用LLM
- 浪费token和API调用
- 响应延迟

### 优化方案

#### 3.1 行为决策树
```python
class BehaviorDecisionTree:
    """行为决策树（硬编码规则）"""
    
    def decide_routine_behavior(self, npc_state) -> Optional[NPCAction]:
        """日常行为决策（不使用LLM）"""
        hour = npc_state.world_time.hour
        energy = npc_state.energy_level
        needs = npc_state.needs
        
        # 睡觉时间（22:00-6:00）
        if 22 <= hour or hour < 6:
            if energy < 30 or needs.fatigue > 0.8:
                return NPCAction.SLEEP
        
        # 吃饭时间（7:00-8:00, 12:00-13:00, 18:00-19:00）
        if hour in [7, 8, 12, 13, 18, 19]:
            if needs.hunger > 0.6:
                return NPCAction.EAT
        
        # 工作时间（根据职业）
        work_hours = self._get_work_hours(npc_state.profession)
        if work_hours[0] <= hour < work_hours[1]:
            if not npc_state.current_task or npc_state.current_task.priority < 80:
                return NPCAction.WORK
        
        # 默认：根据需求
        if needs.fatigue > 0.7:
            return NPCAction.REST
        if needs.social > 0.6:
            return NPCAction.SOCIALIZE
        
        return None  # 需要LLM决策
```

#### 3.2 混合决策系统
```python
def decide_action(self, npc_state) -> NPCAction:
    """混合决策：规则优先，LLM补充"""
    
    # 1. 检查是否有紧急任务
    if npc_state.current_task and npc_state.current_task.priority >= 90:
        return self._llm_decide_urgent_task(npc_state)
    
    # 2. 尝试规则决策（日常行为）
    routine_action = self.behavior_tree.decide_routine_behavior(npc_state)
    if routine_action:
        return routine_action
    
    # 3. 复杂情况使用LLM
    return self._llm_decide_complex_behavior(npc_state)
```

### 预期效果
- **API调用减少**: 60-70%（日常行为）
- **Token节省**: 40-50%
- **响应速度**: 日常行为即时响应
- **成本降低**: 显著

### 优先级：高 ⭐⭐⭐⭐

---

## 4. ReAct工具化行为逻辑 ⭐⭐⭐⭐⭐

### 当前问题
- 行为逻辑分散在代码各处
- 难以扩展和维护
- LLM无法直接调用行为函数

### 优化方案

#### 4.1 工具定义
```python
class NPCActionTools:
    """NPC行为工具集"""
    
    TOOLS = [
        {
            "name": "change_activity",
            "description": "切换NPC当前活动",
            "parameters": {
                "activity": {
                    "type": "string",
                    "enum": ["工作", "休息", "睡觉", "观察", "帮助他人"],
                    "description": "要切换到的活动"
                },
                "reason": {
                    "type": "string",
                    "description": "切换原因"
                }
            }
        },
        {
            "name": "update_emotion",
            "description": "更新NPC情绪状态",
            "parameters": {
                "emotion": {
                    "type": "string",
                    "enum": ["平静", "愤怒", "担忧", "高兴", "悲伤"],
                    "description": "新的情绪状态"
                },
                "intensity": {
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "description": "情绪强度"
                }
            }
        },
        {
            "name": "create_task",
            "description": "创建新任务",
            "parameters": {
                "description": {"type": "string"},
                "priority": {"type": "number", "min": 0, "max": 100},
                "deadline": {"type": "string", "format": "datetime"}
            }
        },
        {
            "name": "update_task_progress",
            "description": "更新任务进度",
            "parameters": {
                "task_id": {"type": "string"},
                "progress_increase": {"type": "number", "min": 0, "max": 1}
            }
        },
        {
            "name": "add_memory",
            "description": "添加新记忆",
            "parameters": {
                "content": {"type": "string"},
                "importance": {"type": "number", "min": 1, "max": 10},
                "tags": {"type": "array", "items": {"type": "string"}}
            }
        },
        {
            "name": "search_memories",
            "description": "搜索相关记忆",
            "parameters": {
                "query": {"type": "string"},
                "max_results": {"type": "number", "default": 5}
            }
        }
    ]
    
    def execute_tool(self, tool_name: str, parameters: dict):
        """执行工具调用"""
        if tool_name == "change_activity":
            return self._change_activity(parameters["activity"], parameters["reason"])
        elif tool_name == "update_emotion":
            return self._update_emotion(parameters["emotion"], parameters["intensity"])
        # ... 其他工具
```

#### 4.2 ReAct循环
```python
class ReActAgent:
    """ReAct风格的NPC Agent"""
    
    def think_and_act(self, situation: str) -> Dict:
        """思考-行动循环"""
        max_iterations = 5
        observation = ""
        
        for i in range(max_iterations):
            # 1. 思考阶段
            thought = self._think(situation, observation)
            
            # 2. 行动阶段（工具调用）
            if "tool_call" in thought:
                result = self._execute_tool(thought["tool_call"])
                observation = f"工具执行结果: {result}"
            else:
                # 3. 最终决策
                return thought["final_decision"]
        
        return {"action": "休息", "reason": "达到最大迭代次数"}
    
    def _think(self, situation: str, observation: str) -> Dict:
        """思考阶段：分析情况并决定行动"""
        prompt = f"""
        当前情况：{situation}
        上次观察：{observation}
        
        可用工具：{self._format_tools()}
        
        请分析情况并决定：
        1. 是否需要调用工具？
        2. 如果需要，调用哪个工具？
        3. 如果不需要，做出最终决策
        
        格式：
        {{
            "reasoning": "你的推理",
            "tool_call": {{"name": "工具名", "parameters": {{}}}},
            "final_decision": {{"action": "行动", "reason": "原因"}}
        }}
        """
        return self.llm.generate_json(prompt)
```

### 预期效果
- **可扩展性**: 易于添加新行为
- **可维护性**: 行为逻辑集中管理
- **LLM控制**: Agent自主决定使用哪些工具
- **调试友好**: 清晰的工具调用链

### 优先级：高 ⭐⭐⭐⭐⭐

---

## 5. RAG/MRAG历史数据库搜索 ⭐⭐⭐⭐⭐

### 当前问题
- 记忆线性存储，检索效率低
- 无法根据相关性检索
- 所有记忆同等权重

### 优化方案

#### 5.1 向量化记忆系统
```python
class VectorMemorySystem:
    """向量化记忆系统（RAG）"""
    
    def __init__(self):
        self.vector_store = VectorStore()  # 使用FAISS或Chroma
        self.memories = {}  # id -> Memory
    
    def add_memory(self, memory: Memory):
        """添加记忆并向量化"""
        # 1. 生成向量
        embedding = self.embed(memory.content)
        
        # 2. 存储向量
        self.vector_store.add(
            id=memory.id,
            vector=embedding,
            metadata={
                "timestamp": memory.timestamp.isoformat(),
                "importance": memory.importance,
                "tags": memory.tags
            }
        )
        
        # 3. 存储完整记忆
        self.memories[memory.id] = memory
    
    def search_relevant_memories(self, query: str, top_k: int = 5) -> List[Memory]:
        """搜索相关记忆"""
        # 1. 查询向量化
        query_embedding = self.embed(query)
        
        # 2. 向量搜索
        results = self.vector_store.search(
            query_embedding,
            top_k=top_k,
            filter={"importance": {"$gte": 3}}  # 只搜索重要性>=3的记忆
        )
        
        # 3. 返回完整记忆对象
        return [self.memories[r.id] for r in results]
```

#### 5.2 MRAG增强检索
```python
class MRAGMemorySystem(VectorMemorySystem):
    """多模态RAG记忆系统"""
    
    def search_with_context(self, 
                           query: str,
                           current_task: Optional[Task] = None,
                           time_context: Optional[Dict] = None) -> List[Memory]:
        """带上下文的记忆检索"""
        
        # 1. 构建增强查询
        enhanced_query = self._enhance_query(query, current_task, time_context)
        
        # 2. 多路检索
        results = []
        
        # 2.1 语义搜索
        semantic_results = self.vector_store.search(enhanced_query, top_k=10)
        results.extend(semantic_results)
        
        # 2.2 时间相关搜索
        if time_context:
            time_results = self._search_by_time(time_context, top_k=5)
            results.extend(time_results)
        
        # 2.3 任务相关搜索
        if current_task:
            task_results = self._search_by_task(current_task, top_k=5)
            results.extend(task_results)
        
        # 3. 重排序和去重
        return self._rerank_and_dedup(results, top_k=5)
```

#### 5.3 Agent自主管理数据库
```python
class AutonomousMemoryManager:
    """自主记忆管理器"""
    
    def manage_memory_database(self, npc_state):
        """Agent自主管理记忆数据库"""
        prompt = f"""
        当前记忆数据库状态：
        - 总记忆数：{len(self.memories)}
        - 最近记忆：{self._get_recent_memories(10)}
        - 当前任务：{npc_state.current_task}
        
        请决定：
        1. 是否需要添加新记忆？
        2. 是否需要删除/归档旧记忆？
        3. 是否需要合并相似记忆？
        4. 是否需要压缩低重要性记忆？
        
        返回JSON：
        {{
            "add_memories": [{{"content": "...", "importance": 5}}],
            "delete_memory_ids": ["id1", "id2"],
            "merge_memory_groups": [[id1, id2, id3]],
            "compress_memory_ids": ["id4", "id5"]
        }}
        """
        
        decision = self.llm.generate_json(prompt)
        
        # 执行决策
        self._execute_memory_operations(decision)
```

### 预期效果
- **检索精度**: 提升60-80%
- **检索速度**: 向量搜索比线性搜索快100倍
- **相关性**: 只返回相关记忆，减少token
- **自主性**: Agent可以管理自己的记忆

### 优先级：高 ⭐⭐⭐⭐⭐

---

## 综合评估与实施建议

### 优先级排序
1. **上下文压缩** ⭐⭐⭐⭐⭐ - 立即实施，效果显著
2. **硬编码日常行为** ⭐⭐⭐⭐ - 快速实施，成本降低明显
3. **记忆管理** ⭐⭐⭐⭐⭐ - 中期实施，长期收益
4. **RAG/MRAG搜索** ⭐⭐⭐⭐⭐ - 中期实施，提升质量
5. **ReAct工具化** ⭐⭐⭐⭐⭐ - 长期重构，提升架构

### 实施路线图

#### 阶段1（1-2周）：快速优化
- [ ] 实现上下文压缩器
- [ ] 实现行为决策树（日常行为）
- [ ] 添加记忆摘要功能

#### 阶段2（2-4周）：记忆系统
- [ ] 实现向量化记忆存储
- [ ] 实现RAG检索系统
- [ ] 实现记忆清理策略

#### 阶段3（4-8周）：架构重构
- [ ] 实现ReAct工具系统
- [ ] 重构决策流程
- [ ] 实现Agent自主记忆管理

### 预期总体效果
- **Token消耗**: 减少70-80%
- **API成本**: 降低60-70%
- **响应速度**: 提升50%
- **系统质量**: 显著提升（更智能、更高效）

---

## 技术选型建议

### 向量数据库
- **FAISS** (Facebook AI Similarity Search): 轻量级，适合单机
- **Chroma**: 简单易用，支持元数据过滤
- **Qdrant**: 功能丰富，支持复杂查询

### 嵌入模型
- **中文**: text2vec-large-chinese
- **多语言**: sentence-transformers/all-MiniLM-L6-v2
- **本地部署**: 避免API调用

### 摘要模型
- **GPT-3.5-turbo**: 质量好但需API
- **本地模型**: ChatGLM-6B, Qwen-7B（可本地部署）

---

## 结论

所有提出的优化方案都具有很高的价值，建议按优先级逐步实施。这些优化将显著提升系统效率、降低成本，同时改善NPC行为的智能性和一致性。

