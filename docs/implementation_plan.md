# 初步实现方案

## 第一阶段：基础框架搭建 (2-3周)

### 目标
建立项目基础架构，实现简单的NPC行为和世界管理

### 技术栈选择
- **后端**: Python + FastAPI (异步支持好)
- **数据库**: SQLite (简化部署，后续可迁移到PostgreSQL)
- **缓存**: 内存缓存 (简化版本，后续集成Redis)
- **前端**: 简单的命令行界面 (CLI)

### 核心组件实现

#### 1. 基础Agent系统
```python
# backend/agents/base_agent.py
class BaseAgent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.memory = {}  # 简单的内存存储

    async def observe(self, world_state):
        """观察世界状态"""
        return world_state.get_visible_entities(self.agent_id)

    async def think(self, observation):
        """简单思考过程"""
        # 基于当前任务和观察做出决策
        current_task = self.memory.get('current_task')
        if current_task:
            return self.evaluate_task_progress(current_task, observation)
        else:
            return self.select_new_task(observation)

    async def act(self, thought):
        """执行行动"""
        action_type = thought.get('action_type')
        if action_type == 'move':
            return self.move_to_location(thought['location'])
        elif action_type == 'interact':
            return self.interact_with_entity(thought['entity_id'])
        # 其他行动类型...
```

#### 2. NPC Agent实现
```python
# backend/agents/npc_agent.py
class NPCAgent(BaseAgent):
    def __init__(self, agent_id: str, config: dict):
        super().__init__(agent_id, config['name'])
        self.background = config['background']  # 职业背景
        self.personality = config['personality']  # 性格特征
        self.abilities = config['abilities']  # 能力值
        self.current_task = None
        self.long_term_goals = config.get('goals', [])

    def select_task_based_on_personality(self, available_tasks):
        """基于性格选择任务"""
        if self.personality.get('lazy'):
            # 懒惰性格偏好轻松任务
            return min(available_tasks, key=lambda t: t.difficulty)
        elif self.personality.get('ambitious'):
            # 有抱负性格偏好挑战性任务
            return max(available_tasks, key=lambda t: t.reward)

        return random.choice(available_tasks)
```

#### 3. 世界状态管理
```python
# backend/world/world_state.py
class WorldState:
    def __init__(self):
        self.entities = {}  # 所有实体
        self.time = 0  # 世界时间
        self.rules = []  # 世界规则

    def add_entity(self, entity):
        """添加实体"""
        entity_id = str(uuid.uuid4())
        self.entities[entity_id] = entity
        return entity_id

    def update_entity(self, entity_id, updates):
        """更新实体"""
        if entity_id in self.entities:
            self.entities[entity_id].update(updates)

    def get_entities_in_location(self, location):
        """获取指定位置的实体"""
        return [e for e in self.entities.values()
                if e.location == location]
```

#### 4. 简单的CLI界面
```python
# backend/cli/interface.py
class CLIInterface:
    def __init__(self, world_manager):
        self.world_manager = world_manager

    def display_world_status(self):
        """显示世界状态"""
        world_state = self.world_manager.get_world_state()
        print("=== 世界状态 ===")
        print(f"时间: {world_state.time}")
        print(f"实体数量: {len(world_state.entities)}")

        for entity_id, entity in world_state.entities.items():
            print(f"- {entity.name} ({entity.type}): {entity.status}")

    def process_command(self, command):
        """处理用户命令"""
        parts = command.split()
        if not parts:
            return

        cmd = parts[0].lower()
        if cmd == 'status':
            self.display_world_status()
        elif cmd == 'create':
            self.create_entity(parts[1:])
        elif cmd == 'update':
            self.update_entity(parts[1:])
        # 其他命令...
```

### 数据库设计
```sql
-- 简单SQLite数据库设计
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    location TEXT,
    properties TEXT,  -- JSON格式存储
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_memory (
    agent_id TEXT,
    key TEXT,
    value TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, key)
);

CREATE TABLE world_events (
    id TEXT PRIMARY KEY,
    event_type TEXT,
    description TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 第二阶段：核心功能扩展 (3-4周)

### 目标
集成LLM支持，实现更复杂的NPC行为

### LLM集成
```python
# backend/llm/client.py
class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    async def generate_response(self, prompt: str, context: dict = None) -> str:
        """生成LLM响应"""
        system_prompt = self.build_system_prompt(context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )

        return response.choices[0].message.content
```

### 增强的NPC行为
```python
# backend/agents/enhanced_npc.py
class EnhancedNPCAgent(NPCAgent):
    def __init__(self, agent_id: str, config: dict, llm_client: LLMClient):
        super().__init__(agent_id, config)
        self.llm_client = llm_client

    async def think(self, observation):
        """使用LLM进行思考"""
        prompt = self.build_thinking_prompt(observation)

        llm_response = await self.llm_client.generate_response(
            prompt,
            context={
                'personality': self.personality,
                'background': self.background,
                'current_task': self.current_task,
                'goals': self.long_term_goals
            }
        )

        return self.parse_llm_response(llm_response)

    def build_thinking_prompt(self, observation):
        """构建思考提示"""
        return f"""
你是一个{self.background}，性格{self.personality}。
当前观察到: {observation}

你的当前任务: {self.current_task}
你的长期目标: {self.long_term_goals}

请分析当前情况，并决定下一步行动。响应格式:
行动类型: [move|interact|wait|...]
目标: [具体目标]
理由: [行动理由]
"""
```

### 工具调用系统
```python
# backend/agents/tool_manager.py
class ToolManager:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name: str, tool_func):
        """注册工具"""
        self.tools[name] = tool_func

    async def execute_tool(self, tool_name: str, parameters: dict):
        """执行工具"""
        if tool_name not in self.tools:
            raise ValueError(f"未知工具: {tool_name}")

        tool_func = self.tools[tool_name]
        return await tool_func(**parameters)

    def get_available_tools(self):
        """获取可用工具列表"""
        return list(self.tools.keys())

# 注册基础工具
tool_manager = ToolManager()
tool_manager.register_tool("move_to", move_to_location)
tool_manager.register_tool("interact_with", interact_with_entity)
tool_manager.register_tool("observe_area", observe_area)
```

## 第三阶段：性能优化和扩展 (2-3周)

### 缓存系统
```python
# backend/cache/cache_manager.py
class CacheManager:
    def __init__(self):
        self.cache = {}  # 简单的内存缓存
        self.ttl = {}    # 过期时间

    def set(self, key: str, value, ttl_seconds: int = 3600):
        """设置缓存"""
        self.cache[key] = value
        self.ttl[key] = time.time() + ttl_seconds

    def get(self, key: str):
        """获取缓存"""
        if key in self.ttl and time.time() > self.ttl[key]:
            del self.cache[key]
            del self.ttl[key]
            return None

        return self.cache.get(key)

    def clear_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [k for k, t in self.ttl.items() if current_time > t]

        for key in expired_keys:
            del self.cache[key]
            del self.ttl[key]
```

### 异步处理优化
```python
# backend/async/async_manager.py
class AsyncManager:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.task_queue = asyncio.Queue()

    async def process_agent_cycle(self, agent, world_state):
        """异步处理agent循环"""
        async with self.semaphore:
            try:
                result = await agent.process_cycle(world_state)
                return result
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} 处理失败: {e}")
                return None

    async def process_all_agents(self, agents, world_state):
        """并发处理所有agents"""
        tasks = [
            self.process_agent_cycle(agent, world_state)
            for agent in agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]

        return successful_results
```

## 实施路线图

### Week 1-2: 基础框架
- [ ] 创建项目结构
- [ ] 实现基础Agent类
- [ ] 实现世界状态管理
- [ ] 创建简单的CLI界面
- [ ] 基础数据库集成

### Week 3-4: NPC行为系统
- [ ] 实现NPC Agent类
- [ ] 添加任务系统
- [ ] 实现基础决策逻辑
- [ ] 集成LLM支持

### Week 5-6: 工具和扩展
- [ ] 实现工具调用系统
- [ ] 添加更多NPC类型
- [ ] 实现世界规则系统
- [ ] 性能优化和缓存

### Week 7-8: 测试和完善
- [ ] 编写单元测试
- [ ] 性能测试和优化
- [ ] 文档完善
- [ ] 部署准备

## 技术决策理由

1. **Python + FastAPI**: 
   - 优秀的异步支持
   - 丰富的AI/ML生态
   - 快速开发

2. **SQLite起步**: 
   - 零配置部署
   - 足够支持早期开发
   - 后期可平滑迁移

3. **CLI界面优先**: 
   - 快速验证核心逻辑
   - 降低前端开发复杂度
   - 便于调试

4. **渐进式LLM集成**: 
   - 先实现基础逻辑
   - 逐步添加AI增强
   - 便于对比和优化

这个实施方案提供了清晰的开发路径，从简单到复杂逐步实现，确保每个阶段都有可工作的系统。
