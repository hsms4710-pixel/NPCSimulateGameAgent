/**
 * NPC 模拟器 API 客户端
 */
class NPCApiClient {
    constructor(baseUrl = 'http://127.0.0.1:8000') {
        this.baseUrl = baseUrl;
        this.ws = null;
        this.wsCallbacks = {};
        this.wsRetryCount = 0;
        this.wsMaxRetries = 3;
        this.wsEnabled = true;
    }

    // ========== HTTP 请求 ==========

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API 请求失败: ${endpoint}`, error);
            throw error;
        }
    }

    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // ========== 系统 API ==========

    async getStatus() {
        return this.get('/api/v1/status');
    }

    // ========== 世界生成器 API ==========

    /**
     * 获取可用的世界主题列表
     */
    async getWorldThemes() {
        return this.get('/api/v1/world/generator/themes');
    }

    /**
     * 获取已保存的世界列表
     */
    async getSavedWorlds() {
        return this.get('/api/v1/world/generator/saved');
    }

    /**
     * 创建新世界
     * @param {string} description - 世界描述
     * @param {string} theme - 世界主题
     * @param {number} npcCount - NPC数量
     */
    async createWorld(description, theme = 'medieval_fantasy', npcCount = 5) {
        return this.post('/api/v1/world/generator/create', {
            description: description,
            theme: theme,
            npc_count: npcCount
        });
    }

    /**
     * 加载已保存的世界
     * @param {string} worldDir - 世界目录名
     */
    async loadWorld(worldDir) {
        return this.post('/api/v1/world/generator/load', {
            world_dir: worldDir
        });
    }

    /**
     * 获取当前世界信息
     */
    async getCurrentWorld() {
        return this.get('/api/v1/world/generator/current');
    }

    /**
     * 删除已保存的世界
     * @param {string} worldDir - 世界目录名
     * @param {boolean} confirm - 确认删除
     */
    async deleteWorld(worldDir, confirm = true) {
        return this.delete(`/api/v1/world/generator/delete/${encodeURIComponent(worldDir)}?confirm=${confirm}`);
    }

    // ========== NPC 注册表 API ==========

    /**
     * 获取所有注册的NPC列表
     */
    async getNPCRegistry() {
        return this.get('/api/v1/npc/registry/list');
    }

    /**
     * 动态创建新NPC
     */
    async createNPC(npcData) {
        return this.post('/api/v1/npc/registry/create', npcData);
    }

    /**
     * 晋升NPC为核心NPC
     */
    async promoteNPC(npcName, reason = '') {
        return this.post(`/api/v1/npc/registry/promote/${encodeURIComponent(npcName)}`, {
            reason: reason
        });
    }

    /**
     * 移除NPC
     */
    async removeNPC(npcName, permanent = false) {
        return this.post(`/api/v1/npc/registry/remove/${encodeURIComponent(npcName)}`, {
            permanent: permanent
        });
    }

    // ========== 配置 API ==========

    async getConfig() {
        return this.get('/api/v1/config');
    }

    async updateConfig(config) {
        return this.post('/api/v1/config', config);
    }

    async testConnection() {
        return this.post('/api/v1/config/test');
    }

    // ========== NPC API ==========

    async getAvailableNPCs() {
        return this.get('/api/v1/npcs');
    }

    async selectNPC(npcName) {
        return this.post('/api/v1/npcs/select', { npc_name: npcName });
    }

    async getNPCStatus() {
        return this.get('/api/v1/npc/status');
    }

    async getNPCMemories(limit = 20) {
        return this.get(`/api/v1/npc/memories?limit=${limit}`);
    }

    async getNPCGoals() {
        return this.get('/api/v1/npc/goals');
    }

    async getNPCRelationships() {
        return this.get('/api/v1/npc/relationships');
    }

    // ========== 事件 API ==========

    async processEvent(content, eventType = 'dialogue') {
        return this.post('/api/v1/events', {
            content: content,
            event_type: eventType
        });
    }

    async sendDialogue(message) {
        return this.post('/api/v1/dialogue', { message: message });
    }

    // ========== 世界模拟器 API ==========

    async worldDialogue(data) {
        return this.post('/api/v1/world/dialogue', data);
    }

    async worldEvent(data) {
        return this.post('/api/v1/world/event', data);
    }

    async getWorldNPCs(location) {
        return this.get(`/api/v1/world/npcs?location=${encodeURIComponent(location)}`);
    }

    async getWorldState() {
        return this.get('/api/v1/world/state');
    }

    // ========== 时间 API ==========

    async getWorldTime() {
        return this.get('/api/v1/time');
    }

    async advanceTime(hours = 1.0) {
        return this.post('/api/v1/time/advance', { hours: hours });
    }

    async pauseTime() {
        return this.post('/api/v1/time/pause');
    }

    async resumeTime() {
        return this.post('/api/v1/time/resume');
    }

    async resetTime() {
        return this.post('/api/v1/time/reset');
    }

    // ========== 自主模式 API ==========

    async startAutonomousMode() {
        return this.post('/api/v1/autonomous/start');
    }

    async stopAutonomousMode() {
        return this.post('/api/v1/autonomous/stop');
    }

    async getAutonomousStatus() {
        return this.get('/api/v1/autonomous/status');
    }

    // ========== 日志 API ==========

    async getLogs(level = null, source = null, limit = 100) {
        let params = `?limit=${limit}`;
        if (level) params += `&level=${level}`;
        if (source) params += `&source=${source}`;
        return this.get(`/api/v1/logs${params}`);
    }

    async getModelOutputs(limit = 50) {
        return this.get(`/api/v1/logs/model?limit=${limit}`);
    }

    async clearLogs() {
        return this.delete('/api/v1/logs');
    }

    // ========== Token 统计 API ==========

    async getTokenStats() {
        return this.get('/api/v1/stats/tokens');
    }

    async resetTokenStats() {
        return this.post('/api/v1/stats/tokens/reset');
    }

    // ========== NPC Agent API ==========

    /**
     * 让单个NPC对事件进行ReAct决策
     */
    async npcAgentDecide(data) {
        return this.post('/api/v1/npc/agent/decide', data);
    }

    /**
     * 处理世界事件，让所有NPC通过Agent决策系统做出反应
     * 区分前台事件（玩家当前位置）和后台事件（其他位置）
     */
    async processEventWithAgents(data) {
        return this.post('/api/v1/npc/agent/event/process', data);
    }

    /**
     * 获取所有NPC的当前状态
     */
    async getAllNPCAgentStates() {
        return this.get('/api/v1/npc/agent/states');
    }

    /**
     * 获取指定NPC的状态
     */
    async getNPCAgentState(npcName) {
        return this.get(`/api/v1/npc/agent/state/${encodeURIComponent(npcName)}`);
    }

    /**
     * 手动更新NPC位置
     */
    async updateNPCLocation(npcName, newLocation, activity = null) {
        let url = `/api/v1/npc/agent/update_location?npc_name=${encodeURIComponent(npcName)}&new_location=${encodeURIComponent(newLocation)}`;
        if (activity) {
            url += `&activity=${encodeURIComponent(activity)}`;
        }
        return this.post(url);
    }

    // ========== 玩家 API ==========

    async createPlayer(name, profession, currentLocation) {
        return this.post('/api/v1/player/create', {
            name: name,
            profession: profession,
            current_location: currentLocation
        });
    }

    async playerAction(action, target = null, details = '') {
        return this.post('/api/v1/player/action', {
            action: action,
            target: target,
            details: details
        });
    }

    async getPlayerStatus() {
        return this.get('/api/v1/player/status');
    }

    // ========== 世界数据系统 API ==========

    // 经济系统
    async getBalance(entity) {
        return this.get(`/api/v1/world/economy/balance/${encodeURIComponent(entity)}`);
    }

    async transfer(fromEntity, toEntity, amount, category = 'transfer', description = '') {
        return this.post(`/api/v1/world/economy/transfer?from_entity=${encodeURIComponent(fromEntity)}&to_entity=${encodeURIComponent(toEntity)}&amount=${amount}&category=${encodeURIComponent(category)}&description=${encodeURIComponent(description)}`);
    }

    // 工作系统
    async getAvailableJobs(location = null) {
        let url = '/api/v1/world/jobs';
        if (location) {
            url += `?location=${encodeURIComponent(location)}`;
        }
        return this.get(url);
    }

    async acceptJob(jobId, worker) {
        return this.post('/api/v1/world/jobs/accept', { job_id: jobId, worker: worker });
    }

    async updateJobProgress(jobId, progress) {
        return this.post(`/api/v1/world/jobs/${encodeURIComponent(jobId)}/progress?progress=${progress}`);
    }

    async getWorkerJobs(worker) {
        return this.get(`/api/v1/world/jobs/worker/${encodeURIComponent(worker)}`);
    }

    // 住宿系统
    async getAvailableLodgings(location = null) {
        let url = '/api/v1/world/lodgings';
        if (location) {
            url += `?location=${encodeURIComponent(location)}`;
        }
        return this.get(url);
    }

    async bookLodging(lodgingId, guest, nights = 1) {
        return this.post('/api/v1/world/lodgings/book', {
            lodging_id: lodgingId,
            guest: guest,
            nights: nights
        });
    }

    async checkoutLodging(lodgingId) {
        return this.post(`/api/v1/world/lodgings/${encodeURIComponent(lodgingId)}/checkout`);
    }

    // 好感度系统
    async getEntityRelationships(entity) {
        return this.get(`/api/v1/world/relationships/${encodeURIComponent(entity)}`);
    }

    async getRelationship(entityA, entityB) {
        return this.get(`/api/v1/world/relationship?entity_a=${encodeURIComponent(entityA)}&entity_b=${encodeURIComponent(entityB)}`);
    }

    async modifyRelationship(entityA, entityB, delta, reason = '') {
        return this.post('/api/v1/world/relationship/modify', {
            entity_a: entityA,
            entity_b: entityB,
            delta: delta,
            reason: reason
        });
    }

    // 异步事件传播
    async startEventPropagation(eventContent, originLocation, eventType = 'world_event', severity = 5) {
        return this.post('/api/v1/world/events/propagate', {
            event_content: eventContent,
            origin_location: originLocation,
            event_type: eventType,
            severity: severity
        });
    }

    async getNextPropagation(eventId) {
        return this.get(`/api/v1/world/events/propagate/${encodeURIComponent(eventId)}/next`);
    }

    async markLocationNotified(eventId, location) {
        return this.post(`/api/v1/world/events/propagate/${encodeURIComponent(eventId)}/notify?location=${encodeURIComponent(location)}`);
    }

    async getPropagationStatus(eventId) {
        return this.get(`/api/v1/world/events/propagate/${encodeURIComponent(eventId)}/status`);
    }

    // 世界状态
    async getWorldDataState() {
        return this.get('/api/v1/world/data/state');
    }

    // ========== WebSocket ==========

    connectWebSocket() {
        // 如果 WebSocket 已禁用或超过重试次数，跳过
        if (!this.wsEnabled || this.wsRetryCount >= this.wsMaxRetries) {
            console.log('WebSocket 已禁用或超过重试次数');
            return Promise.resolve();
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const wsUrl = this.baseUrl.replace('http', 'ws') + '/ws';

            try {
                this.ws = new WebSocket(wsUrl);
            } catch (e) {
                console.warn('WebSocket 创建失败:', e);
                this.wsRetryCount++;
                resolve(); // 不阻塞，继续使用 HTTP 轮询
                return;
            }

            // 设置超时
            const timeout = setTimeout(() => {
                if (this.ws.readyState !== WebSocket.OPEN) {
                    this.ws.close();
                    this.wsRetryCount++;
                    console.warn(`WebSocket 连接超时，重试次数: ${this.wsRetryCount}/${this.wsMaxRetries}`);
                    resolve();
                }
            }, 5000);

            this.ws.onopen = () => {
                clearTimeout(timeout);
                console.log('WebSocket 已连接');
                this.wsRetryCount = 0; // 重置重试计数
                this._triggerCallback('connected');
                resolve();
            };

            this.ws.onclose = (event) => {
                clearTimeout(timeout);
                console.log('WebSocket 已断开', event.code);
                this._triggerCallback('disconnected');
            };

            this.ws.onerror = (error) => {
                clearTimeout(timeout);
                this.wsRetryCount++;
                console.warn(`WebSocket 错误，重试次数: ${this.wsRetryCount}/${this.wsMaxRetries}`, error);
                this._triggerCallback('error', error);

                // 不 reject，让应用继续使用 HTTP 轮询
                if (this.wsRetryCount >= this.wsMaxRetries) {
                    console.warn('WebSocket 重试次数已用尽，将使用 HTTP 轮询');
                    this.wsEnabled = false;
                }
                resolve();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._handleWebSocketMessage(data);
                } catch (e) {
                    console.error('解析 WebSocket 消息失败:', e);
                }
            };
        });
    }

    disconnectWebSocket() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    _handleWebSocketMessage(data) {
        const type = data.type;

        switch (type) {
            case 'logs':
                this._triggerCallback('logs', data.logs);
                break;
            case 'event_processed':
                this._triggerCallback('event', data);
                break;
            case 'dialogue':
                this._triggerCallback('dialogue', data);
                break;
            case 'time_advanced':
                this._triggerCallback('time', data);
                break;
            case 'npc_changed':
                this._triggerCallback('npcChanged', data);
                break;
            case 'autonomous_mode':
                this._triggerCallback('autonomous', data);
                break;
            case 'pong':
                // 心跳响应
                break;
            default:
                this._triggerCallback('message', data);
        }
    }

    onWebSocket(event, callback) {
        if (!this.wsCallbacks[event]) {
            this.wsCallbacks[event] = [];
        }
        this.wsCallbacks[event].push(callback);
    }

    _triggerCallback(event, data) {
        const callbacks = this.wsCallbacks[event] || [];
        callbacks.forEach(cb => cb(data));
    }

    sendWebSocketMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    // 心跳
    startHeartbeat(interval = 30000) {
        this._heartbeatInterval = setInterval(() => {
            this.sendWebSocketMessage({ type: 'ping' });
        }, interval);
    }

    stopHeartbeat() {
        if (this._heartbeatInterval) {
            clearInterval(this._heartbeatInterval);
        }
    }

  // ========== 经济/背包 API（D2）==========

  getPlayerInventory() {
    return this.get('/api/v1/player/inventory');
  }

  getPlayerGold() {
    return this.get('/api/v1/player/gold');
  }

  useItem(itemId) {
    return this.post('/api/v1/player/inventory/use', { item_id: itemId });
  }

  tradeItem(sellerNpc, itemId, quantity, action) {
    return this.post('/api/v1/player/trade', {
      seller_npc: sellerNpc,
      item_id: itemId,
      quantity: quantity || 1,
      action: action || 'buy'
    });
  }

  playerWork(location, durationHours) {
    return this.post('/api/v1/player/work', {
      location: location,
      duration_hours: durationHours || 4
    });
  }

  playerRest(location, durationHours) {
    return this.post('/api/v1/player/rest', {
      location: location,
      duration_hours: durationHours || 8
    });
  }

  getPlayerRelationships() {
    return this.get('/api/v1/player/relationships');
  }

  // ========== 事件 API（D2）==========

  triggerEvent(eventType, content, location, impactScore, metadata) {
    return this.post('/api/v1/events/trigger', {
      event_type: eventType || 'general',
      content: content,
      location: location || '',
      impact_score: impactScore || 50,
      metadata: metadata || {}
    });
  }

  getActiveEvents() {
    return this.get('/api/v1/events/active');
  }

  getEventDetail(eventId) {
    return this.get(`/api/v1/events/${eventId}`);
  }

  getEventTree(eventId) {
    return this.get(`/api/v1/events/${eventId}/tree`);
  }

  settleEvent(eventId) {
    return this.post(`/api/v1/events/${eventId}/settle`, {});
  }

  // ========== NPC实例化 API（D2）==========

  instantiateNPC(entityId, triggerReason, description, profession) {
    return this.post('/api/v1/npc/instantiate', {
      entity_id: entityId,
      trigger_reason: triggerReason || 'player_interaction',
      description: description || '',
      profession: profession || '商人'
    });
  }

  removeNPC(npcName, reason) {
    return this.delete(`/api/v1/npc/${encodeURIComponent(npcName)}?reason=${encodeURIComponent(reason || '任务完成')}`);
  }

  getNPCRelationships(npcName) {
    return this.get(`/api/v1/npc/${encodeURIComponent(npcName)}/relationships`);
  }
}

// 导出全局实例
window.api = new NPCApiClient();
