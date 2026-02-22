"""
经济服务层 - EconomySystem 单例封装（D1/C3）
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# 懒加载 EconomySystem 单例
_economy_system = None


def get_economy_system():
    """获取 EconomySystem 单例"""
    global _economy_system
    if _economy_system is None:
        try:
            from world_simulator.economy_system import EconomySystem
            _economy_system = EconomySystem()
            logger.info("EconomySystem 单例初始化成功")
        except Exception as e:
            logger.warning(f"EconomySystem 初始化失败: {e}")
            _economy_system = None
    return _economy_system


def get_player_inventory(player_name: str):
    """获取玩家背包"""
    eco = get_economy_system()
    if not eco:
        return []
    try:
        return eco.inventory_manager.get_inventory(player_name)
    except Exception as e:
        logger.warning(f"获取背包失败: {e}")
        return []


def get_player_gold(player_name: str) -> dict:
    """获取玩家金币"""
    eco = get_economy_system()
    if not eco:
        return {"gold": 0, "silver": 0, "copper": 0}
    try:
        balance = eco.currency_manager.get_balance(player_name)
        return balance if isinstance(balance, dict) else {"gold": balance, "silver": 0, "copper": 0}
    except Exception as e:
        logger.warning(f"获取金币失败: {e}")
        return {"gold": 0, "silver": 0, "copper": 0}


def execute_trade(buyer: str, seller: str, item_id: str, quantity: int = 1, action: str = "buy") -> dict:
    """执行交易"""
    eco = get_economy_system()
    if not eco:
        return {"success": False, "reason": "经济系统未初始化"}
    try:
        if action == "buy":
            result = eco.market_system.buy_item(buyer=buyer, seller=seller,
                                                 item_id=item_id, quantity=quantity)
        else:
            result = eco.market_system.sell_item(seller=buyer, buyer=seller,
                                                  item_id=item_id, quantity=quantity)
        return result if isinstance(result, dict) else {"success": bool(result)}
    except Exception as e:
        logger.error(f"交易执行失败: {e}")
        return {"success": False, "reason": str(e)}


def use_item(player_name: str, item_id: str, player_state: dict) -> dict:
    """使用物品（从 Item.effects 动态读取效果）"""
    eco = get_economy_system()
    if not eco:
        return {"success": False, "reason": "经济系统未初始化"}
    try:
        item = eco.item_registry.get_item(item_id)
        if not item:
            return {"success": False, "reason": f"物品 {item_id} 不存在"}
        effects = getattr(item, 'effects', {})
        applied = {}
        for stat, delta in effects.items():
            if stat in player_state:
                old_val = player_state[stat]
                player_state[stat] = max(0.0, min(1.0, old_val + delta))
                applied[stat] = player_state[stat] - old_val
        # 从背包移除
        eco.inventory_manager.remove_item(player_name, item_id, 1)
        return {"success": True, "item_id": item_id, "effects_applied": applied}
    except Exception as e:
        logger.error(f"使用物品失败: {e}")
        return {"success": False, "reason": str(e)}
