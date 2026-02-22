# NPC 行为模拟器 - MRAG Enhanced Model

> 基于多层记忆检索增强生成（MRAG）的智能 NPC 行为系统，支持完整的事件驱动、经济系统、社交传播与前后端交互。

---

## 项目结构

```
MRAG_Enhanced_Model/
├── backend/                    # 后端服务层
│   ├── api_server.py           # FastAPI 主服务（仅保留 app + 中间件 + 路由注册）
│   ├── npc_service.py          # NPC 服务封装
│   ├── world_data.py           # 世界数据管理（含动态NPC/地点加载）
│   ├── routes/                 # 路由模块（D1）
│   │   ├── player_routes.py    # /api/v1/player/* 背包/工作/住宿/关系
│   │   ├── event_routes.py     # /api/v1/events/* 统一事件触发/查询
│   │   └── npc_routes.py       # /api/v1/npc/instantiate NPC实例化
│   └── services/               # 服务层（D1）
│       ├── economy_service.py  # EconomySystem 单例封装
│       └── event_service.py    # 完整事件链路封装
├── core_types/                 # 统一数据类型定义
│   ├── npc_types.py            # UnifiedNPCState（含经济/关系/住宿/任务字段）
│   ├── event_types.py          # UnifiedEvent（含child_event_ids/npc_directives等）
│   ├── memory_types.py         # 记忆/目标/关系类型
│   └── enums.py                # 枚举与常量
├── npc_core/                   # NPC 行为系统核心
│   ├── npc_base.py             # 基础设施集成
│   ├── npc_events.py           # 事件处理（含_update_relationship关系系统）
│   ├── npc_dialogue.py         # 对话与记忆
│   ├── npc_autonomous.py       # 自主行为循环
│   ├── npc_registry.py         # NPC 注册表
│   └── npc_persistence.py      # 数据持久化
├── npc_optimization/           # 优化模块
│   ├── event_coordinator.py    # 事件协调与角色分配
│   ├── event_progression.py    # 事件推进系统（含_settle_event_tree）
│   ├── world_event_manager.py  # 空间广播 + 八卦自动传播调度器
│   ├── unified_tools.py        # 统一工具集（含trade_item交易工具）
│   ├── four_level_decisions.py # 四级决策系统
│   ├── memory_layers.py        # 三层记忆管理
│   └── rag_memory.py           # RAG 记忆检索
├── world_simulator/            # 世界模拟器
│   ├── world_manager.py        # 世界管理器（工作/住宿接入经济）
│   ├── economy_system.py       # 经济系统（货币/背包/市场）
│   ├── player_system.py        # 玩家角色系统
│   ├── quest_system.py         # 任务系统
│   └── event_system.py         # 事件触发系统
├── frontend/                   # 前端界面
│   ├── index.html              # 主页面（含背包面板/事件树面板）
│   ├── css/style.css           # 样式（含背包格/事件进度条/关系颜色条）
│   └── js/
│       ├── api.js              # API 客户端（含16个新方法）
│       ├── game.js             # 游戏逻辑（含渲染/刷新/WebSocket处理）
│       └── map.js              # 地图模块
├── npc_storage/                # NPC 持久化数据
├── saves/                      # 游戏存档
├── tests/                      # 测试
├── run.py                      # 启动入口
├── requirements.txt
└── start_demo.bat              # Windows 快速启动
```

---

## 核心架构

### 数据绑定原则
- NPC 相关数据挂在 `UnifiedNPCState` 实体上（金币、背包、关系、任务等）
- 事件数据用 `UnifiedEvent` 传递（子事件链、感知NPC、经济数据等）
- 不使用游离全局变量

### 四级决策系统
```
L1: 生物钟硬判决 (0 tokens)    — 遵循日程
L2: 快速重要性过滤 (50 tokens) — 是否忽视事件
L3: 战略规划 (200 tokens)      — 制定行动计划
L4: 深度推理 (500+ tokens)     — 树搜索复杂推理
```

### 事件驱动流程（以教堂火灾为例）
```
POST /api/v1/events/trigger {type:"disaster", content:"教堂起火", location:"圣光教堂"}
  → event_service.trigger_event()
  → UnifiedEvent 创建 + EventProgressionSystem 注册
  → WorldEventManager.broadcast_spatial_event() 空间广播
  → event.aware_npcs 记录感知NPC
  → EventCoordinator 分析 + 角色分配 → event.npc_directives
  → NPC.process_event() → _execute_decision() → move_to() + 子任务创建
  → EventProgressionSystem.tick() 阶段推进（8阶段）
  → 子事件生成 → child_event_ids 写回父事件
  → phase=resolved → _settle_event_tree() 递归结算
  → 关系更新 + 记忆写入 + WebSocket 推送
```

---

## API 端点

### 事件系统
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/events/trigger` | 统一事件触发入口 |
| GET  | `/api/v1/events/active` | 活跃事件列表（含子事件树） |
| GET  | `/api/v1/events/{id}` | 单事件详情 |
| GET  | `/api/v1/events/{id}/tree` | 事件因果树 |
| POST | `/api/v1/events/{id}/settle` | 手动结算事件树 |

### 玩家系统
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/player/inventory` | 背包查询 |
| POST | `/api/v1/player/inventory/use` | 使用物品 |
| POST | `/api/v1/player/trade` | 与NPC交易 |
| GET  | `/api/v1/player/gold` | 金币余额 |
| POST | `/api/v1/player/work` | 打工（经济结算） |
| POST | `/api/v1/player/rest` | 住宿（经济结算） |
| GET  | `/api/v1/player/relationships` | 关系列表 |

### NPC系统
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/npc/instantiate` | 实例化临时NPC |
| DELETE | `/api/v1/npc/{name}` | 移除临时NPC |
| GET  | `/api/v1/npc/{name}/relationships` | NPC关系查询 |

### WebSocket 推送消息类型
| 类型 | 触发时机 |
|------|---------|
| `event_phase_change` | 事件阶段变化 → 前端更新进度条 |
| `npc_moved` | NPC位置变化 → 地图气泡移动 |
| `gossip_spread` | 八卦传播跳转 |
| `trade_completed` | 交易完成 → 刷新背包 |
| `relationship_changed` | 关系变化 → 刷新关系面板 |
| `task_completed` | 任务完成 → 奖励弹窗 |

---

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python run.py

# 或 Windows 双击
start_demo.bat
```

服务启动后访问：`http://localhost:8000`

API 文档：`http://localhost:8000/docs`

---

## 主要特性

- **事件驱动**：所有行为变化（移动、交易、救援）均由 `UnifiedEvent` 驱动，经 `EventCoordinator` 分发
- **八卦自动传播**：`WorldEventManager` 后台线程每 tick 自动传一跳，模拟真实社交扩散
- **经济系统**：货币转账、背包管理、市场定价，NPC/玩家状态实时同步
- **关系系统**：动态阈值分级（enemy/stranger/friend/close_friend），对话/交易/事件均触发更新
- **子事件树**：父事件 resolved 后递归结算所有子事件，奖励自动分发
- **NPC实例化**：未知实体在交互触发时动态实例化为完整 Agent
- **动态分类**：位置、事件类型等从数据文件读取，不写死枚举或 if-else

---

## 技术栈

- **后端**：Python 3.10+, FastAPI, asyncio, WebSocket
- **LLM**：DeepSeek API（支持替换其他兼容接口）
- **前端**：原生 HTML/CSS/JS，无框架依赖
- **存储**：JSON + gzip 本地持久化
