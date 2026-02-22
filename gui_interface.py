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

from backend.deepseek_client import DeepSeekClient
from npc_core import NPCBehaviorSystem
from core_types import NPCAction, Emotion
from world_simulator.world_lore import NPC_TEMPLATES, ENVIRONMENTAL_EVENTS
from world_simulator.world_clock import get_world_clock
from npc_optimization.event_coordinator import EventCoordinator, NPCRole, NPCEventResponse, EventAnalysis
import asyncio

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# API 配置文件路径
API_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "api_config.json")

# 默认 API 配置
DEFAULT_API_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "api_base": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
}


def load_api_config() -> dict:
    """加载 API 配置"""
    if os.path.exists(API_CONFIG_FILE):
        try:
            with open(API_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 合并默认配置
                return {**DEFAULT_API_CONFIG, **config}
        except Exception as e:
            logger.warning(f"加载 API 配置失败: {e}")
    return DEFAULT_API_CONFIG.copy()


def save_api_config(config: dict) -> bool:
    """保存 API 配置"""
    try:
        with open(API_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存 API 配置失败: {e}")
        return False


class APIConfigDialog:
    """API 配置对话框"""

    def __init__(self, parent, current_config: dict, on_save_callback=None):
        self.result = None
        self.on_save_callback = on_save_callback

        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("API 配置")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.current_config = current_config
        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(main_frame, text="大模型 API 配置", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # 配置表单
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=(0, 20))

        # 提供商选择
        ttk.Label(form_frame, text="API 提供商:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.provider_var = tk.StringVar(value=self.current_config.get("provider", "deepseek"))
        provider_combo = ttk.Combobox(form_frame, textvariable=self.provider_var,
                                       values=["deepseek", "openai", "custom"],
                                       state="readonly", width=40)
        provider_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        provider_combo.bind("<<ComboboxSelected>>", self.on_provider_changed)

        # API Key
        ttk.Label(form_frame, text="API Key:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar(value=self.current_config.get("api_key", ""))
        self.api_key_entry = ttk.Entry(form_frame, textvariable=self.api_key_var, width=43, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # 显示/隐藏密钥按钮
        self.show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="显示", variable=self.show_key,
                        command=self.toggle_key_visibility).grid(row=1, column=2, padx=(5, 0))

        # API Base URL
        ttk.Label(form_frame, text="API Base URL:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.api_base_var = tk.StringVar(value=self.current_config.get("api_base", "https://api.deepseek.com/v1"))
        self.api_base_entry = ttk.Entry(form_frame, textvariable=self.api_base_var, width=43)
        self.api_base_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # 模型选择
        ttk.Label(form_frame, text="模型:", font=("Arial", 10)).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.model_var = tk.StringVar(value=self.current_config.get("model", "deepseek-chat"))
        self.model_combo = ttk.Combobox(form_frame, textvariable=self.model_var, width=40)
        self.model_combo.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        self.update_model_options()

        # 测试连接状态
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.pack(fill=tk.X, pady=(0, 20))

        self.status_label = ttk.Label(self.status_frame, text="", font=("Arial", 9))
        self.status_label.pack(side=tk.LEFT)

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="测试连接", command=self.test_connection).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.RIGHT)

        # 帮助信息
        help_frame = ttk.LabelFrame(main_frame, text="帮助", padding=10)
        help_frame.pack(fill=tk.X, pady=(20, 0))

        help_text = """• DeepSeek: 访问 https://platform.deepseek.com/ 获取 API Key
• OpenAI: 访问 https://platform.openai.com/ 获取 API Key
• 配置将保存到本地 api_config.json 文件"""
        ttk.Label(help_frame, text=help_text, font=("Arial", 9), foreground="gray").pack(anchor=tk.W)

    def toggle_key_visibility(self):
        """切换密钥可见性"""
        if self.show_key.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")

    def on_provider_changed(self, event=None):
        """提供商变更时更新默认值"""
        provider = self.provider_var.get()
        if provider == "deepseek":
            self.api_base_var.set("https://api.deepseek.com/v1")
            self.model_var.set("deepseek-chat")
        elif provider == "openai":
            self.api_base_var.set("https://api.openai.com/v1")
            self.model_var.set("gpt-3.5-turbo")
        self.update_model_options()

    def update_model_options(self):
        """更新模型选项"""
        provider = self.provider_var.get()
        if provider == "deepseek":
            models = ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]
        elif provider == "openai":
            models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]
        else:
            models = ["custom-model"]
        self.model_combo["values"] = models

    def test_connection(self):
        """测试 API 连接"""
        api_key = self.api_key_var.get().strip()
        api_base = self.api_base_var.get().strip()
        model = self.model_var.get().strip()

        if not api_key:
            self.status_label.config(text="❌ 请输入 API Key", foreground="red")
            return

        self.status_label.config(text="⏳ 正在测试连接...", foreground="blue")
        self.dialog.update()

        # 在线程中测试连接
        def do_test():
            try:
                client = DeepSeekClient(api_key=api_key, model=model)
                # 如果有自定义 base_url，需要修改
                if api_base and api_base != "https://api.deepseek.com/v1":
                    client.base_url = api_base

                response = client.generate_response("你好", max_tokens=10)
                if response:
                    self.dialog.after(0, lambda: self.status_label.config(
                        text=f"✅ 连接成功！模型响应正常", foreground="green"))
                else:
                    self.dialog.after(0, lambda: self.status_label.config(
                        text="❌ 连接失败：无响应", foreground="red"))
            except Exception as e:
                error_msg = str(e)[:50]
                self.dialog.after(0, lambda: self.status_label.config(
                    text=f"❌ 连接失败: {error_msg}", foreground="red"))

        threading.Thread(target=do_test, daemon=True).start()

    def save_config(self):
        """保存配置"""
        config = {
            "provider": self.provider_var.get(),
            "api_key": self.api_key_var.get().strip(),
            "api_base": self.api_base_var.get().strip(),
            "model": self.model_var.get().strip()
        }

        if not config["api_key"]:
            messagebox.showerror("错误", "请输入 API Key")
            return

        if save_api_config(config):
            self.result = config
            messagebox.showinfo("成功", "API 配置已保存！")
            if self.on_save_callback:
                self.on_save_callback(config)
            self.dialog.destroy()
        else:
            messagebox.showerror("错误", "保存配置失败")

    def cancel(self):
        """取消"""
        self.result = None
        self.dialog.destroy()


class WorldCreatorDialog:
    """世界创建对话框"""

    THEMES = {
        "medieval_fantasy": "中世纪奇幻",
        "eastern_martial": "东方武侠",
        "steampunk": "蒸汽朋克",
        "post_apocalyptic": "末世废土"
    }

    def __init__(self, parent, deepseek_client, on_world_created=None):
        self.result = None
        self.deepseek_client = deepseek_client
        self.on_world_created = on_world_created
        self.generator = None
        self.is_generating = False

        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("创建新世界")
        self.dialog.geometry("600x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 600) // 2
        y = (self.dialog.winfo_screenheight() - 500) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(main_frame, text="创建你的世界", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # 世界主题
        theme_frame = ttk.LabelFrame(main_frame, text="世界主题", padding=10)
        theme_frame.pack(fill=tk.X, pady=(0, 15))

        self.theme_var = tk.StringVar(value="medieval_fantasy")
        for theme_key, theme_name in self.THEMES.items():
            rb = ttk.Radiobutton(
                theme_frame,
                text=theme_name,
                variable=self.theme_var,
                value=theme_key
            )
            rb.pack(side=tk.LEFT, padx=10)

        # 世界描述
        desc_frame = ttk.LabelFrame(main_frame, text="世界描述", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.description_text = scrolledtext.ScrolledText(
            desc_frame,
            height=6,
            font=("Arial", 10),
            wrap=tk.WORD
        )
        self.description_text.pack(fill=tk.BOTH, expand=True)
        self.description_text.insert(
            tk.END,
            "一个被古老魔法笼罩的神秘山谷小镇，居民们世代守护着一颗沉睡的龙蛋..."
        )

        # NPC数量
        npc_frame = ttk.Frame(main_frame)
        npc_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(npc_frame, text="NPC数量:").pack(side=tk.LEFT, padx=(0, 10))
        self.npc_count_var = tk.IntVar(value=5)
        npc_spinbox = ttk.Spinbox(
            npc_frame,
            from_=3,
            to=10,
            textvariable=self.npc_count_var,
            width=5
        )
        npc_spinbox.pack(side=tk.LEFT)

        # 状态标签
        self.status_label = ttk.Label(main_frame, text="", font=("Arial", 9))
        self.status_label.pack(pady=(0, 10))

        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 15))

        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        self.generate_btn = ttk.Button(
            btn_frame,
            text="生成世界",
            command=self.start_generation
        )
        self.generate_btn.pack(side=tk.RIGHT, padx=(10, 0))

        ttk.Button(
            btn_frame,
            text="取消",
            command=self.cancel
        ).pack(side=tk.RIGHT)

    def start_generation(self):
        """开始生成世界"""
        if self.is_generating:
            return

        description = self.description_text.get("1.0", tk.END).strip()
        if not description:
            messagebox.showerror("错误", "请输入世界描述")
            return

        self.is_generating = True
        self.generate_btn.config(state=tk.DISABLED)
        self.status_label.config(text="正在使用AI生成世界...")
        self.progress_var.set(10)

        # 在后台线程中生成
        threading.Thread(target=self._do_generate, daemon=True).start()

    def _do_generate(self):
        """在后台线程中生成世界"""
        try:
            from world_simulator.world_generator import WorldGenerator, WorldTheme

            theme = self.theme_var.get()
            description = self.description_text.get("1.0", tk.END).strip()
            npc_count = self.npc_count_var.get()

            # 更新状态
            self.dialog.after(0, lambda: self.status_label.config(text="正在初始化世界生成器..."))
            self.dialog.after(0, lambda: self.progress_var.set(20))

            # 创建生成器
            self.generator = WorldGenerator(llm_client=self.deepseek_client)

            # 更新状态
            self.dialog.after(0, lambda: self.status_label.config(text="正在生成世界背景..."))
            self.dialog.after(0, lambda: self.progress_var.set(40))

            # 运行异步生成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                theme_enum = WorldTheme(theme)
                world_config, locations, npcs = loop.run_until_complete(
                    self.generator.generate_world(
                        user_description=description,
                        theme=theme_enum,
                        npc_count=npc_count
                    )
                )

                # 更新状态
                self.dialog.after(0, lambda: self.status_label.config(text="正在保存世界..."))
                self.dialog.after(0, lambda: self.progress_var.set(80))

                # 保存世界
                save_path = self.generator.save_world()

                # 完成
                self.dialog.after(0, lambda: self.progress_var.set(100))
                self.dialog.after(0, lambda: self._on_generation_complete(
                    world_config, locations, npcs, save_path
                ))

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"世界生成失败: {e}")
            self.dialog.after(0, lambda: self._on_generation_error(str(e)))

    def _on_generation_complete(self, world_config, locations, npcs, save_path):
        """生成完成"""
        self.is_generating = False
        self.generate_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"世界 '{world_config.world_name}' 创建成功!")

        self.result = {
            "world_config": world_config,
            "locations": locations,
            "npcs": npcs,
            "save_path": save_path
        }

        messagebox.showinfo(
            "成功",
            f"世界 '{world_config.world_name}' 创建成功!\n"
            f"位置数量: {len(locations)}\n"
            f"NPC数量: {len(npcs)}\n"
            f"保存路径: {save_path}"
        )

        if self.on_world_created:
            self.on_world_created(self.result)

        self.dialog.destroy()

    def _on_generation_error(self, error_msg):
        """生成失败"""
        self.is_generating = False
        self.generate_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"生成失败: {error_msg[:50]}")
        self.progress_var.set(0)
        messagebox.showerror("错误", f"世界生成失败:\n{error_msg}")

    def cancel(self):
        """取消"""
        if self.is_generating:
            if not messagebox.askyesno("确认", "正在生成中，确定要取消吗？"):
                return
        self.result = None
        self.dialog.destroy()


class NPCSimulatorGUI:
    """基于Tkinter的NPC模拟器GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("艾伦谷 NPC 行为模拟器")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # 加载 API 配置
        self.api_config = load_api_config()

        # 初始化 DeepSeek 客户端
        self.deepseek_client = None
        if not self._init_api_client():
            # 如果没有配置 API Key，显示配置对话框
            self.root.withdraw()  # 暂时隐藏主窗口
            self._show_initial_config_dialog()
            self.root.deiconify()  # 重新显示主窗口

        # NPC实例
        self.npc_system: Optional[NPCBehaviorSystem] = None
        self.selected_npc_template = "elder_blacksmith"

        # EventCoordinator（主Agent）用于多NPC事件协调
        self.event_coordinator: Optional[EventCoordinator] = None

        # 是否使用ReAct模式处理事件
        self.use_react_mode = True

        # 界面组件
        self.setup_ui()

        # 自动更新线程
        self.auto_update = False
        self.update_thread: Optional[threading.Thread] = None

        # 活动日志
        self.activity_log: List[str] = []

        # Token 统计信息
        self.token_stats = {
            "total_tokens_sent": 0,
            "total_tokens_received": 0,
            "total_api_calls": 0,
            "session_start_time": datetime.now(),
            "compression_ratio": 1.0,
            "estimated_cost": 0.0
        }

        # 初始化界面
        self.initialize_simulation()

    def _init_api_client(self) -> bool:
        """初始化 API 客户端"""
        api_key = self.api_config.get("api_key", "")

        # 优先使用配置文件，其次使用环境变量
        if not api_key:
            api_key = os.getenv('DEEPSEEK_API_KEY', '')

        if api_key:
            try:
                model = self.api_config.get("model", "deepseek-chat")
                self.deepseek_client = DeepSeekClient(api_key=api_key, model=model)

                # 如果有自定义 base_url
                api_base = self.api_config.get("api_base", "")
                if api_base and api_base != "https://api.deepseek.com/v1":
                    self.deepseek_client.base_url = api_base

                logger.info(f"API 客户端初始化成功，使用模型: {model}")
                return True
            except Exception as e:
                logger.error(f"API 客户端初始化失败: {e}")
                return False
        return False

    def _show_initial_config_dialog(self):
        """显示初始配置对话框"""
        # 创建一个临时的顶层窗口作为父窗口
        temp_root = tk.Tk()
        temp_root.withdraw()

        # 显示欢迎消息
        messagebox.showinfo("欢迎", "欢迎使用艾伦谷 NPC 行为模拟器！\n\n请先配置大模型 API 以启用智能对话功能。")

        # 显示配置对话框
        dialog = APIConfigDialog(temp_root, self.api_config, on_save_callback=self._on_api_config_saved)
        temp_root.wait_window(dialog.dialog)

        # 如果用户取消了配置
        if dialog.result is None:
            if not self.deepseek_client:
                if messagebox.askyesno("提示", "未配置 API Key，部分功能将不可用。\n是否继续？"):
                    pass
                else:
                    temp_root.destroy()
                    self.root.destroy()
                    exit(0)

        temp_root.destroy()

    def _on_api_config_saved(self, config: dict):
        """API 配置保存后的回调"""
        self.api_config = config
        self._init_api_client()

    def open_api_config(self):
        """打开 API 配置对话框"""
        dialog = APIConfigDialog(self.root, self.api_config, on_save_callback=self._on_api_config_saved)
        self.root.wait_window(dialog.dialog)

    def open_world_creator(self):
        """打开世界创建对话框"""
        if not self.deepseek_client:
            messagebox.showerror("错误", "请先配置 API Key")
            self.open_api_config()
            return

        def on_world_created(result):
            """世界创建完成回调"""
            if result:
                self.add_activity_log(f"✨ 新世界 '{result['world_config'].world_name}' 创建成功!")
                self.add_activity_log(f"   包含 {len(result['locations'])} 个位置, {len(result['npcs'])} 个NPC")

        dialog = WorldCreatorDialog(
            self.root,
            self.deepseek_client,
            on_world_created=on_world_created
        )
        self.root.wait_window(dialog.dialog)

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
        
        # 底部：Token 消耗统计面板
        self.create_token_stats_panel(main_frame)

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

        # API 配置按钮
        ttk.Button(clock_frame, text="API配置", command=self.open_api_config).pack(side=tk.LEFT, padx=(5, 0))

        # 创建世界按钮
        ttk.Button(clock_frame, text="创建世界", command=self.open_world_creator).pack(side=tk.LEFT, padx=(5, 0))

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
        """触发预设事件 - 支持ReAct模式和传统模式"""
        # 清空推理面板，准备显示新的思考过程
        self.clear_thinking_panel()

        # 根据use_react_mode选择处理模式
        if self.use_react_mode and self.event_coordinator:
            # 使用ReAct模式处理（异步）
            self.add_activity_log("预设事件", f"触发事件（ReAct模式）：{event_description}")
            self._run_async_event_with_react(event_description, "preset_event")
        else:
            # 使用传统模式处理
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
            "energy": int(self.npc_system.energy * 100),  # 转换为百分比显示
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
- 能量水平：{current_state['energy']}%
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
- 能量水平：{current_state['energy']}%
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
        # 使用core_types中的NPCAction枚举
        from core_types import NPCAction
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

        # 更新能量水平（事件处理会消耗一些能量）- 使用新字段 (0.0-1.0)
        energy_cost = 0.05  # 基础消耗
        if event_analysis.get('urgency') == 'high':
            energy_cost = 0.15  # 紧急事件消耗更多
        elif event_analysis.get('urgency') == 'medium':
            energy_cost = 0.10

        self.npc_system.energy = max(0.0, self.npc_system.energy - energy_cost)

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

    def create_react_thinking_panel(self, parent):
        """创建 ReAct 思考过程面板"""
        thinking_frame = ttk.LabelFrame(parent, text="推理过程", padding=5)
        thinking_frame.pack(fill=tk.X, pady=(0, 5))

        # 思考过程文本框
        self.thinking_text = scrolledtext.ScrolledText(
            thinking_frame,
            height=6,
            width=40,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#f8f8f8"
        )
        self.thinking_text.pack(fill=tk.BOTH, expand=True)
        self.thinking_text.config(state=tk.DISABLED)

        # 配置标签样式
        self.thinking_text.tag_configure("step", foreground="#0066cc", font=("Consolas", 9, "bold"))
        self.thinking_text.tag_configure("thought", foreground="#333333")
        self.thinking_text.tag_configure("action", foreground="#009900")
        self.thinking_text.tag_configure("observation", foreground="#cc6600")

    def add_thinking_step(self, step_type: str, content: str):
        """添加思考步骤到面板"""
        self.thinking_text.config(state=tk.NORMAL)

        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = "thought"

        if step_type.lower() in ["action", "行动"]:
            tag = "action"
        elif step_type.lower() in ["observation", "观察"]:
            tag = "observation"

        self.thinking_text.insert(tk.END, f"[{timestamp}] ", "step")
        self.thinking_text.insert(tk.END, f"{step_type}: ", "step")
        self.thinking_text.insert(tk.END, f"{content}\n", tag)

        self.thinking_text.see(tk.END)
        self.thinking_text.config(state=tk.DISABLED)

    def clear_thinking_panel(self):
        """清空思考面板"""
        self.thinking_text.config(state=tk.NORMAL)
        self.thinking_text.delete(1.0, tk.END)
        self.thinking_text.config(state=tk.DISABLED)

    def add_react_thinking(self, step_type: str, content: str):
        """ReAct 思考过程回调 - NPC系统调用此方法显示推理过程"""
        self.add_thinking_step(step_type, content)

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

            # 初始化EventCoordinator（主Agent）
            self._init_event_coordinator()

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

    def _init_event_coordinator(self):
        """初始化EventCoordinator主Agent，用于多NPC事件协调"""
        if not self.npc_system or not self.deepseek_client:
            logger.warning("无法初始化EventCoordinator: npc_system或deepseek_client未就绪")
            return

        try:
            # 创建EventCoordinator
            self.event_coordinator = EventCoordinator(
                llm_client=self.deepseek_client
            )

            # 注册当前NPC作为子Agent
            # 创建异步处理器用于NPC的ReAct响应
            async_processor = self.npc_system.create_async_processor()

            self.event_coordinator.register_npc(
                npc_name=self.npc_system.config['name'],
                npc_location=self.npc_system.current_location,
                npc_status={
                    'current_activity': self.npc_system.current_activity.value if self.npc_system.current_activity else "空闲",
                    'emotion': self.npc_system.current_emotion.value,
                    'energy': self.npc_system.energy,  # 使用新字段 (0.0-1.0)
                    'profession': self.npc_system.config.get('profession', '未知')
                },
                processor=async_processor
            )

            self.add_activity_log("系统", "EventCoordinator主Agent已初始化")
            logger.info(f"EventCoordinator初始化成功，已注册NPC: {self.npc_system.config['name']}")

        except Exception as e:
            logger.error(f"EventCoordinator初始化失败: {e}")
            self.event_coordinator = None

    def _run_async_event_with_react(self, event_content: str, event_type: str = "general"):
        """
        在后台线程中运行异步事件处理（ReAct模式）

        Args:
            event_content: 事件内容
            event_type: 事件类型
        """
        def run_in_thread():
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self._process_event_with_react_async(event_content, event_type)
                )
                # 在主线程中更新GUI
                self.root.after(0, lambda: self._handle_react_event_result(result))
            except Exception as e:
                logger.error(f"ReAct事件处理失败: {e}")
                self.root.after(0, lambda: self.add_activity_log("错误", f"ReAct处理失败: {e}"))
            finally:
                loop.close()

        # 在后台线程中运行
        threading.Thread(target=run_in_thread, daemon=True).start()

    async def _process_event_with_react_async(self, event_content: str, event_type: str):
        """
        使用EventCoordinator和ReAct模式异步处理事件

        返回值结构:
        {
            'event_analysis': EventAnalysis,  # 主Agent分析结果
            'npc_responses': [NPCEventResponse, ...],  # 各NPC响应
            'coordinator_summary': str  # 协调器总结
        }
        """
        if not self.event_coordinator:
            # 回退到传统处理
            result = self.npc_system.process_event(event_content, event_type)
            return {'fallback': True, 'result': result}

        # 更新NPC状态到Coordinator
        self._update_coordinator_npc_status()

        # 1. 主Agent分析事件
        self.add_thinking_step("主Agent", f"正在分析事件: {event_content[:50]}...")

        event_analysis = await self.event_coordinator.analyze_event_async(
            event_content=event_content,
            event_type=event_type
        )

        self.add_thinking_step("分析结果",
            f"优先级: {event_analysis.priority.value}, "
            f"影响NPC数: {len(event_analysis.affected_npcs)}"
        )

        # 2. 分发到各NPC子Agent进行ReAct处理
        self.add_thinking_step("协调", "正在分发事件到NPC子Agent...")

        npc_responses = await self.event_coordinator.dispatch_to_npcs_with_registered(event_analysis)

        # 3. 收集并汇总结果
        coordinator_summary = self._generate_coordinator_summary(event_analysis, npc_responses)

        return {
            'fallback': False,
            'event_analysis': event_analysis,
            'npc_responses': npc_responses,
            'coordinator_summary': coordinator_summary
        }

    def _update_coordinator_npc_status(self):
        """更新Coordinator中的NPC状态信息"""
        if not self.event_coordinator or not self.npc_system:
            return

        self.event_coordinator.update_npc_status(
            npc_name=self.npc_system.config['name'],
            location=self.npc_system.current_location,
            status={
                'current_activity': self.npc_system.current_activity.value if self.npc_system.current_activity else "空闲",
                'emotion': self.npc_system.current_emotion.value,
                'energy': self.npc_system.energy,  # 使用新字段 (0.0-1.0)
                'fatigue': self.npc_system.need_system.needs.fatigue,
                'hunger': self.npc_system.need_system.needs.hunger
            }
        )

    def _generate_coordinator_summary(self, event_analysis: EventAnalysis, npc_responses: List[NPCEventResponse]) -> str:
        """生成协调器的事件处理总结"""
        summary_parts = []

        # 事件总览
        summary_parts.append(f"事件类型: {event_analysis.event_type}")
        summary_parts.append(f"优先级: {event_analysis.priority.value}")

        # NPC响应统计
        responding_npcs = [r for r in npc_responses if r.responded]
        summary_parts.append(f"响应NPC数: {len(responding_npcs)}/{len(npc_responses)}")

        # 各NPC角色和行动
        for response in npc_responses:
            if response.responded:
                actions_str = ", ".join(response.actions_taken) if response.actions_taken else "无具体行动"
                summary_parts.append(f"  - {response.npc_name} ({response.role.value}): {actions_str}")

        return "\n".join(summary_parts)

    def _handle_react_event_result(self, result: dict):
        """处理ReAct事件的结果并更新GUI"""
        if result.get('fallback'):
            # 使用传统模式的结果
            traditional_result = result['result']
            if traditional_result.get('should_respond') and traditional_result.get('response_text'):
                self.add_dialogue_entry(
                    self.npc_system.config["name"],
                    traditional_result['response_text']
                )
            self.add_activity_log("事件处理", "使用传统模式处理完成")
        else:
            # ReAct模式结果
            event_analysis = result.get('event_analysis')
            npc_responses = result.get('npc_responses', [])
            summary = result.get('coordinator_summary', '')

            # 显示主Agent分析
            self.add_thinking_step("总结", summary)

            # 显示各NPC的对话响应
            for response in npc_responses:
                if response.responded and response.dialogue:
                    self.add_dialogue_entry(response.npc_name, response.dialogue)

                # 记录行动日志
                if response.actions_taken:
                    for action in response.actions_taken:
                        self.add_activity_log(
                            f"NPC行动 ({response.npc_name})",
                            f"{response.role.value}: {action}"
                        )

            self.add_activity_log("事件处理", f"ReAct模式处理完成 - {len(npc_responses)}个NPC响应")

        # 更新角色卡
        self.update_character_card()

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
                # 从持久化状态获取 - 使用新字段
                current_activity_str = self.npc_system.persistence.current_state.current_activity
                current_activity = current_activity_str if current_activity_str else "空闲"

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
        from world_simulator.world_clock import reset_world_clock
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

        from world_simulator.world_lore import ENVIRONMENTAL_EVENTS

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
                    current_activity = status_summary['current_state'].get('current_activity', '空闲')
                    state_info = f"状态已改变为：{current_activity}"
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

    def _get_reasoning_mode(self) -> int:
        """获取当前选择的推理模式对应的最大推理步数"""
        mode_str = self.reasoning_mode_var.get() if hasattr(self, 'reasoning_mode_var') else "normal"
        # 将推理模式映射为最大推理步数
        mode_map = {
            "fast": 1,        # 快速：1步
            "normal": 3,      # 正常：3步
            "deep": 5,        # 深度：5步
            "exhaustive": 10  # 详尽：10步
        }
        return mode_map.get(mode_str, 3)

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
        self.realtime_energy_label.config(text=f"{int(status['energy'] * 100)}/100")

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

    def create_token_stats_panel(self, parent):
        """创建 Token 消耗统计面板"""
        stats_frame = ttk.LabelFrame(parent, text="📊 Token 消耗统计", padding=10)
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        # 统计信息框架（使用网格布局）
        info_frame = ttk.Frame(stats_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        # Token 发送
        ttk.Label(info_frame, text="Tokens 发送:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.tokens_sent_label = ttk.Label(info_frame, text="0", foreground="blue", font=("Arial", 10, "bold"))
        self.tokens_sent_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 30))

        # Token 接收
        ttk.Label(info_frame, text="Tokens 接收:", font=("Arial", 9, "bold")).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.tokens_received_label = ttk.Label(info_frame, text="0", foreground="green", font=("Arial", 10, "bold"))
        self.tokens_received_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 30))

        # API 调用次数
        ttk.Label(info_frame, text="API 调用:", font=("Arial", 9, "bold")).grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.api_calls_label = ttk.Label(info_frame, text="0", foreground="purple", font=("Arial", 10, "bold"))
        self.api_calls_label.grid(row=0, column=5, sticky=tk.W)

        # 第二行信息
        info_frame2 = ttk.Frame(stats_frame)
        info_frame2.pack(fill=tk.X, pady=(5, 5))

        # 总 Token 数
        ttk.Label(info_frame2, text="总 Tokens:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.total_tokens_label = ttk.Label(info_frame2, text="0", foreground="darkblue", font=("Arial", 10, "bold"))
        self.total_tokens_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 30))

        # 压缩比率
        ttk.Label(info_frame2, text="压缩比率:", font=("Arial", 9, "bold")).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.compression_ratio_label = ttk.Label(info_frame2, text="1.00x", foreground="orange", font=("Arial", 10, "bold"))
        self.compression_ratio_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 30))

        # 估计成本 (假设 $0.001 per 1K tokens)
        ttk.Label(info_frame2, text="估计成本:", font=("Arial", 9, "bold")).grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.estimated_cost_label = ttk.Label(info_frame2, text="$0.00", foreground="red", font=("Arial", 10, "bold"))
        self.estimated_cost_label.grid(row=0, column=5, sticky=tk.W)

        # 运行时间
        info_frame3 = ttk.Frame(stats_frame)
        info_frame3.pack(fill=tk.X)

        ttk.Label(info_frame3, text="运行时间:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.runtime_label = ttk.Label(info_frame3, text="00:00:00", font=("Arial", 10))
        self.runtime_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 30))

        # 清除统计按钮
        ttk.Button(info_frame3, text="清除统计", command=self.reset_token_stats).grid(row=0, column=2, sticky=tk.E)
        ttk.Button(info_frame3, text="导出数据", command=self.export_token_stats).grid(row=0, column=3, sticky=tk.E, padx=(5, 0))

    def update_token_stats(self, tokens_sent: int = 0, tokens_received: int = 0, api_call: bool = False):
        """更新 Token 统计"""
        self.token_stats["total_tokens_sent"] += tokens_sent
        self.token_stats["total_tokens_received"] += tokens_received
        if api_call:
            self.token_stats["total_api_calls"] += 1

        # 计算成本（DeepSeek 成本：约 $0.0005 per 1K input tokens, $0.0015 per 1K output tokens）
        # 简化为平均 $0.001 per 1K tokens
        total_tokens = self.token_stats["total_tokens_sent"] + self.token_stats["total_tokens_received"]
        self.token_stats["estimated_cost"] = total_tokens / 1000000.0  # 简化成本

        # 更新 UI
        self.tokens_sent_label.config(text=f"{self.token_stats['total_tokens_sent']:,}")
        self.tokens_received_label.config(text=f"{self.token_stats['total_tokens_received']:,}")
        self.api_calls_label.config(text=f"{self.token_stats['total_api_calls']}")
        self.total_tokens_label.config(text=f"{total_tokens:,}")
        self.compression_ratio_label.config(text=f"{self.token_stats['compression_ratio']:.2f}x")
        self.estimated_cost_label.config(text=f"${self.token_stats['estimated_cost']:.4f}")

        # 更新运行时间
        elapsed = datetime.now() - self.token_stats["session_start_time"]
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.runtime_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def reset_token_stats(self):
        """重置 Token 统计"""
        self.token_stats = {
            "total_tokens_sent": 0,
            "total_tokens_received": 0,
            "total_api_calls": 0,
            "session_start_time": datetime.now(),
            "compression_ratio": 1.0,
            "estimated_cost": 0.0
        }
        self.tokens_sent_label.config(text="0")
        self.tokens_received_label.config(text="0")
        self.api_calls_label.config(text="0")
        self.total_tokens_label.config(text="0")
        self.estimated_cost_label.config(text="$0.00")

    def export_token_stats(self):
        """导出 Token 统计数据"""
        stats_data = {
            "timestamp": datetime.now().isoformat(),
            "total_tokens_sent": self.token_stats["total_tokens_sent"],
            "total_tokens_received": self.token_stats["total_tokens_received"],
            "total_api_calls": self.token_stats["total_api_calls"],
            "estimated_cost": self.token_stats["estimated_cost"],
            "compression_ratio": self.token_stats["compression_ratio"],
            "runtime": str(datetime.now() - self.token_stats["session_start_time"])
        }
        
        # 写入日志文件
        with open("token_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        messagebox.showinfo("导出成功", f"Token 统计数据已导出到 token_stats.json\n\n总消耗: {stats_data['total_api_calls']} 次 API 调用\n估计成本: ${stats_data['estimated_cost']:.4f}")

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
