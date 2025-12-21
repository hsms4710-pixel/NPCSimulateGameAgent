"""
NPC系统优化模块
包含上下文压缩、行为决策树、记忆管理等优化功能
"""

from .context_compressor import ContextCompressor
from .behavior_decision_tree import BehaviorDecisionTree
from .prompt_templates import PromptTemplates
from .memory_manager import MemoryManager, MemorySummarizer, Episode, CompressedMemory
from .react_tools import NPCToolRegistry, ReActAgent, NPCActionTool
from .rag_memory import RAGMemorySystem, SimpleVectorStore

__all__ = [
    'ContextCompressor',
    'BehaviorDecisionTree',
    'PromptTemplates',
    'MemoryManager',
    'MemorySummarizer',
    'Episode',
    'CompressedMemory',
    'NPCToolRegistry',
    'ReActAgent',
    'NPCActionTool',
    'RAGMemorySystem',
    'SimpleVectorStore'
]
