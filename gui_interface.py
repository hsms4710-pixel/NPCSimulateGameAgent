import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import logging
import os
from dotenv import load_dotenv

from deepseek_client import DeepSeekClient
from npc_system import NPCBehaviorSystem, NPCAction, Emotion
from world_lore import NPC_TEMPLATES, ENVIRONMENTAL_EVENTS
from world_clock import get_world_clock

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

class NPCSimulatorGUI:
    """基于Tkinter的NPC模拟器GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("艾伦谷 NPC 行为模拟器")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # 初始化DeepSeek客户端（从环境变量读取API key）
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 环境变量未设置，请检查 .env 文件")
        self.deepseek_client = DeepSeekClient(api_key)

        # NPC实例
        self.npc_system: Optional[NPCBehaviorSystem] = None
        self.selected_npc_template = "elder_blacksmith"

        # 界面组件
        self.setup_ui()

        # 自动更新线程
        self.auto_update = False
        self.update_thread: Optional[threading.Thread] = None

        # 活动日志
        self.activity_log: List[str] = []

        # 初始化界面
        self.initialize_simulation()

    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 顶部控制面板
        self.create_control_panel(main_frame)

        # 主要内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # 左侧：人物卡面板
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.create_character_card(left_panel)

        # 中间：活动日志
        middle_panel = ttk.Frame(content_frame)
        middle_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.create_activity_panel(middle_panel)

        # 右侧：事件、对话和思考过程面板
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(0, 0))
        right_panel.configure(width=350)  # 固定宽度

        self.create_event_panel(right_panel)
        self.create_react_thinking_panel(right_panel)  # 新增：React思考过程面板
        self.create_dialogue_panel(right_panel)

    def create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = ttk.LabelFrame(parent, text="控制面板", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # NPC选择 - 显示中文名字
        npc_options = {key: config["name"] for key, config in NPC_TEMPLATES.items()}
        ttk.Label(control_frame, text="选择NPC:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.npc_combo = ttk.Combobox(control_frame,
                                     values=list(npc_options.values()),
                                     state="readonly",
                                     width=15)
        self.npc_combo.current(0)
        self.npc_combo.grid(row=0, column=1, padx=(0, 10))
        self.npc_combo.bind('<<ComboboxSelected>>', self.on_npc_changed)

        # 世界时间显示
        ttk.Label(control_frame, text="世界时间:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.world_time_label = ttk.Label(control_frame, text="2025-12-06 00:00", font=("Arial", 10, "bold"))
        self.world_time_label.grid(row=0, column=3, padx=(0, 20))

        # 时钟更新定时器
        self.update_world_clock_display()

        # 时钟控制按钮
        clock_frame = ttk.Frame(control_frame)
        clock_frame.grid(row=0, column=4, sticky=tk.E, padx=(10, 0))

        ttk.Button(clock_frame, text="前进1小时", command=self.advance_time_1h).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(clock_frame, text="前进30分钟", command=self.advance_time_30m).pack(side=tk.LEFT, padx=(0, 10))

        # 时钟控制
        ttk.Button(clock_frame, text="暂停", command=self.pause_world_clock).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(clock_frame, text="恢复", command=self.resume_world_clock).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(clock_frame, text="重置时钟", command=self.reset_world_clock).pack(side=tk.LEFT)

        # 推理模式选择
        ttk.Label(clock_frame, text="推理模式:").pack(side=tk.LEFT, padx=(10, 3))
        self.reasoning_mode_var = tk.StringVar(value="normal")
        reasoning_combo = ttk.Combobox(clock_frame,
                                      values=["fast", "normal", "deep", "exhaustive"],
                                      textvariable=self.reasoning_mode_var,
                                      state="readonly",
                                      width=10)
        reasoning_combo.pack(side=tk.LEFT, padx=(0, 10))

        # 重置按钮
        ttk.Button(clock_frame, text="重置模拟", command=self.reset_simulation).pack(side=tk.LEFT, padx=(10, 0))

        # 状态指示器
        self.autonomous_indicator = ttk.Label(clock_frame, text="自主运行中", foreground="green", font=("Arial", 9, "bold"))
        self.autonomous_indicator.pack(side=tk.LEFT, padx=(20, 0))

    def update_world_clock_display(self):
        """更新世界时钟显示"""
        try:
            world_clock = get_world_clock()
            time_str = world_clock.get_formatted_time()
            season = world_clock.get_season()
            time_of_day = world_clock.get_time_of_day()

            # 显示时间、季节和时段
            display_text = f"{time_str} ({season}, {time_of_day})"

            if hasattr(self, 'world_time_label'):
                self.world_time_label.config(text=display_text)

            # 每秒更新一次
            self.root.after(1000, self.update_world_clock_display)

        except Exception as e:
            # 如果出错，1秒后重试
            self.root.after(1000, self.root.after(1000, self.update_world_clock_display))

    def create_character_card(self, parent):
        """创建人物卡面板"""
        # 主容器
        card_frame = ttk.Frame(parent)
        card_frame.pack(fill=tk.BOTH, expand=True)

        # 基本信息卡片
        self.create_basic_info_card(card_frame)

        # 性格与背景卡片
        self.create_personality_card(card_frame)

        # 能力参数卡片
        self.create_abilities_card(card_frame)

        # 任务状态卡片
        self.create_tasks_card(card_frame)

        # 需求状态卡片
        self.create_needs_card(card_frame)

    def create_basic_info_card(self, parent):
        """创建基本信息卡片"""
        basic_frame = ttk.LabelFrame(parent, text="基本信息", padding=5)
        basic_frame.pack(fill=tk.X, pady=(0, 5))

        # 存储标签引用
        self.char_name_label = ttk.Label(basic_frame, text="姓名: -", font=("Arial", 10, "bold"))
        self.char_name_label.pack(anchor=tk.W)

        self.char_race_label = ttk.Label(basic_frame, text="种族: -")
        self.char_race_label.pack(anchor=tk.W)

        self.char_profession_label = ttk.Label(basic_frame, text="职业: -")
        self.char_profession_label.pack(anchor=tk.W)

        self.char_age_label = ttk.Label(basic_frame, text="年龄: -")
        self.char_age_label.pack(anchor=tk.W)

        self.char_gender_label = ttk.Label(basic_frame, text="性别: -")
        self.char_gender_label.pack(anchor=tk.W)

    def create_personality_card(self, parent):
        """创建性格与背景卡片"""
        personality_frame = ttk.LabelFrame(parent, text="性格与背景", padding=5)
        personality_frame.pack(fill=tk.X, pady=(0, 5))

        # 性格特征
        ttk.Label(personality_frame, text="性格特征:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.char_traits_label = ttk.Label(personality_frame, text="-", wraplength=280, justify=tk.LEFT)
        self.char_traits_label.pack(anchor=tk.W, pady=(0, 5))

        # 背景故事
        ttk.Label(personality_frame, text="背景故事:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.char_background_text = tk.Text(personality_frame, height=6, width=35, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 8))
        scrollbar = ttk.Scrollbar(personality_frame, orient=tk.VERTICAL, command=self.char_background_text.yview)
        self.char_background_text.configure(yscrollcommand=scrollbar.set)

        self.char_background_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_abilities_card(self, parent):
        """创建能力参数卡片"""
        abilities_frame = ttk.LabelFrame(parent, text="能力参数", padding=5)
        abilities_frame.pack(fill=tk.X, pady=(0, 5))

        self.abilities_text = tk.Text(abilities_frame, height=8, width=35, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 8))
        scrollbar = ttk.Scrollbar(abilities_frame, orient=tk.VERTICAL, command=self.abilities_text.yview)
        self.abilities_text.configure(yscrollcommand=scrollbar.set)

        self.abilities_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_tasks_card(self, parent):
        """创建任务状态卡片"""
        tasks_frame = ttk.LabelFrame(parent, text="任务状态", padding=5)
        tasks_frame.pack(fill=tk.BOTH, expand=True)

        # 当前任务（使用Text以便显示完整内容）
        ttk.Label(tasks_frame, text="当前任务:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        task_text_frame = ttk.Frame(tasks_frame)
        task_text_frame.pack(fill=tk.X, pady=(0, 5))
        self.current_task_text = tk.Text(task_text_frame, height=2, width=35, wrap=tk.WORD, 
                                         state=tk.DISABLED, font=("Arial", 8))
        self.current_task_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 保留旧标签以兼容
        self.current_task_label = ttk.Label(task_text_frame, text="-", wraplength=280, justify=tk.LEFT)
        self.current_task_label.pack_forget()  # 隐藏旧标签

        # 当前活动
        ttk.Label(tasks_frame, text="当前活动:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.current_activity_label = ttk.Label(tasks_frame, text="-", foreground="blue")
        self.current_activity_label.pack(anchor=tk.W, pady=(0, 5))

        # 长期任务
        ttk.Label(tasks_frame, text="长期任务:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.long_term_tasks_text = tk.Text(tasks_frame, height=6, width=35, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 8))
        scrollbar = ttk.Scrollbar(tasks_frame, orient=tk.VERTICAL, command=self.long_term_tasks_text.yview)
        self.long_term_tasks_text.configure(yscrollcommand=scrollbar.set)

        self.long_term_tasks_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 5))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 实时状态
        status_frame = ttk.Frame(tasks_frame)
        status_frame.pack(fill=tk.X)

        ttk.Label(status_frame, text="情感:", font=("Arial", 8, "bold")).grid(row=0, column=0, sticky=tk.W)
        self.realtime_emotion_label = ttk.Label(status_frame, text="-")
        self.realtime_emotion_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 10))

        ttk.Label(status_frame, text="能量:", font=("Arial", 8, "bold")).grid(row=1, column=0, sticky=tk.W)
        self.realtime_energy_label = ttk.Label(status_frame, text="-")
        self.realtime_energy_label.grid(row=1, column=1, sticky=tk.W, padx=(5, 10))

    def create_needs_card(self, parent):
        """创建需求状态卡片"""
        needs_frame = ttk.LabelFrame(parent, text="需求状态", padding=5)
        needs_frame.pack(fill=tk.X, pady=(0, 5))

        # 需求状态显示
        ttk.Label(needs_frame, text="生理需求:", font=("Arial", 9, "bold")).pack(anchor=tk.W)

        # 饥饿需求
        hunger_frame = ttk.Frame(needs_frame)
        hunger_frame.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(hunger_frame, text="饥饿:", width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.hunger_progress = ttk.Progressbar(hunger_frame, length=150, maximum=1.0, mode='determinate')
        self.hunger_progress.pack(side=tk.LEFT, padx=(5, 5))
        self.hunger_label = ttk.Label(hunger_frame, text="0%", width=5, anchor=tk.W)
        self.hunger_label.pack(side=tk.LEFT)

        # 疲劳需求
        fatigue_frame = ttk.Frame(needs_frame)
        fatigue_frame.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(fatigue_frame, text="疲劳:", width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.fatigue_progress = ttk.Progressbar(fatigue_frame, length=150, maximum=1.0, mode='determinate')
        self.fatigue_progress.pack(side=tk.LEFT, padx=(5, 5))
        self.fatigue_label = ttk.Label(fatigue_frame, text="0%", width=5, anchor=tk.W)
        self.fatigue_label.pack(side=tk.LEFT)

        ttk.Label(needs_frame, text="社交需求:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))

        # 社交需求
        social_frame = ttk.Frame(needs_frame)
        social_frame.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(social_frame, text="社交:", width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.social_progress = ttk.Progressbar(social_frame, length=150, maximum=1.0, mode='determinate')
        self.social_progress.pack(side=tk.LEFT, padx=(5, 5))
        self.social_label = ttk.Label(social_frame, text="0%", width=5, anchor=tk.W)
        self.social_label.pack(side=tk.LEFT)

        # 自主模式状态
        ttk.Label(needs_frame, text="自主模式:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.autonomous_status_label = ttk.Label(needs_frame, text="未启动", foreground="red")
        self.autonomous_status_label.pack(anchor=tk.W, pady=(2, 0))

    def create_event_panel(self, parent):
        """创建事件面板"""
        event_frame = ttk.LabelFrame(parent, text="事件系统", padding=5, width=250)
        event_frame.pack(fill=tk.X, pady=(0, 10))
        event_frame.pack_propagate(False)

        # 模式选择
        mode_frame = ttk.Frame(event_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 5))

        self.event_mode = tk.StringVar(value="preset")
        ttk.Radiobutton(mode_frame, text="预设事件", variable=self.event_mode,
                       value="preset", command=self.switch_event_mode).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="自由事件", variable=self.event_mode,
                       value="free", command=self.switch_event_mode).pack(side=tk.LEFT)

        # 对话模式选择
        dialogue_frame = ttk.Frame(event_frame)
        dialogue_frame.pack(fill=tk.X, pady=(0, 5))

        self.dialogue_mode = tk.StringVar(value="constrained")
        ttk.Radiobutton(dialogue_frame, text="约束对话", variable=self.dialogue_mode,
                       value="constrained").pack(side=tk.LEFT)
        ttk.Radiobutton(dialogue_frame, text="自由对话", variable=self.dialogue_mode,
                       value="free").pack(side=tk.LEFT)

        # 预设事件区域
        self.preset_frame = ttk.Frame(event_frame)
        self.preset_frame.pack(fill=tk.X, pady=(0, 5))

        # 预设事件按钮
        preset_events = [
            ("小偷闯入", "一名小偷偷偷溜进了铁匠铺，试图偷取工具"),
            ("怪物袭击", "村庄外围出现了一只受伤的狼，村民们很恐慌"),
            ("送信人到来", "一个年轻的送信人带来了王国的重要消息"),
            ("火灾事故", "酒馆厨房不小心着火了，需要立即救援"),
            ("访客拜访", "一位老朋友突然造访，想要借住几天"),
            ("健康问题", "NPC突然感到身体不适，需要治疗"),
            ("商业机会", "一个大订单的潜在客户前来洽谈"),
            ("家庭事务", "NPC的远方亲戚来信需要帮助")
        ]

        for event_name, event_desc in preset_events:
            btn = ttk.Button(self.preset_frame, text=event_name,
                           command=lambda desc=event_desc: self.trigger_preset_event(desc))
            btn.pack(fill=tk.X, pady=(0, 2))

        # 自由事件区域
        self.free_frame = ttk.Frame(event_frame)
        # 默认隐藏

        free_label = ttk.Label(self.free_frame, text="自由描述事件:")
        free_label.pack(anchor=tk.W, pady=(0, 2))

        self.free_event_text = tk.Text(self.free_frame, height=3, width=30, wrap=tk.WORD)
        self.free_event_text.pack(fill=tk.X, pady=(0, 2))

        ttk.Button(self.free_frame, text="触发自由事件",
                  command=self.trigger_free_event).pack(fill=tk.X)

        # 默认显示预设模式
        self.switch_event_mode()

    def trigger_preset_event(self, event_description):
        """触发预设事件 - 使用新的持久化架构"""
        result = self.npc_system.process_event(event_description, "preset_event")

        if result['should_respond']:
            # 显示NPC的智能回应（如果适用）
            if result['response_text']:
                self.add_dialogue_entry(self.npc_system.config["name"], result['response_text'])

            # 记录事件处理
            self.add_activity_log(
                "预设事件",
                f"触发事件：{event_description} | 影响度：{result['impact_analysis']['impact_score']}"
            )

            # 显示状态变化
            if result['state_changed']:
                self.add_activity_log("状态变化", "NPC状态已发生变化")

            if result['new_task_created']:
                self.add_activity_log("任务创建", f"新任务：{result['task_description']}")

            # 更新显示
            self.update_character_card()
        else:
            self.add_activity_log("事件过滤", f"预设事件 '{event_description}' 影响度不足，未触发响应")

    def switch_event_mode(self):
        """切换事件输入模式"""
        if self.event_mode.get() == "preset":
            self.free_frame.pack_forget()
            self.preset_frame.pack(fill=tk.X, pady=(0, 5))
        else:  # free mode
            self.preset_frame.pack_forget()
            self.free_frame.pack(fill=tk.X, pady=(0, 5))

    def trigger_free_event(self):
        """触发自由描述的事件"""
        event_description = self.free_event_text.get("1.0", tk.END).strip()
        if not event_description:
            messagebox.showwarning("警告", "请输入事件描述")
            return

        # 清除输入框
        self.free_event_text.delete("1.0", tk.END)

        # 处理事件（与预设事件相同的逻辑）
        self.trigger_preset_event(event_description)

    def _process_unified_event(self, event_content: str, event_type: str = "general"):
        """
        统一事件处理架构 - 实现完整的Agent循环

        Agent循环流程：
        1. 更新npc agent当前状态
        2. 接收事件
        3. 分析事件
        4. 做出回应
        5. 更新当前状态（设置为当前任务）
        6. 处理当前任务
        7. 更新状态
        8. 事件结束
        9. 更新当前状态
        10. 循环
        """
        # 1. 更新NPC当前状态（准备处理事件）
        self.add_activity_log("Agent循环", "开始处理新事件")

        # 2. 接收事件
        event_data = {
            "content": event_content,
            "type": event_type,
            "timestamp": self.npc_system.current_time,
            "source": "player"
        }

        # 3. 分析事件 - 让AI分析事件的性质和影响
        event_analysis = self._analyze_event_with_ai(event_data)

        # 4. 做出回应 - 生成NPC的回应
        npc_response = self._generate_response_with_ai(event_data, event_analysis)

        # 5. 更新当前状态（设置为当前任务）
        new_task = self._determine_task_from_event(event_data, event_analysis, npc_response)

        # 6. 处理当前任务
        task_result = self._execute_task(new_task)

        # 7. 更新状态
        self._update_agent_state_after_event(event_data, event_analysis, npc_response, task_result)

        # 8. 事件结束
        self.add_activity_log("Agent循环", "事件处理完成")

        # 9. 更新当前状态（准备下一个循环）
        self.update_character_card()

        # 10. 循环继续...

    def _analyze_event_with_ai(self, event_data: dict) -> dict:
        """使用AI分析事件的性质和影响"""
        prompt = f"""
请分析以下事件，并提供JSON格式的分析结果：

事件内容：{event_data['content']}
事件类型：{event_data['type']}
当前时间：{event_data['timestamp'].strftime('%H:%M')}

请从以下方面分析：
1. urgency（紧急程度：low/medium/high）
2. emotional_impact（情感影响：positive/negative/neutral）
3. requires_action（是否需要行动：true/false）
4. action_type（行动类型：observe/help/fight/flee/converse/ignore）
5. emotional_response（情感回应：calm/angry/fearful/happy/sad）

响应格式：
{{
    "urgency": "medium",
    "emotional_impact": "negative",
    "requires_action": true,
    "action_type": "observe",
    "emotional_response": "fearful"
}}
"""

        try:
            analysis_text = self.deepseek_client.generate_response(prompt)
            # 尝试解析JSON
            import json
            analysis = json.loads(analysis_text)
            return analysis
        except:
            # 如果解析失败，返回默认分析
            return {
                "urgency": "low",
                "emotional_impact": "neutral",
                "requires_action": False,
                "action_type": "converse",
                "emotional_response": "calm"
            }

    def _generate_response_with_ai(self, event_data: dict, event_analysis: dict) -> str:
        """使用AI生成NPC的智能回应"""
        current_state = {
            "current_activity": self.npc_system.current_activity.value if self.npc_system.current_activity else "空闲",
            "current_emotion": self.npc_system.current_emotion.value,
            "energy_level": self.npc_system.energy_level,
            "time": self.npc_system.current_time.strftime("%H:%M")
        }

        # 根据对话模式调整提示
        if self.dialogue_mode.get() == "free":
            # 自由模式：AI可以完全自主回应
            prompt = f"""
你正在扮演{self.npc_system.config['name']}，一个{self.npc_system.config['profession']}。
性格：{', '.join(self.npc_system.config['personality']['traits'])}
背景：{self.npc_system.config['background'][:200]}...

当前状态：
- 正在做的事情：{current_state['current_activity']}
- 当前情感：{current_state['current_emotion']}
- 能量水平：{current_state['energy_level']}/100
- 当前时间：{current_state['time']}

事件分析：
- 紧急程度：{event_analysis['urgency']}
- 情感影响：{event_analysis['emotional_impact']}
- 需要行动：{event_analysis['requires_action']}
- 行动类型：{event_analysis['action_type']}
- 情感回应：{event_analysis['emotional_response']}

玩家输入：{event_data['content']}

请作为这个NPC，对玩家的输入做出自然的回应。你的回应应该符合你的性格和当前状态，但可以根据事件内容灵活调整。
"""
        else:
            # 约束模式：考虑当前活动状态的限制
            activity_constraint = self._get_activity_constraint(current_state['current_activity'])
            prompt = f"""
你正在扮演{self.npc_system.config['name']}，一个{self.npc_system.config['profession']}。
性格：{', '.join(self.npc_system.config['personality']['traits'])}
背景：{self.npc_system.config['background'][:200]}...

当前状态：
- 正在做的事情：{current_state['current_activity']}
- 当前情感：{current_state['current_emotion']}
- 能量水平：{current_state['energy_level']}/100
- 当前时间：{current_state['time']}

活动限制：{activity_constraint}

事件分析：
- 紧急程度：{event_analysis['urgency']}
- 情感影响：{event_analysis['emotional_impact']}
- 需要行动：{event_analysis['requires_action']}
- 行动类型：{event_analysis['action_type']}
- 情感回应：{event_analysis['emotional_response']}

玩家输入：{event_data['content']}

请作为这个NPC，对玩家的输入做出回应。你的回应必须符合当前正在做的活动与人物性格，但可以根据事件紧急程度进行调整。
"""

        conversation_history = self.get_recent_dialogue_history()
        response = self.deepseek_client.generate_response(prompt)

        # 显示NPC回应
        self.add_dialogue_entry(self.npc_system.config["name"], response)

        return response

    def _get_activity_constraint(self, current_activity: str) -> str:
        """获取当前活动的约束描述"""
        # 使用NPCAction枚举的统一定义
        from npc_system import NPCAction
        try:
            # 查找匹配的活动枚举
            for action in NPCAction:
                if action.value in current_activity or current_activity.lower() in action.value.lower():
                    return action.ui_description
        except:
            pass

        # 如果查找失败，返回默认描述
        return "你可以正常回应"

    def _determine_task_from_event(self, event_data: dict, event_analysis: dict, npc_response: str) -> dict:
        """根据事件确定NPC的新任务"""
        # 如果事件需要行动，设置相应的任务
        if event_analysis.get('requires_action', False):
            action_type = event_analysis.get('action_type', 'converse')

            # 映射到NPCAction
            action_mapping = {
                "observe": NPCAction.OBSERVE,
                "help": NPCAction.HELP_OTHERS,
                "fight": NPCAction.OBSERVE,  # 暂时用观察代替
                "flee": NPCAction.TRAVEL,   # 暂时用移动代替
                "converse": None,  # 不改变当前活动
                "ignore": None     # 不改变当前活动
            }

            new_activity = action_mapping.get(action_type)
            if new_activity and new_activity != self.npc_system.current_activity:
                self.npc_system.current_activity = new_activity
                self.npc_system.activity_start_time = self.npc_system.current_time
                self.add_activity_log("任务更新", f"当前任务变更为：{new_activity.value}")

        return {
            "activity": self.npc_system.current_activity,
            "response": npc_response,
            "analysis": event_analysis
        }

    def _execute_task(self, task: dict) -> dict:
        """执行当前任务"""
        # 这里可以添加更复杂的任务执行逻辑
        # 目前只是记录任务执行
        activity = task.get('activity')
        if activity:
            self.add_activity_log("任务执行", f"正在执行：{activity.value}")

        return {"status": "completed", "activity": activity}

    def _update_agent_state_after_event(self, event_data: dict, event_analysis: dict, npc_response: str, task_result: dict):
        """事件处理后更新Agent状态"""
        # 更新情感状态
        emotional_response = event_analysis.get('emotional_response', 'calm')
        emotion_mapping = {
            "calm": Emotion.CALM,
            "angry": Emotion.ANGRY,
            "fearful": Emotion.WORRIED,
            "happy": Emotion.HAPPY,
            "sad": Emotion.SAD
        }

        if emotional_response in emotion_mapping:
            self.npc_system.current_emotion = emotion_mapping[emotional_response]

        # 更新能量水平（事件处理会消耗一些能量）
        energy_cost = 5  # 基础消耗
        if event_analysis.get('urgency') == 'high':
            energy_cost = 15  # 紧急事件消耗更多
        elif event_analysis.get('urgency') == 'medium':
            energy_cost = 10

        self.npc_system.energy_level = max(0, self.npc_system.energy_level - energy_cost)

        # 添加记忆
        memory_content = f"事件：{event_data['content']}，回应：{npc_response[:50]}..."
        emotional_impact = 0
        if event_analysis.get('emotional_impact') == 'positive':
            emotional_impact = 2
        elif event_analysis.get('emotional_impact') == 'negative':
            emotional_impact = -2

        self.npc_system.add_memory(
            memory_content,
            emotional_impact=emotional_impact,
            importance=5 if event_analysis.get('urgency') == 'high' else 3,
            tags=["event", event_data['type'], event_analysis.get('action_type', 'unknown')]
        )

        # 更新互动关系（如果是对话事件）
        if event_data['type'] == 'dialogue':
            self.npc_system.interact_with_other("player", "conversation")

    def create_activity_panel(self, parent):
        """创建活动日志面板"""
        activity_frame = ttk.LabelFrame(parent, text="活动日志", padding=10)
        activity_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.activity_text = scrolledtext.ScrolledText(
            activity_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=15
        )
        self.activity_text.pack(fill=tk.BOTH, expand=True)
        self.activity_text.config(state=tk.DISABLED)

    def create_dialogue_panel(self, parent):
        """创建对话面板"""
        dialogue_frame = ttk.LabelFrame(parent, text="对话与互动", padding=10)
        dialogue_frame.pack(fill=tk.BOTH, expand=True)

        # 对话历史
        self.dialogue_text = scrolledtext.ScrolledText(
            dialogue_frame,
            wrap=tk.WORD,
            font=("Arial", 9),
            height=8
        )
        self.dialogue_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.dialogue_text.config(state=tk.DISABLED)

        # 输入区域
        input_frame = ttk.Frame(dialogue_frame)
        input_frame.pack(fill=tk.X)

        self.input_entry = ttk.Entry(input_frame, font=("Arial", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", self.send_message)

        ttk.Button(input_frame, text="发送", command=self.send_message).pack(side=tk.RIGHT)

    def initialize_simulation(self):
        """初始化模拟"""
        try:
            # 启动世界时钟
            world_clock = get_world_clock()
            if not world_clock.is_running:
                world_clock.start()
                self.add_activity_log("系统", f"世界时钟已启动: {world_clock.get_formatted_time()}")

            npc_config = NPC_TEMPLATES[self.selected_npc_template]
            self.npc_system = NPCBehaviorSystem(npc_config, self.deepseek_client)
            
            # 设置GUI更新回调，让自主行为循环能通知GUI更新
            self.npc_system.gui_update_callback = self.update_character_card
            
            # 设置React思考过程回调
            self.npc_system.gui_react_thinking_callback = self.add_react_thinking

            self.update_character_card()
            self.update_status_display()
            self.add_activity_log("系统", f"NPC {npc_config['name']} 已初始化")
            self.add_activity_log("系统", "模拟器准备就绪")

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            messagebox.showerror("错误", f"初始化失败: {str(e)}")

    def on_npc_changed(self, event):
        """NPC选择改变事件"""
        # 根据显示的名字找到对应的模板key
        selected_name = self.npc_combo.get()
        for key, config in NPC_TEMPLATES.items():
            if config["name"] == selected_name:
                self.selected_npc_template = key
                break

        self.initialize_simulation()

    def update_status_display(self):
        """更新状态显示"""
        # 现在所有状态显示都通过update_character_card处理
        # 这个方法保留以保持兼容性，但实际上调用update_character_card
        self.update_character_card()

    def add_activity_log(self, source: str, message: str):
        """添加活动日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {source}: {message}\n"

        self.activity_log.append(log_entry)
        if len(self.activity_log) > 100:  # 限制日志数量
            self.activity_log = self.activity_log[-100:]

        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.insert(tk.END, log_entry)
        self.activity_text.see(tk.END)
        self.activity_text.config(state=tk.DISABLED)

        logger.info(f"Activity: {source} - {message}")

    def advance_time_1h(self):
        """前进1小时"""
        self.advance_time(hours=1)

    def advance_time_30m(self):
        """前进30分钟"""
        self.advance_time(hours=0.5)

    def advance_time(self, hours: float):
        """前进指定小时数 - 使用智能任务系统"""
        if not self.npc_system:
            return

        try:
            world_clock = get_world_clock()
            new_time = world_clock.current_time + timedelta(hours=hours)

            # 更新世界时钟
            world_clock.advance_time(hours)

            # 更新NPC时间（这会处理任务进度和状态变化）
            self.npc_system.update_time(new_time)

            # 显示时间流逝的总结
            # 获取当前任务信息
            current_task = self.npc_system.persistence.current_task
            current_activity_enum = self.npc_system.current_activity
            
            # 获取具体的活动内容
            current_activity = "未知"
            if current_task and current_task.status == "active":
                task_description = current_task.description
                progress_pct = int(current_task.progress * 100)
                
                # 根据任务类型显示合适的活动描述
                if current_task.task_type == 'event_response':
                    current_activity = f"处理事件: {task_description[:20]}... ({progress_pct}%)"
                else:
                    current_activity = f"{task_description[:20]}... ({progress_pct}%)"
            elif current_activity_enum:
                # 如果没有当前任务，显示活动状态
                current_activity = current_activity_enum.value
            else:
                # 从持久化状态获取
                primary_state = self.npc_system.persistence.current_state.primary_state
                activity_map = {
                    "sleep": "睡觉",
                    "rest": "休息",
                    "work": "工作",
                    "socialize": "社交",
                    "eat": "吃饭",
                    "observe": "观察",
                    "pray": "祈祷",
                    "learn": "学习",
                    "create": "创造",
                    "help_others": "帮助他人"
                }
                current_activity = activity_map.get(primary_state, f"{primary_state}中")

            time_summary = f"经过 {hours} 小时 | 活动: {current_activity}"

            self.add_activity_log("时间流逝", time_summary)

            # 更新显示
            self.update_character_card()

        except Exception as e:
            logger.error(f"时间前进失败: {e}")
            messagebox.showerror("错误", f"时间前进失败: {str(e)}")

    def pause_world_clock(self):
        """暂停世界时钟"""
        world_clock = get_world_clock()
        world_clock.pause()
        self.add_activity_log("时钟控制", "世界时钟已暂停")

    def resume_world_clock(self):
        """恢复世界时钟"""
        world_clock = get_world_clock()
        world_clock.resume()
        self.add_activity_log("时钟控制", "世界时钟已恢复")

    def reset_world_clock(self):
        """重置世界时钟"""
        from world_clock import reset_world_clock
        from datetime import datetime

        # 重置到默认时间
        reset_world_clock(datetime(2025, 12, 6, 0, 0, 0))
        new_clock = get_world_clock()
        new_clock.start()

        self.add_activity_log("时钟控制", f"世界时钟已重置到: {new_clock.get_formatted_time()}")

        # 更新NPC时间
        if self.npc_system:
            self.npc_system.update_time(new_clock.current_time)

    def trigger_random_event(self):
        """触发随机世界事件"""
        if not self.npc_system:
            return

        from world_lore import ENVIRONMENTAL_EVENTS

        # 随机选择事件类型
        event_types = ["weather", "seasons", "town_events", "personal_events"]
        event_category = random.choice(event_types)

        if event_category == "weather":
            event = random.choice(ENVIRONMENTAL_EVENTS["weather"])
            event_desc = f"天气变化：今天是{event}的天气"
        elif event_category == "seasons":
            season = random.choice(ENVIRONMENTAL_EVENTS["seasons"])
            event_desc = f"季节变化：现在是{season}季节"
        elif event_category == "town_events":
            event = random.choice(ENVIRONMENTAL_EVENTS["town_events"])
            event_desc = f"小镇事件：{event.replace('_', ' ')}"
        else:
            event = random.choice(ENVIRONMENTAL_EVENTS["personal_events"])
            event_desc = f"个人事件：{event.replace('_', ' ')}"

        # NPC响应事件
        try:
            response = self.npc_system.respond_to_world_event(event_desc)
            self.add_activity_log(
                "世界事件",
                f"{event_desc}\nNPC反应: {response.get('thoughts', '无反应')}"
            )

            self.update_status_display()

        except Exception as e:
            logger.error(f"事件处理失败: {e}")
            self.add_activity_log("错误", f"处理事件失败: {str(e)}")

    def send_message(self, event=None):
        """发送消息给NPC - 统一事件处理架构"""
        if not self.npc_system:
            return

        message = self.input_entry.get().strip()
        if not message:
            return

        self.input_entry.delete(0, tk.END)

        # 显示玩家消息
        self.add_dialogue_entry("玩家", message)

        try:
            # 使用React Agent推理
            reasoning_mode = self._get_reasoning_mode()
            result = self.npc_system.process_event(message, "dialogue", reasoning_mode)

            if result['should_respond']:
                # 显示NPC的智能回应
                self.add_dialogue_entry(self.npc_system.config["name"], result['response_text'])

                # 显示推理信息
                if 'reasoning_steps' in result and result['reasoning_steps'] > 0:
                    reasoning_info = f"推理步骤: {result['reasoning_steps']} | 置信度: {result['confidence']:.2f}"
                    self.add_activity_log("推理过程", reasoning_info)

                # 显示状态变化信息
                if result['state_changed']:
                    status_summary = self.npc_system.persistence.get_full_state_summary()
                    state_info = f"状态已改变为：{status_summary['current_state']['primary_state']}"
                    if status_summary['current_state']['current_task']:
                        task = status_summary['current_state']['current_task']
                        state_info += f" | 当前任务：{task['description']}"
                    self.add_activity_log("状态变化", state_info)

                if result['new_task_created']:
                    self.add_activity_log("任务创建", f"新任务：{result['task_description']}")

                # 更新显示
                self.update_character_card()

            else:
                # 不需要回应的低影响事件
                self.add_activity_log("事件过滤", f"事件 '{message}' 影响度不足，未触发响应")

        except Exception as e:
            logger.error(f"事件处理失败: {e}")
            self.add_dialogue_entry("系统", f"事件处理失败: {str(e)}")

    def _is_player_event(self, message: str) -> bool:
        """检查玩家输入是否是重要事件"""
        # 事件关键词
        event_keywords = [
            "小偷", "闯进", "入侵", "攻击", "火灾", "地震", "洪水",
            "盗贼", "强盗", "怪物", "野兽", "事故", "事件", "危机",
            "拜访", "来访", "客人", "访客", "送信", "送信人"
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in event_keywords)

    def _get_reasoning_mode(self) -> ReasoningMode:
        """获取当前选择的推理模式"""
        mode_str = self.reasoning_mode_var.get() if hasattr(self, 'reasoning_mode_var') else "normal"
        mode_map = {
            "fast": ReasoningMode.FAST,
            "normal": ReasoningMode.NORMAL,
            "deep": ReasoningMode.DEEP,
            "exhaustive": ReasoningMode.EXHAUSTIVE
        }
        return mode_map.get(mode_str, ReasoningMode.NORMAL)

    def _handle_player_event(self, event_description: str):
        """处理玩家描述的事件 - 使用React Agent推理"""
        reasoning_mode = self._get_reasoning_mode()
        result = self.npc_system.process_event(event_description, "world_event", reasoning_mode)

        if result['should_respond']:
            # 显示NPC的智能回应
            self.add_dialogue_entry(self.npc_system.config["name"], result['response_text'])

            # 显示推理信息
            if 'reasoning_steps' in result and result['reasoning_steps'] > 0:
                reasoning_info = f"推理步骤: {result['reasoning_steps']} | 置信度: {result['confidence']:.2f}"
                self.add_activity_log("推理过程", reasoning_info)

            # 记录事件处理
            self.add_activity_log(
                "世界事件",
                f"触发事件：{event_description} | 影响度：{result['impact_analysis']['impact_score']}"
            )

            # 显示状态变化
            if result['state_changed']:
                self.add_activity_log("状态变化", "NPC状态已发生变化")

            if result['new_task_created']:
                self.add_activity_log("任务创建", f"新任务：{result['task_description']}")

            # 更新显示
            self.update_character_card()
        else:
            self.add_activity_log("事件过滤", f"事件 '{event_description}' 影响度不足，未触发响应")


    def add_dialogue_entry(self, speaker: str, message: str):
        """添加对话条目"""
        timestamp = datetime.now().strftime("%H:%M")
        dialogue_entry = f"[{timestamp}] {speaker}: {message}\n"

        self.dialogue_text.config(state=tk.NORMAL)
        self.dialogue_text.insert(tk.END, dialogue_entry)
        self.dialogue_text.see(tk.END)
        self.dialogue_text.config(state=tk.DISABLED)

    def get_recent_dialogue_history(self) -> List[Dict[str, str]]:
        """获取最近的对话历史"""
        # 从dialogue_text中提取最近的对话
        dialogue_content = self.dialogue_text.get(1.0, tk.END)
        lines = dialogue_content.strip().split('\n')

        history = []
        for line in lines[-10:]:  # 最近10条消息
            if ': ' in line:
                timestamp_speaker, message = line.split(': ', 1)
                if '] ' in timestamp_speaker:
                    speaker = timestamp_speaker.split('] ')[1]
                    history.append({
                        "role": "user" if speaker == "玩家" else "assistant",
                        "content": message
                    })

        return history

    def toggle_auto_mode(self):
        """切换自动模式"""
        self.auto_update = not self.auto_update

        if self.auto_update:
            self.start_auto_update()
        else:
            self.stop_auto_update()

    def start_auto_update(self):
        """开始自动更新"""
        if self.update_thread and self.update_thread.is_alive():
            return

        self.update_thread = threading.Thread(target=self.auto_update_loop, daemon=True)
        self.update_thread.start()
        self.add_activity_log("系统", "自动模式已启动")

    def stop_auto_update(self):
        """停止自动更新"""
        self.auto_update = False
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
        self.add_activity_log("系统", "自动模式已停止")

    def auto_update_loop(self):
        """自动更新循环"""
        while self.auto_update:
            try:
                # 在主线程中执行UI更新
                self.root.after(0, self.advance_time_30m)
                time.sleep(3)  # 每3秒前进30分钟
            except Exception as e:
                logger.error(f"自动更新错误: {e}")
                break

    def reset_simulation(self):
        """重置模拟"""
        self.stop_auto_update()
        
        # 停止NPC的自主行为
        if self.npc_system:
            self.npc_system.stop_autonomous_behavior()
            # 清除当前任务和活动状态
            if hasattr(self.npc_system, 'persistence'):
                self.npc_system.persistence.clear_current_task()
                self.npc_system.persistence.clear_all_event_tasks()
            # 重置活动状态
            self.npc_system.current_activity = None
            self.npc_system.activity_start_time = None
        
        # 清除GUI日志
        self.activity_log.clear()
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.delete(1.0, tk.END)
        self.activity_text.config(state=tk.DISABLED)

        self.dialogue_text.config(state=tk.NORMAL)
        self.dialogue_text.delete(1.0, tk.END)
        self.dialogue_text.config(state=tk.DISABLED)

        # 重新初始化
        self.initialize_simulation()

    def start_autonomous_mode(self):
        """启动NPC自主行为模式"""
        try:
            if not self.npc_system.autonomous_mode:
                self.npc_system.start_autonomous_behavior()
                self.add_activity_log("系统", "NPC自主行为模式已启动")
                self.update_character_card()
            else:
                self.add_activity_log("系统", "自主行为模式已在运行中")

        except Exception as e:
            self.add_activity_log("错误", f"启动自主模式失败: {str(e)}")

    def stop_autonomous_mode(self):
        """停止NPC自主行为模式"""
        try:
            if self.npc_system.autonomous_mode:
                self.npc_system.stop_autonomous_behavior()
                self.add_activity_log("系统", "NPC自主行为模式已停止")
                self.update_character_card()
            else:
                self.add_activity_log("系统", "自主行为模式未在运行")

        except Exception as e:
            self.add_activity_log("错误", f"停止自主模式失败: {str(e)}")

    def update_character_card(self):
        """更新人物卡显示"""
        if not self.npc_system:
            return

        config = self.npc_system.config

        # 基本信息
        self.char_name_label.config(text=f"姓名: {config['name']}")
        self.char_race_label.config(text=f"种族: {config['race']}")
        self.char_profession_label.config(text=f"职业: {config['profession']}")
        self.char_age_label.config(text=f"年龄: {config['age']}")
        self.char_gender_label.config(text=f"性别: {config['gender']}")

        # 性格特征
        traits = config['personality']['traits']
        traits_text = ", ".join(traits)
        self.char_traits_label.config(text=traits_text)

        # 背景故事
        background = config['background']
        self.char_background_text.config(state=tk.NORMAL)
        self.char_background_text.delete(1.0, tk.END)
        self.char_background_text.insert(tk.END, background)
        self.char_background_text.config(state=tk.DISABLED)

        # 能力参数
        skills = config.get('skills', {})
        self.abilities_text.config(state=tk.NORMAL)
        self.abilities_text.delete(1.0, tk.END)

        for skill_name, skill_value in skills.items():
            # 将技能名翻译为中文
            skill_translations = {
                "forging": "锻造",
                "weapon_crafting": "武器制作",
                "repair": "修理",
                "teaching": "教学",
                "negotiation": "谈判",
                "cooking": "烹饪",
                "brewing": "酿酒",
                "storytelling": "讲故事",
                "conflict_resolution": "冲突解决",
                "business_management": "经营管理",
                "healing": "治疗",
                "divination": "占卜",
                "counseling": "咨询",
                "ancient_knowledge": "古代知识",
                "mediation": "调解"
            }

            chinese_name = skill_translations.get(skill_name, skill_name)
            self.abilities_text.insert(tk.END, f"{chinese_name}: {skill_value}\n")

        self.abilities_text.config(state=tk.DISABLED)

        # 任务状态
        status = self.npc_system.get_status_summary()

        # 当前活动 - 用颜色标注不同状态
        activity_colors = {
            "睡觉": "#4A90E2",  # 蓝色 - 休息状态
            "休息": "#7ED321",  # 绿色 - 放松状态
            "工作": "#F5A623",  # 橙色 - 活动状态
            "社交": "#BD10E0",  # 紫色 - 社交状态
            "吃饭": "#50E3C2",  # 青色 - 日常状态
            "观察": "#D0021B",  # 红色 - 警惕状态
            "帮助他人": "#9013FE", # 深紫色 - 利他状态
            "思考": "#B8E986",   # 浅绿色 - 反思状态
            "祈祷": "#F8E71C",   # 黄色 - 精神状态
            "学习": "#FF6B6B",   # 粉色 - 成长状态
        }

        # 获取当前活动名称
        current_activity_enum = self.npc_system.current_activity
        if current_activity_enum:
            activity_name = current_activity_enum.value
        else:
            activity_name = "未知"

        # 设置颜色
        color = activity_colors.get(activity_name, "#666666")  # 默认灰色

        # 显示活动和颜色
        self.current_activity_label.configure(foreground=color)
        self.current_activity_label.config(text=f"当前活动: {activity_name}")

        # 更新当前任务显示（使用Text显示完整内容）
        current_task_data = None
        if self.npc_system.persistence.current_task:
            current_task_data = {
                'description': self.npc_system.persistence.current_task.description,
                'progress': self.npc_system.persistence.current_task.progress,
                'task_type': self.npc_system.persistence.current_task.task_type
            }
        
        if current_task_data:
            task_desc = current_task_data.get('description', '未知任务')
            progress = current_task_data.get('progress', 0) * 100
            # 使用Text显示完整任务描述
            self.current_task_text.config(state=tk.NORMAL)
            self.current_task_text.delete("1.0", tk.END)
            self.current_task_text.insert("1.0", f"{task_desc}\n进度: {progress:.0f}%")
            self.current_task_text.config(state=tk.DISABLED)
            # 如果有任务，在活动标签中显示任务状态
            if current_task_data.get('task_type') == 'event_response':
                self.current_activity_label.config(
                    text=f"当前活动: {activity_name} | 处理事件中"
                )
            else:
                self.current_activity_label.config(
                    text=f"当前活动: {activity_name} | 任务进行中"
                )
        else:
            self.current_task_text.config(state=tk.NORMAL)
            self.current_task_text.delete("1.0", tk.END)
            self.current_task_text.insert("1.0", "无")
            self.current_task_text.config(state=tk.DISABLED)
            # 如果没有任务，只显示活动
            self.current_activity_label.config(text=f"当前活动: {activity_name}")

        # 长期任务
        self.long_term_tasks_text.config(state=tk.NORMAL)
        self.long_term_tasks_text.delete(1.0, tk.END)

        long_term_goals = self.npc_system.long_term_goals
        for goal in long_term_goals:
            progress_percent = int(goal.progress * 100)
            status_text = "进行中" if goal.status == "active" else goal.status
            self.long_term_tasks_text.insert(tk.END, f"• {goal.description}\n  进度: {progress_percent}% | 状态: {status_text}\n\n")

        self.long_term_tasks_text.config(state=tk.DISABLED)

        # 实时状态
        self.realtime_emotion_label.config(text=status['current_emotion'])
        self.realtime_energy_label.config(text=f"{status['energy_level']}/100")

        # 更新需求状态
        if hasattr(self.npc_system, 'need_system'):
            needs = self.npc_system.need_system.needs

            # 更新进度条和标签
            self.hunger_progress['value'] = needs.hunger
            self.hunger_label.config(text=f"{needs.hunger:.0%}")

            self.fatigue_progress['value'] = needs.fatigue
            self.fatigue_label.config(text=f"{needs.fatigue:.0%}")

            self.social_progress['value'] = needs.social
            self.social_label.config(text=f"{needs.social:.0%}")

        # 更新自主模式状态
        if hasattr(self.npc_system, 'autonomous_mode'):
            if self.npc_system.autonomous_mode:
                self.autonomous_status_label.config(text="运行中", foreground="green")
            else:
                self.autonomous_status_label.config(text="未启动", foreground="red")

    def on_closing(self):
        """窗口关闭处理"""
        self.stop_auto_update()
        self.root.destroy()

def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('npc_simulator.log'),
            logging.StreamHandler()
        ]
    )

    # 创建主窗口
    root = tk.Tk()
    app = NPCSimulatorGUI(root)

    # 设置关闭处理
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    main()
