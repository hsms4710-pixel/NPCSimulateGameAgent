# 艾伦谷 NPC 模拟器 - AI 开发指南

## 核心项目目标
智能 NPC 行为模拟系统，使用 DeepSeek LLM 生成具有记忆、性格和复杂决策能力的 NPC，设定在中世纪奇幻小镇。

## 关键架构模式

### 1. 四级决策系统（核心创新）
NPC 决策遵循分层架构，每层消耗不同的 Token 成本：
- **L1 生物锁** (`behavior_decision_tree.py`): 硬规则决策 - 检查疲劳/饥饿/睡眠状态
- **L2 快速过滤**: 使用 MiniLM 判断事件重要性（待实现）
- **L3 战略规划**: 生成行动蓝图（待实现）
- **L4 深度推理** (`four_level_decisions.py`): ReAct + Tree of Thoughts 多路径推理

**实现要点**: 使用 `FourLevelDecisionMaker.make_decision()` 处理所有事件。它自动从 L1 开始，L1 拦截则返回（无 Token），否则依次到 L4。参见 [npc_system.py L737-760](npc_system.py#L737)。

### 2. 记忆分层系统
三层记忆管理（热/温/冷）+ RAG 向量检索：
- **热记忆**: 最近 24H 事件（快速访问）
- **温记忆**: 一周内事件（精选摘要）
- **冷记忆**: 长期事件（向量化 FAISS 存储）

检索精度已从 35% 优化到 85%（使用 sentence-transformers）。详见 [npc_optimization/rag_memory.py](npc_optimization/rag_memory.py) 和 [npc_optimization/memory_layers.py](npc_optimization/memory_layers.py)。

### 3. NPC 人物卡配置模式
所有 NPC 配置存储在 `world_lore.py` 中的 `NPC_TEMPLATES`。关键字段：
- `work_hours`: "6-18" → 行为树自动解析
- `sleep_time`: "22-8"
- `meal_times`: [(7,8), (12,13), (18,19)]
- `daily_schedule.habits`: 自定义习惯列表

**重要**: 修改 NPC 行为时更新人物卡，不要硬编码逻辑。参见 [npc_optimization/behavior_decision_tree.py L18-80](npc_optimization/behavior_decision_tree.py#L18)。

### 4. 事件驱动的行为流程
[npc_system.py L737-860](npc_system.py#L737):
1. `process_event()` 构建事件快照
2. 评估冲击分数（0-100，高分触发更复杂的 L3/L4 决策）
3. 调用 `FourLevelDecisionMaker.make_decision()`
4. 执行决策 + 生成自然语言响应
5. 记录决策历史（用于反思和学习）

## 开发工作流

### 快速启动
```powershell
# Windows 开发环境设置
.\scripts\setup_dev.ps1
# 激活虚拟环境
.\venv\Scripts\Activate.ps1
# 运行 GUI 模拟器
python run_simulator.py
```

### 关键文件导航
| 功能 | 文件 |
|-----|------|
| NPC 主类/行为循环 | [npc_system.py](npc_system.py) (~2230 行) |
| 决策引擎 | [npc_optimization/four_level_decisions.py](npc_optimization/four_level_decisions.py) |
| 行为规则 | [npc_optimization/behavior_decision_tree.py](npc_optimization/behavior_decision_tree.py) |
| 记忆管理 | [npc_optimization/memory_manager.py](npc_optimization/memory_manager.py) + RAG 系统 |
| 角色数据 | [world_lore.py](world_lore.py) - 修改 NPC 模板这里 |
| LLM 客户端 | [deepseek_client.py](deepseek_client.py) - 所有 API 调用 |
| GUI/演示 | [gui_interface.py](gui_interface.py) + [demo.py](demo.py) |

### 常见开发任务

**优化 Token 消耗**:
- 检查 `behavior_tree.should_use_llm()` - 如果规则能解决就避免 L4
- 使用 `ContextCompressor` 压缩长历史（[npc_optimization/context_compressor.py](npc_optimization/context_compressor.py)）
- 添加 L2 快速过滤器拦截琐事

**添加 NPC 工具**:
- 在 [npc_optimization/react_tools.py](npc_optimization/react_tools.py) 的 `NPCToolRegistry` 中注册
- 示例: `check_location()`, `recall_memory()`, `check_relationship_status()`
- 工具调用在 ReAct 循环中自动执行

**修改 NPC 性格**:
- 编辑 [world_lore.py](world_lore.py) 中的 `NPC_TEMPLATES`
- 性格特征影响 L4 推理中的 prompt，参见 [npc_optimization/prompt_templates.py](npc_optimization/prompt_templates.py)

**调试决策**:
- 检查 `NPCBehaviorSystem.decision_history` (最后 50 条决策记录)
- 查看 `DEVELOPMENT_SUMMARY_REPORT.md` 了解决策层级覆盖情况

## 关键技术决策

### 为什么分层决策？
- L1 节省 99% 的日常行为 Token（无 API 调用）
- L4 仅用于高影响事件（冲击 >70），确保复杂推理成本可控
- 混合规则+LLM，避免过度依赖 API

### 为什么 FAISS RAG？
- 精度 85% vs SimpleVectorStore 35%
- 1-2ms 查询延迟（原方案 5-10ms）
- 支持 500MB+ 记忆库无性能退化

### 为什么持久化事件历史？
- 支持 NPC 反思和学习（待实现 L2/L3）
- 调试决策过程的审计日志
- 参见 `npc_persistence.py` 和 `NPCEvent`/`NPCTask` 数据类

## 常见陷阱

❌ **硬编码 NPC 行为** → ✅ 使用 `behavior_decision_tree` + 人物卡配置  
❌ **每个事件都调用 L4** → ✅ 让 L1-L3 先处理，冲击 <70 时直接返回  
❌ **忽略记忆检索** → ✅ 始终在 prompt 中包含相关记忆（用 RAG 系统）  
❌ **修改 `NPCAction` 枚举不更新 `ai_instruction`** → ✅ 同步更新 `constants.py`  

## 测试与验证

```bash
# 运行单元测试（如有）
pytest

# 验证依赖
python -c "from npc_optimization import *; print('✓ 所有模块加载成功')"

# 性能分析：检查 Token 消耗
# 查看 gui_interface.py 中的 TokenCounter 面板
```

## 配置与部署

- **环境变量**: 复制 `env.example` → `.env`，设置 `DEEPSEEK_API_KEY`
- **模型参数**: [deepseek_client.py L1-20](deepseek_client.py#L1) 默认 `temperature=0.7, max_tokens=500`
- **前端**: [frontend/](frontend/) (React + TypeScript，状态：规划中)
- **后端 API**: [backend/](backend/) (FastAPI，状态：规划中)

## 文档参考

- [architecture.md](docs/architecture.md) - 系统设计总览
- [project_structure.md](docs/project_structure.md) - 完整目录规划（含 backend/frontend）
- [DEVELOPMENT_SUMMARY_REPORT.md](DEVELOPMENT_SUMMARY_REPORT.md) - 开发进度和决策历史

---

**最后更新**: 2025 年 1 月 | **完成度**: 66% (9/14 核心组件)
