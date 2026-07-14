"""经济系统 — 货币 + 物品 + 交易"""
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_ITEMS = {
    "面包": {"price": 2, "type": "food"},
    "麦酒": {"price": 5, "type": "drink"},
    "铁器": {"price": 30, "type": "tool"},
    "草药": {"price": 8, "type": "medicine"},
    "衣物": {"price": 20, "type": "clothing"},
    "矿石": {"price": 15, "type": "material"},
    "木材": {"price": 10, "type": "material"},
}


class EconomySystem:
    def __init__(self):
        self.items = DEFAULT_ITEMS.copy()
        self.balances: Dict[str, int] = {}  # entity -> gold
        self.inventories: Dict[str, Dict[str, int]] = {}  # entity -> {item: count}
        self.transactions: list = []

    def init_entity(self, name: str, gold: int = 50):
        self.balances[name] = gold
        self.inventories[name] = {}

    def get_balance(self, entity: str) -> int:
        return self.balances.get(entity, 0)

    def get_inventory(self, entity: str) -> Dict[str, int]:
        return self.inventories.get(entity, {})

    def trade(self, buyer: str, seller: str, item: str, action: str = "buy") -> dict:
        if item not in self.items:
            return {"ok": False, "error": f"物品{item}不存在"}
        price = self.items[item]["price"]

        if action == "buy":
            if self.balances.get(buyer, 0) < price:
                return {"ok": False, "error": "金币不足"}
            if self.inventories.get(seller, {}).get(item, 0) <= 0:
                return {"ok": False, "error": f"{seller}没有{item}"}
            self.balances[buyer] -= price
            self.balances[seller] = self.balances.get(seller, 0) + price
            self.inventories.setdefault(buyer, {})[item] = self.inventories.setdefault(buyer, {}).get(item, 0) + 1
            self.inventories[seller][item] -= 1
        elif action == "sell":
            if self.inventories.get(buyer, {}).get(item, 0) <= 0:
                return {"ok": False, "error": f"你没有{item}"}
            self.balances[buyer] = self.balances.get(buyer, 0) + price
            self.balances[seller] -= price
            self.inventories[buyer][item] -= 1
            self.inventories.setdefault(seller, {})[item] = self.inventories.setdefault(seller, {}).get(item, 0) + 1

        self.transactions.append({"buyer": buyer, "seller": seller, "item": item, "price": price, "action": action})
        return {"ok": True, "item": item, "price": price, "balance": self.balances.get(buyer, 0)}

    def give_item(self, entity: str, item: str, count: int = 1):
        self.inventories.setdefault(entity, {})[item] = self.inventories.setdefault(entity, {}).get(item, 0) + count

    def to_dict(self) -> dict:
        return {"balances": self.balances, "items": self.items}
