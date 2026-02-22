# -*- coding: utf-8 -*-
"""
经济系统模块
============

管理货币、交易、物品、市场价格等经济相关功能。

主要组件:
- CurrencyManager: 货币管理器，处理资金增减和转账
- ItemRegistry: 物品注册表，管理游戏中所有物品定义
- MarketSystem: 市场系统，处理价格波动和供需关系
- InventoryManager: 库存管理器，管理实体的物品库存
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import random
import math

logger = logging.getLogger(__name__)


# =============================================================================
# 货币类型定义
# =============================================================================

class CurrencyType(Enum):
    """货币类型"""
    GOLD = "金币"           # 主要货币
    SILVER = "银币"         # 次要货币 (10银币=1金币)
    COPPER = "铜币"         # 基础货币 (10铜币=1银币)
    REPUTATION = "声望点"   # 特殊货币，用于声望商店


# 货币兑换比率 (相对于铜币)
CURRENCY_RATES = {
    CurrencyType.COPPER: 1,
    CurrencyType.SILVER: 10,
    CurrencyType.GOLD: 100,
    CurrencyType.REPUTATION: 0  # 声望不可兑换
}


# =============================================================================
# 物品类别定义
# =============================================================================

class ItemCategory(Enum):
    """物品类别"""
    WEAPON = "武器"
    ARMOR = "防具"
    CONSUMABLE = "消耗品"
    MATERIAL = "材料"
    FOOD = "食物"
    TOOL = "工具"
    JEWELRY = "饰品"
    BOOK = "书籍"
    QUEST = "任务物品"
    MISC = "杂物"


class ItemRarity(Enum):
    """物品稀有度"""
    COMMON = ("普通", 1.0)
    UNCOMMON = ("优秀", 1.5)
    RARE = ("稀有", 2.5)
    EPIC = ("史诗", 5.0)
    LEGENDARY = ("传说", 10.0)

    def __init__(self, display_name: str, price_multiplier: float):
        self.display_name = display_name
        self.price_multiplier = price_multiplier


# =============================================================================
# 交易记录
# =============================================================================

@dataclass
class Transaction:
    """交易记录"""
    transaction_id: str
    from_entity: str
    to_entity: str
    amount: int
    currency: CurrencyType
    category: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "transaction_id": self.transaction_id,
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "amount": self.amount,
            "currency": self.currency.value,
            "category": self.category,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


# =============================================================================
# 物品定义
# =============================================================================

@dataclass
class Item:
    """物品定义"""
    item_id: str
    name: str
    description: str
    category: ItemCategory
    base_price: int  # 基础价格(铜币)
    rarity: ItemRarity = ItemRarity.COMMON
    stackable: bool = True
    max_stack: int = 99
    weight: float = 1.0  # 重量(单位)
    durability: Optional[int] = None  # 耐久度，None表示不可损坏
    effects: Dict[str, Any] = field(default_factory=dict)  # 物品效果
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_display_price(self) -> int:
        """获取显示价格（考虑稀有度）"""
        return int(self.base_price * self.rarity.price_multiplier)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "base_price": self.base_price,
            "rarity": self.rarity.display_name,
            "stackable": self.stackable,
            "max_stack": self.max_stack,
            "weight": self.weight,
            "durability": self.durability,
            "effects": self.effects,
            "metadata": self.metadata
        }


@dataclass
class InventoryItem:
    """库存中的物品实例"""
    item_id: str
    quantity: int = 1
    current_durability: Optional[int] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "item_id": self.item_id,
            "quantity": self.quantity,
            "current_durability": self.current_durability,
            "custom_data": self.custom_data
        }


# =============================================================================
# 货币管理器
# =============================================================================

class CurrencyManager:
    """
    货币管理器

    负责管理实体的货币余额、资金增减、转账等操作。
    支持多种货币类型和完整的交易历史记录。
    """

    def __init__(self):
        """初始化货币管理器"""
        # 实体余额: {entity_id: {currency_type: amount}}
        self._balances: Dict[str, Dict[CurrencyType, int]] = {}
        # 交易历史: {entity_id: [Transaction]}
        self._transaction_history: Dict[str, List[Transaction]] = {}
        # 交易计数器
        self._transaction_counter = 0

    def _ensure_entity(self, entity: str):
        """确保实体存在"""
        if entity not in self._balances:
            self._balances[entity] = {ct: 0 for ct in CurrencyType}
            self._transaction_history[entity] = []

    def _generate_transaction_id(self) -> str:
        """生成交易ID"""
        self._transaction_counter += 1
        return f"txn_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._transaction_counter}"

    def get_balance(self, entity: str, currency: CurrencyType = CurrencyType.GOLD) -> int:
        """
        获取实体的货币余额

        参数:
            entity: 实体标识符（玩家名/NPC名/商店名等）
            currency: 货币类型，默认为金币

        返回:
            货币余额
        """
        self._ensure_entity(entity)
        return self._balances[entity].get(currency, 0)

    def get_all_balances(self, entity: str) -> Dict[str, int]:
        """
        获取实体的所有货币余额

        参数:
            entity: 实体标识符

        返回:
            各货币类型的余额字典
        """
        self._ensure_entity(entity)
        return {ct.value: amount for ct, amount in self._balances[entity].items()}

    def add_funds(self, entity: str, amount: int,
                  currency: CurrencyType = CurrencyType.GOLD,
                  reason: str = "系统添加") -> bool:
        """
        为实体添加货币

        参数:
            entity: 实体标识符
            amount: 添加数量（必须为正数）
            currency: 货币类型
            reason: 添加原因

        返回:
            是否成功
        """
        if amount <= 0:
            logger.warning(f"尝试添加非正数金额: {amount}")
            return False

        self._ensure_entity(entity)
        self._balances[entity][currency] += amount

        # 记录交易
        transaction = Transaction(
            transaction_id=self._generate_transaction_id(),
            from_entity="SYSTEM",
            to_entity=entity,
            amount=amount,
            currency=currency,
            category="income",
            description=reason
        )
        self._transaction_history[entity].append(transaction)

        logger.info(f"货币添加: {entity} 获得 {amount} {currency.value}, 原因: {reason}")
        return True

    def deduct_funds(self, entity: str, amount: int,
                     currency: CurrencyType = CurrencyType.GOLD,
                     reason: str = "系统扣除",
                     allow_negative: bool = False) -> bool:
        """
        从实体扣除货币

        参数:
            entity: 实体标识符
            amount: 扣除数量（必须为正数）
            currency: 货币类型
            reason: 扣除原因
            allow_negative: 是否允许余额为负

        返回:
            是否成功
        """
        if amount <= 0:
            logger.warning(f"尝试扣除非正数金额: {amount}")
            return False

        self._ensure_entity(entity)
        current_balance = self._balances[entity][currency]

        if not allow_negative and current_balance < amount:
            logger.warning(f"余额不足: {entity} 需要 {amount} {currency.value}, 当前 {current_balance}")
            return False

        self._balances[entity][currency] -= amount

        # 记录交易
        transaction = Transaction(
            transaction_id=self._generate_transaction_id(),
            from_entity=entity,
            to_entity="SYSTEM",
            amount=amount,
            currency=currency,
            category="expense",
            description=reason
        )
        self._transaction_history[entity].append(transaction)

        logger.info(f"货币扣除: {entity} 支付 {amount} {currency.value}, 原因: {reason}")
        return True

    def transfer(self, from_entity: str, to_entity: str, amount: int,
                 currency: CurrencyType = CurrencyType.GOLD,
                 category: str = "transfer",
                 description: str = "转账") -> bool:
        """
        在两个实体之间转账

        参数:
            from_entity: 付款方
            to_entity: 收款方
            amount: 转账金额
            currency: 货币类型
            category: 交易类别
            description: 交易描述

        返回:
            是否成功
        """
        if amount <= 0:
            logger.warning(f"尝试转账非正数金额: {amount}")
            return False

        self._ensure_entity(from_entity)
        self._ensure_entity(to_entity)

        # 检查余额
        if self._balances[from_entity][currency] < amount:
            logger.warning(f"转账失败: {from_entity} 余额不足")
            return False

        # 执行转账
        self._balances[from_entity][currency] -= amount
        self._balances[to_entity][currency] += amount

        # 记录交易
        transaction = Transaction(
            transaction_id=self._generate_transaction_id(),
            from_entity=from_entity,
            to_entity=to_entity,
            amount=amount,
            currency=currency,
            category=category,
            description=description
        )
        self._transaction_history[from_entity].append(transaction)
        self._transaction_history[to_entity].append(transaction)

        logger.info(f"转账完成: {from_entity} -> {to_entity}, {amount} {currency.value}")
        return True

    def get_transaction_history(self, entity: str,
                                 limit: int = 50,
                                 category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取实体的交易历史

        参数:
            entity: 实体标识符
            limit: 返回记录数量限制
            category: 可选的类别过滤

        返回:
            交易记录列表
        """
        self._ensure_entity(entity)
        history = self._transaction_history[entity]

        if category:
            history = [t for t in history if t.category == category]

        return [t.to_dict() for t in history[-limit:]]

    def convert_currency(self, entity: str,
                         from_currency: CurrencyType,
                         to_currency: CurrencyType,
                         amount: int) -> bool:
        """
        货币兑换

        参数:
            entity: 实体标识符
            from_currency: 源货币类型
            to_currency: 目标货币类型
            amount: 兑换数量（源货币）

        返回:
            是否成功
        """
        if from_currency == CurrencyType.REPUTATION or to_currency == CurrencyType.REPUTATION:
            logger.warning("声望点不可兑换")
            return False

        from_rate = CURRENCY_RATES[from_currency]
        to_rate = CURRENCY_RATES[to_currency]

        # 计算可兑换的目标货币数量
        base_value = amount * from_rate
        converted_amount = base_value // to_rate

        if converted_amount <= 0:
            logger.warning(f"兑换数量太少: {amount} {from_currency.value}")
            return False

        # 执行兑换
        if self.deduct_funds(entity, amount, from_currency, "货币兑换"):
            self.add_funds(entity, converted_amount, to_currency, "货币兑换")
            return True

        return False


# =============================================================================
# 物品注册表
# =============================================================================

class ItemRegistry:
    """
    物品注册表

    管理游戏中所有物品的定义。提供物品注册、查询、分类等功能。
    """

    def __init__(self):
        """初始化物品注册表"""
        self._items: Dict[str, Item] = {}
        self._category_index: Dict[ItemCategory, List[str]] = {cat: [] for cat in ItemCategory}
        self._initialize_default_items()

    def _initialize_default_items(self):
        """初始化默认物品"""
        default_items = [
            # 食物
            Item("bread", "面包", "新鲜的面包，可以恢复少量饥饿度",
                 ItemCategory.FOOD, 5, effects={"hunger": -20}),
            Item("meat", "烤肉", "香喷喷的烤肉，恢复较多饥饿度",
                 ItemCategory.FOOD, 15, effects={"hunger": -40}),
            Item("apple", "苹果", "红彤彤的苹果，清脆可口",
                 ItemCategory.FOOD, 3, effects={"hunger": -10}),
            Item("water", "水袋", "装满清水的水袋",
                 ItemCategory.FOOD, 2, effects={"thirst": -30}),
            Item("ale", "麦酒", "酒馆的特制麦酒",
                 ItemCategory.FOOD, 8, effects={"thirst": -20, "fatigue": -10}),

            # 消耗品
            Item("health_potion", "治疗药水", "可以恢复生命值的红色药水",
                 ItemCategory.CONSUMABLE, 50, ItemRarity.UNCOMMON, effects={"health": 50}),
            Item("stamina_potion", "精力药水", "可以恢复精力的绿色药水",
                 ItemCategory.CONSUMABLE, 40, ItemRarity.UNCOMMON, effects={"stamina": 50}),
            Item("antidote", "解毒药", "可以解除毒素的药剂",
                 ItemCategory.CONSUMABLE, 30, effects={"cure_poison": True}),

            # 材料
            Item("iron_ore", "铁矿石", "可用于锻造的铁矿石",
                 ItemCategory.MATERIAL, 10),
            Item("wood", "木材", "常见的建筑和制作材料",
                 ItemCategory.MATERIAL, 5),
            Item("leather", "皮革", "经过处理的动物皮革",
                 ItemCategory.MATERIAL, 20),
            Item("cloth", "布料", "纺织而成的普通布料",
                 ItemCategory.MATERIAL, 8),
            Item("herb", "草药", "具有药用价值的草药",
                 ItemCategory.MATERIAL, 12),

            # 工具
            Item("pickaxe", "镐子", "用于采矿的工具",
                 ItemCategory.TOOL, 100, stackable=False, durability=100),
            Item("axe", "斧头", "用于伐木的工具",
                 ItemCategory.TOOL, 80, stackable=False, durability=100),
            Item("fishing_rod", "钓竿", "用于钓鱼的工具",
                 ItemCategory.TOOL, 60, stackable=False, durability=50),

            # 武器
            Item("iron_sword", "铁剑", "普通的铁制长剑",
                 ItemCategory.WEAPON, 200, stackable=False, durability=150,
                 effects={"attack": 10}),
            Item("wooden_bow", "木弓", "简易的木制弓箭",
                 ItemCategory.WEAPON, 150, stackable=False, durability=80,
                 effects={"attack": 8, "range": 50}),
            Item("dagger", "匕首", "小巧锋利的匕首",
                 ItemCategory.WEAPON, 80, stackable=False, durability=100,
                 effects={"attack": 5, "speed": 10}),

            # 防具
            Item("leather_armor", "皮甲", "轻便的皮革护甲",
                 ItemCategory.ARMOR, 180, stackable=False, durability=120,
                 effects={"defense": 5}),
            Item("iron_helmet", "铁盔", "保护头部的铁制头盔",
                 ItemCategory.ARMOR, 120, stackable=False, durability=150,
                 effects={"defense": 3}),

            # 饰品
            Item("silver_ring", "银戒指", "闪亮的银质戒指",
                 ItemCategory.JEWELRY, 100, ItemRarity.UNCOMMON, stackable=False),
            Item("amulet", "护身符", "据说能带来好运的护身符",
                 ItemCategory.JEWELRY, 150, ItemRarity.UNCOMMON, stackable=False,
                 effects={"luck": 5}),

            # 书籍
            Item("recipe_book", "食谱书", "记载着各种料理方法的书籍",
                 ItemCategory.BOOK, 50, stackable=False),
            Item("map", "地图", "标注了周边地区的地图",
                 ItemCategory.BOOK, 30, stackable=False),

            # 杂物
            Item("torch", "火把", "可以照明的火把",
                 ItemCategory.MISC, 5, max_stack=20),
            Item("rope", "绳索", "结实的麻绳",
                 ItemCategory.MISC, 15),
            Item("key", "钥匙", "不知道能开什么锁的钥匙",
                 ItemCategory.MISC, 1, stackable=False),
        ]

        for item in default_items:
            self.register_item(item)

    def register_item(self, item: Item) -> bool:
        """
        注册物品

        参数:
            item: 物品对象

        返回:
            是否成功
        """
        if item.item_id in self._items:
            logger.warning(f"物品已存在，将被覆盖: {item.item_id}")

        self._items[item.item_id] = item

        # 更新分类索引
        if item.item_id not in self._category_index[item.category]:
            self._category_index[item.category].append(item.item_id)

        logger.debug(f"物品注册: {item.name} ({item.item_id})")
        return True

    def register_item_from_data(self, item_id: str, name: str, base_price: int,
                                 category: ItemCategory, description: str = "",
                                 rarity: ItemRarity = ItemRarity.COMMON,
                                 **kwargs) -> bool:
        """
        从数据注册物品

        参数:
            item_id: 物品ID
            name: 物品名称
            base_price: 基础价格
            category: 物品类别
            description: 物品描述
            rarity: 稀有度
            **kwargs: 其他物品属性

        返回:
            是否成功
        """
        item = Item(
            item_id=item_id,
            name=name,
            description=description or f"{name}",
            category=category,
            base_price=base_price,
            rarity=rarity,
            **kwargs
        )
        return self.register_item(item)

    def get_item(self, item_id: str) -> Optional[Item]:
        """
        获取物品定义

        参数:
            item_id: 物品ID

        返回:
            物品对象，不存在则返回None
        """
        return self._items.get(item_id)

    def get_items_by_category(self, category: ItemCategory) -> List[Item]:
        """
        按类别获取物品

        参数:
            category: 物品类别

        返回:
            该类别的物品列表
        """
        item_ids = self._category_index.get(category, [])
        return [self._items[iid] for iid in item_ids if iid in self._items]

    def get_items_by_rarity(self, rarity: ItemRarity) -> List[Item]:
        """
        按稀有度获取物品

        参数:
            rarity: 稀有度

        返回:
            该稀有度的物品列表
        """
        return [item for item in self._items.values() if item.rarity == rarity]

    def search_items(self, keyword: str) -> List[Item]:
        """
        搜索物品

        参数:
            keyword: 搜索关键词

        返回:
            匹配的物品列表
        """
        keyword = keyword.lower()
        return [
            item for item in self._items.values()
            if keyword in item.name.lower() or keyword in item.description.lower()
        ]

    def get_all_items(self) -> List[Item]:
        """获取所有物品"""
        return list(self._items.values())

    def get_item_count(self) -> int:
        """获取物品总数"""
        return len(self._items)


# =============================================================================
# 市场系统
# =============================================================================

class MarketSystem:
    """
    市场系统

    管理物品价格波动、供需关系、买卖交易等。
    支持动态价格调整和市场事件。
    """

    def __init__(self, item_registry: ItemRegistry, currency_manager: CurrencyManager):
        """
        初始化市场系统

        参数:
            item_registry: 物品注册表
            currency_manager: 货币管理器
        """
        self.item_registry = item_registry
        self.currency_manager = currency_manager

        # 当前价格修正: {item_id: multiplier}
        self._price_modifiers: Dict[str, float] = {}

        # 供需因子: {item_id: {"supply": float, "demand": float}}
        self._supply_demand: Dict[str, Dict[str, float]] = {}

        # 交易历史
        self._trade_history: List[Dict[str, Any]] = []

        # 价格波动范围
        self.min_price_multiplier = 0.5
        self.max_price_multiplier = 2.0

    def get_current_price(self, item_id: str,
                          quantity: int = 1,
                          is_buying: bool = True) -> int:
        """
        获取物品当前价格

        参数:
            item_id: 物品ID
            quantity: 数量
            is_buying: 是否是购买价（否则为出售价）

        返回:
            总价格（铜币）
        """
        item = self.item_registry.get_item(item_id)
        if not item:
            logger.warning(f"未知物品: {item_id}")
            return 0

        base_price = item.get_display_price()
        modifier = self._price_modifiers.get(item_id, 1.0)

        # 供需影响
        sd = self._supply_demand.get(item_id, {"supply": 1.0, "demand": 1.0})
        sd_modifier = sd["demand"] / max(sd["supply"], 0.1)
        sd_modifier = max(0.5, min(2.0, sd_modifier))

        final_price = base_price * modifier * sd_modifier

        # 买卖价差（卖出价为买入价的60%）
        if not is_buying:
            final_price *= 0.6

        return int(final_price * quantity)

    def update_prices(self, supply_demand_factors: Dict[str, Dict[str, float]]):
        """
        根据供需因素更新价格

        参数:
            supply_demand_factors: {item_id: {"supply": float, "demand": float}}
        """
        for item_id, factors in supply_demand_factors.items():
            if item_id not in self._supply_demand:
                self._supply_demand[item_id] = {"supply": 1.0, "demand": 1.0}

            # 渐进式更新
            current = self._supply_demand[item_id]
            current["supply"] = current["supply"] * 0.7 + factors.get("supply", 1.0) * 0.3
            current["demand"] = current["demand"] * 0.7 + factors.get("demand", 1.0) * 0.3

        logger.debug(f"价格更新: 影响 {len(supply_demand_factors)} 种物品")

    def set_price_modifier(self, item_id: str, modifier: float):
        """
        设置物品价格修正

        参数:
            item_id: 物品ID
            modifier: 价格倍率
        """
        modifier = max(self.min_price_multiplier, min(self.max_price_multiplier, modifier))
        self._price_modifiers[item_id] = modifier

    def buy_item(self, buyer: str, seller: str,
                 item_id: str, quantity: int = 1) -> Tuple[bool, str]:
        """
        购买物品

        参数:
            buyer: 购买者
            seller: 出售者
            item_id: 物品ID
            quantity: 数量

        返回:
            (是否成功, 消息)
        """
        item = self.item_registry.get_item(item_id)
        if not item:
            return False, f"未知物品: {item_id}"

        total_price = self.get_current_price(item_id, quantity, is_buying=True)

        # 检查购买者余额
        if self.currency_manager.get_balance(buyer, CurrencyType.GOLD) * 100 < total_price:
            return False, f"余额不足，需要 {total_price} 铜币"

        # 执行交易（转换为金币）
        gold_price = math.ceil(total_price / 100)
        if not self.currency_manager.transfer(
            buyer, seller, gold_price, CurrencyType.GOLD,
            "purchase", f"购买 {item.name} x{quantity}"
        ):
            return False, "交易失败"

        # 更新供需
        self._update_supply_demand_on_trade(item_id, quantity, is_buy=True)

        # 记录交易
        self._trade_history.append({
            "type": "buy",
            "buyer": buyer,
            "seller": seller,
            "item_id": item_id,
            "item_name": item.name,
            "quantity": quantity,
            "total_price": total_price,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"交易完成: {buyer} 从 {seller} 购买 {item.name} x{quantity}")
        return True, f"成功购买 {item.name} x{quantity}，花费 {gold_price} 金币"

    def sell_item(self, seller: str, buyer: str,
                  item_id: str, quantity: int = 1) -> Tuple[bool, str]:
        """
        出售物品

        参数:
            seller: 出售者
            buyer: 购买者
            item_id: 物品ID
            quantity: 数量

        返回:
            (是否成功, 消息)
        """
        item = self.item_registry.get_item(item_id)
        if not item:
            return False, f"未知物品: {item_id}"

        total_price = self.get_current_price(item_id, quantity, is_buying=False)

        # 执行交易（转换为金币）
        gold_price = total_price // 100
        if gold_price > 0:
            self.currency_manager.add_funds(
                seller, gold_price, CurrencyType.GOLD,
                f"出售 {item.name} x{quantity}"
            )

        # 更新供需
        self._update_supply_demand_on_trade(item_id, quantity, is_buy=False)

        # 记录交易
        self._trade_history.append({
            "type": "sell",
            "seller": seller,
            "buyer": buyer,
            "item_id": item_id,
            "item_name": item.name,
            "quantity": quantity,
            "total_price": total_price,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"交易完成: {seller} 向 {buyer} 出售 {item.name} x{quantity}")
        return True, f"成功出售 {item.name} x{quantity}，获得 {gold_price} 金币"

    def _update_supply_demand_on_trade(self, item_id: str, quantity: int, is_buy: bool):
        """交易后更新供需"""
        if item_id not in self._supply_demand:
            self._supply_demand[item_id] = {"supply": 1.0, "demand": 1.0}

        sd = self._supply_demand[item_id]
        impact = quantity * 0.05

        if is_buy:
            sd["demand"] = min(2.0, sd["demand"] + impact)
            sd["supply"] = max(0.5, sd["supply"] - impact * 0.5)
        else:
            sd["supply"] = min(2.0, sd["supply"] + impact)
            sd["demand"] = max(0.5, sd["demand"] - impact * 0.5)

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return self._trade_history[-limit:]

    def get_market_status(self) -> Dict[str, Any]:
        """获取市场状态概览"""
        return {
            "total_trades": len(self._trade_history),
            "price_modifiers": dict(self._price_modifiers),
            "supply_demand": dict(self._supply_demand)
        }

    def simulate_market_fluctuation(self):
        """模拟市场波动"""
        for item in self.item_registry.get_all_items():
            if random.random() < 0.3:  # 30%概率波动
                change = random.uniform(-0.1, 0.1)
                current = self._price_modifiers.get(item.item_id, 1.0)
                new_modifier = max(self.min_price_multiplier,
                                   min(self.max_price_multiplier, current + change))
                self._price_modifiers[item.item_id] = new_modifier


# =============================================================================
# 库存管理器
# =============================================================================

class InventoryManager:
    """
    库存管理器

    管理实体的物品库存，包括添加、移除、查询等操作。
    """

    def __init__(self, item_registry: ItemRegistry):
        """
        初始化库存管理器

        参数:
            item_registry: 物品注册表
        """
        self.item_registry = item_registry
        # 实体库存: {entity_id: [InventoryItem]}
        self._inventories: Dict[str, List[InventoryItem]] = {}
        # 库存容量限制: {entity_id: max_slots}
        self._capacity: Dict[str, int] = {}
        # 默认容量
        self.default_capacity = 50

    def _ensure_entity(self, entity: str):
        """确保实体存在"""
        if entity not in self._inventories:
            self._inventories[entity] = []
            self._capacity[entity] = self.default_capacity

    def set_capacity(self, entity: str, capacity: int):
        """设置库存容量"""
        self._ensure_entity(entity)
        self._capacity[entity] = capacity

    def get_inventory(self, entity: str) -> List[Dict[str, Any]]:
        """
        获取实体库存

        参数:
            entity: 实体标识符

        返回:
            库存物品列表
        """
        self._ensure_entity(entity)
        result = []
        for inv_item in self._inventories[entity]:
            item_def = self.item_registry.get_item(inv_item.item_id)
            if item_def:
                result.append({
                    **inv_item.to_dict(),
                    "name": item_def.name,
                    "category": item_def.category.value,
                    "description": item_def.description
                })
        return result

    def add_item(self, entity: str, item_id: str,
                 quantity: int = 1,
                 custom_data: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        添加物品到库存

        参数:
            entity: 实体标识符
            item_id: 物品ID
            quantity: 数量
            custom_data: 自定义数据

        返回:
            (是否成功, 消息)
        """
        item_def = self.item_registry.get_item(item_id)
        if not item_def:
            return False, f"未知物品: {item_id}"

        if quantity <= 0:
            return False, "数量必须为正数"

        self._ensure_entity(entity)
        inventory = self._inventories[entity]

        # 检查是否可堆叠
        if item_def.stackable:
            # 查找现有堆叠
            for inv_item in inventory:
                if inv_item.item_id == item_id:
                    space = item_def.max_stack - inv_item.quantity
                    add_amount = min(quantity, space)
                    inv_item.quantity += add_amount
                    quantity -= add_amount
                    if quantity <= 0:
                        return True, f"已添加 {item_def.name}"

            # 创建新堆叠
            while quantity > 0:
                if len(inventory) >= self._capacity[entity]:
                    return False, "库存已满"
                add_amount = min(quantity, item_def.max_stack)
                inventory.append(InventoryItem(
                    item_id=item_id,
                    quantity=add_amount,
                    current_durability=item_def.durability,
                    custom_data=custom_data or {}
                ))
                quantity -= add_amount
        else:
            # 不可堆叠物品
            for _ in range(quantity):
                if len(inventory) >= self._capacity[entity]:
                    return False, "库存已满"
                inventory.append(InventoryItem(
                    item_id=item_id,
                    quantity=1,
                    current_durability=item_def.durability,
                    custom_data=custom_data or {}
                ))

        logger.debug(f"物品添加: {entity} 获得 {item_def.name} x{quantity}")
        return True, f"已添加 {item_def.name} x{quantity}"

    def remove_item(self, entity: str, item_id: str,
                    quantity: int = 1) -> Tuple[bool, str]:
        """
        从库存移除物品

        参数:
            entity: 实体标识符
            item_id: 物品ID
            quantity: 数量

        返回:
            (是否成功, 消息)
        """
        item_def = self.item_registry.get_item(item_id)
        if not item_def:
            return False, f"未知物品: {item_id}"

        self._ensure_entity(entity)
        inventory = self._inventories[entity]

        # 计算拥有的总数量
        total_owned = sum(inv.quantity for inv in inventory if inv.item_id == item_id)
        if total_owned < quantity:
            return False, f"物品不足: 需要 {quantity}，拥有 {total_owned}"

        # 移除物品
        remaining = quantity
        items_to_remove = []

        for i, inv_item in enumerate(inventory):
            if inv_item.item_id == item_id:
                if inv_item.quantity <= remaining:
                    remaining -= inv_item.quantity
                    items_to_remove.append(i)
                else:
                    inv_item.quantity -= remaining
                    remaining = 0
                if remaining <= 0:
                    break

        # 从后向前移除，避免索引问题
        for i in reversed(items_to_remove):
            inventory.pop(i)

        logger.debug(f"物品移除: {entity} 失去 {item_def.name} x{quantity}")
        return True, f"已移除 {item_def.name} x{quantity}"

    def has_item(self, entity: str, item_id: str, quantity: int = 1) -> bool:
        """
        检查是否拥有足够数量的物品

        参数:
            entity: 实体标识符
            item_id: 物品ID
            quantity: 需要的数量

        返回:
            是否拥有足够数量
        """
        self._ensure_entity(entity)
        total = sum(inv.quantity for inv in self._inventories[entity]
                    if inv.item_id == item_id)
        return total >= quantity

    def get_item_count(self, entity: str, item_id: str) -> int:
        """
        获取物品数量

        参数:
            entity: 实体标识符
            item_id: 物品ID

        返回:
            物品数量
        """
        self._ensure_entity(entity)
        return sum(inv.quantity for inv in self._inventories[entity]
                   if inv.item_id == item_id)

    def transfer_item(self, from_entity: str, to_entity: str,
                      item_id: str, quantity: int = 1) -> Tuple[bool, str]:
        """
        转移物品

        参数:
            from_entity: 源实体
            to_entity: 目标实体
            item_id: 物品ID
            quantity: 数量

        返回:
            (是否成功, 消息)
        """
        # 先检查是否有足够的物品
        if not self.has_item(from_entity, item_id, quantity):
            return False, "物品不足"

        # 先添加到目标
        success, msg = self.add_item(to_entity, item_id, quantity)
        if not success:
            return False, msg

        # 从源移除
        self.remove_item(from_entity, item_id, quantity)

        item_def = self.item_registry.get_item(item_id)
        logger.info(f"物品转移: {from_entity} -> {to_entity}, {item_def.name} x{quantity}")
        return True, f"已转移 {item_def.name} x{quantity}"

    def get_inventory_weight(self, entity: str) -> float:
        """获取库存总重量"""
        self._ensure_entity(entity)
        total_weight = 0.0
        for inv_item in self._inventories[entity]:
            item_def = self.item_registry.get_item(inv_item.item_id)
            if item_def:
                total_weight += item_def.weight * inv_item.quantity
        return total_weight

    def get_inventory_value(self, entity: str) -> int:
        """获取库存总价值（铜币）"""
        self._ensure_entity(entity)
        total_value = 0
        for inv_item in self._inventories[entity]:
            item_def = self.item_registry.get_item(inv_item.item_id)
            if item_def:
                total_value += item_def.get_display_price() * inv_item.quantity
        return total_value

    def clear_inventory(self, entity: str):
        """清空库存"""
        self._ensure_entity(entity)
        self._inventories[entity] = []
        logger.info(f"库存清空: {entity}")


# =============================================================================
# 经济系统整合类
# =============================================================================

class EconomySystem:
    """
    经济系统整合类

    整合货币管理、物品注册、市场交易和库存管理的统一接口。
    """

    def __init__(self):
        """初始化经济系统"""
        self.currency_manager = CurrencyManager()
        self.item_registry = ItemRegistry()
        self.market_system = MarketSystem(self.item_registry, self.currency_manager)
        self.inventory_manager = InventoryManager(self.item_registry)

        logger.info("经济系统初始化完成")

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "registered_items": self.item_registry.get_item_count(),
            "market_status": self.market_system.get_market_status()
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出系统状态为字典"""
        return {
            "items": [item.to_dict() for item in self.item_registry.get_all_items()],
            "market_status": self.market_system.get_market_status()
        }
