/**
 * 可视化地图系统
 * 使用HTML5 Canvas绘制镇子地图和NPC位置
 */

class WorldMap {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('Canvas element not found:', canvasId);
            return;
        }
        this.ctx = this.canvas.getContext('2d');
        this.locations = {};  // 地点坐标
        this.npcs = {};       // NPC位置 {npc_name: location_name}
        this.player = null;   // 玩家位置
        this.selectedLocation = null;
        this.hoveredLocation = null;
        this.animatingNPCs = []; // 正在移动的NPC动画
        this.eventHighlights = []; // 事件高亮效果

        // 响应式尺寸
        this.baseWidth = 600;
        this.baseHeight = 550;

        this._initLocations();
        this._bindEvents();
        this._setupResponsive();
        this.render();
    }

    // 初始化地点坐标
    _initLocations() {
        // 定义镇子布局 - 坐标基于600x550的基础尺寸
        this.locations = {
            "镇中心": {
                x: 300, y: 275,
                radius: 45,
                color: "#4CAF50",
                icon: "flag",
                connections: ["酒馆", "市场区", "教堂", "村庄大门"]
            },
            "酒馆": {
                x: 180, y: 160,
                radius: 38,
                color: "#FF9800",
                icon: "beer",
                connections: ["镇中心", "市场区"]
            },
            "市场区": {
                x: 420, y: 160,
                radius: 38,
                color: "#2196F3",
                icon: "shop",
                connections: ["镇中心", "酒馆", "铁匠铺"]
            },
            "铁匠铺": {
                x: 520, y: 275,
                radius: 35,
                color: "#795548",
                icon: "anvil",
                connections: ["市场区", "工坊区"]
            },
            "教堂": {
                x: 300, y: 420,
                radius: 40,
                color: "#9C27B0",
                icon: "church",
                connections: ["镇中心", "农田"]
            },
            "工坊区": {
                x: 480, y: 400,
                radius: 35,
                color: "#607D8B",
                icon: "gear",
                connections: ["铁匠铺", "农田"]
            },
            "农田": {
                x: 380, y: 480,
                radius: 42,
                color: "#8BC34A",
                icon: "wheat",
                connections: ["教堂", "工坊区", "森林边缘"]
            },
            "村庄大门": {
                x: 80, y: 275,
                radius: 35,
                color: "#F44336",
                icon: "gate",
                connections: ["镇中心", "森林边缘"]
            },
            "森林边缘": {
                x: 120, y: 450,
                radius: 38,
                color: "#009688",
                icon: "tree",
                connections: ["村庄大门", "农田"]
            }
        };
    }

    // 设置响应式
    _setupResponsive() {
        const resizeObserver = new ResizeObserver(() => this._handleResize());
        const container = this.canvas.parentElement;
        if (container) {
            resizeObserver.observe(container);
        }
        this._handleResize();
    }

    _handleResize() {
        const container = this.canvas.parentElement;
        if (!container) return;

        const containerWidth = container.clientWidth - 20;
        const containerHeight = container.clientHeight - 20;

        // 保持宽高比
        const aspectRatio = this.baseWidth / this.baseHeight;
        let width = containerWidth;
        let height = containerWidth / aspectRatio;

        if (height > containerHeight) {
            height = containerHeight;
            width = containerHeight * aspectRatio;
        }

        // 设置最小尺寸
        width = Math.max(300, Math.min(width, 800));
        height = Math.max(275, Math.min(height, 733));

        this.canvas.width = width;
        this.canvas.height = height;
        this.scale = width / this.baseWidth;

        this.render();
    }

    // 绑定鼠标事件
    _bindEvents() {
        this.canvas.addEventListener('click', (e) => this._handleClick(e));
        this.canvas.addEventListener('mousemove', (e) => this._handleHover(e));
        this.canvas.addEventListener('mouseleave', () => {
            this.hoveredLocation = null;
            this.render();
        });
    }

    _getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: (e.clientX - rect.left) / this.scale,
            y: (e.clientY - rect.top) / this.scale
        };
    }

    _getLocationAtPoint(x, y) {
        for (const [name, loc] of Object.entries(this.locations)) {
            const dx = x - loc.x;
            const dy = y - loc.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance <= loc.radius) {
                return name;
            }
        }
        return null;
    }

    _handleClick(e) {
        const pos = this._getMousePos(e);
        const location = this._getLocationAtPoint(pos.x, pos.y);

        if (location) {
            this.selectedLocation = location;
            this.render();

            // 触发自定义事件
            const event = new CustomEvent('locationSelected', {
                detail: { location, locationData: this.locations[location] }
            });
            this.canvas.dispatchEvent(event);
        }
    }

    _handleHover(e) {
        const pos = this._getMousePos(e);
        const location = this._getLocationAtPoint(pos.x, pos.y);

        if (location !== this.hoveredLocation) {
            this.hoveredLocation = location;
            this.canvas.style.cursor = location ? 'pointer' : 'default';
            this.render();
        }
    }

    // 绘制整个地图
    render() {
        if (!this.ctx) return;

        const ctx = this.ctx;
        const scale = this.scale || 1;

        ctx.save();
        ctx.scale(scale, scale);

        ctx.clearRect(0, 0, this.baseWidth, this.baseHeight);
        this._drawBackground();
        this._drawConnections();
        this._drawEventHighlights();
        this._drawLocations();
        this._drawNPCs();
        this._drawPlayer();
        this._drawAnimatingNPCs();
        this._drawTooltip();
        this._drawLegend();

        ctx.restore();
    }

    _drawBackground() {
        const ctx = this.ctx;

        // 渐变背景
        const gradient = ctx.createRadialGradient(300, 275, 50, 300, 275, 400);
        gradient.addColorStop(0, '#1e3a5f');
        gradient.addColorStop(1, '#0f172a');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, this.baseWidth, this.baseHeight);

        // 装饰性网格
        ctx.strokeStyle = 'rgba(139, 92, 246, 0.1)';
        ctx.lineWidth = 1;
        for (let x = 0; x < this.baseWidth; x += 50) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.baseHeight);
            ctx.stroke();
        }
        for (let y = 0; y < this.baseHeight; y += 50) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.baseWidth, y);
            ctx.stroke();
        }
    }

    _drawConnections() {
        const ctx = this.ctx;
        const drawnConnections = new Set();

        for (const [name, loc] of Object.entries(this.locations)) {
            for (const connectedName of loc.connections) {
                const key = [name, connectedName].sort().join('-');
                if (drawnConnections.has(key)) continue;
                drawnConnections.add(key);

                const connectedLoc = this.locations[connectedName];
                if (!connectedLoc) continue;

                // 绘制路径
                ctx.beginPath();
                ctx.moveTo(loc.x, loc.y);
                ctx.lineTo(connectedLoc.x, connectedLoc.y);

                // 渐变路径
                const gradient = ctx.createLinearGradient(loc.x, loc.y, connectedLoc.x, connectedLoc.y);
                gradient.addColorStop(0, 'rgba(139, 92, 246, 0.3)');
                gradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.5)');
                gradient.addColorStop(1, 'rgba(139, 92, 246, 0.3)');

                ctx.strokeStyle = gradient;
                ctx.lineWidth = 3;
                ctx.setLineDash([8, 4]);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }
    }

    _drawEventHighlights() {
        const ctx = this.ctx;
        const now = Date.now();

        this.eventHighlights = this.eventHighlights.filter(event => {
            const elapsed = now - event.startTime;
            if (elapsed > event.duration) return false;

            const loc = this.locations[event.location];
            if (!loc) return false;

            const progress = elapsed / event.duration;
            const pulsePhase = (elapsed / 300) % 1;
            const pulseRadius = loc.radius + 20 + Math.sin(pulsePhase * Math.PI * 2) * 10;
            const alpha = (1 - progress) * 0.6;

            // 绘制脉冲效果
            ctx.beginPath();
            ctx.arc(loc.x, loc.y, pulseRadius, 0, Math.PI * 2);

            const color = event.severity >= 7 ? '239, 68, 68' :
                          event.severity >= 4 ? '245, 158, 11' : '59, 130, 246';
            ctx.fillStyle = `rgba(${color}, ${alpha * 0.3})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(${color}, ${alpha})`;
            ctx.lineWidth = 3;
            ctx.stroke();

            return true;
        });
    }

    _drawLocations() {
        const ctx = this.ctx;

        for (const [name, loc] of Object.entries(this.locations)) {
            const isHovered = name === this.hoveredLocation;
            const isSelected = name === this.selectedLocation;
            const isPlayerHere = name === this.player;

            // 外发光效果
            if (isHovered || isSelected || isPlayerHere) {
                ctx.beginPath();
                ctx.arc(loc.x, loc.y, loc.radius + 8, 0, Math.PI * 2);
                const glowColor = isPlayerHere ? 'rgba(16, 185, 129, 0.4)' :
                                  isSelected ? 'rgba(139, 92, 246, 0.5)' : 'rgba(255, 255, 255, 0.3)';
                ctx.fillStyle = glowColor;
                ctx.fill();
            }

            // 地点圆形背景
            ctx.beginPath();
            ctx.arc(loc.x, loc.y, loc.radius, 0, Math.PI * 2);

            // 渐变填充
            const gradient = ctx.createRadialGradient(
                loc.x - loc.radius * 0.3, loc.y - loc.radius * 0.3, 0,
                loc.x, loc.y, loc.radius
            );
            gradient.addColorStop(0, this._lightenColor(loc.color, 30));
            gradient.addColorStop(1, loc.color);
            ctx.fillStyle = gradient;
            ctx.fill();

            // 边框
            ctx.strokeStyle = isPlayerHere ? '#10b981' :
                             isSelected ? '#8b5cf6' :
                             isHovered ? '#ffffff' : 'rgba(255, 255, 255, 0.5)';
            ctx.lineWidth = isPlayerHere || isSelected ? 4 : 2;
            ctx.stroke();

            // 绘制图标
            this._drawLocationIcon(loc.x, loc.y, loc.icon, loc.radius * 0.5);

            // 地点名称
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 12px "Microsoft YaHei", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillText(name, loc.x, loc.y + loc.radius + 8);

            // 玩家标识
            if (isPlayerHere) {
                ctx.fillStyle = '#10b981';
                ctx.font = '10px "Microsoft YaHei", sans-serif';
                ctx.fillText('(你在这里)', loc.x, loc.y + loc.radius + 22);
            }
        }
    }

    _drawLocationIcon(x, y, iconType, size) {
        const ctx = this.ctx;
        ctx.save();
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
        ctx.font = `${size * 2}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const icons = {
            'flag': '🏛️',
            'beer': '🍺',
            'shop': '🏪',
            'anvil': '⚒️',
            'church': '⛪',
            'gear': '🔧',
            'wheat': '🌾',
            'gate': '🚪',
            'tree': '🌲'
        };

        ctx.fillText(icons[iconType] || '📍', x, y);
        ctx.restore();
    }

    _drawNPCs() {
        const ctx = this.ctx;

        // 按位置分组NPC
        const npcsByLocation = {};
        for (const [npcName, location] of Object.entries(this.npcs)) {
            if (!npcsByLocation[location]) {
                npcsByLocation[location] = [];
            }
            npcsByLocation[location].push(npcName);
        }

        // 绘制每个位置的NPC
        for (const [location, npcNames] of Object.entries(npcsByLocation)) {
            const loc = this.locations[location];
            if (!loc) continue;

            const count = npcNames.length;
            const angleStep = (Math.PI * 2) / Math.max(count, 6);
            const radius = loc.radius + 25;

            npcNames.forEach((npcName, index) => {
                const angle = -Math.PI / 2 + index * angleStep;
                const npcX = loc.x + Math.cos(angle) * radius;
                const npcY = loc.y + Math.sin(angle) * radius;

                // NPC小图标
                ctx.beginPath();
                ctx.arc(npcX, npcY, 12, 0, Math.PI * 2);
                ctx.fillStyle = '#e91e63';
                ctx.fill();
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 2;
                ctx.stroke();

                // NPC emoji
                ctx.font = '14px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('👤', npcX, npcY);

                // NPC名称（简短）
                ctx.fillStyle = '#ffffff';
                ctx.font = '9px "Microsoft YaHei", sans-serif';
                const shortName = npcName.length > 4 ? npcName.substring(0, 4) + '...' : npcName;
                ctx.fillText(shortName, npcX, npcY + 18);
            });
        }
    }

    _drawPlayer() {
        if (!this.player) return;

        const loc = this.locations[this.player];
        if (!loc) return;

        const ctx = this.ctx;

        // 玩家标记 - 在地点中心上方
        const playerY = loc.y - loc.radius - 15;

        // 发光效果
        ctx.beginPath();
        ctx.arc(loc.x, playerY, 18, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(16, 185, 129, 0.3)';
        ctx.fill();

        // 玩家图标
        ctx.beginPath();
        ctx.arc(loc.x, playerY, 14, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // 玩家emoji
        ctx.font = '16px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('⭐', loc.x, playerY);
    }

    _drawAnimatingNPCs() {
        const ctx = this.ctx;
        const now = Date.now();

        this.animatingNPCs = this.animatingNPCs.filter(anim => {
            const elapsed = now - anim.startTime;
            const progress = Math.min(elapsed / anim.duration, 1);

            if (progress >= 1) {
                // 动画完成，更新NPC位置
                this.npcs[anim.npcName] = anim.toLocation;
                return false;
            }

            const fromLoc = this.locations[anim.fromLocation];
            const toLoc = this.locations[anim.toLocation];
            if (!fromLoc || !toLoc) return false;

            // 计算当前位置 (使用缓动函数)
            const easeProgress = this._easeInOutQuad(progress);
            const currentX = fromLoc.x + (toLoc.x - fromLoc.x) * easeProgress;
            const currentY = fromLoc.y + (toLoc.y - fromLoc.y) * easeProgress;

            // 绘制移动中的NPC
            ctx.beginPath();
            ctx.arc(currentX, currentY, 15, 0, Math.PI * 2);
            ctx.fillStyle = '#ff5722';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // 移动emoji
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('🚶', currentX, currentY);

            // NPC名称
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 10px "Microsoft YaHei", sans-serif';
            ctx.fillText(anim.npcName, currentX, currentY + 22);

            return true;
        });

        // 如果有动画在进行，继续渲染
        if (this.animatingNPCs.length > 0) {
            requestAnimationFrame(() => this.render());
        }
    }

    _easeInOutQuad(t) {
        return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
    }

    _drawTooltip() {
        if (!this.hoveredLocation) return;

        const loc = this.locations[this.hoveredLocation];
        if (!loc) return;

        const ctx = this.ctx;
        const npcsHere = Object.entries(this.npcs)
            .filter(([_, location]) => location === this.hoveredLocation)
            .map(([name, _]) => name);

        const padding = 10;
        const lineHeight = 18;
        const lines = [
            `地点: ${this.hoveredLocation}`,
            `NPC: ${npcsHere.length > 0 ? npcsHere.join(', ') : '无'}`
        ];

        if (this.player === this.hoveredLocation) {
            lines.push('你在这里');
        }

        // 计算tooltip尺寸
        ctx.font = '12px "Microsoft YaHei", sans-serif';
        const maxWidth = Math.max(...lines.map(line => ctx.measureText(line).width));
        const width = maxWidth + padding * 2;
        const height = lines.length * lineHeight + padding * 2;

        // 计算位置（避免超出边界）
        let tooltipX = loc.x + loc.radius + 15;
        let tooltipY = loc.y - height / 2;

        if (tooltipX + width > this.baseWidth) {
            tooltipX = loc.x - loc.radius - width - 15;
        }
        if (tooltipY < 0) tooltipY = 5;
        if (tooltipY + height > this.baseHeight) tooltipY = this.baseHeight - height - 5;

        // 绘制tooltip背景
        ctx.fillStyle = 'rgba(30, 41, 59, 0.95)';
        ctx.strokeStyle = 'rgba(139, 92, 246, 0.5)';
        ctx.lineWidth = 1;
        this._roundRect(ctx, tooltipX, tooltipY, width, height, 8);
        ctx.fill();
        ctx.stroke();

        // 绘制文字
        ctx.fillStyle = '#f1f5f9';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        lines.forEach((line, index) => {
            ctx.fillText(line, tooltipX + padding, tooltipY + padding + index * lineHeight);
        });
    }

    _drawLegend() {
        const ctx = this.ctx;
        const legendX = 10;
        const legendY = 10;
        const itemHeight = 20;

        const items = [
            { color: '#10b981', label: '玩家位置' },
            { color: '#e91e63', label: 'NPC' },
            { color: '#8b5cf6', label: '选中地点' }
        ];

        // 图例背景
        ctx.fillStyle = 'rgba(30, 41, 59, 0.8)';
        this._roundRect(ctx, legendX, legendY, 100, items.length * itemHeight + 16, 6);
        ctx.fill();

        // 图例项
        items.forEach((item, index) => {
            const y = legendY + 8 + index * itemHeight;

            ctx.beginPath();
            ctx.arc(legendX + 15, y + 6, 6, 0, Math.PI * 2);
            ctx.fillStyle = item.color;
            ctx.fill();

            ctx.fillStyle = '#f1f5f9';
            ctx.font = '11px "Microsoft YaHei", sans-serif';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(item.label, legendX + 28, y + 6);
        });
    }

    _roundRect(ctx, x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }

    _lightenColor(color, percent) {
        const num = parseInt(color.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.min(255, (num >> 16) + amt);
        const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
        const B = Math.min(255, (num & 0x0000FF) + amt);
        return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
    }

    // ========== 公共API ==========

    /**
     * 更新NPC位置
     * @param {Object} npcData - {npc_name: location_name}
     */
    updateNPCPositions(npcData) {
        this.npcs = npcData || {};
        this.render();
    }

    /**
     * 更新玩家位置
     * @param {string} location - 地点名称
     */
    updatePlayerPosition(location) {
        this.player = location;
        this.render();
    }

    /**
     * 高亮事件位置
     * @param {string} location - 地点名称
     * @param {number} severity - 严重程度 (1-10)
     * @param {number} duration - 持续时间(毫秒)，默认5000
     */
    highlightEvent(location, severity = 5, duration = 5000) {
        this.eventHighlights.push({
            location,
            severity,
            duration,
            startTime: Date.now()
        });
        this.render();

        // 启动动画循环
        const animate = () => {
            if (this.eventHighlights.length > 0) {
                this.render();
                requestAnimationFrame(animate);
            }
        };
        requestAnimationFrame(animate);
    }

    /**
     * 显示NPC移动动画
     * @param {string} npcName - NPC名称
     * @param {string} fromLocation - 起始地点
     * @param {string} toLocation - 目标地点
     * @param {number} duration - 动画持续时间(毫秒)，默认2000
     */
    animateNPCMovement(npcName, fromLocation, toLocation, duration = 2000) {
        // 暂时从原位置移除NPC
        delete this.npcs[npcName];

        this.animatingNPCs.push({
            npcName,
            fromLocation,
            toLocation,
            duration,
            startTime: Date.now()
        });

        this.render();
    }

    /**
     * 选中指定地点
     * @param {string} location - 地点名称
     */
    selectLocation(location) {
        this.selectedLocation = location;
        this.render();
    }

    /**
     * 清除选中状态
     */
    clearSelection() {
        this.selectedLocation = null;
        this.render();
    }

    /**
     * 获取所有地点信息
     * @returns {Object} 地点数据
     */
    getLocations() {
        return this.locations;
    }

    /**
     * 获取指定地点的NPC列表
     * @param {string} location - 地点名称
     * @returns {Array} NPC名称列表
     */
    getNPCsAtLocation(location) {
        return Object.entries(this.npcs)
            .filter(([_, loc]) => loc === location)
            .map(([name, _]) => name);
    }
}

// 导出
window.WorldMap = WorldMap;
