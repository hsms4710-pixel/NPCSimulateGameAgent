# 项目文件结构规划

## 整体目录结构

```
MRAG_Enhanced_Model/
├── backend/                          # 后端服务
│   ├── app/                         # 应用主目录
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI应用入口
│   │   ├── config.py                # 配置管理
│   │   └── dependencies.py          # 依赖注入
│   ├── agents/                      # Agent系统
│   │   ├── __init__.py
│   │   ├── base_agent.py            # 基础Agent类
│   │   ├── npc_agent.py             # NPC Agent
│   │   ├── world_agent.py           # 世界管理Agent
│   │   ├── reasoning_engine.py      # 推理引擎
│   │   ├── tool_manager.py          # 工具管理器
│   │   └── consistency_manager.py   # 一致性管理器
│   ├── world/                       # 世界管理系统
│   │   ├── __init__.py
│   │   ├── world_state.py           # 世界状态
│   │   ├── entity_manager.py        # 实体管理器
│   │   ├── rule_engine.py           # 规则引擎
│   │   ├── event_system.py          # 事件系统
│   │   └── time_system.py           # 时间系统
│   ├── api/                         # API接口
│   │   ├── __init__.py
│   │   ├── routes/                  # 路由
│   │   │   ├── __init__.py
│   │   │   ├── world.py             # 世界相关API
│   │   │   ├── agents.py            # Agent相关API
│   │   │   └── god.py               # 上帝控制API
│   │   └── websocket/               # WebSocket处理
│   │       ├── __init__.py
│   │       └── connection_manager.py
│   ├── multimodal/                  # 多模态处理
│   │   ├── __init__.py
│   │   ├── input_processor.py       # 输入处理器
│   │   ├── feature_extractor.py     # 特征提取器
│   │   ├── fusion_model.py          # 融合模型
│   │   └── output_generator.py      # 输出生成器
│   ├── rag/                         # RAG系统
│   │   ├── __init__.py
│   │   ├── retriever.py             # 检索器
│   │   ├── knowledge_base.py        # 知识库
│   │   ├── index_builder.py         # 索引构建器
│   │   └── query_processor.py       # 查询处理器
│   ├── performance/                 # 性能优化
│   │   ├── __init__.py
│   │   ├── cache_manager.py         # 缓存管理器
│   │   ├── memory_optimizer.py      # 内存优化器
│   │   ├── async_processor.py       # 异步处理器
│   │   └── profiler.py              # 性能分析器
│   ├── utils/                       # 工具函数
│   │   ├── __init__.py
│   │   ├── logger.py                # 日志工具
│   │   ├── serializer.py            # 序列化工具
│   │   ├── validator.py             # 验证工具
│   │   └── helpers.py               # 辅助函数
│   └── tests/                       # 后端测试
│       ├── __init__.py
│       ├── conftest.py              # 测试配置
│       ├── test_agents.py
│       ├── test_world.py
│       └── test_api.py
├── frontend/                        # 前端应用
│   ├── public/                      # 静态资源
│   ├── src/
│   │   ├── components/              # React组件
│   │   │   ├── WorldMonitor/        # 世界监控组件
│   │   │   ├── EntityEditor/        # 实体编辑器
│   │   │   ├── NPCPanel/            # NPC控制面板
│   │   │   ├── RuleConfigurator/    # 规则配置器
│   │   │   └── ChatInterface/       # 聊天界面
│   │   ├── hooks/                   # 自定义hooks
│   │   ├── services/                # API服务
│   │   ├── stores/                  # 状态管理
│   │   ├── utils/                   # 工具函数
│   │   ├── types/                   # TypeScript类型
│   │   └── App.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.js
├── docs/                           # 文档
│   ├── architecture.md             # 架构设计
│   ├── api_reference.md            # API参考
│   ├── deployment.md               # 部署指南
│   └── user_guide.md               # 用户指南
├── scripts/                        # 部署和维护脚本
│   ├── deploy.sh                   # 部署脚本
│   ├── backup.sh                   # 备份脚本
│   ├── migrate.py                  # 数据迁移
│   └── setup_dev.sh                # 开发环境设置
├── docker/                         # Docker配置
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
├── requirements.txt                # Python依赖
├── pyproject.toml                  # 项目配置
├── .gitignore
├── .env.example                    # 环境变量示例
└── README.md
```

## 核心文件详解

### 后端核心文件

#### `backend/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api.routes import world, agents, god

app = FastAPI(title="MRAG Enhanced Model API")

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(world.router, prefix="/api/world", tags=["world"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(god.router, prefix="/api/god", tags=["god"])

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 初始化数据库连接
    # 初始化缓存系统
    # 启动后台任务
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    # 清理资源
    pass
```

#### `backend/agents/base_agent.py`
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..multimodal.input_processor import MultiModalInput
from ..world.world_state import WorldState
from .tool_manager import ToolManager
from .reasoning_engine import ReasoningEngine

class BaseAgent(ABC):
    def __init__(self, agent_id: str, config: Dict[str, Any]):
        self.agent_id = agent_id
        self.config = config
        self.tool_manager = ToolManager()
        self.reasoning_engine = ReasoningEngine()
        self.memory: Dict[str, Any] = {}

    @abstractmethod
    async def observe(self, world_state: WorldState) -> Dict[str, Any]:
        """观察世界状态"""
        pass

    @abstractmethod
    async def think(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """思考和推理"""
        pass

    @abstractmethod
    async def act(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """执行行动"""
        pass

    async def process_cycle(self, world_state: WorldState) -> Dict[str, Any]:
        """完整的代理循环"""
        observation = await self.observe(world_state)
        thought = await self.think(observation)
        action = await self.act(thought)

        return {
            "observation": observation,
            "thought": thought,
            "action": action
        }
```

#### `backend/world/world_state.py`
```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
from .entity import Entity
from .rule import Rule
from .event import Event

@dataclass
class WorldState:
    """世界状态管理"""
    entities: Dict[str, Entity] = field(default_factory=dict)
    rules: List[Rule] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    current_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """更新实体"""
        async with self._lock:
            if entity_id not in self.entities:
                return False

            entity = self.entities[entity_id]
            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)

            return True

    async def add_entity(self, entity: Entity) -> str:
        """添加新实体"""
        async with self._lock:
            entity_id = str(uuid.uuid4())
            self.entities[entity_id] = entity
            return entity_id

    def get_snapshot(self) -> Dict[str, Any]:
        """获取世界快照"""
        return {
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "rules": [rule.to_dict() for rule in self.rules],
            "events": [event.to_dict() for event in self.events],
            "current_time": self.current_time.isoformat(),
            "metadata": self.metadata
        }
```

### 前端核心文件

#### `frontend/src/components/WorldMonitor/WorldMonitor.tsx`
```typescript
import React, { useEffect, useState } from 'react';
import { Entity, WorldState } from '../../types';
import EntityList from './EntityList';
import WorldMap from './WorldMap';
import ControlPanel from './ControlPanel';

interface WorldMonitorProps {
  worldState: WorldState;
  onEntityUpdate: (entityId: string, updates: Partial<Entity>) => void;
  onEntityCreate: (entity: Omit<Entity, 'id'>) => void;
}

const WorldMonitor: React.FC<WorldMonitorProps> = ({
  worldState,
  onEntityUpdate,
  onEntityCreate
}) => {
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  return (
    <div className="world-monitor">
      <div className="world-overview">
        <WorldMap
          entities={worldState.entities}
          onEntitySelect={setSelectedEntity}
        />
        <ControlPanel
          worldState={worldState}
          onCreateEntity={onEntityCreate}
        />
      </div>
      <EntityList
        entities={worldState.entities}
        selectedEntity={selectedEntity}
        onEntityUpdate={onEntityUpdate}
        onEntitySelect={setSelectedEntity}
      />
    </div>
  );
};

export default WorldMonitor;
```

## 配置文件

### `backend/app/config.py`
```python
from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    # API配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # 数据库配置
    DATABASE_URL: str = "postgresql://user:password@localhost/mrag_world"

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379"

    # LLM配置
    OPENAI_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4"

    # 世界配置
    WORLD_UPDATE_INTERVAL: float = 1.0  # 秒
    MAX_AGENTS: int = 100
    MEMORY_LIMIT_MB: int = 1024

    # 缓存配置
    CACHE_TTL: int = 3600  # 秒
    ENABLE_KV_CACHE: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### `pyproject.toml`
```toml
[tool.poetry]
name = "mrag-enhanced-model"
version = "0.1.0"
description = "Multi-modal RAG Enhanced Agent Model for Game Worlds"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
fastapi = "^0.104.1"
uvicorn = "^0.24.0"
sqlalchemy = "^2.0.23"
alembic = "^1.12.1"
redis = "^5.0.1"
openai = "^1.3.7"
anthropic = "^0.7.8"
pydantic = "^2.5.0"
python-multipart = "^0.0.6"
aiofiles = "^23.2.1"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"
black = "^23.11.0"
isort = "^5.12.0"
mypy = "^1.7.1"

[build-system]
requires = ["poetry-core"]
build-system = "poetry-core"
```

## 开发环境配置

### `docker-compose.dev.yml`
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app/backend
      - ./docs:/app/docs
    environment:
      - ENVIRONMENT=development
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: ./frontend
      dockerfile: ../docker/Dockerfile.frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mrag_world
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

这个文件结构提供了完整的项目框架，支持从简单到复杂的逐步实现。每个目录和文件都有明确的职责，支持模块化开发和扩展。
