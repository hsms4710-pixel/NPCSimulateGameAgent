"""
优化后的LLM系统 - 针对NPC智能决策的完整解决方案
结合上下文压缩、向量记忆、工具化架构和智能prompt设计
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib
import numpy as np
from enum import Enum


class MemoryType(Enum):
    SHORT_TERM = "short_term"    # 最近24小时
    WORKING = "working"         # 当前任务相关
    EPISODIC = "episodic"       # 具体事件记忆
    SEMANTIC = "semantic"       # 一般知识和规则
    PROCEDURAL = "procedural"   # 技能和习惯


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    memory_type: MemoryType
    importance: float  # 0-10
    emotional_impact: float  # -10到10
    timestamp: datetime
    tags: List[str]
    context: Dict[str, Any]  # 相关上下文
    vector_embedding: Optional[List[float]] = None
    access_count: int = 0
    last_access: Optional[datetime] = None
    summary: Optional[str] = None  # 压缩摘要


@dataclass
class NPCContext:
    """NPC当前上下文"""
    name: str
    race: str
    profession: str
    personality: Dict[str, Any]
    background: str
    current_activity: str
    current_emotion: str
    current_needs: Dict[str, float]
    current_task: Optional[Dict] = None
    recent_memories: List[MemoryEntry] = None
    time_context: Dict[str, Any] = None

    def __post_init__(self):
        if self.recent_memories is None:
            self.recent_memories = []
        if self.time_context is None:
            self.time_context = {}


class ContextCompressor:
    """上下文压缩器 - 智能压缩以减少token消耗"""

    def __init__(self):
        self.compression_cache = {}
        self.max_memory_entries = 5

    def compress_context(self, full_context: NPCContext, max_tokens: int = 2000) -> Dict[str, Any]:
        """
        压缩NPC上下文到指定token限制内
        """
        cache_key = self._generate_cache_key(full_context)
        if cache_key in self.compression_cache:
            return self.compression_cache[cache_key]

        compressed = {
            'identity': self._compress_identity(full_context),
            'current_state': self._compress_current_state(full_context),
            'memory_summary': self._compress_memories(full_context.recent_memories),
            'time_context': self._compress_time_context(full_context.time_context),
            'decision_context': self._extract_decision_context(full_context)
        }

        # 估算token数量并调整
        compressed = self._adjust_for_token_limit(compressed, max_tokens)

        self.compression_cache[cache_key] = compressed
        return compressed

    def _compress_identity(self, context: NPCContext) -> Dict[str, Any]:
        """压缩NPC身份信息"""
        return {
            'name': context.name,
            'profession': context.profession,
            'personality_core': self._extract_personality_core(context.personality),
            'background_key': self._summarize_background(context.background, 50)  # 50字摘要
        }

    def _compress_current_state(self, context: NPCContext) -> Dict[str, Any]:
        """压缩当前状态"""
        return {
            'activity': context.current_activity,
            'emotion': context.current_emotion,
            'critical_needs': {k: v for k, v in context.current_needs.items() if v > 0.6},
            'task_focus': context.current_task.get('description', '') if context.current_task else None
        }

    def _compress_memories(self, memories: List[MemoryEntry]) -> Dict[str, Any]:
        """智能压缩记忆"""
        if not memories:
            return {'count': 0, 'summary': '无近期记忆'}

        # 按重要性和时间排序
        sorted_memories = sorted(
            memories,
            key=lambda m: (m.importance * 0.6 + (1 / (1 + (datetime.now() - m.timestamp).days)) * 0.4),
            reverse=True
        )

        # 选择最重要的记忆
        selected = sorted_memories[:self.max_memory_entries]

        # 生成记忆摘要
        memory_texts = [m.content for m in selected]
        combined_summary = self._generate_combined_summary(memory_texts)

        return {
            'count': len(selected),
            'summary': combined_summary,
            'key_events': [self._summarize_memory(m) for m in selected[:3]],
            'emotional_pattern': self._extract_emotional_pattern(selected)
        }

    def _compress_time_context(self, time_context: Dict[str, Any]) -> Dict[str, Any]:
        """压缩时间上下文"""
        return {
            'season': time_context.get('season', '未知'),
            'time_of_day': time_context.get('time_of_day', '未知'),
            'day_of_week': time_context.get('day_of_week', '未知'),
            'weather_impact': time_context.get('weather', '正常')
        }

    def _extract_decision_context(self, context: NPCContext) -> Dict[str, Any]:
        """提取决策相关上下文"""
        # 推断社交偏好（简化处理）
        social_preference = '中性'
        if isinstance(context.personality, list):
            if '沉默寡言' in context.personality:
                social_preference = '内向'
            elif '八卦' in context.personality or '善于倾听' in context.personality:
                social_preference = '外向'
        elif isinstance(context.personality, dict):
            social_preference = context.personality.get('social_preference', '中性')

        return {
            'available_actions': self._get_available_actions(context),
            'current_priorities': self._calculate_priorities(context),
            'social_context': social_preference
        }

    def _extract_personality_core(self, personality) -> Dict[str, str]:
        """提取性格核心特征"""
        if isinstance(personality, list):
            # 如果是列表格式，直接返回前3个特征
            core_traits = {}
            for trait in personality[:3]:  # 只取前3个
                core_traits[trait] = '显著'
            return core_traits
        elif isinstance(personality, dict):
            # 如果是字典格式，按数值处理
            core_traits = {}
            for trait, value in personality.items():
                if isinstance(value, (int, float)):
                    if value > 0.7:
                        core_traits[trait] = '高'
                    elif value < 0.3:
                        core_traits[trait] = '低'
                    else:
                        core_traits[trait] = '中'
            return core_traits
        else:
            return {'性格': '未知'}

    def _summarize_background(self, background: str, max_words: int) -> str:
        """生成背景摘要"""
        words = background.split()
        if len(words) <= max_words:
            return background
        return ' '.join(words[:max_words]) + '...'

    def _generate_combined_summary(self, memory_texts: List[str]) -> str:
        """生成记忆组合摘要"""
        if len(memory_texts) <= 2:
            return '; '.join(memory_texts)

        # 简单模式识别和合并
        patterns = self._identify_patterns(memory_texts)
        if patterns:
            return f"主要模式: {patterns[0]}; 其他事件: {len(memory_texts)-1}项"

        return f"近期经历{len(memory_texts)}项，主要涉及{'、'.join([t[:10]+'...' for t in memory_texts[:2]])}"

    def _summarize_memory(self, memory: MemoryEntry) -> str:
        """生成单个记忆摘要"""
        if memory.summary:
            return memory.summary

        content = memory.content
        if len(content) > 30:
            content = content[:27] + '...'

        return f"{memory.timestamp.strftime('%m-%d %H:%M')}: {content}"

    def _extract_emotional_pattern(self, memories: List[MemoryEntry]) -> str:
        """提取情绪模式"""
        emotions = [m.emotional_impact for m in memories]
        avg_emotion = sum(emotions) / len(emotions) if emotions else 0

        if avg_emotion > 2:
            return '积极'
        elif avg_emotion < -2:
            return '消极'
        else:
            return '中性'

    def _get_available_actions(self, context: NPCContext) -> List[str]:
        """获取可用行动"""
        base_actions = ['继续当前活动', '切换活动', '休息', '社交', '工作']

        # 根据时间和职业添加特定行动
        time_actions = []
        if context.time_context.get('time_of_day') in ['早晨', '上午']:
            time_actions.extend(['准备工作', '早餐'])

        profession_actions = []
        if context.profession == '铁匠':
            profession_actions.extend(['锻造', '修理工具', '购买材料'])

        return base_actions + time_actions + profession_actions

    def _calculate_priorities(self, context: NPCContext) -> List[str]:
        """计算当前优先级"""
        priorities = []

        # 需求驱动的优先级
        if context.current_needs.get('hunger', 0) > 0.7:
            priorities.append('满足饥饿')
        if context.current_needs.get('fatigue', 0) > 0.8:
            priorities.append('休息恢复')

        # 任务驱动的优先级
        if context.current_task:
            priorities.append(f"完成任务: {context.current_task.get('description', '')[:20]}")

        # 时间驱动的优先级
        hour = context.time_context.get('hour', 12)
        if 9 <= hour <= 17:
            priorities.append('工作时间')

        return priorities[:3]  # 最多3个优先级

    def _identify_patterns(self, texts: List[str]) -> List[str]:
        """识别记忆模式"""
        patterns = []

        # 简单关键词模式识别
        work_keywords = ['工作', '锻造', '修理', '工具']
        social_keywords = ['对话', '见面', '朋友', '喝酒']
        rest_keywords = ['休息', '睡觉', '疲惫']

        for text in texts:
            lower_text = text.lower()
            if any(kw in lower_text for kw in work_keywords):
                if '工作' not in patterns:
                    patterns.append('工作')
            if any(kw in lower_text for kw in social_keywords):
                if '社交' not in patterns:
                    patterns.append('社交')
            if any(kw in lower_text for kw in rest_keywords):
                if '休息' not in patterns:
                    patterns.append('休息')

        return patterns

    def _adjust_for_token_limit(self, compressed: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """根据token限制调整压缩内容"""
        # 粗略估算token数 (中文大约1:1.2)
        estimated_tokens = self._estimate_tokens(compressed)

        if estimated_tokens <= max_tokens:
            return compressed

        # 逐步压缩
        if 'memory_summary' in compressed:
            compressed['memory_summary']['key_events'] = compressed['memory_summary']['key_events'][:1]

        if estimated_tokens > max_tokens * 1.5:
            # 深度压缩
            compressed['memory_summary'] = {'summary': compressed['memory_summary']['summary']}

        return compressed

    def _estimate_tokens(self, data: Dict[str, Any]) -> int:
        """粗略估算token数量"""
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        # 中文字符算1.2个token，英文算1个
        chinese_chars = sum(1 for c in json_str if '\u4e00' <= c <= '\u9fff')
        total_chars = len(json_str)
        return int(chinese_chars * 1.2 + (total_chars - chinese_chars) * 0.3)

    def _generate_cache_key(self, context: NPCContext) -> str:
        """生成缓存键"""
        key_data = {
            'name': context.name,
            'activity': context.current_activity,
            'emotion': context.current_emotion,
            'task': context.current_task.get('id') if context.current_task else None,
            'memory_count': len(context.recent_memories)
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()


class VectorMemorySystem:
    """向量记忆系统 - 支持语义搜索和长期记忆"""

    def __init__(self):
        self.memories: Dict[str, MemoryEntry] = {}
        self.vector_index = {}  # memory_id -> vector
        self.semantic_index = {}  # 语义标签 -> memory_ids
        self.importance_index = {}  # 重要性分层
        self.temporal_index = {}  # 时间索引

        # 简单的向量生成 (实际应用中应该使用专业的embedding模型)
        self.embedding_dim = 128

    def add_memory(self, content: str, memory_type: MemoryType,
                  importance: float, emotional_impact: float,
                  tags: List[str], context: Dict[str, Any]) -> str:
        """添加新记忆"""
        memory_id = self._generate_memory_id()

        # 生成向量嵌入 (简化版本)
        vector = self._generate_embedding(content)

        memory = MemoryEntry(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            emotional_impact=emotional_impact,
            timestamp=datetime.now(),
            tags=tags,
            context=context,
            vector_embedding=vector
        )

        # 存储记忆
        self.memories[memory_id] = memory
        self.vector_index[memory_id] = vector

        # 更新索引
        self._update_indexes(memory)

        # 触发自主维护
        self._autonomous_maintenance()

        return memory_id

    def retrieve_relevant_memories(self, query: str, context: Dict[str, Any],
                                 top_k: int = 5, max_age_days: int = 30) -> List[MemoryEntry]:
        """检索相关记忆"""
        query_vector = self._generate_embedding(query)

        # 获取候选记忆
        candidates = self._get_candidate_memories(query_vector, context, max_age_days)

        # 计算相似度并排序
        scored_candidates = []
        for memory_id in candidates:
            memory = self.memories[memory_id]
            similarity = self._calculate_similarity(query_vector, memory.vector_embedding)

            # 考虑其他因素
            recency_score = self._calculate_recency_score(memory.timestamp)
            importance_score = memory.importance / 10.0
            context_relevance = self._calculate_context_relevance(memory, context)

            # 综合评分
            total_score = (
                similarity * 0.4 +
                recency_score * 0.2 +
                importance_score * 0.2 +
                context_relevance * 0.2
            )

            scored_candidates.append((memory, total_score))

        # 排序并返回
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, score in scored_candidates[:top_k]]

    def get_memory_summary(self, memory_type: Optional[MemoryType] = None,
                          time_range: Optional[Tuple[datetime, datetime]] = None) -> Dict[str, Any]:
        """获取记忆摘要"""
        target_memories = self._filter_memories(memory_type, time_range)

        if not target_memories:
            return {'count': 0, 'summary': '无相关记忆'}

        # 分析模式
        patterns = self._analyze_patterns(target_memories)
        emotional_trends = self._analyze_emotional_trends(target_memories)
        key_events = self._extract_key_events(target_memories)

        return {
            'count': len(target_memories),
            'patterns': patterns,
            'emotional_trends': emotional_trends,
            'key_events': key_events,
            'time_span': self._calculate_time_span(target_memories)
        }

    def compress_old_memories(self, days_threshold: int = 7):
        """压缩旧记忆"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        old_memories = [m for m in self.memories.values() if m.timestamp < cutoff_date]

        for memory in old_memories:
            if memory.importance < 5:  # 低重要性记忆
                # 生成摘要并压缩
                memory.summary = self._generate_memory_summary(memory)
                memory.content = memory.summary  # 替换原始内容

    def _generate_embedding(self, text: str) -> List[float]:
        """生成向量嵌入 (简化实现)"""
        # 实际应用中应该使用专业的embedding模型如text2vec, bge等
        # 这里使用简单的hash-based方法作为占位符
        hash_obj = hashlib.md5(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()

        # 将hash转换为固定维度的向量
        vector = []
        for i in range(self.embedding_dim):
            # 使用hash字节生成伪随机向量
            value = (hash_bytes[i % len(hash_bytes)] - 128) / 128.0  # 归一化到[-1, 1]
            vector.append(value)

        # L2归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _calculate_recency_score(self, timestamp: datetime) -> float:
        """计算时效性评分"""
        days_since = (datetime.now() - timestamp).days
        # 指数衰减
        return max(0.1, np.exp(-days_since / 30.0))  # 30天半衰期

    def _calculate_context_relevance(self, memory: MemoryEntry, current_context: Dict[str, Any]) -> float:
        """计算上下文相关性"""
        relevance = 0.0

        # 活动相关性
        if current_context.get('activity') in memory.tags:
            relevance += 0.3

        # 情绪相关性
        if current_context.get('emotion') == memory.context.get('emotion'):
            relevance += 0.2

        # 时间相关性
        current_hour = current_context.get('hour', 12)
        memory_hour = memory.timestamp.hour
        if abs(current_hour - memory_hour) <= 2:
            relevance += 0.1

        return min(1.0, relevance)

    def _get_candidate_memories(self, query_vector: List[float],
                              context: Dict[str, Any], max_age_days: int) -> List[str]:
        """获取候选记忆"""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        candidates = []
        for memory_id, memory in self.memories.items():
            if memory.timestamp >= cutoff_date:
                # 基础相似度筛选
                similarity = self._calculate_similarity(query_vector, memory.vector_embedding)
                if similarity > 0.3:  # 相似度阈值
                    candidates.append(memory_id)

        return candidates

    def _update_indexes(self, memory: MemoryEntry):
        """更新索引"""
        # 语义索引
        for tag in memory.tags:
            if tag not in self.semantic_index:
                self.semantic_index[tag] = []
            self.semantic_index[tag].append(memory.id)

        # 重要性索引
        importance_level = int(memory.importance // 2)  # 0-5层
        if importance_level not in self.importance_index:
            self.importance_index[importance_level] = []
        self.importance_index[importance_level].append(memory.id)

        # 时间索引
        date_key = memory.timestamp.date().isoformat()
        if date_key not in self.temporal_index:
            self.temporal_index[date_key] = []
        self.temporal_index[date_key].append(memory.id)

    def _autonomous_maintenance(self):
        """自主维护"""
        # 定期压缩旧记忆
        if len(self.memories) > 1000:  # 阈值
            self.compress_old_memories()

        # 清理低质量记忆
        self._cleanup_low_quality_memories()

    def _cleanup_low_quality_memories(self):
        """清理低质量记忆"""
        to_remove = []
        for memory_id, memory in self.memories.items():
            # 删除标准：低重要性 + 很少访问 + 超过90天
            age_days = (datetime.now() - memory.timestamp).days
            if (memory.importance < 3 and
                memory.access_count < 2 and
                age_days > 90):
                to_remove.append(memory_id)

        for memory_id in to_remove:
            del self.memories[memory_id]
            if memory_id in self.vector_index:
                del self.vector_index[memory_id]

    def _generate_memory_id(self) -> str:
        """生成记忆ID"""
        return f"mem_{int(time.time() * 1000000)}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

    def _filter_memories(self, memory_type: Optional[MemoryType],
                        time_range: Optional[Tuple[datetime, datetime]]) -> List[MemoryEntry]:
        """过滤记忆"""
        memories = list(self.memories.values())

        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]

        if time_range:
            start_date, end_date = time_range
            memories = [m for m in memories if start_date <= m.timestamp <= end_date]

        return memories

    def _analyze_patterns(self, memories: List[MemoryEntry]) -> List[str]:
        """分析记忆模式"""
        patterns = []
        tag_counts = {}

        # 统计标签频率
        for memory in memories:
            for tag in memory.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # 提取高频标签作为模式
        for tag, count in tag_counts.items():
            if count >= len(memories) * 0.3:  # 30%以上
                patterns.append(tag)

        return patterns

    def _analyze_emotional_trends(self, memories: List[MemoryEntry]) -> str:
        """分析情绪趋势"""
        emotions = [m.emotional_impact for m in memories]
        if not emotions:
            return '无明显趋势'

        avg_emotion = sum(emotions) / len(emotions)
        trend = '上升' if avg_emotion > 1 else '下降' if avg_emotion < -1 else '稳定'

        intensity = '强烈' if abs(avg_emotion) > 3 else '温和' if abs(avg_emotion) > 1 else '微弱'

        return f'{intensity}{trend}'

    def _extract_key_events(self, memories: List[MemoryEntry]) -> List[str]:
        """提取关键事件"""
        # 按重要性排序
        sorted_memories = sorted(memories, key=lambda m: m.importance, reverse=True)
        return [m.content for m in sorted_memories[:3]]

    def _calculate_time_span(self, memories: List[MemoryEntry]) -> str:
        """计算时间跨度"""
        if not memories:
            return '无'

        timestamps = [m.timestamp for m in memories]
        min_time = min(timestamps)
        max_time = max(timestamps)
        days = (max_time - min_time).days

        if days < 1:
            return '今天'
        elif days < 7:
            return f'{days}天'
        elif days < 30:
            return f'{days // 7}周'
        else:
            return f'{days // 30}个月'

    def _generate_memory_summary(self, memory: MemoryEntry) -> str:
        """生成记忆摘要"""
        # 简化摘要生成
        content = memory.content
        if len(content) > 50:
            content = content[:47] + '...'

        return f"{memory.timestamp.strftime('%m-%d')}: {content} (重要性:{memory.importance})"


class OptimizedLLMClient:
    """优化后的LLM客户端 - 结合所有优化策略"""

    def __init__(self, deepseek_client):
        self.deepseek_client = deepseek_client
        self.context_compressor = ContextCompressor()
        self.memory_system = VectorMemorySystem()
        self.decision_cache = {}  # 决策缓存
        self.prompt_templates = self._load_prompt_templates()

    def make_decision(self, npc_context: NPCContext, available_actions: List[str],
                     situation: str) -> Dict[str, Any]:
        """
        智能决策 - 结合压缩上下文、记忆检索和工具化决策
        """
        # 1. 压缩上下文
        compressed_context = self.context_compressor.compress_context(npc_context)

        # 2. 检索相关记忆
        relevant_memories = self.memory_system.retrieve_relevant_memories(
            situation, compressed_context, top_k=3
        )

        # 3. 获取记忆摘要
        memory_summary = self.memory_system.get_memory_summary()

        # 4. 检查缓存
        cache_key = self._generate_decision_cache_key(compressed_context, situation)
        if cache_key in self.decision_cache:
            return self.decision_cache[cache_key]

        # 5. 构建优化prompt
        prompt = self._build_decision_prompt(
            compressed_context,
            relevant_memories,
            memory_summary,
            available_actions,
            situation
        )

        # 6. 调用LLM
        response = self.deepseek_client.generate_response(prompt, max_tokens=500)

        # 7. 解析和结构化响应
        decision = self._parse_decision_response(response)

        # 8. 缓存结果
        self.decision_cache[cache_key] = decision

        # 9. 记录到记忆系统
        self._record_decision_to_memory(decision, situation, npc_context)

        return decision

    def _build_decision_prompt(self, compressed_context: Dict[str, Any],
                              relevant_memories: List[MemoryEntry],
                              memory_summary: Dict[str, Any],
                              available_actions: List[str],
                              situation: str) -> str:
        """构建优化的决策prompt"""

        # 身份和性格描述
        identity_section = self.prompt_templates['identity'].format(
            name=compressed_context['identity']['name'],
            profession=compressed_context['identity']['profession'],
            personality=json.dumps(compressed_context['identity']['personality_core'], ensure_ascii=False),
            background=compressed_context['identity']['background_key']
        )

        # 当前状态
        state_section = self.prompt_templates['current_state'].format(
            activity=compressed_context['current_state']['activity'],
            emotion=compressed_context['current_state']['emotion'],
            critical_needs=json.dumps(compressed_context['current_state']['critical_needs'], ensure_ascii=False),
            task_focus=compressed_context['current_state']['task_focus'] or '无'
        )

        # 记忆上下文
        memory_section = self.prompt_templates['memory_context'].format(
            memory_summary=json.dumps(memory_summary, ensure_ascii=False),
            relevant_memories=self._format_memories(relevant_memories)
        )

        # 时间和环境
        time_section = self.prompt_templates['time_context'].format(
            season=compressed_context['time_context']['season'],
            time_of_day=compressed_context['time_context']['time_of_day'],
            weather=compressed_context['time_context']['weather_impact']
        )

        # 决策指导
        decision_section = self.prompt_templates['decision_guidance'].format(
            available_actions=json.dumps(available_actions, ensure_ascii=False),
            situation=situation,
            priorities=json.dumps(compressed_context['decision_context']['current_priorities'], ensure_ascii=False)
        )

        # 组合完整prompt
        full_prompt = self.prompt_templates['full_structure'].format(
            identity=identity_section,
            state=state_section,
            memory=memory_section,
            time=time_section,
            decision=decision_section
        )

        return full_prompt

    def _parse_decision_response(self, response: str) -> Dict[str, Any]:
        """解析LLM决策响应"""
        try:
            # 尝试解析JSON格式响应
            decision = json.loads(response)
        except json.JSONDecodeError:
            # 回退到文本解析
            decision = self._parse_text_decision(response)

        # 标准化决策格式
        return self._standardize_decision(decision)

    def _parse_text_decision(self, response: str) -> Dict[str, Any]:
        """从文本中解析决策"""
        decision = {
            'action': '保持现状',
            'reasoning': response,
            'confidence': 0.5,
            'expected_outcome': '未知'
        }

        # 简单关键词提取
        lower_response = response.lower()

        if '休息' in lower_response or '睡觉' in lower_response:
            decision['action'] = '休息'
        elif '工作' in lower_response or '锻造' in lower_response:
            decision['action'] = '工作'
        elif '社交' in lower_response or '对话' in lower_response:
            decision['action'] = '社交'

        return decision

    def _standardize_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """标准化决策格式"""
        standard_decision = {
            'action': decision.get('action', '保持现状'),
            'reasoning': decision.get('reasoning', '基于当前情况的合理决策'),
            'confidence': min(1.0, max(0.0, decision.get('confidence', 0.5))),
            'expected_outcome': decision.get('expected_outcome', '情况可能改善'),
            'emotional_impact': decision.get('emotional_impact', 0),
            'time_commitment': decision.get('time_commitment', 1),  # 小时
            'tool_calls': decision.get('tool_calls', [])
        }

        return standard_decision

    def _record_decision_to_memory(self, decision: Dict[str, Any],
                                  situation: str, npc_context: NPCContext):
        """将决策记录到记忆系统"""
        content = f"面对'{situation}'时决定：{decision['action']}。理由：{decision['reasoning']}"

        # 确定记忆类型
        memory_type = MemoryType.EPISODIC

        # 计算重要性 (基于信心度和结果预期)
        importance = (decision['confidence'] * 7) + 3  # 3-10范围

        # 情绪影响
        emotional_impact = decision.get('emotional_impact', 0)

        # 标签
        tags = [decision['action'], npc_context.current_activity, npc_context.profession]

        # 上下文
        context = {
            'situation': situation,
            'emotion': npc_context.current_emotion,
            'time': npc_context.time_context,
            'decision_type': 'autonomous'
        }

        # 添加到记忆系统
        self.memory_system.add_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            emotional_impact=emotional_impact,
            tags=tags,
            context=context
        )

    def _load_prompt_templates(self) -> Dict[str, str]:
        """加载prompt模板"""
        return {
            'identity': """
你是{profession} {name}。

性格特征：{personality}

背景简介：{background}
""",

            'current_state': """
当前状态：
- 活动：{activity}
- 情绪：{emotion}
- 紧急需求：{critical_needs}
- 任务焦点：{task_focus}
""",

            'memory_context': """
记忆摘要：{memory_summary}

相关回忆：
{relevant_memories}
""",

            'time_context': """
环境信息：
- 季节：{season}
- 时间段：{time_of_day}
- 天气影响：{weather}
""",

            'decision_guidance': """
当前情况：{situation}

可用行动：{available_actions}

当前优先级：{priorities}

请基于你的性格、当前状态和记忆历史，做出最合适的决策。
要求：
1. 决策要符合你的性格和职业背景
2. 考虑当前需求和时间因素
3. 参考过去的类似经历
4. 提供具体的行动和理由
5. 评估预期的结果和情绪影响

请以JSON格式回复：
{{
    "action": "行动名称",
    "reasoning": "决策理由",
    "confidence": 0.0-1.0,
    "expected_outcome": "预期结果",
    "emotional_impact": -10到10,
    "time_commitment": 预估小时数
}}
""",

            'full_structure': """
{identity}

{state}

{memory}

{time}

{decision}
"""
        }

    def _format_memories(self, memories: List[MemoryEntry]) -> str:
        """格式化记忆列表"""
        if not memories:
            return "无相关记忆"

        formatted = []
        for memory in memories:
            formatted.append(f"- {memory.content} (重要性:{memory.importance})")

        return "\n".join(formatted)

    def _generate_decision_cache_key(self, compressed_context: Dict[str, Any], situation: str) -> str:
        """生成决策缓存键"""
        key_data = {
            'identity': compressed_context['identity'],
            'state': compressed_context['current_state'],
            'situation': situation[:100]  # 限制长度
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()


# 工具定义装饰器
def tool(description: str):
    """工具装饰器"""
    def decorator(func):
        func.is_tool = True
        func.description = description
        return func
    return decorator


class NPCActionTools:
    """NPC行动工具集"""

    def __init__(self, npc_system):
        self.npc_system = npc_system
        self.tools = self._collect_tools()

    def _collect_tools(self) -> Dict[str, callable]:
        """收集所有工具"""
        tools = {}
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, 'is_tool'):
                tools[attr_name] = attr
        return tools

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        if tool_name not in self.tools:
            return {'success': False, 'error': f'未知工具: {tool_name}'}

        try:
            tool_func = self.tools[tool_name]
            result = tool_func(**kwargs)
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @tool("切换NPC活动状态")
    def switch_activity(self, new_activity: str, reason: str) -> Dict[str, Any]:
        """切换活动"""
        # 验证活动转换的合理性
        current_activity = self.npc_system.current_activity

        if not self._is_valid_transition(current_activity, new_activity):
            return {
                'success': False,
                'reason': f'从{current_activity}切换到{new_activity}不合理'
            }

        # 执行切换
        old_activity = current_activity
        self.npc_system.current_activity = new_activity

        # 记录状态变化
        self.npc_system.persistence.record_event({
            'type': 'activity_change',
            'old_activity': old_activity,
            'new_activity': new_activity,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })

        return {
            'success': True,
            'old_activity': old_activity,
            'new_activity': new_activity,
            'reason': reason
        }

    @tool("更新任务进度")
    def update_task_progress(self, task_id: str, progress_delta: float, reason: str) -> Dict[str, Any]:
        """更新任务进度"""
        task = self.npc_system.persistence.get_task(task_id)
        if not task:
            return {'success': False, 'reason': f'任务不存在: {task_id}'}

        old_progress = task.progress
        new_progress = min(1.0, max(0.0, old_progress + progress_delta))

        # 更新任务
        task.progress = new_progress
        task.last_updated = datetime.now().isoformat()
        self.npc_system.persistence.update_task(task)

        # 检查任务完成
        if new_progress >= 1.0:
            self.npc_system.persistence.record_event({
                'type': 'task_completed',
                'task_id': task_id,
                'completion_time': datetime.now().isoformat()
            })

        return {
            'success': True,
            'task_id': task_id,
            'old_progress': old_progress,
            'new_progress': new_progress,
            'completed': new_progress >= 1.0,
            'reason': reason
        }

    @tool("更新NPC情绪状态")
    def update_emotion(self, new_emotion: str, intensity: float, trigger: str) -> Dict[str, Any]:
        """更新情绪状态"""
        valid_emotions = ['平静', '开心', '愤怒', '悲伤', '焦虑', '兴奋', '疲惫']

        if new_emotion not in valid_emotions:
            return {'success': False, 'reason': f'无效情绪: {new_emotion}'}

        old_emotion = self.npc_system.current_emotion
        self.npc_system.current_emotion = new_emotion

        # 记录情绪变化
        self.npc_system.persistence.record_event({
            'type': 'emotion_change',
            'old_emotion': old_emotion,
            'new_emotion': new_emotion,
            'intensity': intensity,
            'trigger': trigger,
            'timestamp': datetime.now().isoformat()
        })

        return {
            'success': True,
            'old_emotion': old_emotion,
            'new_emotion': new_emotion,
            'intensity': intensity,
            'trigger': trigger
        }

    @tool("添加新记忆")
    def add_memory(self, content: str, importance: int, tags: List[str]) -> Dict[str, Any]:
        """添加记忆"""
        memory_id = self.npc_system.optimized_llm.memory_system.add_memory(
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=min(10, max(0, importance)),
            emotional_impact=0,  # 可以后续更新
            tags=tags,
            context={
                'activity': self.npc_system.current_activity,
                'emotion': self.npc_system.current_emotion,
                'time': self.npc_system.world_clock.current_time.isoformat()
            }
        )

        return {
            'success': True,
            'memory_id': memory_id,
            'content': content,
            'importance': importance
        }

    def _is_valid_transition(self, old_activity: str, new_activity: str) -> bool:
        """验证活动转换的合理性"""
        # 简单的转换规则
        invalid_transitions = [
            ('睡觉', '锻造'),  # 睡觉不能直接锻造
            ('锻造', '睡觉'),  # 锻造后不能直接睡觉
        ]

        for invalid in invalid_transitions:
            if old_activity == invalid[0] and new_activity == invalid[1]:
                return False

        return True
