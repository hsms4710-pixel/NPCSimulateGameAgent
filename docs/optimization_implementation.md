# NPC系统优化实施文档

## 概述
本文档记录NPC系统优化的实施过程，包括上下文压缩、行为决策树、Prompt优化等模块的实现细节。

---

## 阶段1：上下文压缩和行为决策树（已完成）

### 1.1 上下文压缩器 (`npc_optimization/context_compressor.py`)

#### 功能
- 分层压缩上下文，减少token消耗60-70%
- 保留关键信息：世界观、NPC性格、当前状态
- 智能摘要：背景故事、事件历史

#### 使用方式
```python
from npc_optimization import ContextCompressor

compressor = ContextCompressor(max_tokens=1000)
compressed = compressor.compress_context(
    npc_config=npc_config,
    npc_state=npc_state,
    current_task=current_task,
    recent_events=recent_events,
    relevant_memories=relevant_memories
)
```

#### 压缩策略
1. **核心状态**（必需，~200 tokens）
   - 当前活动、情绪、能量
   - 当前任务（简化）
   - 时间、位置、需求状态

2. **NPC摘要**（~300 tokens）
   - 姓名、种族、职业、年龄
   - 性格特征（最多5个）
   - 背景故事摘要（150字）

3. **最近上下文**（~400 tokens）
   - 最近3个事件（摘要）
   - 相关记忆（最多5个）

4. **日常作息**（从人物卡读取）
   - 睡觉时间
   - 工作时间
   - 吃饭时间
   - 自定义习惯

---

### 1.2 行为决策树 (`npc_optimization/behavior_decision_tree.py`)

#### 功能
- 使用硬编码规则处理日常行为
- **所有规则从人物卡读取**，确保可自定义
- 减少60-70%的LLM调用

#### 从人物卡读取的配置
```python
{
    "daily_schedule": {
        "sleep_time": "22:00-6:00",  # 睡觉时间
        "work_time": "6:00-19:00",   # 工作时间
        "meal_times": ["7:00-8:00", "12:00-13:00", "18:00-19:00"],  # 吃饭时间
        "habits": [  # 自定义习惯
            {
                "time": "8:00",
                "action": "祈祷"
            }
        ]
    },
    "work_hours": "早上6点-晚上7点"  # 备用格式
}
```

#### 决策流程
1. 检查紧急任务（优先级>=90）→ 需要LLM
2. 检查睡觉时间（从人物卡）→ 规则决策
3. 检查吃饭时间（从人物卡）→ 规则决策
4. 检查工作时间（从人物卡）→ 规则决策
5. 检查需求状态 → 规则决策
6. 检查自定义习惯（从人物卡）→ 规则决策
7. 其他情况 → 需要LLM

#### 使用方式
```python
from npc_optimization import BehaviorDecisionTree

tree = BehaviorDecisionTree(npc_config)
action = tree.decide_routine_behavior(
    current_hour=14,
    energy_level=80,
    needs={"hunger": 0.3, "fatigue": 0.2, "social": 0.5},
    current_task=None
)
# 返回 NPCAction 或 None（None表示需要LLM决策）
```

---

### 1.3 Prompt模板 (`npc_optimization/prompt_templates.py`)

#### 功能
- 设计精简但保留世界观和NPC性格的prompt
- 使用压缩后的上下文
- 确保角色一致性

#### Prompt设计原则
1. **精简**：只包含必要信息
2. **保留世界观**：包含世界设定（精简版）
3. **保留性格**：包含NPC性格特征和背景
4. **结构化**：使用JSON格式输出

#### 模板类型
- `get_task_progress_prompt`: 任务进度决策
- `get_behavior_decision_prompt`: 行为决策
- `get_event_response_prompt`: 事件响应

---

## 阶段2：整合到现有系统

### 2.1 修改 `npc_system.py`

#### 新增导入
```python
from npc_optimization import ContextCompressor as OptimizedContextCompressor
from npc_optimization import BehaviorDecisionTree
from npc_optimization import PromptTemplates
```

#### 初始化优化模块
```python
# 在 __init__ 中
self.context_compressor = OptimizedContextCompressor(max_tokens=1000)
self.behavior_tree = BehaviorDecisionTree(npc_config)
self.prompt_templates = PromptTemplates()
```

#### 替换旧逻辑
- ✅ 替换 `_llm_decide_task_progress` 使用压缩上下文
- ✅ 在 `_autonomous_behavior_loop` 中使用行为决策树
- ✅ 删除旧的硬编码prompt

---

## 阶段3：人物卡自定义配置

### 3.1 人物卡结构

所有NPC的作息、习惯都应该在人物卡中定义：

```python
{
    "name": "埃尔德·铁锤",
    "race": "矮人",
    "profession": "铁匠",
    
    # 日常作息（可自定义）
    "daily_schedule": {
        "sleep_time": "22:00-6:00",  # 睡觉时间
        "work_time": "6:00-19:00",   # 工作时间
        "meal_times": ["7:00-8:00", "12:00-13:00", "18:00-19:00"],  # 吃饭时间
        "habits": [  # 自定义习惯
            {
                "time": "8:00",
                "action": "祈祷",
                "description": "每天早上祈祷"
            }
        ]
    },
    
    # 备用格式（兼容旧配置）
    "work_hours": "早上6点-晚上7点",
    
    # 其他配置...
}
```

### 3.2 扩展性

- ✅ 所有作息时间可自定义
- ✅ 支持自定义习惯
- ✅ 支持多个吃饭时间
- ✅ 兼容旧配置格式

---

## 阶段4：文档和结构整理

### 4.1 模块结构
```
npc_optimization/
├── __init__.py              # 模块导出
├── context_compressor.py    # 上下文压缩器
├── behavior_decision_tree.py # 行为决策树
└── prompt_templates.py      # Prompt模板
```

### 4.2 文档
- ✅ 本文档：实施文档
- ✅ `optimization_evaluation.md`: 优化方案评估
- ✅ 代码注释：详细的函数和类注释

---

## 测试和验证

### 测试要点
1. ✅ 上下文压缩是否正确保留关键信息
2. ✅ 行为决策树是否正确从人物卡读取配置
3. ✅ Prompt是否精简但保留世界观
4. ✅ 系统是否能正常运行
5. ✅ Token消耗是否减少

### 验证方法
```python
# 测试上下文压缩
compressed = compressor.compress_context(...)
assert len(compressed) < original_size * 0.4  # 减少60%+

# 测试行为决策树
action = tree.decide_routine_behavior(...)
assert action in [NPCAction.SLEEP, NPCAction.EAT, NPCAction.WORK, None]

# 测试Prompt
prompt = templates.get_task_progress_prompt(...)
assert "世界观" in prompt or "艾伦谷" in prompt
assert "性格" in prompt
```

---

## 下一步计划

### 阶段2：记忆管理
- [ ] 实现记忆摘要系统
- [ ] 实现记忆清理策略
- [ ] 实现记忆压缩

### 阶段3：ReAct工具系统
- [ ] 设计工具定义结构
- [ ] 实现工具执行系统
- [ ] 实现ReAct循环

### 阶段4：RAG记忆检索
- [ ] 实现向量化记忆存储
- [ ] 实现语义搜索
- [ ] 实现Agent自主管理

---

## 注意事项

1. **删除旧逻辑**：引入新逻辑后，确保删除旧的硬编码逻辑
2. **保持兼容性**：支持旧的人物卡格式
3. **可扩展性**：所有配置都应该可以从人物卡读取
4. **文档更新**：每次修改都要更新文档

---

## 总结

阶段1已完成：
- ✅ 上下文压缩器
- ✅ 行为决策树（从人物卡读取）
- ✅ Prompt模板优化
- ✅ 整合到现有系统

预期效果：
- Token消耗减少60-70%
- LLM调用减少60-70%（日常行为）
- 保留世界观和NPC性格
- 所有配置可自定义

