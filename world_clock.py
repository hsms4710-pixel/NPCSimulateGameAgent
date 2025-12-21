"""
世界时钟系统
管理游戏世界的全局时间
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Callable
import threading


class WorldClock:
    """世界时钟 - 管理游戏世界的全局时间"""

    def __init__(self, start_date: Optional[datetime] = None):
        """
        初始化世界时钟

        Args:
            start_date: 起始日期，默认为2025年12月6日0点（冬天）
        """
        if start_date is None:
            # 默认从2025年12月6日0点开始（冬天）
            start_date = datetime(2025, 12, 6, 0, 0, 0)

        self._current_time = start_date
        self._start_time = start_date
        self._is_running = False
        self._speed_multiplier = 1.0  # 时间流逝速度倍数
        self._last_real_time = time.time()
        self._paused = False

        # 时间事件监听器
        self._time_listeners: list[Callable[[datetime, float], None]] = []

        # 定时器线程
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def current_time(self) -> datetime:
        """获取当前世界时间"""
        return self._current_time

    @property
    def is_running(self) -> bool:
        """时钟是否正在运行"""
        return self._is_running

    @property
    def speed_multiplier(self) -> float:
        """时间流逝速度倍数"""
        return self._speed_multiplier

    @speed_multiplier.setter
    def speed_multiplier(self, value: float):
        """设置时间流逝速度倍数"""
        if value <= 0:
            raise ValueError("时间流逝速度必须大于0")
        self._speed_multiplier = value

    @property
    def is_paused(self) -> bool:
        """时钟是否暂停"""
        return self._paused

    def start(self):
        """启动时钟"""
        if self._is_running:
            return

        self._is_running = True
        self._paused = False
        self._last_real_time = time.time()
        self._stop_event.clear()

        # 启动定时器线程
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

    def stop(self):
        """停止时钟"""
        self._is_running = False
        self._paused = False
        self._stop_event.set()

        if self._timer_thread and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=1.0)

    def pause(self):
        """暂停时钟"""
        self._paused = True

    def resume(self):
        """恢复时钟"""
        if self._is_running:
            self._paused = False
            self._last_real_time = time.time()

    def advance_time(self, hours: float):
        """
        手动前进指定小时数

        Args:
            hours: 要前进的小时数
        """
        if hours <= 0:
            return

        old_time = self._current_time
        self._current_time += timedelta(hours=hours)

        # 通知监听器
        self._notify_listeners(old_time, hours)

    def set_time(self, new_time: datetime):
        """
        设置世界时间

        Args:
            new_time: 新的世界时间
        """
        if new_time < self._start_time:
            raise ValueError("时间不能早于起始时间")

        old_time = self._current_time
        time_diff = (new_time - old_time).total_seconds() / 3600  # 小时差

        self._current_time = new_time
        self._last_real_time = time.time()

        # 通知监听器
        self._notify_listeners(old_time, time_diff)

    def reset(self):
        """重置时钟到起始时间"""
        old_time = self._current_time
        time_diff = (self._start_time - old_time).total_seconds() / 3600

        self._current_time = self._start_time
        self._last_real_time = time.time()

        # 通知监听器
        self._notify_listeners(old_time, time_diff)

    def add_time_listener(self, listener: Callable[[datetime, float], None]):
        """
        添加时间变化监听器

        Args:
            listener: 监听器函数，参数为(新时间, 时间变化小时数)
        """
        if listener not in self._time_listeners:
            self._time_listeners.append(listener)

    def remove_time_listener(self, listener: Callable[[datetime, float], None]):
        """移除时间变化监听器"""
        if listener in self._time_listeners:
            self._time_listeners.remove(listener)

    def get_season(self) -> str:
        """获取当前季节"""
        month = self._current_time.month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:  # 9, 10, 11
            return "autumn"

    def get_time_of_day(self) -> str:
        """获取一天中的时间段"""
        hour = self._current_time.hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:  # 21-4
            return "night"

    def get_weather_modifier(self) -> dict:
        """获取天气对活动的影响修正"""
        season = self.get_season()
        time_of_day = self.get_time_of_day()

        # 基础修正
        modifiers = {
            "energy_cost": 1.0,  # 能量消耗倍数
            "mood_bonus": 0,    # 心情加成
            "activity_bonus": 0  # 活动效率加成
        }

        # 季节影响
        if season == "winter":
            modifiers["energy_cost"] = 1.2  # 冬天消耗更多能量
            modifiers["mood_bonus"] = -5    # 冬天心情略差
        elif season == "summer":
            modifiers["energy_cost"] = 1.1  # 夏天消耗稍多
            modifiers["activity_bonus"] = 5  # 夏天活动效率更高
        elif season == "spring":
            modifiers["mood_bonus"] = 10   # 春天心情很好
            modifiers["activity_bonus"] = 5
        elif season == "autumn":
            modifiers["mood_bonus"] = 5    # 秋天心情不错
            modifiers["activity_bonus"] = 3

        # 时间影响
        if time_of_day == "night":
            modifiers["energy_cost"] = modifiers["energy_cost"] * 0.8  # 晚上消耗较少
            modifiers["mood_bonus"] -= 10  # 晚上心情较差
        elif time_of_day == "morning":
            modifiers["mood_bonus"] += 5   # 早上心情较好
        elif time_of_day == "afternoon":
            modifiers["activity_bonus"] += 5  # 下午活动效率最高

        return modifiers

    def get_formatted_time(self) -> str:
        """获取格式化的时间字符串"""
        return self._current_time.strftime("%Y年%m月%d日 %H:%M")

    def get_day_of_year(self) -> int:
        """获取一年中的第几天"""
        return self._current_time.timetuple().tm_yday

    def get_week_of_year(self) -> int:
        """获取一年中的第几周"""
        return int(self._current_time.strftime("%W"))

    def _timer_loop(self):
        """定时器循环"""
        while not self._stop_event.is_set():
            if not self._paused and self._is_running:
                current_real_time = time.time()
                real_time_diff = current_real_time - self._last_real_time

                # 根据速度倍数计算世界时间变化
                world_time_diff_hours = real_time_diff * self._speed_multiplier / 3600

                if world_time_diff_hours >= 0.0167:  # 大约1分钟的真实时间
                    old_time = self._current_time
                    self._current_time += timedelta(hours=world_time_diff_hours)
                    self._last_real_time = current_real_time

                    # 通知监听器（只在小时级别变化时通知）
                    hours_passed = world_time_diff_hours
                    if hours_passed >= 1.0 or int(old_time.hour) != int(self._current_time.hour):
                        self._notify_listeners(old_time, hours_passed)

            time.sleep(0.1)  # 100ms检查一次

    def _notify_listeners(self, old_time: datetime, hours_passed: float):
        """通知所有时间监听器"""
        for listener in self._time_listeners:
            try:
                listener(self._current_time, hours_passed)
            except Exception as e:
                print(f"时间监听器错误: {e}")

    def __str__(self) -> str:
        status = "运行中" if self._is_running else "已停止"
        if self._paused:
            status = "已暂停"

        return f"世界时钟: {self.get_formatted_time()} | 状态: {status} | 速度: {self._speed_multiplier}x"

    def __repr__(self) -> str:
        return f"WorldClock(current_time={self._current_time}, running={self._is_running}, speed={self._speed_multiplier})"


# 全局世界时钟实例
_world_clock = None

def get_world_clock() -> WorldClock:
    """获取全局世界时钟实例"""
    global _world_clock
    if _world_clock is None:
        _world_clock = WorldClock()
    return _world_clock

def reset_world_clock(start_date: Optional[datetime] = None):
    """重置全局世界时钟"""
    global _world_clock
    _world_clock = WorldClock(start_date)
    return _world_clock
