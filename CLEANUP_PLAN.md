# 代码清理计划

## 需要清理的内容

### 1. 重复的React Agent实现
- `react_agent.py` - 旧版实现
- `npc_optimization/react_tools.py` - 新版优化实现
- **处理**: 保留新版，旧版标记为legacy，逐步迁移

### 2. 重复的优化模块
- `optimized_llm_system.py` - 旧版优化系统
- `npc_optimization/` - 新版优化模块
- **处理**: 保留新版，旧版标记为legacy

### 3. 未使用的文件
- `backend/` - 如果为空或未使用
- `frontend/` - 如果为空或未使用
- `main.py` - 如果未使用（已有demo.py）
- `run_simulator.py` - 如果未使用

### 4. 代码结构优化
- 按功能模块组织文件
- 删除重复导入
- 统一命名规范

## 清理步骤

1. ✅ 修复react_agent重复定义（已标记为legacy）
2. ⏳ 检查optimized_llm_system的使用情况
3. ⏳ 清理未使用的导入
4. ⏳ 组织文件结构

