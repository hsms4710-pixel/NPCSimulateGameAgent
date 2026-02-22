import requests
import json
import time
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DeepSeekClient:
    """DeepSeek API客户端，用于生成NPC的智能行为"""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_response(self,
                         prompt: str,
                         context: Optional[Dict[str, Any]] = None,
                         temperature: float = 0.7,
                         max_tokens: int = 500,
                         timeout: int = 60) -> str:
        """
        生成LLM响应

        Args:
            prompt: 提示文本
            context: 上下文信息
            temperature: 创造性参数 (0.0-1.0)
            max_tokens: 最大token数

        Returns:
            生成的响应文本
        """
        try:
            # 构建消息
            messages = []

            # 添加系统提示
            if context and "system_prompt" in context:
                messages.append({
                    "role": "system",
                    "content": context["system_prompt"]
                })

            # 添加上下文消息
            if context and "conversation_history" in context:
                messages.extend(context["conversation_history"])

            # 添加用户提示
            messages.append({
                "role": "user",
                "content": prompt
            })

            # 构建请求体
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }

            # 发送请求 - 手动编码确保UTF-8
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                timeout=timeout
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                logger.info(f"成功生成响应，长度: {len(content)}")
                return content
            else:
                logger.error(f"API请求失败: {response.status_code} - {response.text}")
                return f"API错误: {response.status_code}"

        except requests.exceptions.Timeout:
            logger.error("API请求超时")
            return "请求超时，请重试"
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            return f"网络错误: {str(e)}"
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return f"未知错误: {str(e)}"

    def generate_npc_behavior(self,
                             npc_config: Dict[str, Any],
                             current_state: Dict[str, Any],
                             available_actions: List[str]) -> Dict[str, Any]:
        """
        生成NPC的行为决策

        Args:
            npc_config: NPC配置
            current_state: 当前状态
            available_actions: 可用行动

        Returns:
            行为决策结果
        """
        # 构建系统提示
        system_prompt = f"""你是一个智能NPC，名叫{npc_config['name']}，职业是{npc_config['profession']}。
你的性格特点：{', '.join(npc_config['personality']['traits'])}
你的背景故事：{npc_config['background'][:200]}...

请根据当前状态和可用行动，决定下一步的行为。响应必须是JSON格式：
{{
    "action": "行动名称",
    "reasoning": "行动理由",
    "emotion": "当前情绪",
    "dialogue": "可能的对话内容"
}}"""

        # 构建当前状态描述
        state_description = f"""
当前时间：{current_state.get('time', '未知')}
当前位置：{current_state.get('location', '未知')}
当前情绪：{current_state.get('emotion', '平静')}
当前任务：{current_state.get('current_task', '无')}
长期目标：{current_state.get('goals', [])[:2]}

可用行动：{', '.join(available_actions)}

请决定下一步行动，并解释原因。"""

        # 生成响应
        response_text = self.generate_response(
            prompt=state_description,
            context={"system_prompt": system_prompt},
            temperature=0.8
        )

        try:
            # 尝试解析JSON响应
            result = json.loads(response_text)
            return result
        except json.JSONDecodeError:
            # 如果不是有效JSON，返回默认行为
            logger.warning(f"无法解析LLM响应作为JSON: {response_text}")
            return {
                "action": available_actions[0] if available_actions else "休息",
                "reasoning": "LLM响应格式错误，使用默认行为",
                "emotion": "困惑",
                "dialogue": "让我想想..."
            }

    def generate_npc_conversation(self,
                                 npc_config: Dict[str, Any],
                                 player_input: str,
                                 conversation_history: List[Dict[str, str]],
                                 current_activity: str = None,
                                 current_time: str = None) -> str:
        """
        生成NPC对话响应

        Args:
            npc_config: NPC配置
            player_input: 玩家输入
            conversation_history: 对话历史

        Returns:
            NPC的对话响应
        """
        # 构建当前状态信息
        activity_info = ""
        if current_activity:
            activity_info = f"你当前正在：{current_activity}。"

        time_info = ""
        if current_time:
            time_info = f"现在是{current_time}。"

        # 根据当前活动强制回应风格
        activity_instruction = ""
        if current_activity:
            # 从NPCAction枚举获取指令
            from core_types import NPCAction
            try:
                # 查找匹配的活动枚举
                for action in NPCAction:
                    if action.value in current_activity or current_activity.lower() in action.value.lower():
                        activity_instruction = action.ai_instruction
                        break
            except:
                # 如果查找失败，使用默认指令
                activity_instruction = "请根据你的性格和当前情境自然回应。"

        system_prompt = f"""你正在扮演{npc_config['name']}，一个{npc_config['profession']}。
性格：{', '.join(npc_config['personality']['traits'])}
背景：{npc_config['background'][:300]}...
{time_info}{activity_info}
{activity_instruction}

严格遵守：你的回应必须完全符合你当前正在做的活动。不要表现出与当前活动与人物性格矛盾的行为。"""

        # 构建对话上下文
        context = {
            "system_prompt": system_prompt,
            "conversation_history": conversation_history[-5:]  # 只保留最近5轮对话
        }

        response = self.generate_response(
            prompt=player_input,
            context=context,
            temperature=0.9,
            max_tokens=200
        )

        return response

    def generate_world_event_response(self,
                                    npc_config: Dict[str, Any],
                                    event_description: str) -> Dict[str, Any]:
        """
        生成NPC对世界事件的响应

        Args:
            npc_config: NPC配置
            event_description: 事件描述

        Returns:
            事件响应
        """
        system_prompt = f"""你正在扮演{npc_config['name']}。
请对发生的事件做出自然反应，包括你的想法、感受和可能的行动。"""

        prompt = f"小镇发生了以下事件：{event_description}\n\n请描述你的反应和可能的行动。"

        response = self.generate_response(
            prompt=prompt,
            context={"system_prompt": system_prompt},
            temperature=0.7
        )

        return {
            "thoughts": response,
            "action_taken": self._extract_action_from_response(response),
            "emotional_impact": self._analyze_emotional_impact(response)
        }

    def _extract_action_from_response(self, response: str) -> str:
        """从响应中提取行动"""
        # 简单的关键词提取
        if "去" in response or "前往" in response:
            return "移动"
        elif "说" in response or "告诉" in response:
            return "对话"
        elif "工作" in response or "做" in response:
            return "工作"
        else:
            return "观察"

    def _analyze_emotional_impact(self, response: str) -> str:
        """分析情感影响"""
        positive_words = ["高兴", "开心", "满意", "激动", "感激"]
        negative_words = ["担心", "害怕", "生气", "难过", "失望"]

        for word in positive_words:
            if word in response:
                return "正面"

        for word in negative_words:
            if word in response:
                return "负面"

        return "中性"

    def call_model(self,
                   messages: List[Dict[str, str]],
                   model: str = None,
                   max_tokens: int = 500,
                   temperature: float = 0.7) -> str:
        """
        调用模型接口 - 兼容four_level_decisions等模块的调用方式

        Args:
            messages: 消息列表，格式为 [{"role": "user/system/assistant", "content": "..."}]
            model: 模型名称（可选，使用默认模型）
            max_tokens: 最大token数
            temperature: 创造性参数

        Returns:
            生成的响应文本
        """
        try:
            # 使用传入的模型或默认模型
            use_model = model if model else self.model

            # 构建请求体
            payload = {
                "model": use_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }

            # 发送请求 - 手动编码确保UTF-8
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                logger.info(f"call_model 成功，响应长度: {len(content)}")
                return content
            else:
                logger.error(f"API请求失败: {response.status_code} - {response.text}")
                return f"API错误: {response.status_code}"

        except requests.exceptions.Timeout:
            logger.error("API请求超时")
            return "请求超时，请重试"
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            return f"网络错误: {str(e)}"
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return f"未知错误: {str(e)}"
