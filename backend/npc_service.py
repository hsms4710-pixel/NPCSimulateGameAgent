"""
NPC 服务层
封装 NPC 系统的业务逻辑，提供给 API 层使用
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import threading
from collections import deque

from backend.log_manager import LogManager, LogLevel, ModelOutputTracker


class NPCService:
    """
    NPC 服务层

    职责：
    1. 管理 NPC 系统实例
    2. 处理 API 配置
    3. 封装业务逻辑
    4. 追踪模型输出和 Token 统计
    """

    def __init__(self, log_manager: LogManager):
        self.log_manager = log_manager
        self.logger = log_manager.get_logger("npc_service")
        self.model_tracker = ModelOutputTracker(log_manager)

        # NPC 系统
        self.npc_system = None
        self.llm_client = None
        self.world_clock = None

        # API 配置
        self.api_config = self._load_api_config()

        # Token 统计
        self.token_stats = {
            "total_sent": 0,
            "total_received": 0,
            "api_calls": 0,
            "session_start": datetime.now().isoformat()
        }

        # 模型输出缓存
        self.model_outputs: deque = deque(maxlen=100)

        # 自主模式状态
        self._autonomous_mode = False

        # 初始化
        self._initialize()

    def _load_api_config(self) -> Dict[str, Any]:
        """加载 API 配置"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "api_config.json"
        )

        default_config = {
            "provider": "deepseek",
            "api_key": "",
            "api_base": "https://api.deepseek.com/v1",
            "model": "deepseek-chat"
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.logger.info("API 配置加载成功")
                    return {**default_config, **config}
        except Exception as e:
            self.logger.error(f"加载 API 配置失败: {e}")

        return default_config

    def _save_api_config(self):
        """保存 API 配置"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "api_config.json"
        )

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.api_config, f, ensure_ascii=False, indent=2)
            self.logger.info("API 配置已保存")
        except Exception as e:
            self.logger.error(f"保存 API 配置失败: {e}")

    def _initialize(self):
        """初始化 NPC 系统"""
        try:
            # 导入必要模块
            from world_simulator.world_clock import get_world_clock
            from backend.deepseek_client import DeepSeekClient
            from world_simulator.world_lore import NPC_TEMPLATES

            self.world_clock = get_world_clock()

            # 初始化 LLM 客户端
            if self.api_config.get("api_key"):
                self.llm_client = DeepSeekClient(
                    api_key=self.api_config["api_key"],
                    model=self.api_config.get("model", "deepseek-chat")
                )

                # 包装 LLM 调用以追踪输出
                self._wrap_llm_calls()

                self.logger.info(f"LLM 客户端初始化成功，模型: {self.api_config.get('model')}")
            else:
                self.logger.warning("API Key 未配置，LLM 功能不可用")

            # 存储 NPC 模板
            self.npc_templates = NPC_TEMPLATES

            self.logger.info("NPC 服务初始化完成")

        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            raise

    def _wrap_llm_calls(self):
        """包装 LLM 调用方法以追踪输出"""
        if not self.llm_client:
            return

        original_generate = self.llm_client.generate_response
        original_call_model = self.llm_client.call_model

        def wrapped_generate(*args, **kwargs):
            import time
            start = time.time()

            prompt = args[0] if args else kwargs.get("prompt", "")
            result = original_generate(*args, **kwargs)

            latency = (time.time() - start) * 1000

            # 记录模型输出
            self.log_manager.log_model_output(
                source="DeepSeekClient.generate_response",
                prompt=str(prompt)[:500],
                response=str(result)[:1000],
                latency_ms=latency
            )

            # 更新统计
            self._update_token_stats(prompt, result)

            return result

        def wrapped_call_model(*args, **kwargs):
            import time
            start = time.time()

            messages = kwargs.get("messages", args[0] if args else [])
            prompt = str(messages[-1].get("content", "")) if messages else ""

            result = original_call_model(*args, **kwargs)

            latency = (time.time() - start) * 1000

            # 记录模型输出
            self.log_manager.log_model_output(
                source="DeepSeekClient.call_model",
                prompt=prompt[:500],
                response=str(result)[:1000],
                latency_ms=latency
            )

            # 更新统计
            self._update_token_stats(prompt, result)

            return result

        self.llm_client.generate_response = wrapped_generate
        self.llm_client.call_model = wrapped_call_model

    def _update_token_stats(self, prompt: str, response: str):
        """更新 Token 统计（估算）"""
        # 简单估算：中文约 2 字符 = 1 token，英文约 4 字符 = 1 token
        def estimate_tokens(text: str) -> int:
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 2 + other_chars / 4)

        self.token_stats["total_sent"] += estimate_tokens(str(prompt))
        self.token_stats["total_received"] += estimate_tokens(str(response))
        self.token_stats["api_calls"] += 1

    def is_initialized(self) -> bool:
        """检查 NPC 是否已初始化"""
        return self.npc_system is not None

    def get_current_npc_name(self) -> Optional[str]:
        """获取当前 NPC 名称"""
        if self.npc_system:
            return self.npc_system.npc_name
        return None

    def get_api_config(self) -> Dict[str, Any]:
        """获取 API 配置"""
        return self.api_config.copy()

    def update_api_config(self, config: Dict[str, Any]) -> bool:
        """更新 API 配置"""
        try:
            self.api_config.update(config)
            self._save_api_config()

            # 重新初始化 LLM 客户端
            if config.get("api_key"):
                from backend.deepseek_client import DeepSeekClient
                self.llm_client = DeepSeekClient(
                    api_key=config["api_key"],
                    model=config.get("model", "deepseek-chat")
                )
                self._wrap_llm_calls()
                self.logger.info("LLM 客户端已重新初始化")

            return True
        except Exception as e:
            self.logger.error(f"更新 API 配置失败: {e}")
            return False

    def test_api_connection(self) -> Dict[str, Any]:
        """测试 API 连接"""
        if not self.llm_client:
            return {"success": False, "error": "LLM 客户端未初始化"}

        try:
            response = self.llm_client.generate_response(
                "你好，请回复'连接成功'",
                temperature=0.1,
                max_tokens=20
            )

            success = "连接成功" in response or "成功" in response or len(response) > 0
            return {
                "success": success,
                "response": response,
                "model": self.api_config.get("model")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_available_npcs(self) -> List[Dict[str, Any]]:
        """获取可用的 NPC 列表"""
        npcs = []
        for name, config in self.npc_templates.items():
            npcs.append({
                "name": name,
                "profession": config.get("profession", "未知"),
                "description": config.get("background", "")[:100] + "..."
            })
        return npcs

    def select_npc(self, npc_name: str) -> bool:
        """选择/切换 NPC"""
        try:
            if npc_name not in self.npc_templates:
                self.logger.error(f"NPC 不存在: {npc_name}")
                return False

            if not self.llm_client:
                self.logger.error("LLM 客户端未初始化")
                return False

            from npc_core import NPCBehaviorSystem

            npc_config = self.npc_templates[npc_name]
            self.npc_system = NPCBehaviorSystem(npc_config, self.llm_client)

            self.logger.info(f"NPC 已切换: {npc_name}")
            return True

        except Exception as e:
            self.logger.error(f"选择 NPC 失败: {e}")
            return False

    def get_npc_status(self) -> Dict[str, Any]:
        """获取当前 NPC 状态"""
        if not self.npc_system:
            return {}

        try:
            status = self.npc_system.get_status_summary()

            # 添加额外信息
            status["world_time"] = self.get_world_time()

            return status
        except Exception as e:
            self.logger.error(f"获取 NPC 状态失败: {e}")
            return {"error": str(e)}

    def get_recent_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        if not self.npc_system:
            return []

        try:
            memories = []
            # 从持久化存储获取记忆
            for memory in list(self.npc_system.persistence.memories.values())[-limit:]:
                memories.append({
                    "content": memory.content,
                    "importance": memory.importance,
                    "emotional_impact": memory.emotional_impact,
                    "timestamp": memory.timestamp if isinstance(memory.timestamp, str) else memory.timestamp.isoformat(),
                    "tags": memory.tags
                })
            return memories
        except Exception as e:
            self.logger.error(f"获取记忆失败: {e}")
            return []

    def get_goals(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取 NPC 目标"""
        if not self.npc_system:
            return {"short_term": [], "long_term": []}

        try:
            short_term = []
            long_term = []

            for goal in self.npc_system.short_term_goals:
                short_term.append({
                    "description": goal.description,
                    "priority": goal.priority,
                    "progress": goal.progress,
                    "status": goal.status
                })

            for goal in self.npc_system.long_term_goals:
                long_term.append({
                    "description": goal.description,
                    "priority": goal.priority,
                    "progress": goal.progress,
                    "status": goal.status
                })

            return {"short_term": short_term, "long_term": long_term}
        except Exception as e:
            self.logger.error(f"获取目标失败: {e}")
            return {"short_term": [], "long_term": []}

    def get_relationships(self) -> List[Dict[str, Any]]:
        """获取 NPC 关系"""
        if not self.npc_system:
            return []

        try:
            relationships = []
            for rel in self.npc_system.persistence.relationships.values():
                relationships.append({
                    "npc_name": rel.npc_name,
                    "affection": rel.affection,
                    "trust": rel.trust,
                    "relationship_type": rel.relationship_type,
                    "interactions_count": rel.interactions_count
                })
            return relationships
        except Exception as e:
            self.logger.error(f"获取关系失败: {e}")
            return []

    def process_event(self, content: str, event_type: str,
                       event_location: str = None) -> Dict[str, Any]:
        """处理事件

        Args:
            content: 事件内容
            event_type: 事件类型
            event_location: 事件发生位置（用于触发NPC移动）
        """
        if not self.npc_system:
            return {"error": "NPC 未初始化"}

        try:
            self.logger.info(f"处理事件 [{event_type}] @{event_location}: {content[:50]}...")

            result = self.npc_system.process_event(
                event_content=content,
                event_type=event_type,
                event_location=event_location
            )

            self.logger.info(f"事件处理完成，决策级别: {result.get('decision_level')}, "
                           f"移动触发: {result.get('movement_triggered', False)}")

            return result
        except Exception as e:
            self.logger.error(f"事件处理失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def send_dialogue(self, message: str) -> Dict[str, Any]:
        """发送对话"""
        if not self.npc_system:
            return {"error": "NPC 未初始化"}

        try:
            self.logger.info(f"对话输入: {message[:50]}...")

            # 使用 process_event 处理对话
            result = self.npc_system.process_event(message, "dialogue")

            response = result.get("response_text", "")

            self.logger.info(f"NPC 回复: {response[:50]}...")

            return {
                "response": response,
                "decision_level": result.get("decision_level"),
                "state_changed": result.get("state_changed", False)
            }
        except Exception as e:
            self.logger.error(f"对话处理失败: {e}")
            return {"error": str(e)}

    def get_world_time(self) -> Dict[str, Any]:
        """获取世界时间"""
        if not self.world_clock:
            return {}

        return {
            "current_time": self.world_clock.current_time.strftime("%Y年%m月%d日 %H:%M"),
            "hour": self.world_clock.current_time.hour,
            "day": self.world_clock.current_time.day,
            "is_running": self.world_clock.is_running
        }

    def advance_time(self, hours: float) -> Dict[str, Any]:
        """推进时间"""
        if not self.npc_system or not self.world_clock:
            return {"error": "系统未初始化"}

        try:
            self.world_clock.advance_time(hours=hours)

            # 通知 NPC 系统时间变化
            self.npc_system.update_time(self.world_clock.current_time)

            activity = self.npc_system._get_activity_value()

            self.logger.info(f"时间推进 {hours} 小时，当前活动: {activity}")

            return {
                "current_time": self.world_clock.current_time.strftime("%Y年%m月%d日 %H:%M"),
                "activity": activity,
                "hours_advanced": hours
            }
        except Exception as e:
            self.logger.error(f"时间推进失败: {e}")
            return {"error": str(e)}

    def pause_time(self):
        """暂停时间"""
        if self.world_clock:
            self.world_clock.pause()
            self.logger.info("时间已暂停")

    def resume_time(self):
        """恢复时间"""
        if self.world_clock:
            self.world_clock.resume()
            self.logger.info("时间已恢复")

    def reset_time(self):
        """重置时间"""
        if self.world_clock:
            self.world_clock.reset()
            self.logger.info("时间已重置")

    def start_autonomous_mode(self):
        """启动自主模式"""
        if self.npc_system:
            self.npc_system.start_autonomous_behavior()
            self._autonomous_mode = True
            self.logger.info("自主模式已启动")

    def stop_autonomous_mode(self):
        """停止自主模式"""
        if self.npc_system:
            self.npc_system.stop_autonomous_behavior()
            self._autonomous_mode = False
            self.logger.info("自主模式已停止")

    def is_autonomous_mode_active(self) -> bool:
        """检查自主模式是否激活"""
        return self._autonomous_mode

    def get_model_outputs(self, limit: int = 50) -> List[Dict]:
        """获取模型输出"""
        return self.log_manager.get_model_outputs(limit)

    def get_token_stats(self) -> Dict[str, Any]:
        """获取 Token 统计"""
        return self.token_stats.copy()

    def reset_token_stats(self):
        """重置 Token 统计"""
        self.token_stats = {
            "total_sent": 0,
            "total_received": 0,
            "api_calls": 0,
            "session_start": datetime.now().isoformat()
        }

    def shutdown(self):
        """关闭服务"""
        self.logger.info("正在关闭 NPC 服务...")

        if self.npc_system:
            self.stop_autonomous_mode()

        self.logger.info("NPC 服务已关闭")
