/**
 * 艾伦谷世界模拟器 - 游戏主逻辑
 */

class WorldSimulator {
    constructor() {
        // 游戏状态
        this.gameState = {
            screen: 'start',
            player: null,
            currentLocation: '村庄大门',
            day: 1,
            hour: 8,
            minute: 0,
            isPaused: false,
            gold: 100,
            hunger: 1.0,
            energy: 1.0,
            social: 0.5,
            relationships: {},
            activeEvents: [],
            conversationTarget: null
        };

        // NPC数据（将被世界数据覆盖）
        this.npcs = {};

        // 世界地点详情
        this.worldLocations = {};

        // 预设角色
        this.presets = {
            adventurer: { name: '艾瑞克', age: 28, gender: '男', profession: '冒险者' },
            traveler: { name: '莉娜', age: 24, gender: '女', profession: '旅行者' },
            merchant: { name: '马库斯', age: 35, gender: '男', profession: '商人' },
            scholar: { name: '艾琳', age: 30, gender: '女', profession: '学者' }
        };

        // 时间图标
        this.timeIcons = {
            morning: '☀️',
            afternoon: '🌤️',
            evening: '🌅',
            night: '🌙'
        };

        // 可视化地图实例
        this.worldMap = null;
        this.isMapCollapsed = false;

        this.init();
    }

    init() {
        this.bindElements();
        this.bindEvents();
        this.checkSavedGame();
        this.initWorldMap();

        // 初始化国际化系统
        if (window.I18N) {
            window.I18N.init();
            // 监听语言变更事件
            window.addEventListener('languageChanged', () => this.onLanguageChanged());
        }

        // 接入 WebSocket - 将新消息类型分发到 handleWebSocketMessage
        if (window.api) {
            window.api.onWebSocket('message', (data) => this.handleWebSocketMessage(data));
            // 同时覆盖已有的通用分发，确保 6 种新消息类型都能被处理
            const _origHandle = window.api._handleWebSocketMessage.bind(window.api);
            window.api._handleWebSocketMessage = (data) => {
                _origHandle(data);
                // 新增消息类型分发给 game.js
                const newTypes = ['event_phase_change','npc_moved','gossip_spread',
                                  'trade_completed','relationship_changed','task_completed'];
                if (newTypes.includes(data.type)) {
                    this.handleWebSocketMessage(data);
                }
            };
        }
    }

    /**
     * 语言变更时的回调
     */
    onLanguageChanged() {
        // 更新动态生成的内容
        if (this.gameState.screen === 'game') {
            this.updatePlayerPanel();
            this.updateNPCList();
            this.updateLocationDisplay();
            this.updateTimeDisplay();
            this.renderActiveEvents();
            this.updateRelationships();
        }
    }

    /**
     * 初始化可视化地图
     */
    initWorldMap() {
        // 延迟初始化，确保DOM已加载
        setTimeout(() => {
            if (typeof WorldMap !== 'undefined') {
                this.worldMap = new WorldMap('world-map-canvas');

                // 监听地图点击事件
                const canvas = document.getElementById('world-map-canvas');
                if (canvas) {
                    canvas.addEventListener('locationSelected', (e) => {
                        this.handleMapLocationClick(e.detail.location);
                    });
                }

                // 绑定地图展开/收起按钮
                const toggleBtn = document.getElementById('btn-toggle-map');
                if (toggleBtn) {
                    toggleBtn.addEventListener('click', () => this.toggleMapVisibility());
                }

                console.log('WorldMap initialized');
            }
        }, 100);
    }

    /**
     * 切换地图显示/隐藏
     */
    toggleMapVisibility() {
        const container = document.getElementById('map-canvas-container');
        const toggleBtn = document.getElementById('btn-toggle-map');

        if (container) {
            this.isMapCollapsed = !this.isMapCollapsed;
            container.classList.toggle('collapsed', this.isMapCollapsed);

            if (toggleBtn) {
                toggleBtn.textContent = this.isMapCollapsed ? '展开' : '收起';
            }

            // 如果展开，重新渲染地图
            if (!this.isMapCollapsed && this.worldMap) {
                setTimeout(() => this.worldMap.render(), 100);
            }
        }
    }

    /**
     * 处理地图位置点击
     */
    handleMapLocationClick(location) {
        if (location === this.gameState.currentLocation) {
            this.showToast('你已经在这里了', 'info');
            return;
        }

        // 执行移动
        const oldLocation = this.gameState.currentLocation;
        this.gameState.currentLocation = location;

        // 移动消耗15分钟时间
        this.advanceTime(0.25, false);

        // 更新界面
        this.updateLocationDisplay();
        this.updateNPCList();
        this.enableDialogueIfNPCsPresent();
        this.updateWorldMap();

        // 清空对话并显示移动信息
        this.clearDialogue();
        this.addDialogueMessage(`你从${oldLocation}来到了${location}`, 'system');

        // 记录日志
        this.addLog('移动', `${this.gameState.player.name} 移动到 ${location}`, 'info');

        // 保存游戏
        this.saveGame();
    }

    /**
     * 更新可视化地图
     */
    updateWorldMap() {
        if (!this.worldMap) return;

        // 更新玩家位置
        this.worldMap.updatePlayerPosition(this.gameState.currentLocation);

        // 构建NPC位置数据
        const npcPositions = {};
        for (const [location, npcsHere] of Object.entries(this.npcs)) {
            for (const npc of npcsHere) {
                npcPositions[npc.name] = location;
            }
        }
        this.worldMap.updateNPCPositions(npcPositions);
    }

    /**
     * 在地图上高亮事件
     */
    highlightEventOnMap(location, severity) {
        if (this.worldMap) {
            this.worldMap.highlightEvent(location, severity, 5000);
        }
    }

    /**
     * 在地图上显示NPC移动动画
     */
    animateNPCMovementOnMap(npcName, fromLocation, toLocation) {
        if (this.worldMap) {
            this.worldMap.animateNPCMovement(npcName, fromLocation, toLocation, 2000);
        }
    }

    bindElements() {
        // 屏幕
        this.screens = {
            start: document.getElementById('start-screen'),
            worldCreate: document.getElementById('world-create-screen'),
            worldLoad: document.getElementById('world-load-screen'),
            character: document.getElementById('character-screen'),
            game: document.getElementById('game-screen')
        };

        // 启动界面
        this.btnNewGame = document.getElementById('btn-new-game');
        this.btnLoadWorld = document.getElementById('btn-load-world');
        this.btnSettingsStart = document.getElementById('btn-settings-start');

        // 世界创建界面
        this.themeCards = document.getElementById('theme-cards');
        this.worldDescription = document.getElementById('world-description');
        this.npcCountSlider = document.getElementById('npc-count');
        this.npcCountDisplay = document.getElementById('npc-count-display');
        this.generationStatus = document.getElementById('generation-status');
        this.generationMessage = document.getElementById('generation-message');
        this.btnBackStart = document.getElementById('btn-back-start');
        this.btnGenerateWorld = document.getElementById('btn-generate-world');

        // 世界加载界面
        this.savedWorldsList = document.getElementById('saved-worlds-list');
        this.btnBackStartLoad = document.getElementById('btn-back-start-load');

        // 角色创建
        this.presetCards = document.getElementById('preset-cards');
        this.charName = document.getElementById('char-name');
        this.charAge = document.getElementById('char-age');
        this.charGender = document.getElementById('char-gender');
        this.btnEnterWorld = document.getElementById('btn-enter-world');

        // 游戏界面
        this.timeIcon = document.getElementById('time-icon');
        this.gameTime = document.getElementById('game-time');
        this.currentLocationHeader = document.getElementById('current-location-header');
        this.playerName = document.getElementById('player-name');
        this.playerProfession = document.getElementById('player-profession');
        this.playerLocation = document.getElementById('player-location');
        this.playerGold = document.getElementById('player-gold');
        this.hungerBar = document.getElementById('hunger-bar');
        this.energyBar = document.getElementById('energy-bar');
        this.socialBar = document.getElementById('social-bar');
        this.relationshipsList = document.getElementById('relationships-list');
        this.npcList = document.getElementById('npc-list');
        this.npcResponseBox = document.getElementById('npc-response-box');
        this.llmStatus = document.getElementById('llm-status');
        this.dialogueContent = document.getElementById('dialogue-content');
        this.dialogueInput = document.getElementById('dialogue-input');
        this.btnSendDialogue = document.getElementById('btn-send-dialogue');
        this.eventInput = document.getElementById('event-input');
        this.eventLocation = document.getElementById('event-location');
        this.btnTriggerEvent = document.getElementById('btn-trigger-event');
        this.activeEvents = document.getElementById('active-events');
        this.logContainer = document.getElementById('log-container');

        // 时间控制
        this.btnPause = document.getElementById('btn-pause');
        this.btnAdvance1h = document.getElementById('btn-advance-1h');
        this.btnAdvance6h = document.getElementById('btn-advance-6h');

        // 行动按钮
        this.btnMove = document.getElementById('btn-move');
        this.btnSocialize = document.getElementById('btn-socialize');
        this.btnEat = document.getElementById('btn-eat');
        this.btnWork = document.getElementById('btn-work');
        this.btnRest = document.getElementById('btn-rest');

        // 地图模态框
        this.mapGridModal = document.getElementById('map-grid-modal');

        // 头部按钮
        this.btnLog = document.getElementById('btn-log');
        this.btnApiConfig = document.getElementById('btn-api-config');
        this.btnExitGame = document.getElementById('btn-exit-game');
    }

    bindEvents() {
        // 启动界面
        this.btnNewGame.addEventListener('click', () => this.showScreen('worldCreate'));
        this.btnLoadWorld.addEventListener('click', () => this.showWorldLoadScreen());
        this.btnSettingsStart.addEventListener('click', () => this.openModal('settings-modal'));

        // 世界创建界面
        if (this.themeCards) {
            this.themeCards.addEventListener('click', (e) => this.selectTheme(e));
        }
        if (this.npcCountSlider) {
            this.npcCountSlider.addEventListener('input', (e) => {
                this.npcCountDisplay.textContent = e.target.value;
            });
        }
        if (this.btnBackStart) {
            this.btnBackStart.addEventListener('click', () => this.showScreen('start'));
        }
        if (this.btnGenerateWorld) {
            this.btnGenerateWorld.addEventListener('click', () => this.generateWorld());
        }

        // 世界加载界面
        if (this.btnBackStartLoad) {
            this.btnBackStartLoad.addEventListener('click', () => this.showScreen('start'));
        }

        // 角色创建
        this.presetCards.addEventListener('click', (e) => this.selectPreset(e));
        this.btnEnterWorld.addEventListener('click', () => this.enterWorld());

        // 移动按钮 - 打开地图模态框
        this.btnMove.addEventListener('click', () => this.openMapModal());

        // 地图模态框点击事件
        this.mapGridModal.addEventListener('click', (e) => this.handleMapModalClick(e));

        // 时间控制
        this.btnPause.addEventListener('click', () => this.togglePause());
        this.btnAdvance1h.addEventListener('click', () => this.advanceTime(1));
        this.btnAdvance6h.addEventListener('click', () => this.advanceTime(6));

        // 行动按钮
        this.btnSocialize.addEventListener('click', () => this.actionSocialize());
        this.btnEat.addEventListener('click', () => this.actionEat());
        this.btnWork.addEventListener('click', () => this.actionWork());
        this.btnRest.addEventListener('click', () => this.actionRest());

        // 对话
        this.btnSendDialogue.addEventListener('click', () => this.sendDialogue());
        this.dialogueInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendDialogue();
        });

        // 事件触发
        this.btnTriggerEvent.addEventListener('click', () => this.triggerWorldEvent());
        this.eventInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.triggerWorldEvent();
        });

        // 头部按钮
        this.btnLog.addEventListener('click', () => this.openModal('log-modal'));
        this.btnApiConfig.addEventListener('click', () => this.openModal('settings-modal'));
        this.btnExitGame.addEventListener('click', () => this.exitGame());

        // API设置按钮
        document.getElementById('btn-test-api').addEventListener('click', () => this.testApiConnection());
        document.getElementById('btn-save-api').addEventListener('click', () => this.saveApiConfig());
    }

    // ========== 屏幕切换 ==========

    showScreen(screenName) {
        Object.values(this.screens).forEach(s => s.classList.remove('active'));
        this.screens[screenName].classList.add('active');
        this.gameState.screen = screenName;
    }

    // ========== 角色创建 ==========

    selectPreset(e) {
        const card = e.target.closest('.preset-card');
        if (!card) return;

        // 更新选中状态
        document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');

        // 填充属性
        const preset = this.presets[card.dataset.preset];
        if (preset) {
            this.charName.value = preset.name;
            this.charAge.value = preset.age;
            this.charGender.value = preset.gender;
        }
    }

    enterWorld() {
        const name = this.charName.value.trim();
        if (!name) {
            this.showToast(window.I18N ? window.I18N.t('toast.enterName') : '请输入角色名称', 'warning');
            return;
        }

        // 获取选中的预设职业
        const selectedPreset = document.querySelector('.preset-card.selected');
        const presetKey = selectedPreset ? selectedPreset.dataset.preset : 'adventurer';
        const profession = this.presets[presetKey].profession;

        // 获取角色背景描述
        const backgroundElement = document.getElementById('char-background');
        const background = backgroundElement ? backgroundElement.value.trim() : '';

        // 创建玩家
        this.gameState.player = {
            name: name,
            age: parseInt(this.charAge.value) || 28,
            gender: this.charGender.value,
            profession: profession,
            background: background
        };

        // 初始化游戏状态
        this.gameState.day = 1;
        this.gameState.hour = 8;
        this.gameState.minute = 0;
        this.gameState.currentLocation = '村庄大门';

        // 切换到游戏界面
        this.showScreen('game');
        this.initGameUI();
        this.addLog('系统', `玩家 ${name} 进入了艾伦谷`, 'info');
        this.saveGame();
    }

    // ========== 游戏界面初始化 ==========

    initGameUI() {
        this.updatePlayerPanel();
        this.updateTimeDisplay();
        this.updateLocationDisplay();
        this.updateNPCList();
        this.enableDialogueIfNPCsPresent();
        this.updateWorldMap();
    }

    updatePlayerPanel() {
        const p = this.gameState.player;
        const s = this.gameState;

        this.playerName.textContent = p.name;
        this.playerProfession.textContent = p.profession;
        this.playerLocation.textContent = s.currentLocation;
        this.playerGold.textContent = s.gold;

        this.hungerBar.style.width = `${s.hunger * 100}%`;
        this.energyBar.style.width = `${s.energy * 100}%`;
        this.socialBar.style.width = `${s.social * 100}%`;

        this.updateRelationships();
    }

    updateRelationships() {
        const rels = this.gameState.relationships;
        const keys = Object.keys(rels);
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;

        if (keys.length === 0) {
            this.relationshipsList.innerHTML = `<p class="no-data">${t('relationship.empty')}</p>`;
            return;
        }

        const affinityLabel = t('relationship.affinity');
        this.relationshipsList.innerHTML = keys.map(name => {
            const r = rels[name];
            return `
                <div class="relationship-item">
                    <span>${name}</span>
                    <span>${affinityLabel}: ${r.affinity}</span>
                </div>
            `;
        }).join('');
    }

    updateTimeDisplay() {
        const s = this.gameState;
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k, p) => `第${p?.day || s.day}天`;

        // 根据语言显示不同格式的时间
        let timeStr;
        if (window.I18N && window.I18N.isEnglish()) {
            timeStr = `Day ${s.day} ${String(s.hour).padStart(2, '0')}:${String(s.minute).padStart(2, '0')}`;
        } else {
            timeStr = `第${s.day}天 ${String(s.hour).padStart(2, '0')}:${String(s.minute).padStart(2, '0')}`;
        }
        this.gameTime.textContent = timeStr;

        // 更新时间图标
        if (s.hour >= 6 && s.hour < 12) {
            this.timeIcon.textContent = this.timeIcons.morning;
        } else if (s.hour >= 12 && s.hour < 18) {
            this.timeIcon.textContent = this.timeIcons.afternoon;
        } else if (s.hour >= 18 && s.hour < 21) {
            this.timeIcon.textContent = this.timeIcons.evening;
        } else {
            this.timeIcon.textContent = this.timeIcons.night;
        }
    }

    /**
     * 更新所有状态显示（时间、玩家面板等）
     * 用于时间推进后的统一更新
     */
    updateStats() {
        this.updateTimeDisplay();
        this.updatePlayerPanel();
    }

    updateLocationDisplay() {
        const location = this.gameState.currentLocation;
        // 翻译地点名称用于显示
        const displayLocation = window.I18N ? window.I18N.translateLocation(location) : location;

        this.currentLocationHeader.textContent = displayLocation;
        this.playerLocation.textContent = displayLocation;

        // 更新地图高亮
        document.querySelectorAll('.map-location').forEach(loc => {
            loc.classList.remove('current');
            if (loc.dataset.location === location) {
                loc.classList.add('current');
            }
        });

        // 更新行动按钮状态
        this.updateActionButtons();
    }

    /**
     * 根据当前地点特性更新行动按钮状态
     * - 休息：仅在有住宿设施的地点可用
     * - 工作：仅在有工作机会的地点可用
     * - 饮食：在有商店或酒馆的地点可用
     */
    updateActionButtons() {
        const location = this.gameState.currentLocation;
        const locData = this.worldLocations[location] || {};
        const npcsHere = this.npcs[location] || [];

        // 获取地点类型和特性
        const locationType = locData.type || locData.location_type || 'public';
        const features = locData.features || [];
        const jobs = locData.jobs || [];
        const isResidential = locData.is_residential || false;
        const isShop = locData.is_shop || false;

        // 检查是否有休息设施
        const hasRestFacility = isResidential ||
            locationType === 'residence' ||
            locationType === 'tavern' ||
            features.some(f => f.interaction_type === 'rest') ||
            location.includes('酒馆') ||
            location.includes('旅馆') ||
            location.includes('客栈') ||
            location.includes('住宅');

        // 检查是否有工作机会
        const hasWorkOpportunity = jobs.length > 0 ||
            locationType === 'workshop' ||
            locationType === 'shop' ||
            locationType === 'farm' ||
            features.some(f => f.interaction_type === 'work') ||
            location.includes('铁匠') ||
            location.includes('工坊') ||
            location.includes('农田') ||
            location.includes('市场') ||
            location.includes('店');

        // 检查是否可以饮食
        const canEat = isShop ||
            locationType === 'tavern' ||
            locationType === 'shop' ||
            location.includes('酒馆') ||
            location.includes('市场') ||
            location.includes('餐') ||
            location.includes('食');

        // 更新休息按钮
        if (this.btnRest) {
            this.btnRest.disabled = !hasRestFacility;
            this.btnRest.title = hasRestFacility ? '在此处休息恢复精力' : '此地点没有休息设施';
            this.btnRest.classList.toggle('disabled', !hasRestFacility);
        }

        // 更新工作按钮
        if (this.btnWork) {
            this.btnWork.disabled = !hasWorkOpportunity;
            this.btnWork.title = hasWorkOpportunity ? '在此处工作赚取金币' : '此地点没有工作机会';
            this.btnWork.classList.toggle('disabled', !hasWorkOpportunity);
        }

        // 更新饮食按钮
        if (this.btnEat) {
            this.btnEat.disabled = !canEat;
            this.btnEat.title = canEat ? '在此处用餐' : '此地点没有餐饮服务';
            this.btnEat.classList.toggle('disabled', !canEat);
        }

        // 社交按钮：如果当前位置没有NPC则禁用
        // 由于可以直接点击NPC进行社交，这个按钮主要作为备选
        if (this.btnSocialize) {
            const hasNPCs = npcsHere.length > 0;
            this.btnSocialize.disabled = !hasNPCs;
            this.btnSocialize.title = hasNPCs ? '与此处的NPC交谈' : '此地点没有可交谈的NPC';
            this.btnSocialize.classList.toggle('disabled', !hasNPCs);
        }
    }

    updateNPCList() {
        const location = this.gameState.currentLocation;
        const npcsHere = this.npcs[location] || [];
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;

        if (npcsHere.length === 0) {
            this.npcList.innerHTML = `<p class="no-data">${t('npc.empty')}</p>`;
            return;
        }

        this.npcList.innerHTML = npcsHere.map(npc => `
            <div class="npc-card" data-npc="${npc.name}">
                <div class="npc-avatar">${npc.icon}</div>
                <div class="npc-info">
                    <div class="npc-name">${npc.name}</div>
                    <div class="npc-profession">${npc.profession}</div>
                    <div class="npc-details">${npc.gender || ''} ${npc.age ? npc.age + '岁' : ''}</div>
                </div>
                <div class="npc-activity">${npc.activity}</div>
            </div>
        `).join('');

        // 绑定NPC点击事件
        this.npcList.querySelectorAll('.npc-card').forEach(card => {
            card.addEventListener('click', () => this.selectNPC(card.dataset.npc));
        });
    }

    enableDialogueIfNPCsPresent() {
        const location = this.gameState.currentLocation;
        const npcsHere = this.npcs[location] || [];

        if (npcsHere.length > 0) {
            this.dialogueInput.disabled = false;
            this.btnSendDialogue.disabled = false;
        } else {
            this.dialogueInput.disabled = true;
            this.btnSendDialogue.disabled = true;
        }
    }

    // ========== 地图移动 ==========

    moveToLocation(e) {
        const loc = e.target.closest('.map-location');
        if (!loc) return;

        const newLocation = loc.dataset.location;
        if (newLocation === this.gameState.currentLocation) return;

        const oldLocation = this.gameState.currentLocation;
        this.gameState.currentLocation = newLocation;

        // 移动消耗时间
        this.advanceTime(0.25, false);

        // 更新UI
        this.updateLocationDisplay();
        this.updateNPCList();
        this.enableDialogueIfNPCsPresent();
        this.clearDialogue();

        this.addDialogueMessage(`你从${oldLocation}来到了${newLocation}`, 'system');
        this.addLog('移动', `${this.gameState.player.name} 移动到 ${newLocation}`, 'info');
        this.saveGame();
    }

    // ========== 时间控制 ==========

    togglePause() {
        this.gameState.isPaused = !this.gameState.isPaused;
        this.btnPause.textContent = this.gameState.isPaused ? '▶️' : '⏸️';
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;
        this.showToast(this.gameState.isPaused ? t('time.paused') : t('time.resumed'), 'info');
    }

    advanceTime(hours, showMessage = true) {
        const minutes = hours * 60;
        this.gameState.minute += minutes;

        while (this.gameState.minute >= 60) {
            this.gameState.minute -= 60;
            this.gameState.hour++;
        }

        while (this.gameState.hour >= 24) {
            this.gameState.hour -= 24;
            this.gameState.day++;
        }

        // 需求变化
        this.gameState.hunger = Math.max(0, this.gameState.hunger - hours * 0.06);
        this.gameState.energy = Math.max(0, this.gameState.energy - hours * 0.04);

        this.updateTimeDisplay();
        this.updatePlayerPanel();

        if (showMessage) {
            this.addLog('时间', `时间推进 ${hours} 小时`, 'info');
        }

        // 更新活动事件状态
        if (hours >= 1 && this.gameState.activeEvents.length > 0) {
            this.updateWorldEvents(Math.floor(hours));
        }

        // 随机事件触发（每小时有15%概率触发随机事件）
        if (hours >= 1) {
            this.tryTriggerRandomEvent(hours);
        }

        this.saveGame();
    }

    /**
     * 尝试触发随机事件
     */
    tryTriggerRandomEvent(hours) {
        const eventChance = 0.15 * hours; // 每小时15%概率
        if (Math.random() > eventChance) return;

        // 获取当前位置的NPC
        const npcsHere = this.npcs[this.gameState.currentLocation] || [];
        if (npcsHere.length === 0) return;

        // 随机事件模板
        const eventTemplates = [
            { type: 'npc_activity', templates: [
                '{npc}正在{activity}，看起来心情{mood}。',
                '{npc}放下手中的活计，伸了个懒腰。',
                '{npc}哼着小曲，似乎想起了什么开心的事。',
                '{npc}皱着眉头，似乎在为什么事情烦恼。'
            ]},
            { type: 'environmental', templates: [
                '一阵微风吹过，带来了远处田野的清香。',
                '天空中飘过几朵白云，阳光温暖宜人。',
                '远处传来几声鸟鸣，让人感到宁静。',
                '街道上传来孩童嬉戏的笑声。'
            ]},
            { type: 'social', templates: [
                '{npc}向你点头致意。',
                '{npc}注意到了你，微微一笑。',
                '你听到{npc}和路人打招呼的声音。'
            ]}
        ];

        // 随机选择事件类型和模板
        const eventType = eventTemplates[Math.floor(Math.random() * eventTemplates.length)];
        const template = eventType.templates[Math.floor(Math.random() * eventType.templates.length)];

        // 随机选择NPC
        const npc = npcsHere[Math.floor(Math.random() * npcsHere.length)];

        // 填充模板
        const moods = ['不错', '一般', '有些忧虑', '很开心'];
        const activities = ['忙碌', '休息', '整理物品', '与人交谈'];

        let eventText = template
            .replace('{npc}', npc.name)
            .replace('{mood}', moods[Math.floor(Math.random() * moods.length)])
            .replace('{activity}', activities[Math.floor(Math.random() * activities.length)]);

        // 显示在NPC反应面板（后台事件专用）
        this.addNPCResponse('世界', eventText);
        this.addLog('环境', eventText.substring(0, 40) + '...', 'info');
    }

    async updateWorldEvents(hours) {
        // 调用后端更新事件状态
        try {
            const response = await window.api.post(`/api/v1/world/time/advance/events?hours=${hours}`, {});

            if (response.updated_events && response.updated_events.length > 0) {
                for (const event of response.updated_events) {
                    this.addDialogueMessage(
                        `[事件进展] ${event.content} - ${event.phase_description}`,
                        'system'
                    );
                    this.addLog('事件', `${event.content} 进入阶段: ${event.phase_description}`, 'warning');

                    // 获取NPC对新阶段的反应
                    await this.getEventPhaseReactions(event);
                }
            }

            if (response.ended_events && response.ended_events.length > 0) {
                for (const event of response.ended_events) {
                    this.addDialogueMessage(`[事件结束] ${event.content}`, 'system');
                    this.addLog('事件', `${event.content} 已结束`, 'success');

                    // 从本地活动事件列表中移除
                    this.gameState.activeEvents = this.gameState.activeEvents.filter(
                        e => e.content !== event.content
                    );
                }
                this.renderActiveEvents();
            }

            // 更新活动事件的阶段描述
            if (response.active_events) {
                for (const activeEvent of response.active_events) {
                    const localEvent = this.gameState.activeEvents.find(
                        e => e.content === activeEvent.content
                    );
                    if (localEvent) {
                        localEvent.phase = activeEvent.current_phase;
                        localEvent.phase_description = activeEvent.phase_description;
                    }
                }
                this.renderActiveEvents();
            }

        } catch (error) {
            console.error('更新世界事件失败:', error);
        }
    }

    async getEventPhaseReactions(event) {
        // 获取相关NPC对事件新阶段的反应
        const allNPCs = this.getAllNPCs();
        const playerLocation = this.gameState.currentLocation;
        // 只获取1-2个NPC的反应，避免太多API调用
        const npcsToReact = allNPCs.slice(0, 2);

        for (const npc of npcsToReact) {
            const npcLocation = this.getNPCLocation(npc.name);
            const isNPCHere = npcLocation === playerLocation;

            try {
                const response = await window.api.post('/api/v1/world/event/trigger', {
                    event_content: event.content,
                    event_type: 'world_event',
                    location: event.location,
                    npc_name: npc.name,
                    context: {
                        day: this.gameState.day,
                        hour: this.gameState.hour,
                        npc_location: npcLocation
                    }
                });

                if (response.response) {
                    const phaseDesc = response.phase_description ? ` [${response.phase_description}]` : '';
                    // 如果NPC在玩家当前场景，显示在对话框中
                    if (isNPCHere) {
                        this.addDialogueMessage(response.response + phaseDesc, 'npc', npc.name);
                    } else {
                        this.addNPCResponse(npc.name, response.response + phaseDesc);
                    }
                }
            } catch (error) {
                console.error(`获取${npc.name}的事件阶段反应失败:`, error);
            }
        }
    }

    // ========== 玩家行动 ==========

    actionSocialize() {
        const location = this.gameState.currentLocation;
        const npcsHere = this.npcs[location] || [];
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;

        if (npcsHere.length === 0) {
            this.showToast(t('social.noNpc'), 'warning');
            return;
        }

        // 打开社交选择模态框
        const socialList = document.getElementById('social-npc-list');
        socialList.innerHTML = npcsHere.map(npc => `
            <div class="social-npc-item" data-npc="${npc.name}">
                <div class="npc-avatar">${npc.icon}</div>
                <div class="npc-info">
                    <div class="npc-name">${npc.name}</div>
                    <div class="npc-profession">${npc.profession}</div>
                </div>
            </div>
        `).join('');

        socialList.querySelectorAll('.social-npc-item').forEach(item => {
            item.addEventListener('click', () => {
                this.startConversation(item.dataset.npc);
                this.closeModal('social-modal');
            });
        });

        this.openModal('social-modal');
    }

    startConversation(npcName) {
        this.gameState.conversationTarget = npcName;
        this.dialogueInput.disabled = false;
        this.btnSendDialogue.disabled = false;
        this.dialogueInput.placeholder = `对 ${npcName} 说...`;
        this.dialogueInput.focus();

        // 查找NPC详细信息
        const npc = this.findNPCByName(npcName);

        // 清空对话区域并显示NPC信息
        this.dialogueContent.innerHTML = '';

        if (npc) {
            // 显示NPC详细信息卡片
            const infoHtml = `
                <div class="npc-info-card">
                    <div class="npc-info-header">
                        <span class="npc-info-icon">${npc.icon}</span>
                        <span class="npc-info-name">${npc.name}</span>
                    </div>
                    <div class="npc-info-body">
                        <div class="npc-info-row"><span>职业:</span> ${npc.profession}</div>
                        <div class="npc-info-row"><span>性别:</span> ${npc.gender || '未知'}</div>
                        <div class="npc-info-row"><span>年龄:</span> ${npc.age || '未知'}岁</div>
                        ${npc.race ? `<div class="npc-info-row"><span>种族:</span> ${npc.race}</div>` : ''}
                        ${npc.traits && npc.traits.length > 0 ? `<div class="npc-info-row"><span>性格:</span> ${npc.traits.join('、')}</div>` : ''}
                        ${npc.background ? `<div class="npc-info-row npc-background"><span>背景:</span> ${npc.background}</div>` : ''}
                    </div>
                </div>
            `;
            this.dialogueContent.innerHTML = infoHtml;
        }

        this.addDialogueMessage(`你走向${npcName}，准备交谈`, 'system');

        // 显示历史对话记录（如果有）
        this.loadConversationHistory(npcName);
    }

    /**
     * 根据名字查找NPC
     */
    findNPCByName(npcName) {
        for (const location in this.npcs) {
            const npc = this.npcs[location].find(n => n.name === npcName);
            if (npc) return npc;
        }
        return null;
    }

    /**
     * 加载与NPC的对话历史
     */
    loadConversationHistory(npcName) {
        // 从本地存储加载对话历史
        const historyKey = `conversation_${npcName}`;
        const history = JSON.parse(localStorage.getItem(historyKey) || '[]');

        if (history.length > 0) {
            this.addDialogueMessage('--- 历史对话 ---', 'system');
            // 只显示最近5条
            const recentHistory = history.slice(-5);
            for (const msg of recentHistory) {
                if (msg.type === 'player') {
                    this.addDialogueMessage(msg.text, 'player');
                } else {
                    this.addDialogueMessage(msg.text, 'npc', npcName);
                }
            }
            this.addDialogueMessage('--- 继续对话 ---', 'system');
        }
    }

    /**
     * 保存对话到历史记录
     */
    saveToConversationHistory(npcName, text, type) {
        const historyKey = `conversation_${npcName}`;
        const history = JSON.parse(localStorage.getItem(historyKey) || '[]');
        history.push({ text, type, timestamp: Date.now() });
        // 只保留最近20条
        if (history.length > 20) {
            history.splice(0, history.length - 20);
        }
        localStorage.setItem(historyKey, JSON.stringify(history));
    }

    selectNPC(npcName) {
        this.startConversation(npcName);

        // 高亮选中的NPC
        this.npcList.querySelectorAll('.npc-card').forEach(card => {
            card.classList.remove('selected');
            if (card.dataset.npc === npcName) {
                card.classList.add('selected');
            }
        });
    }

    async actionEat() {
        // 检查当前地点是否可以饮食
        const location = this.gameState.currentLocation;
        const locData = this.worldLocations[location] || {};
        const locationType = locData.type || locData.location_type || 'public';
        const isShop = locData.is_shop || false;

        const canEat = isShop ||
            locationType === 'tavern' ||
            locationType === 'shop' ||
            location.includes('酒馆') ||
            location.includes('市场') ||
            location.includes('餐') ||
            location.includes('食');

        if (!canEat) {
            this.showToast('此地点没有餐饮服务，请前往酒馆或市场', 'warning');
            return;
        }

        // 使用后端 API 处理饮食
        try {
            const result = await window.api.playerAction('eat');

            if (result.result && result.result.success) {
                // 更新本地状态
                if (result.player) {
                    this.gameState.gold = result.player.gold;
                    this.gameState.hunger = 1 - (result.player.needs?.hunger || 0);
                }
                if (result.world_time) {
                    this.gameState.hour = result.world_time.hour;
                    this.gameState.day = result.world_time.day || this.gameState.day;
                }

                this.addDialogueMessage(result.result.message || '你享用了一顿美餐', 'system');
                this.addLog('饮食', `${this.gameState.player.name} 用餐`, 'info');
            } else {
                this.showToast(result.result?.message || '饮食失败', 'warning');
            }
        } catch (error) {
            console.error('饮食操作失败:', error);
            // 降级到本地处理
            const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;
            if (this.gameState.gold < 5) {
                this.showToast(t('toast.notEnoughGold'), 'warning');
                return;
            }
            this.gameState.gold -= 5;
            this.gameState.hunger = Math.min(1, this.gameState.hunger + 0.4);
            this.advanceTime(0.5, false);
            this.addDialogueMessage('你享用了一顿美餐，花费5金币', 'system');
            this.addLog('饮食', `${this.gameState.player.name} 用餐`, 'info');
        }
        this.updatePlayerPanel();
    }

    async actionWork() {
        // 检查当前地点是否有工作机会
        const location = this.gameState.currentLocation;
        const locData = this.worldLocations[location] || {};
        const locationType = locData.type || locData.location_type || 'public';
        const features = locData.features || [];
        const jobs = locData.jobs || [];

        const hasWorkOpportunity = jobs.length > 0 ||
            locationType === 'workshop' ||
            locationType === 'shop' ||
            locationType === 'farm' ||
            features.some(f => f.interaction_type === 'work') ||
            location.includes('铁匠') ||
            location.includes('工坊') ||
            location.includes('农田') ||
            location.includes('市场') ||
            location.includes('店');

        if (!hasWorkOpportunity) {
            this.showToast('此地点没有工作机会，请前往工坊、商店或农田', 'warning');
            return;
        }

        // 使用后端 API 处理工作
        try {
            const result = await window.api.playerAction('work');

            if (result.result && result.result.success) {
                // 更新本地状态
                if (result.player) {
                    this.gameState.gold = result.player.gold;
                    this.gameState.energy = 1 - (result.player.needs?.fatigue || 0);
                }
                if (result.world_time) {
                    this.gameState.hour = result.world_time.hour;
                    this.gameState.day = result.world_time.day || this.gameState.day;
                }

                this.addDialogueMessage(result.result.message || '你完成了工作', 'system');
                this.addLog('工作', `${this.gameState.player.name} 工作`, 'info');
            } else {
                this.showToast(result.result?.message || '工作失败', 'warning');
            }
        } catch (error) {
            console.error('工作操作失败:', error);
            // 降级到本地处理
            this.gameState.gold += 10;
            this.gameState.energy = Math.max(0, this.gameState.energy - 0.15);
            this.advanceTime(1, false);
            this.addDialogueMessage('你工作了一小时，获得10金币', 'system');
            this.addLog('工作', `${this.gameState.player.name} 工作`, 'info');
        }
        this.updatePlayerPanel();
    }

    async actionRest() {
        // 检查当前地点是否有休息设施
        const location = this.gameState.currentLocation;
        const locData = this.worldLocations[location] || {};
        const locationType = locData.type || locData.location_type || 'public';
        const features = locData.features || [];
        const isResidential = locData.is_residential || false;

        const hasRestFacility = isResidential ||
            locationType === 'residence' ||
            locationType === 'tavern' ||
            features.some(f => f.interaction_type === 'rest') ||
            location.includes('酒馆') ||
            location.includes('旅馆') ||
            location.includes('客栈') ||
            location.includes('住宅');

        if (!hasRestFacility) {
            this.showToast('此地点没有休息设施，请前往酒馆或住宅区', 'warning');
            return;
        }

        // 使用后端 API 处理休息
        try {
            const result = await window.api.playerAction('rest');

            if (result.result && result.result.success) {
                // 更新本地状态
                if (result.player) {
                    this.gameState.energy = 1 - (result.player.needs?.fatigue || 0);
                }
                if (result.world_time) {
                    this.gameState.hour = result.world_time.hour;
                    this.gameState.day = result.world_time.day || this.gameState.day;
                }

                this.addDialogueMessage(result.result.message || '你休息了一会儿', 'system');
                this.addLog('休息', `${this.gameState.player.name} 休息`, 'info');
            } else {
                this.showToast(result.result?.message || '休息失败', 'warning');
            }
        } catch (error) {
            console.error('休息操作失败:', error);
            // 降级到本地处理
            this.gameState.energy = Math.min(1, this.gameState.energy + 0.3);
            this.advanceTime(0.5, false);
            this.addDialogueMessage('你休息了一会儿，感觉精神好多了', 'system');
            this.addLog('休息', `${this.gameState.player.name} 休息`, 'info');
        }
        this.updatePlayerPanel();
    }

    // ========== 对话系统 ==========

    clearDialogue() {
        this.dialogueContent.innerHTML = '<p class="system-message">选择一个NPC开始交谈</p>';
        this.gameState.conversationTarget = null;
        this.dialogueInput.placeholder = '输入你想说的话...';
    }

    addDialogueMessage(text, type, speaker = null) {
        // 移除初始提示
        const placeholder = this.dialogueContent.querySelector('.system-message');
        if (placeholder && type !== 'system') {
            placeholder.remove();
        }

        const msgDiv = document.createElement('div');
        msgDiv.className = `dialogue-message ${type}`;

        if (type === 'system') {
            msgDiv.classList.add('system-message');
            msgDiv.textContent = text;
        } else if (type === 'player') {
            msgDiv.textContent = text;
        } else if (type === 'npc') {
            msgDiv.innerHTML = `<div class="npc-speaker">${speaker}</div>${text}`;
        }

        this.dialogueContent.appendChild(msgDiv);
        this.dialogueContent.parentElement.scrollTop = this.dialogueContent.parentElement.scrollHeight;
    }

    async sendDialogue() {
        const message = this.dialogueInput.value.trim();
        if (!message) return;

        const target = this.gameState.conversationTarget;
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;

        if (!target) {
            // 如果没有选择目标，尝试选择第一个NPC
            const npcsHere = this.npcs[this.gameState.currentLocation] || [];
            if (npcsHere.length > 0) {
                this.gameState.conversationTarget = npcsHere[0].name;
            } else {
                this.showToast(t('toast.selectNpc'), 'warning');
                return;
            }
        }

        // 显示玩家消息
        this.addDialogueMessage(message, 'player');
        this.dialogueInput.value = '';

        // 保存玩家消息到历史记录
        this.saveToConversationHistory(this.gameState.conversationTarget, message, 'player');

        // 更新社交需求
        this.gameState.social = Math.min(1, this.gameState.social + 0.05);
        this.updatePlayerPanel();

        // 更新关系
        if (!this.gameState.relationships[this.gameState.conversationTarget]) {
            this.gameState.relationships[this.gameState.conversationTarget] = { affinity: 50, trust: 50, interactions: 0 };
        }
        this.gameState.relationships[this.gameState.conversationTarget].affinity += 1;
        this.gameState.relationships[this.gameState.conversationTarget].interactions++;
        this.updateRelationships();

        // 调用API获取NPC响应
        await this.getNPCResponse(message, this.gameState.conversationTarget);

        this.advanceTime(0.25, false);
        this.saveGame();
    }

    async getNPCResponse(message, npcName) {
        this.llmStatus.classList.add('loading');
        this.llmStatus.textContent = 'LLM...';

        try {
            // 构建玩家信息
            const playerInfo = this.gameState.player ? {
                name: this.gameState.player.name || '旅行者',
                age: this.gameState.player.age || 28,
                gender: this.gameState.player.gender || '男性',
                profession: this.gameState.player.profession || '冒险者',
                background: this.gameState.player.background || ''
            } : null;

            const response = await window.api.post('/api/v1/world/dialogue', {
                player_message: message,
                npc_name: npcName,
                location: this.gameState.currentLocation,
                context: {
                    day: this.gameState.day,
                    hour: this.gameState.hour
                },
                player_info: playerInfo
            });

            const npcResponse = response.response || response.npc_response || `${npcName}看着你，似乎在思考该如何回应。`;

            // 只在对话框中显示NPC回复（不在右侧NPC反应面板重复显示）
            this.addDialogueMessage(npcResponse, 'npc', npcName);
            this.addLog('对话', `${npcName}: ${npcResponse.substring(0, 50)}...`, 'npc');

            // 保存NPC响应到历史记录
            this.saveToConversationHistory(npcName, npcResponse, 'npc');

        } catch (error) {
            console.error('获取NPC响应失败:', error);
            // 使用离线响应
            const fallbackResponses = [
                `${npcName}友好地看着你，点了点头。`,
                `${npcName}似乎很忙，但还是停下来听你说话。`,
                `${npcName}微笑着回应你。`
            ];
            const fallback = fallbackResponses[Math.floor(Math.random() * fallbackResponses.length)];
            this.addDialogueMessage(fallback, 'npc', npcName);
            // 回退响应不需要重复显示在NPC反应面板
        } finally {
            this.llmStatus.classList.remove('loading');
            this.llmStatus.textContent = 'LLM';
        }
    }

    addNPCResponse(npcName, response) {
        // 清除"暂无"提示
        const noData = this.npcResponseBox.querySelector('.no-data');
        if (noData) noData.remove();

        const timeStr = `第${this.gameState.day}天 ${String(this.gameState.hour).padStart(2, '0')}:${String(this.gameState.minute).padStart(2, '0')}`;

        const responseDiv = document.createElement('div');
        responseDiv.className = 'npc-response';
        responseDiv.innerHTML = `
            <div class="response-header">
                <span class="response-npc-name">${npcName}</span>
                <span>${timeStr}</span>
            </div>
            <div class="response-text">${response}</div>
        `;

        this.npcResponseBox.insertBefore(responseDiv, this.npcResponseBox.firstChild);

        // 限制显示数量
        while (this.npcResponseBox.children.length > 10) {
            this.npcResponseBox.lastChild.remove();
        }
    }

    // ========== 世界事件 ==========

    async triggerWorldEvent() {
        const eventContent = this.eventInput.value.trim();
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;

        if (!eventContent) {
            this.showToast(t('toast.enterEvent'), 'warning');
            return;
        }

        const location = this.eventLocation.value || this.gameState.currentLocation;

        // 判断事件严重程度
        const severity = this.calculateEventSeverity(eventContent);

        // 添加到活动事件列表
        const event = {
            id: Date.now(),
            content: eventContent,
            location: location,
            severity: severity,
            time: `第${this.gameState.day}天 ${String(this.gameState.hour).padStart(2, '0')}:${String(this.gameState.minute).padStart(2, '0')}`
        };
        this.gameState.activeEvents.push(event);

        this.renderActiveEvents();
        this.eventInput.value = '';

        // 在地图上高亮事件位置
        this.highlightEventOnMap(location, severity);

        this.addDialogueMessage(`[世界事件] ${eventContent} (发生在${location})`, 'system');
        this.addLog('事件', `[${location}] ${eventContent} (严重度: ${severity})`, 'warning');

        // 启动异步事件传播
        await this.startAsyncEventPropagation(event);

        this.saveGame();
    }

    /**
     * 计算事件严重程度 (1-10)
     */
    calculateEventSeverity(eventContent) {
        const highSeverityKeywords = ['火', '燃烧', '着火', '爆炸', '死亡', '攻击', '入侵'];
        const mediumSeverityKeywords = ['倒塌', '洪水', '地震', '强盗', '怪物', '危险'];
        const lowSeverityKeywords = ['争吵', '丢失', '迷路', '受伤'];

        if (highSeverityKeywords.some(k => eventContent.includes(k))) {
            return 9;
        } else if (mediumSeverityKeywords.some(k => eventContent.includes(k))) {
            return 6;
        } else if (lowSeverityKeywords.some(k => eventContent.includes(k))) {
            return 4;
        }
        return 3; // 默认低严重度
    }

    /**
     * 真正的异步事件传播 - 基于游戏内时间，逐个请求NPC决策
     * 传播延迟以游戏内分钟计算，并推进游戏时间
     */
    async startAsyncEventPropagation(event) {
        const playerLocation = this.gameState.currentLocation;

        try {
            this.addDialogueMessage(`--- [${event.location}] 事件发生 ---`, 'system');

            // 1. 获取所有NPC状态，计算传播顺序
            const npcStatesResponse = await window.api.getAllNPCAgentStates();
            if (!npcStatesResponse.npcs) {
                console.error('获取NPC状态失败');
                return;
            }

            const npcs = npcStatesResponse.npcs;
            const propagationQueue = [];

            // 2. 为每个NPC计算传播延迟（游戏内分钟）并排序
            for (const [npcName, npcData] of Object.entries(npcs)) {
                const npcLocation = npcData.location;
                const delayMinutes = this.calculatePropagationDelayMinutes(event.location, npcLocation, event.severity);
                const isForeground = npcLocation === playerLocation;
                const isAtEventLocation = npcLocation === event.location;

                propagationQueue.push({
                    npcName,
                    npcLocation,
                    delayMinutes,  // 游戏内分钟
                    isForeground,
                    isAtEventLocation,
                    profession: npcData.profession,
                    activity: npcData.current_activity
                });
            }

            // 按延迟时间排序
            propagationQueue.sort((a, b) => a.delayMinutes - b.delayMinutes);

            this.addLog('事件传播', `开始传播事件到 ${propagationQueue.length} 个NPC`, 'info');

            // 3. 按游戏时间顺序处理NPC
            let lastDelayMinutes = 0;
            for (const npc of propagationQueue) {
                // 计算距离上一个NPC的时间差
                const timeDelta = npc.delayMinutes - lastDelayMinutes;

                // 如果有时间差，推进游戏时间
                if (timeDelta > 0) {
                    this.advanceGameTimeMinutes(timeDelta);
                    this.addLog('时间流逝', `${timeDelta}分钟后...`, 'info');
                }

                // 请求NPC决策
                await this.requestSingleNPCDecision(event, npc, playerLocation);

                lastDelayMinutes = npc.delayMinutes;
            }

            // 4. 记录传播完成
            this.addLog('事件传播', `事件传播完成，共耗时${lastDelayMinutes}游戏分钟`, 'success');

        } catch (error) {
            console.error('事件传播失败:', error);
            // 回退到同步处理
            await this.notifyNPCsOfEvent(event);
        }
    }

    /**
     * 推进游戏时间（分钟）
     */
    advanceGameTimeMinutes(minutes) {
        this.gameState.minute += minutes;

        // 处理分钟溢出
        while (this.gameState.minute >= 60) {
            this.gameState.minute -= 60;
            this.gameState.hour++;
        }

        // 处理小时溢出
        while (this.gameState.hour >= 24) {
            this.gameState.hour -= 24;
            this.gameState.day++;
        }

        // 更新状态（饥饿、体力等）
        const hours = minutes / 60;
        this.gameState.hunger = Math.max(0, this.gameState.hunger - hours * 0.06);
        this.gameState.energy = Math.max(0, this.gameState.energy - hours * 0.04);

        this.updateStats();
    }

    /**
     * 计算传播延迟（游戏内分钟）
     * 每步距离 = 5分钟（普通）/ 2分钟（紧急）
     */
    calculatePropagationDelayMinutes(fromLocation, toLocation, severity) {
        const adjacency = {
            '村庄大门': ['镇中心', '森林边缘'],
            '镇中心': ['村庄大门', '酒馆', '市场区', '教堂'],
            '酒馆': ['镇中心', '市场区'],
            '市场区': ['镇中心', '酒馆', '铁匠铺'],
            '铁匠铺': ['市场区', '工坊区'],
            '教堂': ['镇中心', '农田'],
            '工坊区': ['铁匠铺', '农田'],
            '农田': ['教堂', '工坊区', '森林边缘'],
            '森林边缘': ['村庄大门', '农田']
        };

        // BFS计算距离
        if (fromLocation === toLocation) return 0;

        const visited = new Set([fromLocation]);
        const queue = [[fromLocation, 0]];

        while (queue.length > 0) {
            const [current, dist] = queue.shift();
            const neighbors = adjacency[current] || [];
            for (const neighbor of neighbors) {
                if (neighbor === toLocation) {
                    // 基础延迟：每步5游戏分钟
                    // 紧急事件：每步2游戏分钟
                    const baseDelayPerStep = severity >= 7 ? 2 : 5;
                    return (dist + 1) * baseDelayPerStep;
                }
                if (!visited.has(neighbor)) {
                    visited.add(neighbor);
                    queue.push([neighbor, dist + 1]);
                }
            }
        }

        return 15; // 默认15游戏分钟（较远）
    }

    /**
     * 请求单个NPC的决策（真正的按需异步）
     */
    async requestSingleNPCDecision(event, npcInfo, playerLocation) {
        const { npcName, npcLocation, isForeground, profession, activity } = npcInfo;

        try {
            this.addLog('NPC决策', `${npcName} 收到事件通知...`, 'info');

            // 调用单NPC决策API
            const response = await window.api.npcAgentDecide({
                npc_name: npcName,
                event_content: event.content,
                event_location: event.location,
                npc_location: npcLocation,
                context: {
                    day: this.gameState.day,
                    hour: this.gameState.hour,
                    severity: event.severity,
                    player_location: playerLocation,
                    profession: profession,
                    activity: activity
                }
            });

            if (response.status === 'success') {
                const actionIcon = this.getActionIcon(response.action?.action_type || 'continue');
                const description = response.description || '无反应';

                // 根据NPC位置决定显示方式
                if (isForeground) {
                    // 前台：显示在对话框
                    this.addDialogueMessage(`${actionIcon} ${description}`, 'npc', npcName);
                } else {
                    // 后台：显示在NPC响应区域
                    this.addNPCResponse(npcName, `[${npcLocation}] ${actionIcon} ${description}`);
                }

                // 处理NPC移动
                if (response.new_location && response.new_location !== npcLocation) {
                    setTimeout(() => {
                        this.addDialogueMessage(
                            `🚶 ${npcName} 从 ${npcLocation} 赶往 ${response.new_location}`,
                            'system'
                        );
                        this.updateLocalNPCLocation(npcName, npcLocation, response.new_location, response.action?.reason);
                        this.updateNPCList();
                    }, 500);
                }

                // 更新传播计数
                if (this.currentPropagation) {
                    this.currentPropagation.processedNPCs++;
                }
            }

        } catch (error) {
            console.error(`NPC ${npcName} 决策请求失败:`, error);
            // 使用规则回退
            this.addNPCResponse(npcName, `[${npcLocation}] 注意到了事件但没有特别反应`);
        }
    }

    renderActiveEvents() {
        if (this.gameState.activeEvents.length === 0) {
            this.activeEvents.innerHTML = '';
            return;
        }

        this.activeEvents.innerHTML = this.gameState.activeEvents.slice(-3).map(e => `
            <div class="event-item">
                <strong>[${e.location}]</strong> ${e.content}
                ${e.phase_description ? `<span style="color: var(--warning); margin-left: 8px;">[${e.phase_description}]</span>` : ''}
                <div style="font-size: 0.7rem; color: var(--text-muted);">${e.time}</div>
            </div>
        `).join('');
    }

    async notifyNPCsOfEvent(event) {
        const playerLocation = this.gameState.currentLocation;
        const eventLocation = event.location;

        this.llmStatus.classList.add('loading');

        try {
            // 使用新的NPC Agent系统处理事件
            const response = await window.api.processEventWithAgents({
                event_content: event.content,
                event_location: eventLocation,
                event_type: 'world_event',
                player_location: playerLocation,
                context: {
                    day: this.gameState.day,
                    hour: this.gameState.hour
                }
            });

            if (response.status === 'success') {
                // 处理前台响应（玩家当前位置的NPC）
                if (response.foreground_responses && response.foreground_responses.length > 0) {
                    this.addDialogueMessage('--- 当前场景的NPC反应 ---', 'system');
                    for (const resp of response.foreground_responses) {
                        const actionType = resp.action?.action_type || 'continue';
                        const actionIcon = this.getActionIcon(actionType);
                        const message = `${actionIcon} ${resp.description}`;
                        this.addDialogueMessage(message, 'npc', resp.npc_name);

                        // 如果NPC有思考过程，可以显示（可选）
                        if (resp.thinking && resp.thinking.length > 10) {
                            this.addLog('NPC思考', `${resp.npc_name}: ${resp.thinking.substring(0, 80)}...`, 'debug');
                        }
                    }
                }

                // 处理后台响应（其他位置的NPC）
                if (response.background_responses && response.background_responses.length > 0) {
                    this.addDialogueMessage('--- 其他位置的NPC反应 ---', 'system');
                    for (const resp of response.background_responses) {
                        const actionType = resp.action?.action_type || 'continue';
                        const actionIcon = this.getActionIcon(actionType);
                        const locationInfo = `[${resp.original_location}]`;
                        this.addNPCResponse(resp.npc_name, `${locationInfo} ${actionIcon} ${resp.description}`);
                    }
                }

                // 处理NPC移动
                if (response.npc_movements && response.npc_movements.length > 0) {
                    this.addDialogueMessage('--- NPC移动 ---', 'system');
                    for (const movement of response.npc_movements) {
                        this.addDialogueMessage(
                            `🚶 ${movement.npc_name} 从 ${movement.from} 前往 ${movement.to}`,
                            'system'
                        );

                        // 更新本地NPC位置数据
                        this.updateLocalNPCLocation(movement.npc_name, movement.from, movement.to, movement.reason);
                    }

                    // 刷新NPC列表
                    this.updateNPCList();
                }

                // 更新事件状态
                event.is_emergency = response.is_emergency;
                this.renderActiveEvents();

                this.addLog('事件处理',
                    `前台响应: ${response.foreground_responses?.length || 0}, ` +
                    `后台响应: ${response.background_responses?.length || 0}, ` +
                    `NPC移动: ${response.npc_movements?.length || 0}`,
                    'success'
                );
            }

        } catch (error) {
            console.error('NPC Agent事件处理失败:', error);
            // 回退到简单通知
            await this.notifyNPCsOfEventFallback(event);
        }

        this.llmStatus.classList.remove('loading');
    }

    /**
     * 获取行动类型对应的图标
     */
    getActionIcon(actionType) {
        const icons = {
            'move': '🚶',
            'speak': '💬',
            'work': '🔨',
            'help': '🤝',
            'observe': '👀',
            'flee': '🏃',
            'alert': '⚠️',
            'continue': '➡️',
            'rest': '😴',
            'socialize': '🗣️'
        };
        return icons[actionType] || '❓';
    }

    /**
     * 更新本地NPC位置数据
     */
    updateLocalNPCLocation(npcName, fromLocation, toLocation, reason) {
        // 在地图上显示移动动画
        this.animateNPCMovementOnMap(npcName, fromLocation, toLocation);

        // 从原位置移除
        if (this.npcs[fromLocation]) {
            const index = this.npcs[fromLocation].findIndex(n => n.name === npcName);
            if (index !== -1) {
                const npc = this.npcs[fromLocation].splice(index, 1)[0];

                // 更新活动
                npc.activity = reason || `前往${toLocation}`;

                // 添加到新位置
                if (!this.npcs[toLocation]) {
                    this.npcs[toLocation] = [];
                }
                this.npcs[toLocation].push(npc);
            }
        }

        // 延迟更新地图（等动画完成）
        setTimeout(() => this.updateWorldMap(), 2100);
    }

    /**
     * 回退的NPC通知方法（当Agent系统失败时使用）
     */
    async notifyNPCsOfEventFallback(event) {
        const playerLocation = this.gameState.currentLocation;
        const eventLocation = event.location;
        const allNPCs = this.getAllNPCs();
        const isEmergency = this.isEmergencyEvent(event.content);

        for (const npc of allNPCs) {
            const npcLocation = this.getNPCLocation(npc.name);
            const isNPCHere = npcLocation === playerLocation;

            try {
                const response = await window.api.post('/api/v1/world/event/trigger', {
                    event_content: event.content,
                    event_type: 'world_event',
                    location: eventLocation,
                    npc_name: npc.name,
                    context: {
                        day: this.gameState.day,
                        hour: this.gameState.hour,
                        npc_location: npcLocation,
                        player_location: playerLocation
                    }
                });

                const npcReaction = response.response || response.npc_reaction || `${npc.name}注意到了这个事件。`;

                if (isNPCHere) {
                    this.addDialogueMessage(npcReaction, 'npc', npc.name);
                } else {
                    this.addNPCResponse(npc.name, npcReaction);
                }

                // 紧急事件时移动NPC
                if (isEmergency && npcLocation !== eventLocation) {
                    this.updateLocalNPCLocation(npc.name, npcLocation, eventLocation, event.content);
                }

            } catch (error) {
                console.error(`获取${npc.name}的事件反应失败:`, error);
                if (isNPCHere) {
                    this.addDialogueMessage(`${npc.name}注意到了周围发生的事情。`, 'npc', npc.name);
                }
            }
        }
    }

    isEmergencyEvent(eventContent) {
        // 判断是否是紧急事件
        const emergencyKeywords = ['火', '燃烧', '着火', '爆炸', '攻击', '入侵', '强盗', '怪物', '倒塌', '洪水', '地震'];
        return emergencyKeywords.some(keyword => eventContent.includes(keyword));
    }

    async moveNPCToLocation(npcName, fromLocation, toLocation, reason) {
        // 从原位置移除NPC
        const fromNPCs = this.npcs[fromLocation];
        if (!fromNPCs) return;

        const npcIndex = fromNPCs.findIndex(n => n.name === npcName);
        if (npcIndex === -1) return;

        const npc = fromNPCs[npcIndex];

        // 延迟移动（模拟赶路时间）
        setTimeout(() => {
            // 从原位置移除
            fromNPCs.splice(npcIndex, 1);

            // 添加到新位置
            if (!this.npcs[toLocation]) {
                this.npcs[toLocation] = [];
            }
            // 更新NPC的活动状态
            npc.activity = this.getEmergencyActivity(reason);
            this.npcs[toLocation].push(npc);

            // 如果玩家在目的地，更新NPC列表
            if (this.gameState.currentLocation === toLocation) {
                this.updateNPCList();
                this.addDialogueMessage(`${npcName}赶到了现场。`, 'system');
            }

            // 如果玩家在原位置，也更新
            if (this.gameState.currentLocation === fromLocation) {
                this.updateNPCList();
                this.addDialogueMessage(`${npcName}匆忙离开，赶往${toLocation}。`, 'system');
            }

            this.addLog('NPC移动', `${npcName}: ${fromLocation} → ${toLocation}`, 'info');
        }, 2000 + Math.random() * 3000); // 2-5秒后到达
    }

    getEmergencyActivity(eventContent) {
        if (eventContent.includes('火') || eventContent.includes('燃烧')) {
            return '救火';
        } else if (eventContent.includes('攻击') || eventContent.includes('强盗')) {
            return '警戒';
        } else if (eventContent.includes('倒塌') || eventContent.includes('地震')) {
            return '救援';
        }
        return '帮忙';
    }

    getAllNPCs() {
        // 获取所有地点的NPC列表
        const allNPCs = [];
        for (const location of Object.keys(this.npcs)) {
            allNPCs.push(...this.npcs[location]);
        }
        return allNPCs;
    }

    getNPCLocation(npcName) {
        // 查找NPC所在位置
        for (const [location, npcs] of Object.entries(this.npcs)) {
            if (npcs.some(npc => npc.name === npcName)) {
                return location;
            }
        }
        return '未知';
    }

    // ========== 日志系统 ==========

    addLog(source, message, type = 'info') {
        const timeStr = `第${this.gameState.day}天 ${String(this.gameState.hour).padStart(2, '0')}:${String(this.gameState.minute).padStart(2, '0')}`;

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.innerHTML = `
            <span class="log-time">${timeStr}</span>
            <span class="log-source">[${source}]</span>
            <span class="log-message">${message}</span>
        `;

        this.logContainer.insertBefore(logEntry, this.logContainer.firstChild);

        // 限制日志数量
        while (this.logContainer.children.length > 100) {
            this.logContainer.lastChild.remove();
        }
    }

    // ========== 存档系统 ==========

    saveGame() {
        try {
            localStorage.setItem('ellenValley_gameState', JSON.stringify(this.gameState));
        } catch (e) {
            console.warn('保存游戏失败:', e);
        }
    }

    loadGame() {
        try {
            const saved = localStorage.getItem('ellenValley_gameState');
            if (saved) {
                this.gameState = JSON.parse(saved);
                this.showScreen('game');
                this.initGameUI();
                this.renderActiveEvents();
                this.showToast(window.I18N ? window.I18N.t('common.loaded') : '游戏已加载', 'success');
            }
        } catch (e) {
            console.error('加载游戏失败:', e);
            this.showToast(window.I18N ? window.I18N.t('common.loadFailed') : '加载游戏失败', 'error');
        }
    }

    checkSavedGame() {
        try {
            const saved = localStorage.getItem('ellenValley_gameState');
            if (saved) {
                this.btnContinue.disabled = false;
            }
        } catch (e) {}
    }

    exitGame() {
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;
        if (confirm(t('common.exitConfirm'))) {
            this.showScreen('start');
        }
    }

    // ========== 模态框 ==========

    openModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    }

    closeModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    }

    // ========== 地图模态框 ==========

    // 地点类型对应的图标
    getLocationIcon(locationType, locationName) {
        const typeIcons = {
            'public': '🏛️',
            'workshop': '⚒️',
            'shop': '🏪',
            'tavern': '🍺',
            'residence': '🏠',
            'entrance': '🚪',
            'farm': '🌾',
            'outdoor': '🌲'
        };
        // 根据名称匹配特定图标
        const nameIcons = {
            '广场': '🏛️', '铁匠': '⚒️', '酒馆': '🍺', '杂货': '🏪',
            '农田': '🌾', '森林': '🌲', '教堂': '⛪', '村口': '🚪',
            '磨坊': '🔧', '村长': '🏠', '市场': '🏪'
        };
        for (const [key, icon] of Object.entries(nameIcons)) {
            if (locationName.includes(key)) return icon;
        }
        return typeIcons[locationType] || '📍';
    }

    openMapModal() {
        const mapGrid = document.getElementById('map-grid-modal');

        // 动态生成地图内容
        const locations = Object.keys(this.npcs);
        if (locations.length === 0) {
            mapGrid.innerHTML = '<p class="no-data">暂无可用地点</p>';
        } else {
            mapGrid.innerHTML = locations.map(locName => {
                const isCurrent = locName === this.gameState.currentLocation;
                const npcsHere = this.npcs[locName] || [];
                const npcCount = npcsHere.length;
                const locData = this.worldLocations?.[locName] || {};
                const icon = this.getLocationIcon(locData.type, locName);

                return `
                    <div class="map-location-modal ${isCurrent ? 'current' : ''}" data-location="${locName}">
                        <span class="location-icon">${icon}</span>
                        <span class="location-name">${locName}</span>
                        ${npcCount > 0 ? `<span class="location-npc-count">${npcCount}人</span>` : ''}
                    </div>
                `;
            }).join('');
        }

        this.openModal('map-modal');
    }

    handleMapModalClick(e) {
        const loc = e.target.closest('.map-location-modal');
        if (!loc) return;

        const newLocation = loc.dataset.location;
        const t = window.I18N ? window.I18N.t.bind(window.I18N) : (k) => k;

        if (newLocation === this.gameState.currentLocation) {
            this.showToast(t('map.alreadyHere'), 'info');
            return;
        }

        // 执行移动
        const oldLocation = this.gameState.currentLocation;
        this.gameState.currentLocation = newLocation;

        // 移动消耗15分钟时间
        this.advanceTime(0.25, false);

        // 更新界面
        this.updateLocationDisplay();
        this.updateNPCList();
        this.enableDialogueIfNPCsPresent();

        // 清空对话并显示移动信息
        this.clearDialogue();
        this.addDialogueMessage(`你从${oldLocation}来到了${newLocation}`, 'system');

        // 记录日志
        this.addLog('移动', `${this.gameState.player.name} 移动到 ${newLocation}`, 'info');

        // 关闭模态框
        this.closeModal('map-modal');

        // 保存游戏
        this.saveGame();
    }

    // ========== API配置 ==========

    async testApiConnection() {
        const statusDiv = document.getElementById('api-status');
        statusDiv.textContent = '正在测试连接...';
        statusDiv.className = 'api-status';

        try {
            const result = await window.api.testConnection();
            if (result.success) {
                statusDiv.textContent = '连接成功!';
                statusDiv.className = 'api-status success';
            } else {
                statusDiv.textContent = '连接失败: ' + (result.error || '未知错误');
                statusDiv.className = 'api-status error';
            }
        } catch (error) {
            statusDiv.textContent = '连接失败: ' + error.message;
            statusDiv.className = 'api-status error';
        }
    }

    async saveApiConfig() {
        const provider = document.getElementById('api-provider').value;
        const apiKey = document.getElementById('api-key').value;
        const model = document.getElementById('api-model').value;

        try {
            await window.api.updateConfig({
                provider: provider,
                api_key: apiKey || undefined,
                model: model
            });

            this.showToast('配置已保存', 'success');
            this.closeModal('settings-modal');
        } catch (error) {
            this.showToast('保存配置失败: ' + error.message, 'error');
        }
    }

    // ========== Toast 通知 ==========

    showToast(message, type = 'info') {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ========== 世界创建相关方法 ==========

    /**
     * 选择世界主题
     */
    selectTheme(event) {
        const card = event.target.closest('.theme-card');
        if (!card) return;

        // 移除其他卡片的选中状态
        this.themeCards.querySelectorAll('.theme-card').forEach(c => {
            c.classList.remove('selected');
        });

        // 选中当前卡片
        card.classList.add('selected');
        this.selectedTheme = card.dataset.theme;
    }

    /**
     * 显示世界加载界面
     */
    async showWorldLoadScreen() {
        this.showScreen('worldLoad');
        await this.loadSavedWorldsList();
    }

    /**
     * 加载已保存的世界列表
     */
    async loadSavedWorldsList() {
        try {
            const result = await api.getSavedWorlds();
            const worlds = result.saved_worlds || [];

            if (worlds.length === 0) {
                this.savedWorldsList.innerHTML = '<p class="no-data">没有找到已保存的世界</p>';
                return;
            }

            this.savedWorldsList.innerHTML = worlds.map(world => `
                <div class="saved-world-item" data-world-dir="${world.dir_name}">
                    <div class="saved-world-content">
                        <div class="saved-world-name">${world.world_name}</div>
                        <div class="saved-world-info">${world.npc_count} 个NPC | ${world.location_count} 个地点</div>
                        <div class="saved-world-date">保存时间: ${new Date(world.modified_time * 1000).toLocaleString()}</div>
                    </div>
                    <button class="btn btn-small btn-danger delete-world-btn" data-world-dir="${world.dir_name}" title="删除">X</button>
                </div>
            `).join('');

            // 绑定加载事件
            this.savedWorldsList.querySelectorAll('.saved-world-content').forEach(item => {
                item.addEventListener('click', () => {
                    const worldDir = item.parentElement.dataset.worldDir;
                    this.loadSavedWorld(worldDir);
                });
            });

            // 绑定删除事件
            this.savedWorldsList.querySelectorAll('.delete-world-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteWorld(btn.dataset.worldDir);
                });
            });

        } catch (error) {
            console.error('加载存档列表失败:', error);
            this.savedWorldsList.innerHTML = '<p class="no-data">加载存档列表失败</p>';
        }
    }

    /**
     * 删除世界
     */
    async deleteWorld(worldDir) {
        if (!confirm(`确定要删除世界 "${worldDir}" 吗？此操作不可恢复！`)) {
            return;
        }

        try {
            const result = await api.deleteWorld(worldDir, true);

            if (result.status === 'success') {
                this.showToast(`世界 "${worldDir}" 已删除`, 'success');
                // 刷新列表
                await this.loadSavedWorldsList();
            } else {
                this.showToast(result.message || '删除失败', 'error');
            }
        } catch (error) {
            console.error('删除世界失败:', error);
            this.showToast('删除世界失败: ' + error.message, 'error');
        }
    }

    /**
     * 加载已保存的世界
     */
    async loadSavedWorld(worldDir) {
        try {
            this.showToast('正在加载世界...', 'info');

            const result = await api.loadWorld(worldDir);

            if (result.success) {
                // 保存世界数据
                this.currentWorld = {
                    config: result.world_config,
                    locations: result.locations,
                    npcs: result.npcs
                };

                // 更新NPC数据
                this.updateNPCsFromWorld(result.npcs, result.locations);

                this.showToast(`世界 "${result.world_config.world_name}" 加载成功!`, 'success');

                // 进入角色创建界面
                this.showScreen('character');
            } else {
                this.showToast(result.message || '加载世界失败', 'error');
            }

        } catch (error) {
            console.error('加载世界失败:', error);
            this.showToast('加载世界失败: ' + error.message, 'error');
        }
    }

    /**
     * 生成新世界
     */
    async generateWorld() {
        const description = this.worldDescription.value.trim();
        const theme = this.selectedTheme || 'medieval_fantasy';
        const npcCount = parseInt(this.npcCountSlider.value);

        if (!description) {
            this.showToast('请输入世界描述', 'warning');
            return;
        }

        // 显示生成状态
        this.generationStatus.style.display = 'flex';
        this.generationMessage.textContent = '正在使用AI生成世界...';
        this.btnGenerateWorld.disabled = true;

        try {
            const result = await api.createWorld(description, theme, npcCount);

            if (result.status === 'success') {
                // 保存世界数据
                this.currentWorld = {
                    config: result.world,
                    locations: result.locations,
                    npcs: result.npcs
                };

                // 更新NPC数据
                this.updateNPCsFromWorld(result.npcs, result.locations);

                this.showToast(`世界 "${result.world.name}" 创建成功!`, 'success');

                // 隐藏生成状态
                this.generationStatus.style.display = 'none';
                this.btnGenerateWorld.disabled = false;

                // 进入角色创建界面
                this.showScreen('character');
            } else {
                throw new Error(result.message || '世界生成失败');
            }

        } catch (error) {
            console.error('世界生成失败:', error);
            this.generationMessage.textContent = '生成失败: ' + error.message;
            this.btnGenerateWorld.disabled = false;
            this.showToast('世界生成失败: ' + error.message, 'error');
        }
    }

    /**
     * 从世界数据更新NPC
     */
    updateNPCsFromWorld(npcs, locations) {
        // 清空现有NPC数据
        this.npcs = {};
        this.worldLocations = {};

        // 根据locations初始化位置 (locations可能是字符串数组或对象)
        if (locations) {
            if (Array.isArray(locations)) {
                // 字符串数组格式
                for (const locName of locations) {
                    this.npcs[locName] = [];
                    this.worldLocations[locName] = { name: locName, type: 'public' };
                }
            } else if (typeof locations === 'object') {
                // 对象格式 {地点名: {name, type, description, ...}}
                for (const [locName, locData] of Object.entries(locations)) {
                    this.npcs[locName] = [];
                    this.worldLocations[locName] = locData;
                }
            }
        }

        // 设置初始位置为第一个地点
        const locationKeys = Object.keys(this.npcs);
        if (locationKeys.length > 0 && !this.npcs[this.gameState.currentLocation]) {
            this.gameState.currentLocation = locationKeys[0];
        }

        // 添加NPC到对应位置 (npcs是数组 [{name, profession, gender, age, ...}, ...])
        if (npcs && Array.isArray(npcs)) {
            for (let i = 0; i < npcs.length; i++) {
                const npc = npcs[i];
                // 优先使用NPC的默认位置，否则分配到不同位置
                let location = npc.default_location;
                if (!location || !this.npcs[location]) {
                    location = locationKeys[i % locationKeys.length] || locationKeys[0];
                }

                if (!this.npcs[location]) {
                    this.npcs[location] = [];
                }

                this.npcs[location].push({
                    name: npc.name,
                    profession: npc.profession,
                    gender: npc.gender || '未知',
                    age: npc.age || 0,
                    race: npc.race || '人类',
                    background: npc.background || '',
                    traits: npc.traits || [],
                    icon: this.getProfessionIcon(npc.profession),
                    activity: '日常活动'
                });
            }
        }

        console.log('世界数据加载完成:', {
            locations: Object.keys(this.npcs),
            npcCount: npcs?.length || 0,
            currentLocation: this.gameState.currentLocation
        });
    }

    /**
     * 根据职业获取图标
     */
    getProfessionIcon(profession) {
        const icons = {
            '铁匠': '⚒️',
            '酒馆老板': '🍺',
            '酒馆老板娘': '🍺',
            '牧师': '⛪',
            '商人': '💰',
            '农夫': '🌾',
            '工匠': '🔧',
            '学者': '📚',
            '医师': '💊',
            '守卫': '🛡️',
            '猎人': '🏹',
            '渔夫': '🎣',
            '面包师': '🍞',
            '花商': '🌸',
            '裁缝': '🧵',
            '旅行者': '🚶',
            '冒险者': '⚔️'
        };

        return icons[profession] || '👤';
    }

  // ========== D3.1 背包渲染 ==========
  renderInventory(items, gold) {
    const grid = document.getElementById('inventory-grid');
    const goldEl = document.getElementById('player-gold-display');
    if (goldEl) goldEl.textContent = `💰 ${gold || 0}`;
    if (!grid) return;

    // 生成20格
    grid.innerHTML = '';
    const slots = Array(20).fill(null);
    if (Array.isArray(items)) {
      items.forEach((item, i) => { if (i < 20) slots[i] = item; });
    }
    slots.forEach(item => {
      const slot = document.createElement('div');
      slot.className = 'inventory-slot';
      if (item) {
        slot.textContent = item.icon || '📦';
        slot.title = `${item.name || item.item_id}${item.qty > 1 ? ' x' + item.qty : ''}`;
        const qty = document.createElement('span');
        qty.className = 'item-qty';
        qty.textContent = item.qty > 1 ? item.qty : '';
        slot.appendChild(qty);
        // 右键菜单：使用/丢弃
        slot.addEventListener('contextmenu', (e) => {
          e.preventDefault();
          this.showItemContextMenu(e, item);
        });
      }
      grid.appendChild(slot);
    });
  }

  showItemContextMenu(e, item) {
    // 简单提示（可扩展为完整上下文菜单）
    const action = confirm(`物品：${item.name || item.item_id}\n点击确定使用`);
    if (action && window.api) {
      window.api.useItem(item.item_id).then(r => {
        if (r.success) this.refreshPlayerState();
      });
    }
  }

  // ========== D3.2 事件树面板渲染 ==========
  renderEventTree(events) {
    const container = document.getElementById('event-tree-list');
    if (!container) return;
    if (!events || events.length === 0) {
      container.innerHTML = '<div class="no-data">暂无活跃事件</div>';
      return;
    }
    const phaseMap = {
      'initial': [1, 8], 'spreading': [2, 8], 'reacting': [3, 8],
      'developing': [4, 8], 'climax': [5, 8], 'resolving': [6, 8],
      'resolved': [7, 8], 'faded': [8, 8]
    };
    container.innerHTML = events.map(ev => {
      const [cur, total] = phaseMap[ev.phase] || [1, 8];
      const pct = Math.round(cur / total * 100);
      const children = (ev.child_event_ids || []).map(cid =>
        `<div class="event-child-item">↳ ${cid.substring(0, 12)}...</div>`
      ).join('');
      return `
        <div class="event-tree-item">
          <div style="font-size:13px;font-weight:600">${ev.content || ev.event_id}</div>
          <div style="font-size:11px;color:#888">${ev.location || ''} | ${ev.phase}</div>
          <div class="event-phase-bar">
            <div class="event-phase-fill" style="width:${pct}%"></div>
          </div>
          <div style="font-size:11px;color:#888">
            已知晓: ${ev.npcs_aware || 0}人 | 已响应: ${ev.npcs_reacted || 0}人
          </div>
          ${children ? `<div class="event-children">${children}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  // ========== D3.3 关系面板扩展渲染 ==========
  renderRelationships(relationships) {
    const container = document.getElementById('relationships-list');
    if (!container) return;
    if (!relationships || relationships.length === 0) {
      container.innerHTML = '<div class="no-data">暂无关系记录</div>';
      return;
    }
    // 按好感度排序
    const sorted = [...relationships].sort((a, b) => (b.affinity || 0) - (a.affinity || 0));
    container.innerHTML = sorted.map(rel => {
      const other = rel.entity_a === (this.gameState.playerName) ? rel.entity_b : rel.entity_a;
      const affinity = rel.affinity || 0;
      const pct = Math.round((affinity + 100) / 200 * 100);
      const relType = rel.relationship_type || 'stranger';
      const colorClass = affinity < -20 ? 'enemy' : affinity < 20 ? 'stranger' : affinity < 60 ? 'friend' : 'close_friend';
      return `
        <div>
          <div class="relationship-item" onclick="this.classList.toggle('expanded')">
            <span style="font-size:13px;min-width:70px">${other}</span>
            <div class="relationship-bar-wrap">
              <div class="relationship-bar-fill ${colorClass}" style="width:${pct}%"></div>
            </div>
            <span style="font-size:11px;color:#888">${relType}</span>
          </div>
          <div class="relationship-detail">
            好感度: ${affinity} | 信任: ${rel.trust || 0} | 互动: ${rel.interaction_count || 0}次
          </div>
        </div>
      `;
    }).join('');
  }

  // ========== WebSocket 新消息类型处理（D3.5）==========
  handleWebSocketMessage(data) {
    switch (data.type) {
      case 'event_phase_change':
        // 刷新事件树
        this.refreshActiveEvents();
        break;
      case 'npc_moved':
        // 更新地图上NPC气泡
        if (window.worldMap && data.npc_name && data.new_location) {
          window.worldMap.updateNPCPosition(data.npc_name, data.new_location);
        }
        break;
      case 'gossip_spread':
        // 可以在控制台或日志面板显示
        console.log(`[八卦] ${data.from} → ${data.to}: ${data.content}`);
        break;
      case 'trade_completed':
        // 刷新背包
        this.refreshInventory();
        break;
      case 'relationship_changed':
        // 刷新关系面板
        this.refreshRelationships();
        break;
      case 'task_completed':
        // 显示任务完成提示
        this.showTaskReward(data);
        break;
    }
  }

  showTaskReward(data) {
    const rewards = data.rewards || {};
    const msg = `任务完成！${rewards.gold ? '获得 ' + rewards.gold + ' 金币' : ''}`;
    // 简单的状态栏提示
    const el = document.querySelector('.system-message');
    if (el) {
      el.textContent = msg;
      setTimeout(() => { el.textContent = ''; }, 5000);
    }
  }

  // ========== 刷新方法（供外部调用）==========
  async refreshInventory() {
    if (!window.api) return;
    try {
      const [inv, gold] = await Promise.all([
        window.api.getPlayerInventory(),
        window.api.getPlayerGold()
      ]);
      this.renderInventory(inv.inventory || [], gold.gold || 0);
    } catch (e) { /* 忽略错误 */ }
  }

  async refreshActiveEvents() {
    if (!window.api) return;
    try {
      const data = await window.api.getActiveEvents();
      this.renderEventTree(data.events || []);
    } catch (e) { /* 忽略错误 */ }
  }

  async refreshRelationships() {
    if (!window.api) return;
    try {
      const data = await window.api.getPlayerRelationships();
      this.renderRelationships(data.relationships || []);
    } catch (e) { /* 忽略错误 */ }
  }

  async refreshPlayerState() {
    await Promise.all([
      this.refreshInventory(),
      this.refreshRelationships()
    ]);
  }
}

// 全局模态框关闭函数
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// 启动游戏
document.addEventListener('DOMContentLoaded', () => {
    window.game = new WorldSimulator();
});
