# -*- coding: utf-8 -*-
"""
存档管理系统
统一管理世界、玩家和NPC的存档
"""

import gzip
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.types.world import WorldState, Location
from core.types.player import PlayerState
from core.types.npc import NPCState

logger = logging.getLogger(__name__)


@dataclass
class SaveMetadata:
    """存档元数据"""
    save_id: str
    save_name: str
    world_name: str
    player_name: str
    game_time: str
    real_time: str
    play_time_hours: float
    npc_count: int
    location_count: int
    version: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "save_id": self.save_id,
            "save_name": self.save_name,
            "world_name": self.world_name,
            "player_name": self.player_name,
            "game_time": self.game_time,
            "real_time": self.real_time,
            "play_time_hours": self.play_time_hours,
            "npc_count": self.npc_count,
            "location_count": self.location_count,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SaveMetadata':
        return cls(
            save_id=data.get("save_id", ""),
            save_name=data.get("save_name", ""),
            world_name=data.get("world_name", ""),
            player_name=data.get("player_name", ""),
            game_time=data.get("game_time", ""),
            real_time=data.get("real_time", ""),
            play_time_hours=data.get("play_time_hours", 0.0),
            npc_count=data.get("npc_count", 0),
            location_count=data.get("location_count", 0),
            version=data.get("version", "1.0")
        )


class SaveManager:
    """
    存档管理器
    负责游戏存档的保存、加载和管理
    """

    def __init__(self, saves_dir: str = "saves"):
        """
        初始化存档管理器

        Args:
            saves_dir: 存档根目录
        """
        self.saves_dir = saves_dir
        self.worlds_dir = os.path.join(saves_dir, "worlds")
        self.players_dir = os.path.join(saves_dir, "players")
        self.games_dir = os.path.join(saves_dir, "games")

        # 确保目录存在
        for d in [self.saves_dir, self.worlds_dir, self.players_dir, self.games_dir]:
            os.makedirs(d, exist_ok=True)

    # ==================== 游戏存档 ====================

    def save_game(
        self,
        save_name: str,
        world_state: WorldState,
        player_state: PlayerState,
        npc_states: Dict[str, NPCState],
        overwrite: bool = False
    ) -> str:
        """
        保存游戏

        Args:
            save_name: 存档名称
            world_state: 世界状态
            player_state: 玩家状态
            npc_states: NPC状态字典
            overwrite: 是否覆盖已有存档

        Returns:
            存档路径
        """
        # 生成存档ID
        save_id = save_name.replace(" ", "_")
        save_path = os.path.join(self.games_dir, save_id)

        if os.path.exists(save_path) and not overwrite:
            raise FileExistsError(f"存档已存在: {save_name}")

        os.makedirs(save_path, exist_ok=True)

        # 保存元数据
        metadata = SaveMetadata(
            save_id=save_id,
            save_name=save_name,
            world_name=world_state.world_name,
            player_name=player_state.name,
            game_time=world_state.current_time.to_string(),
            real_time=datetime.now().isoformat(),
            play_time_hours=player_state.play_time_hours,
            npc_count=len(npc_states),
            location_count=len(world_state.locations)
        )

        with open(os.path.join(save_path, "metadata.json"), 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存世界状态
        with open(os.path.join(save_path, "world.json"), 'w', encoding='utf-8') as f:
            json.dump(world_state.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存玩家状态
        with open(os.path.join(save_path, "player.json"), 'w', encoding='utf-8') as f:
            json.dump(player_state.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存NPC状态（压缩）
        npcs_dir = os.path.join(save_path, "npcs")
        os.makedirs(npcs_dir, exist_ok=True)

        for npc_id, npc_state in npc_states.items():
            npc_file = os.path.join(npcs_dir, f"{npc_id}.json.gz")
            with gzip.open(npc_file, 'wt', encoding='utf-8') as f:
                json.dump(npc_state.to_dict(), f, ensure_ascii=False)

        logger.info(f"游戏已保存: {save_path}")
        return save_path

    def load_game(self, save_id: str) -> Tuple[WorldState, PlayerState, Dict[str, NPCState]]:
        """
        加载游戏

        Args:
            save_id: 存档ID

        Returns:
            (世界状态, 玩家状态, NPC状态字典)
        """
        save_path = os.path.join(self.games_dir, save_id)

        if not os.path.exists(save_path):
            raise FileNotFoundError(f"存档不存在: {save_id}")

        # 加载世界状态
        with open(os.path.join(save_path, "world.json"), 'r', encoding='utf-8') as f:
            world_data = json.load(f)
            world_state = WorldState.from_dict(world_data)

        # 加载玩家状态
        with open(os.path.join(save_path, "player.json"), 'r', encoding='utf-8') as f:
            player_data = json.load(f)
            player_state = PlayerState.from_dict(player_data)

        # 加载NPC状态
        npc_states = {}
        npcs_dir = os.path.join(save_path, "npcs")
        if os.path.exists(npcs_dir):
            for filename in os.listdir(npcs_dir):
                if filename.endswith(".json.gz"):
                    npc_file = os.path.join(npcs_dir, filename)
                    with gzip.open(npc_file, 'rt', encoding='utf-8') as f:
                        npc_data = json.load(f)
                        npc_state = NPCState.from_dict(npc_data)
                        npc_states[npc_state.npc_id] = npc_state
                elif filename.endswith(".json"):
                    npc_file = os.path.join(npcs_dir, filename)
                    with open(npc_file, 'r', encoding='utf-8') as f:
                        npc_data = json.load(f)
                        npc_state = NPCState.from_dict(npc_data)
                        npc_states[npc_state.npc_id] = npc_state

        logger.info(f"游戏已加载: {save_id}")
        return world_state, player_state, npc_states

    def list_saves(self) -> List[SaveMetadata]:
        """列出所有存档"""
        saves = []

        if not os.path.exists(self.games_dir):
            return saves

        for save_id in os.listdir(self.games_dir):
            metadata_file = os.path.join(self.games_dir, save_id, "metadata.json")
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        saves.append(SaveMetadata.from_dict(data))
                except Exception as e:
                    logger.warning(f"无法读取存档元数据: {save_id}, {e}")

        # 按保存时间排序
        saves.sort(key=lambda s: s.real_time, reverse=True)
        return saves

    def delete_save(self, save_id: str) -> bool:
        """删除存档"""
        save_path = os.path.join(self.games_dir, save_id)
        if os.path.exists(save_path):
            shutil.rmtree(save_path)
            logger.info(f"存档已删除: {save_id}")
            return True
        return False

    # ==================== 世界模板 ====================

    def save_world_template(
        self,
        world_state: WorldState,
        npc_templates: Dict[str, NPCState]
    ) -> str:
        """
        保存世界模板（用于创建新游戏）

        Args:
            world_state: 世界状态
            npc_templates: NPC模板

        Returns:
            模板路径
        """
        template_path = os.path.join(self.worlds_dir, world_state.world_id)
        os.makedirs(template_path, exist_ok=True)

        # 保存索引
        index = {
            "world_id": world_state.world_id,
            "world_name": world_state.world_name,
            "theme": world_state.theme.value,
            "created_at": datetime.now().isoformat(),
            "location_count": len(world_state.locations),
            "npc_count": len(npc_templates),
            "npc_names": [npc.name for npc in npc_templates.values()]
        }

        with open(os.path.join(template_path, "index.json"), 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        # 保存世界设定
        with open(os.path.join(template_path, "world_settings.json"), 'w', encoding='utf-8') as f:
            json.dump(world_state.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存地点
        locations_data = {loc_id: loc.to_dict() for loc_id, loc in world_state.locations.items()}
        with open(os.path.join(template_path, "locations.json"), 'w', encoding='utf-8') as f:
            json.dump({"locations": locations_data}, f, ensure_ascii=False, indent=2)

        # 保存NPC模板
        npcs_dir = os.path.join(template_path, "npcs")
        os.makedirs(npcs_dir, exist_ok=True)

        for npc_id, npc_state in npc_templates.items():
            npc_file = os.path.join(npcs_dir, f"{npc_state.name}.json")
            with open(npc_file, 'w', encoding='utf-8') as f:
                json.dump(npc_state.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"世界模板已保存: {template_path}")
        return template_path

    def list_world_templates(self) -> List[Dict[str, Any]]:
        """列出所有世界模板"""
        templates = []

        if not os.path.exists(self.worlds_dir):
            return templates

        for world_id in os.listdir(self.worlds_dir):
            index_file = os.path.join(self.worlds_dir, world_id, "index.json")
            if os.path.exists(index_file):
                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data['dir_name'] = world_id
                        data['modified_time'] = os.path.getmtime(index_file)
                        templates.append(data)
                except Exception as e:
                    logger.warning(f"无法读取世界模板: {world_id}, {e}")

        return templates

    def load_world_template(self, world_id: str) -> Tuple[WorldState, Dict[str, NPCState]]:
        """
        加载世界模板

        Args:
            world_id: 世界ID

        Returns:
            (世界状态, NPC模板字典)
        """
        template_path = os.path.join(self.worlds_dir, world_id)

        if not os.path.exists(template_path):
            raise FileNotFoundError(f"世界模板不存在: {world_id}")

        # 加载世界设定
        settings_file = os.path.join(template_path, "world_settings.json")
        with open(settings_file, 'r', encoding='utf-8') as f:
            world_data = json.load(f)
            world_state = WorldState.from_dict(world_data)

        # 加载NPC模板
        npc_templates = {}
        npcs_dir = os.path.join(template_path, "npcs")
        if os.path.exists(npcs_dir):
            for filename in os.listdir(npcs_dir):
                if filename.endswith(".json"):
                    npc_file = os.path.join(npcs_dir, filename)
                    with open(npc_file, 'r', encoding='utf-8') as f:
                        npc_data = json.load(f)
                        npc_state = NPCState.from_dict(npc_data)
                        npc_templates[npc_state.npc_id] = npc_state

        return world_state, npc_templates

    # ==================== 玩家存档 ====================

    def save_player(self, player_state: PlayerState) -> str:
        """保存玩家状态"""
        player_file = os.path.join(self.players_dir, f"{player_state.player_id}.json")
        with open(player_file, 'w', encoding='utf-8') as f:
            json.dump(player_state.to_dict(), f, ensure_ascii=False, indent=2)
        return player_file

    def load_player(self, player_id: str) -> PlayerState:
        """加载玩家状态"""
        player_file = os.path.join(self.players_dir, f"{player_id}.json")
        with open(player_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return PlayerState.from_dict(data)

    def list_players(self) -> List[Dict[str, Any]]:
        """列出所有玩家存档"""
        players = []

        if not os.path.exists(self.players_dir):
            return players

        for filename in os.listdir(self.players_dir):
            if filename.endswith(".json"):
                player_file = os.path.join(self.players_dir, filename)
                try:
                    with open(player_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        players.append({
                            "player_id": data.get("player_id"),
                            "name": data.get("name"),
                            "play_time_hours": data.get("play_time_hours", 0),
                            "last_saved": data.get("last_saved")
                        })
                except Exception as e:
                    logger.warning(f"无法读取玩家存档: {filename}, {e}")

        return players


# 全局存档管理器实例
save_manager = SaveManager()
