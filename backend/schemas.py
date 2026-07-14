# -*- coding: utf-8 -*-
"""Pydantic 模型定义 — 从 api_server.py 提取"""

from typing import Optional, Dict
from pydantic import BaseModel


class APIConfig(BaseModel):
    provider: Optional[str] = "deepseek"
    api_key: Optional[str] = None
    api_base: Optional[str] = "https://api.deepseek.com/v1"
    model: Optional[str] = "deepseek-chat"


class EventRequest(BaseModel):
    content: str
    event_type: str = "dialogue"


class DialogueRequest(BaseModel):
    message: str


class NPCSelectRequest(BaseModel):
    npc_name: str


class PlayerCreateRequest(BaseModel):
    """玩家创建请求"""
    preset_id: Optional[str] = None
    name: str
    age: int = 25
    gender: str = "男"
    birthplace: str = "远方"
    appearance: str = ""
    profession: Optional[str] = None
    background: Optional[str] = None
    personality: Optional[str] = None
    skills: Optional[Dict[str, int]] = None


class PlayerActionRequest(BaseModel):
    """玩家行动请求"""
    action: str
    target: Optional[str] = None
    details: Optional[str] = None


class WorldEventRequest(BaseModel):
    """世界事件请求"""
    title: str
    description: str
    location: str
    event_type: str = "自定义"
    severity: int = 3


class TimeAdvanceRequest(BaseModel):
    hours: float = 1.0
    update_npcs: bool = True
