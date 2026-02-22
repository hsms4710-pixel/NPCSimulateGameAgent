/**
 * 国际化支持 (i18n)
 * 艾伦谷世界模拟器 - 多语言系统
 */

const I18N = {
    currentLang: 'zh-CN',

    translations: {
        'zh-CN': {
            // 应用标题
            'app.title': 'NPC行为模拟系统',
            'app.game.title': '艾伦谷世界模拟器',
            'app.subtitle': '探索一个由AI驱动的奇幻小镇',

            // 导航
            'nav.home': '首页',
            'nav.npcs': 'NPC列表',
            'nav.map': '地图',
            'nav.events': '事件',

            // 启动界面
            'start.newGame': '开始模拟',
            'start.continue': '继续模拟',
            'start.settings': 'API设置',

            // 角色创建
            'character.title': '创建你的角色',
            'character.presetSection': '选择预设角色',
            'character.customSection': '自定义属性',
            'character.back': '返回',
            'character.enter': '进入世界',

            // 预设角色
            'preset.adventurer': '冒险者',
            'preset.adventurer.desc': '寻求刺激的勇士',
            'preset.traveler': '旅行者',
            'preset.traveler.desc': '四处漂泊的旅人',
            'preset.merchant': '商人',
            'preset.merchant.desc': '精明的生意人',
            'preset.scholar': '学者',
            'preset.scholar.desc': '追求知识的智者',

            // 玩家属性
            'player.create': '创建角色',
            'player.name': '姓名',
            'player.name.placeholder': '输入角色名称',
            'player.age': '年龄',
            'player.gender': '性别',
            'player.gender.male': '男',
            'player.gender.female': '女',
            'player.location': '位置',
            'player.gold': '金币',
            'player.hunger': '饱腹',
            'player.energy': '精力',
            'player.social': '社交',

            // 行动
            'action.title': '可执行行动',
            'action.move': '移动',
            'action.socialize': '社交',
            'action.eat': '用餐',
            'action.work': '工作',
            'action.rest': '休息',

            // 关系
            'relationship.title': '人际关系',
            'relationship.empty': '暂无建立的关系',
            'relationship.affinity': '好感',

            // 对话
            'dialogue.title': '交互区',
            'dialogue.send': '发送',
            'dialogue.placeholder': '输入你想说的话...',
            'dialogue.talkTo': '对 {npc} 说...',
            'dialogue.selectNpc': '选择一个NPC开始交谈',
            'dialogue.welcome': '欢迎来到艾伦谷！你站在村庄大门前，清晨的阳光洒在古老的石板路上。',

            // NPC相关
            'npc.title': '当前区域NPC',
            'npc.empty': '当前区域没有NPC',
            'npc.response.title': 'NPC反应',
            'npc.response.empty': '暂无NPC反应',
            'npc.status': '状态',
            'npc.activity': '当前活动',
            'npc.emotion': '情绪',

            // 事件
            'event.title': '世界事件触发',
            'event.trigger': '触发',
            'event.placeholder': '输入事件，如：小偷闯入铁匠铺',
            'event.location.current': '当前位置',

            // 时间
            'time.day': '第{day}天',
            'time.pause': '暂停',
            'time.resume': '继续',
            'time.paused': '时间已暂停',
            'time.resumed': '时间已恢复',
            'time.advance': '时间推进 {hours} 小时',

            // 地图
            'map.title': '艾伦谷地图',
            'map.hint': '点击选择目的地',
            'map.current': '(当前)',
            'map.alreadyHere': '你已经在这里了',

            // 地点名称
            'location.gate': '村庄大门',
            'location.center': '镇中心',
            'location.tavern': '酒馆',
            'location.market': '市场区',
            'location.smithy': '铁匠铺',
            'location.church': '教堂',
            'location.workshop': '工坊区',
            'location.farm': '农田',
            'location.forest': '森林边缘',

            // 社交
            'social.title': '选择交谈对象',
            'social.noNpc': '这里没有可以交谈的人',

            // 工作/饮食相关
            'job.accept': '接受工作',
            'job.wage': '报酬',
            'lodging.book': '预订住宿',

            // API设置
            'settings.title': 'API 配置',
            'settings.provider': 'API 提供商',
            'settings.apiKey': 'API Key',
            'settings.apiKey.placeholder': '输入你的 API Key',
            'settings.model': '模型',
            'settings.test': '测试连接',
            'settings.save': '保存配置',
            'settings.testing': '正在测试连接...',
            'settings.success': '连接成功!',
            'settings.failed': '连接失败',
            'settings.saved': '配置已保存',

            // 日志
            'log.title': '事件日志',

            // 通用
            'common.close': '关闭',
            'common.confirm': '确认',
            'common.cancel': '取消',
            'common.exit': '退出',
            'common.exitConfirm': '确定要退出游戏吗？进度已自动保存。',
            'common.loaded': '游戏已加载',
            'common.loadFailed': '加载游戏失败',

            // 提示消息
            'toast.enterName': '请输入角色名称',
            'toast.notEnoughGold': '金币不足',
            'toast.selectNpc': '请先选择一个NPC进行交谈',
            'toast.enterEvent': '请输入事件内容'
        },

        'en-US': {
            // App title
            'app.title': 'NPC Behavior Simulation',
            'app.game.title': 'Ellen Valley World Simulator',
            'app.subtitle': 'Explore an AI-powered fantasy town',

            // Navigation
            'nav.home': 'Home',
            'nav.npcs': 'NPC List',
            'nav.map': 'Map',
            'nav.events': 'Events',

            // Start screen
            'start.newGame': 'Start Simulation',
            'start.continue': 'Continue',
            'start.settings': 'API Settings',

            // Character creation
            'character.title': 'Create Your Character',
            'character.presetSection': 'Choose Preset Character',
            'character.customSection': 'Custom Attributes',
            'character.back': 'Back',
            'character.enter': 'Enter World',

            // Preset characters
            'preset.adventurer': 'Adventurer',
            'preset.adventurer.desc': 'Thrill-seeking warrior',
            'preset.traveler': 'Traveler',
            'preset.traveler.desc': 'Wandering nomad',
            'preset.merchant': 'Merchant',
            'preset.merchant.desc': 'Shrewd businessman',
            'preset.scholar': 'Scholar',
            'preset.scholar.desc': 'Seeker of knowledge',

            // Player attributes
            'player.create': 'Create Character',
            'player.name': 'Name',
            'player.name.placeholder': 'Enter character name',
            'player.age': 'Age',
            'player.gender': 'Gender',
            'player.gender.male': 'Male',
            'player.gender.female': 'Female',
            'player.location': 'Location',
            'player.gold': 'Gold',
            'player.hunger': 'Hunger',
            'player.energy': 'Energy',
            'player.social': 'Social',

            // Actions
            'action.title': 'Available Actions',
            'action.move': 'Move',
            'action.socialize': 'Socialize',
            'action.eat': 'Eat',
            'action.work': 'Work',
            'action.rest': 'Rest',

            // Relationships
            'relationship.title': 'Relationships',
            'relationship.empty': 'No relationships yet',
            'relationship.affinity': 'Affinity',

            // Dialogue
            'dialogue.title': 'Interaction',
            'dialogue.send': 'Send',
            'dialogue.placeholder': 'Type your message...',
            'dialogue.talkTo': 'Say to {npc}...',
            'dialogue.selectNpc': 'Select an NPC to start conversation',
            'dialogue.welcome': 'Welcome to Ellen Valley! You stand at the village gate, morning sunlight casting over the ancient stone path.',

            // NPC related
            'npc.title': 'NPCs in Area',
            'npc.empty': 'No NPCs in this area',
            'npc.response.title': 'NPC Reactions',
            'npc.response.empty': 'No NPC reactions',
            'npc.status': 'Status',
            'npc.activity': 'Activity',
            'npc.emotion': 'Emotion',

            // Events
            'event.title': 'World Event Trigger',
            'event.trigger': 'Trigger',
            'event.placeholder': 'Enter event, e.g.: Thief breaks into smithy',
            'event.location.current': 'Current Location',

            // Time
            'time.day': 'Day {day}',
            'time.pause': 'Pause',
            'time.resume': 'Resume',
            'time.paused': 'Time paused',
            'time.resumed': 'Time resumed',
            'time.advance': 'Advanced {hours} hour(s)',

            // Map
            'map.title': 'Ellen Valley Map',
            'map.hint': 'Click to select destination',
            'map.current': '(Current)',
            'map.alreadyHere': 'You are already here',

            // Location names
            'location.gate': 'Village Gate',
            'location.center': 'Town Center',
            'location.tavern': 'Tavern',
            'location.market': 'Market District',
            'location.smithy': 'Smithy',
            'location.church': 'Church',
            'location.workshop': 'Workshop',
            'location.farm': 'Farmland',
            'location.forest': 'Forest Edge',

            // Social
            'social.title': 'Choose Conversation Partner',
            'social.noNpc': 'No one here to talk to',

            // Work/Lodging
            'job.accept': 'Accept Job',
            'job.wage': 'Wage',
            'lodging.book': 'Book Lodging',

            // API Settings
            'settings.title': 'API Configuration',
            'settings.provider': 'API Provider',
            'settings.apiKey': 'API Key',
            'settings.apiKey.placeholder': 'Enter your API Key',
            'settings.model': 'Model',
            'settings.test': 'Test Connection',
            'settings.save': 'Save Config',
            'settings.testing': 'Testing connection...',
            'settings.success': 'Connection successful!',
            'settings.failed': 'Connection failed',
            'settings.saved': 'Configuration saved',

            // Log
            'log.title': 'Event Log',

            // Common
            'common.close': 'Close',
            'common.confirm': 'Confirm',
            'common.cancel': 'Cancel',
            'common.exit': 'Exit',
            'common.exitConfirm': 'Are you sure you want to exit? Progress has been auto-saved.',
            'common.loaded': 'Game loaded',
            'common.loadFailed': 'Failed to load game',

            // Toast messages
            'toast.enterName': 'Please enter character name',
            'toast.notEnoughGold': 'Not enough gold',
            'toast.selectNpc': 'Please select an NPC first',
            'toast.enterEvent': 'Please enter event content'
        }
    },

    // 地点名称映射 (用于动态翻译)
    locationMap: {
        'zh-CN': {
            '村庄大门': '村庄大门',
            '镇中心': '镇中心',
            '酒馆': '酒馆',
            '市场区': '市场区',
            '铁匠铺': '铁匠铺',
            '教堂': '教堂',
            '工坊区': '工坊区',
            '农田': '农田',
            '森林边缘': '森林边缘'
        },
        'en-US': {
            '村庄大门': 'Village Gate',
            '镇中心': 'Town Center',
            '酒馆': 'Tavern',
            '市场区': 'Market District',
            '铁匠铺': 'Smithy',
            '教堂': 'Church',
            '工坊区': 'Workshop',
            '农田': 'Farmland',
            '森林边缘': 'Forest Edge'
        }
    },

    /**
     * 获取翻译文本
     * @param {string} key - 翻译键
     * @param {object} params - 可选的替换参数
     * @returns {string} 翻译后的文本
     */
    t(key, params = {}) {
        let text = this.translations[this.currentLang][key] ||
                   this.translations['zh-CN'][key] ||
                   key;

        // 替换参数 {param}
        Object.keys(params).forEach(param => {
            text = text.replace(new RegExp(`\\{${param}\\}`, 'g'), params[param]);
        });

        return text;
    },

    /**
     * 翻译地点名称
     * @param {string} location - 中文地点名称
     * @returns {string} 翻译后的地点名称
     */
    translateLocation(location) {
        const map = this.locationMap[this.currentLang];
        return map ? (map[location] || location) : location;
    },

    /**
     * 获取原始中文地点名称（用于后端通信）
     * @param {string} translatedLocation - 翻译后的地点名称
     * @returns {string} 原始中文地点名称
     */
    getOriginalLocation(translatedLocation) {
        if (this.currentLang === 'zh-CN') {
            return translatedLocation;
        }

        const map = this.locationMap[this.currentLang];
        for (const [zhName, enName] of Object.entries(map)) {
            if (enName === translatedLocation) {
                return zhName;
            }
        }
        return translatedLocation;
    },

    /**
     * 切换语言
     * @param {string} lang - 语言代码 (zh-CN 或 en-US)
     */
    setLanguage(lang) {
        if (!this.translations[lang]) {
            console.warn(`Language ${lang} not supported, falling back to zh-CN`);
            lang = 'zh-CN';
        }

        this.currentLang = lang;
        localStorage.setItem('preferred_lang', lang);
        this.updateUI();
        this.updateLangButtons();

        // 触发自定义事件，通知其他组件语言已更改
        window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang } }));
    },

    /**
     * 更新所有带有 data-i18n 属性的元素
     */
    updateUI() {
        // 更新文本内容
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            el.textContent = this.t(key);
        });

        // 更新placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = this.t(key);
        });

        // 更新title属性
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = this.t(key);
        });

        // 更新页面标题
        document.title = this.t('app.game.title');
    },

    /**
     * 更新语言切换按钮状态
     */
    updateLangButtons() {
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.lang === this.currentLang) {
                btn.classList.add('active');
            }
        });
    },

    /**
     * 初始化国际化系统
     */
    init() {
        // 从localStorage读取保存的语言偏好
        const saved = localStorage.getItem('preferred_lang');
        if (saved && this.translations[saved]) {
            this.currentLang = saved;
        } else {
            // 尝试检测浏览器语言
            const browserLang = navigator.language || navigator.userLanguage;
            if (browserLang.startsWith('en')) {
                this.currentLang = 'en-US';
            } else {
                this.currentLang = 'zh-CN';
            }
        }

        this.updateUI();
        this.updateLangButtons();
        this.bindLanguageSwitcher();

        console.log(`I18N initialized with language: ${this.currentLang}`);
    },

    /**
     * 绑定语言切换按钮事件
     */
    bindLanguageSwitcher() {
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const lang = btn.dataset.lang;
                if (lang && lang !== this.currentLang) {
                    this.setLanguage(lang);
                }
            });
        });
    },

    /**
     * 获取当前语言
     * @returns {string} 当前语言代码
     */
    getCurrentLanguage() {
        return this.currentLang;
    },

    /**
     * 检查是否为中文
     * @returns {boolean}
     */
    isChinese() {
        return this.currentLang === 'zh-CN';
    },

    /**
     * 检查是否为英文
     * @returns {boolean}
     */
    isEnglish() {
        return this.currentLang === 'en-US';
    }
};

// 导出到全局
window.I18N = I18N;
