/**
 * NPC 模拟器前端应用
 */
class NPCSimulatorApp {
    constructor() {
        this.isConnected = false;
        this.currentNPC = null;
        this.isAutoMode = false;
        this.isPaused = false;

        this.init();
    }

    async init() {
        console.log('初始化 NPC 模拟器...');

        // 绑定 DOM 元素
        this.bindElements();

        // 绑定事件
        this.bindEvents();

        // 连接服务器
        await this.connect();

        // 加载初始数据
        await this.loadInitialData();

        // 启动定时更新
        this.startPeriodicUpdates();
    }

    bindElements() {
        // 状态显示
        this.connectionStatus = document.getElementById('connection-status');
        this.worldTimeNav = document.getElementById('world-time');
        this.timeDisplay = document.getElementById('time-display');

        // NPC 选择器
        this.npcSelector = document.getElementById('npc-selector');

        // 角色信息
        this.charName = document.getElementById('char-name');
        this.charProfession = document.getElementById('char-profession');
        this.statEmotion = document.getElementById('stat-emotion');
        this.statEnergy = document.getElementById('stat-energy');
        this.statHunger = document.getElementById('stat-hunger');
        this.statFatigue = document.getElementById('stat-fatigue');
        this.currentActivity = document.getElementById('current-activity');

        // 需求条
        this.needHunger = document.getElementById('need-hunger');
        this.needFatigue = document.getElementById('need-fatigue');
        this.needSocial = document.getElementById('need-social');
        this.needSecurity = document.getElementById('need-security');

        // 对话区域
        this.dialogueHistory = document.getElementById('dialogue-history');
        this.dialogueInput = document.getElementById('dialogue-input');
        this.btnSend = document.getElementById('btn-send');

        // 时间控制
        this.btnTime30m = document.getElementById('btn-time-30m');
        this.btnTime1h = document.getElementById('btn-time-1h');
        this.btnTimePause = document.getElementById('btn-time-pause');
        this.btnAutoMode = document.getElementById('btn-auto-mode');

        // 事件触发
        this.customEventInput = document.getElementById('custom-event-input');
        this.btnTriggerEvent = document.getElementById('btn-trigger-event');

        // 推理过程
        this.reasoningContent = document.getElementById('reasoning-content');
        this.reasoningLevel = document.getElementById('reasoning-level');

        // 活动日志
        this.activityLog = document.getElementById('activity-log');

        // Token 统计
        this.tokensSent = document.getElementById('tokens-sent');
        this.tokensReceived = document.getElementById('tokens-received');
        this.apiCalls = document.getElementById('api-calls');

        // 模态框
        this.settingsModal = document.getElementById('settings-modal');
        this.logsModal = document.getElementById('logs-modal');

        // Toast 容器
        this.toastContainer = document.getElementById('toast-container');
    }

    bindEvents() {
        // NPC 选择
        this.npcSelector.addEventListener('change', (e) => this.onNPCSelect(e));

        // 对话
        this.btnSend.addEventListener('click', () => this.sendDialogue());
        this.dialogueInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendDialogue();
        });

        // 时间控制
        this.btnTime30m.addEventListener('click', () => this.advanceTime(0.5));
        this.btnTime1h.addEventListener('click', () => this.advanceTime(1));
        this.btnTimePause.addEventListener('click', () => this.togglePause());
        this.btnAutoMode.addEventListener('click', () => this.toggleAutoMode());

        // 事件触发
        this.btnTriggerEvent.addEventListener('click', () => this.triggerCustomEvent());
        this.customEventInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.triggerCustomEvent();
        });

        // 预设事件按钮
        document.querySelectorAll('.btn-event').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const event = e.currentTarget.dataset.event;
                this.triggerEvent(event, 'preset_event');
            });
        });

        // 设置按钮
        document.getElementById('btn-settings').addEventListener('click', () => {
            this.openSettingsModal();
        });

        document.getElementById('btn-close-settings').addEventListener('click', () => {
            this.closeSettingsModal();
        });

        document.getElementById('btn-save-settings').addEventListener('click', () => {
            this.saveSettings();
        });

        document.getElementById('btn-test-connection').addEventListener('click', () => {
            this.testAPIConnection();
        });

        // 密码显示切换
        document.getElementById('btn-toggle-key').addEventListener('click', (e) => {
            const input = document.getElementById('api-key');
            const icon = e.currentTarget.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fas fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fas fa-eye';
            }
        });

        // 日志按钮
        document.getElementById('btn-logs').addEventListener('click', () => {
            this.openLogsModal();
        });

        document.getElementById('btn-close-logs').addEventListener('click', () => {
            this.closeLogsModal();
        });

        document.getElementById('btn-refresh-logs').addEventListener('click', () => {
            this.loadLogs();
        });

        // 日志标签页
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e));
        });

        // 清空日志
        document.getElementById('btn-clear-logs').addEventListener('click', () => {
            this.clearActivityLog();
        });

        // WebSocket 回调
        api.onWebSocket('connected', () => this.onConnected());
        api.onWebSocket('disconnected', () => this.onDisconnected());
        api.onWebSocket('logs', (logs) => this.onLogsReceived(logs));
        api.onWebSocket('event', (data) => this.onEventProcessed(data));
        api.onWebSocket('dialogue', (data) => this.onDialogueReceived(data));
        api.onWebSocket('time', (data) => this.onTimeAdvanced(data));
    }

    // ========== 连接 ==========

    async connect() {
        try {
            // 检查 API 状态
            const status = await api.getStatus();
            console.log('服务器状态:', status);

            // 连接 WebSocket
            await api.connectWebSocket();
            api.startHeartbeat();

            this.isConnected = true;
            this.updateConnectionStatus(true);

        } catch (error) {
            console.error('连接失败:', error);
            this.updateConnectionStatus(false);
            this.showToast('无法连接到服务器', 'error');
        }
    }

    updateConnectionStatus(connected) {
        const icon = this.connectionStatus.querySelector('i');
        const text = this.connectionStatus.querySelector('span');

        if (connected) {
            this.connectionStatus.className = 'status-indicator connected';
            text.textContent = '已连接';
        } else {
            this.connectionStatus.className = 'status-indicator disconnected';
            text.textContent = '未连接';
        }
    }

    onConnected() {
        this.updateConnectionStatus(true);
        this.showToast('已连接到服务器', 'success');
    }

    onDisconnected() {
        this.updateConnectionStatus(false);
        this.showToast('与服务器断开连接', 'warning');

        // 尝试重连
        setTimeout(() => this.connect(), 5000);
    }

    // ========== 初始数据 ==========

    async loadInitialData() {
        try {
            // 加载 NPC 列表
            const npcsData = await api.getAvailableNPCs();
            this.populateNPCSelector(npcsData.npcs);

            // 加载世界时间
            const timeData = await api.getWorldTime();
            this.updateTimeDisplay(timeData);

            // 加载 API 配置
            const config = await api.getConfig();
            this.populateSettings(config);

            // 加载 Token 统计
            const stats = await api.getTokenStats();
            this.updateTokenStats(stats);

        } catch (error) {
            console.error('加载初始数据失败:', error);
        }
    }

    populateNPCSelector(npcs) {
        this.npcSelector.innerHTML = '<option value="">选择 NPC...</option>';
        npcs.forEach(npc => {
            const option = document.createElement('option');
            option.value = npc.name;
            option.textContent = `${npc.name} - ${npc.profession}`;
            this.npcSelector.appendChild(option);
        });
    }

    populateSettings(config) {
        document.getElementById('api-provider').value = config.provider || 'deepseek';
        document.getElementById('api-base').value = config.api_base || 'https://api.deepseek.com/v1';
        document.getElementById('api-model').value = config.model || 'deepseek-chat';

        if (config.api_key_masked) {
            document.getElementById('api-key').placeholder = config.api_key_masked;
        }
    }

    // ========== NPC 选择 ==========

    async onNPCSelect(e) {
        const npcName = e.target.value;
        if (!npcName) return;

        try {
            this.showToast(`正在加载 ${npcName}...`, 'info');

            await api.selectNPC(npcName);
            this.currentNPC = npcName;

            // 更新 UI
            await this.updateNPCStatus();

            // 启用对话输入
            this.dialogueInput.disabled = false;
            this.btnSend.disabled = false;

            // 清空对话历史
            this.dialogueHistory.innerHTML = '';

            this.showToast(`${npcName} 已就绪`, 'success');
            this.addActivityLog('系统', `NPC ${npcName} 已加载`);

        } catch (error) {
            console.error('选择 NPC 失败:', error);
            this.showToast(`加载 NPC 失败: ${error.message}`, 'error');
        }
    }

    async updateNPCStatus() {
        if (!this.currentNPC) return;

        try {
            const status = await api.getNPCStatus();

            // 更新角色信息
            this.charName.textContent = status.name || this.currentNPC;
            this.charProfession.textContent = status.profession || '-';
            this.statEmotion.textContent = status.emotion || '-';
            this.currentActivity.textContent = status.current_activity || '-';

            // 更新进度条
            const energy = (status.energy_level || 0);
            this.statEnergy.style.width = `${energy}%`;

            // 更新需求
            if (status.needs) {
                this.updateNeedBar(this.needHunger, status.needs.hunger || 0);
                this.updateNeedBar(this.needFatigue, status.needs.fatigue || 0);
                this.updateNeedBar(this.needSocial, status.needs.social || 0);
                this.updateNeedBar(this.needSecurity, status.needs.security || 0);
            }

        } catch (error) {
            console.error('更新 NPC 状态失败:', error);
        }
    }

    updateNeedBar(element, value) {
        const percentage = Math.min(100, Math.max(0, value * 100));

        // 移除旧的类
        element.classList.remove('low', 'medium');

        // 添加状态类
        if (percentage < 30) {
            element.classList.add('low');
        } else if (percentage < 60) {
            element.classList.add('medium');
        }

        // 使用 CSS 变量或直接设置样式
        element.style.setProperty('--value', `${percentage}%`);
    }

    // ========== 对话 ==========

    async sendDialogue() {
        const message = this.dialogueInput.value.trim();
        if (!message || !this.currentNPC) return;

        // 添加用户消息到对话历史
        this.addDialogueMessage(message, 'user', '你');

        // 清空输入框
        this.dialogueInput.value = '';

        try {
            // 发送对话
            const result = await api.sendDialogue(message);

            // 添加 NPC 回复
            this.addDialogueMessage(result.response, 'npc', this.currentNPC);

            // 更新推理过程
            if (result.decision_level) {
                this.reasoningLevel.textContent = `L${result.decision_level}`;
            }

            // 更新状态
            await this.updateNPCStatus();
            await this.updateTokenStats();

        } catch (error) {
            console.error('发送对话失败:', error);
            this.showToast('发送失败', 'error');
        }
    }

    addDialogueMessage(text, type, speaker) {
        // 移除占位符
        const placeholder = this.dialogueHistory.querySelector('.dialogue-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const message = document.createElement('div');
        message.className = `dialogue-message ${type}`;
        message.innerHTML = `
            <div class="speaker">${speaker}</div>
            <div class="content">${text}</div>
        `;

        this.dialogueHistory.appendChild(message);
        this.dialogueHistory.scrollTop = this.dialogueHistory.scrollHeight;
    }

    onDialogueReceived(data) {
        // WebSocket 收到对话
        this.addDialogueMessage(data.npc_response, 'npc', this.currentNPC);
    }

    // ========== 事件触发 ==========

    async triggerCustomEvent() {
        const eventContent = this.customEventInput.value.trim();
        if (!eventContent) return;

        await this.triggerEvent(eventContent, 'world_event');
        this.customEventInput.value = '';
    }

    async triggerEvent(content, eventType) {
        if (!this.currentNPC) {
            this.showToast('请先选择 NPC', 'warning');
            return;
        }

        try {
            this.addActivityLog('事件', content);

            const result = await api.processEvent(content, eventType);

            // 更新推理过程
            this.updateReasoningPanel(result);

            // 添加 NPC 回应
            if (result.response_text) {
                this.addDialogueMessage(result.response_text, 'npc', this.currentNPC);
            }

            // 更新状态
            await this.updateNPCStatus();
            await this.updateTokenStats();

            this.addActivityLog('响应', `决策级别: L${result.decision_level}`);

        } catch (error) {
            console.error('触发事件失败:', error);
            this.showToast('事件处理失败', 'error');
        }
    }

    onEventProcessed(data) {
        this.updateReasoningPanel(data.result);
    }

    updateReasoningPanel(result) {
        if (!result) return;

        const level = result.decision_level || '-';
        this.reasoningLevel.textContent = `L${level}`;

        let html = '';

        if (result.reasoning) {
            html += `
                <div class="reasoning-step thought">
                    <div class="step-type">思考</div>
                    <div class="step-content">${result.reasoning}</div>
                </div>
            `;
        }

        if (result.recommended_action) {
            html += `
                <div class="reasoning-step action">
                    <div class="step-type">行动</div>
                    <div class="step-content">${result.recommended_action}</div>
                </div>
            `;
        }

        if (result.response_text) {
            html += `
                <div class="reasoning-step observation">
                    <div class="step-type">回应</div>
                    <div class="step-content">${result.response_text}</div>
                </div>
            `;
        }

        this.reasoningContent.innerHTML = html || '<div class="reasoning-placeholder"><i class="fas fa-lightbulb"></i><p>等待 NPC 决策...</p></div>';
    }

    // ========== 时间控制 ==========

    async advanceTime(hours) {
        try {
            const result = await api.advanceTime(hours);

            this.updateTimeDisplay(result);
            this.addActivityLog('时间', `推进 ${hours} 小时，当前活动: ${result.activity}`);

            await this.updateNPCStatus();

        } catch (error) {
            console.error('推进时间失败:', error);
            this.showToast('时间推进失败', 'error');
        }
    }

    async togglePause() {
        try {
            if (this.isPaused) {
                await api.resumeTime();
                this.isPaused = false;
                this.btnTimePause.innerHTML = '<i class="fas fa-pause"></i>';
                this.showToast('时间已恢复', 'info');
            } else {
                await api.pauseTime();
                this.isPaused = true;
                this.btnTimePause.innerHTML = '<i class="fas fa-play"></i>';
                this.showToast('时间已暂停', 'info');
            }
        } catch (error) {
            console.error('切换暂停状态失败:', error);
        }
    }

    async toggleAutoMode() {
        try {
            if (this.isAutoMode) {
                await api.stopAutonomousMode();
                this.isAutoMode = false;
                this.btnAutoMode.classList.remove('btn-primary');
                this.btnAutoMode.classList.add('btn-outline');
                this.showToast('自主模式已关闭', 'info');
            } else {
                await api.startAutonomousMode();
                this.isAutoMode = true;
                this.btnAutoMode.classList.remove('btn-outline');
                this.btnAutoMode.classList.add('btn-primary');
                this.showToast('自主模式已开启', 'success');
            }
        } catch (error) {
            console.error('切换自主模式失败:', error);
        }
    }

    updateTimeDisplay(data) {
        const timeStr = data.current_time || '--:--';
        this.timeDisplay.textContent = timeStr;
        this.worldTimeNav.textContent = data.hour !== undefined ? `${String(data.hour).padStart(2, '0')}:00` : '--:--';
    }

    onTimeAdvanced(data) {
        this.updateTimeDisplay(data);
        this.addActivityLog('时间', `${data.new_time} | ${data.activity}`);
    }

    // ========== 活动日志 ==========

    addActivityLog(source, message) {
        const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

        const entry = document.createElement('div');
        entry.className = 'log-entry info';
        entry.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-source">[${source}]</span>
            <span class="log-message">${message}</span>
        `;

        this.activityLog.prepend(entry);

        // 限制日志数量
        while (this.activityLog.children.length > 50) {
            this.activityLog.lastChild.remove();
        }
    }

    clearActivityLog() {
        this.activityLog.innerHTML = '';
    }

    onLogsReceived(logs) {
        // 实时日志更新（可选）
    }

    // ========== Token 统计 ==========

    async updateTokenStats(stats) {
        if (!stats) {
            stats = await api.getTokenStats();
        }

        this.tokensSent.textContent = this.formatNumber(stats.total_sent || 0);
        this.tokensReceived.textContent = this.formatNumber(stats.total_received || 0);
        this.apiCalls.textContent = stats.api_calls || 0;
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    // ========== 设置模态框 ==========

    openSettingsModal() {
        this.settingsModal.classList.add('active');
    }

    closeSettingsModal() {
        this.settingsModal.classList.remove('active');
    }

    async saveSettings() {
        const config = {
            provider: document.getElementById('api-provider').value,
            api_key: document.getElementById('api-key').value,
            api_base: document.getElementById('api-base').value,
            model: document.getElementById('api-model').value
        };

        // 如果密钥为空，不更新
        if (!config.api_key) {
            delete config.api_key;
        }

        try {
            await api.updateConfig(config);
            this.showToast('设置已保存', 'success');
            this.closeSettingsModal();
        } catch (error) {
            this.showToast('保存失败: ' + error.message, 'error');
        }
    }

    async testAPIConnection() {
        try {
            this.showToast('正在测试连接...', 'info');
            const result = await api.testConnection();

            if (result.success) {
                this.showToast('连接成功！', 'success');
            } else {
                this.showToast('连接失败: ' + (result.error || '未知错误'), 'error');
            }
        } catch (error) {
            this.showToast('测试失败: ' + error.message, 'error');
        }
    }

    // ========== 日志模态框 ==========

    openLogsModal() {
        this.logsModal.classList.add('active');
        this.loadLogs();
        this.loadModelOutputs();
    }

    closeLogsModal() {
        this.logsModal.classList.remove('active');
    }

    async loadLogs() {
        try {
            const level = document.getElementById('log-level-filter').value;
            const source = document.getElementById('log-source-filter').value;

            const data = await api.getLogs(level || null, source || null);
            const viewer = document.getElementById('log-viewer');

            if (data.logs.length === 0) {
                viewer.innerHTML = '<div class="text-muted">暂无日志</div>';
                return;
            }

            viewer.innerHTML = data.logs.map(log => `
                <div class="log-line">
                    <span class="timestamp">${log.timestamp.split('T')[1]?.split('.')[0] || ''}</span>
                    <span class="level ${log.level}">${log.level.toUpperCase()}</span>
                    <span class="source">${log.source}</span>
                    <span class="message">${log.message}</span>
                </div>
            `).join('');

        } catch (error) {
            console.error('加载日志失败:', error);
        }
    }

    async loadModelOutputs() {
        try {
            const data = await api.getModelOutputs();
            const viewer = document.getElementById('model-output-viewer');

            if (data.model_outputs.length === 0) {
                viewer.innerHTML = '<div class="text-muted">暂无模型输出</div>';
                return;
            }

            viewer.innerHTML = data.model_outputs.map(output => `
                <div class="model-output-entry">
                    <div class="output-header">
                        <span>${output.source}</span>
                        <span>${output.data?.latency_ms?.toFixed(0) || '-'}ms</span>
                    </div>
                    <div class="output-prompt">
                        <strong>输入:</strong> ${output.data?.prompt || '-'}
                    </div>
                    <div class="output-response">
                        <strong>输出:</strong> ${output.data?.response || '-'}
                    </div>
                </div>
            `).reverse().join('');

        } catch (error) {
            console.error('加载模型输出失败:', error);
        }
    }

    switchTab(e) {
        const tabId = e.target.dataset.tab;

        // 更新标签状态
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');

        // 更新内容显示
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
    }

    // ========== Toast 通知 ==========

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-times-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info}"></i>
            <span>${message}</span>
        `;

        this.toastContainer.appendChild(toast);

        // 自动移除
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ========== 定时更新 ==========

    startPeriodicUpdates() {
        // 每 5 秒更新时间
        setInterval(async () => {
            if (this.isConnected && !this.isPaused) {
                try {
                    const time = await api.getWorldTime();
                    this.updateTimeDisplay(time);
                } catch (e) { }
            }
        }, 5000);

        // 每 10 秒更新 NPC 状态
        setInterval(async () => {
            if (this.isConnected && this.currentNPC) {
                await this.updateNPCStatus();
            }
        }, 10000);

        // 每 30 秒更新 Token 统计
        setInterval(async () => {
            if (this.isConnected) {
                await this.updateTokenStats();
            }
        }, 30000);
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new NPCSimulatorApp();
});
