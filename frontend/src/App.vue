<template>
  <div class="app">
    <!-- 顶部状态栏 -->
    <header class="header">
      <div class="title">银溪镇 — NPC Agent</div>
      <div class="info" v-if="store.state.time">
        {{ store.state.time.display }}
        <span v-if="store.state.player"> | {{ store.state.player.name }} | {{ store.state.player.gold }}银币</span>
        <span :class="['conn', store.connected ? 'on' : 'off']">{{ store.connected ? '已连接' : '连接中' }}</span>
      </div>
    </header>

    <!-- 创建玩家 -->
    <div v-if="!store.state.player && !store.loading" class="create-player">
      <h2>创建角色</h2>
      <input v-model="playerName" placeholder="角色名" @keyup.enter="createPlayer">
      <button @click="createPlayer">进入银溪镇</button>
    </div>

    <!-- 主游戏界面 -->
    <div v-if="store.state.player" class="game-area">
      <GameMap />
      <div class="sidebar">
        <!-- 当前位置NPC -->
        <div class="panel">
          <h3>当前位置：{{ store.playerLocation }}</h3>
          <div class="npc-list">
            <div v-for="npc in store.npcsAtPlayerLocation" :key="npc"
                 :class="['npc-item', { active: store.selectedNpc === npc }]"
                 @click="store.selectedNpc = npc">
              <span class="npc-name">{{ npc }}</span>
              <span class="npc-prof">{{ store.state.npcs?.[npc]?.profession }}</span>
              <span class="npc-mood">{{ store.state.npcs?.[npc]?.mood }}</span>
            </div>
            <div v-if="store.npcsAtPlayerLocation.length === 0" class="empty">这里没有人</div>
          </div>
        </div>

        <!-- 对话面板 -->
        <div class="panel dialogue" v-if="store.selectedNpc">
          <h3>与{{ store.selectedNpc }}对话</h3>
          <div class="dialogues">
            <div v-for="(d, i) in store.dialogues" :key="i" :class="['dlg', d.speaker === store.state.player?.name ? 'me' : 'npc']">
              <span class="speaker">{{ d.speaker }}</span>
              <p>{{ d.message }}</p>
            </div>
          </div>
          <div class="dlg-input">
            <input v-model="store.dialogueInput" placeholder="说点什么..." @keyup.enter="sendDialogue">
            <button @click="sendDialogue">发送</button>
          </div>
        </div>

        <!-- 任务面板 -->
        <div class="panel">
          <h3>任务</h3>
          <div v-for="[id, q] in store.availableQuests" :key="id" class="quest">
            <span class="quest-title">{{ q.title }}</span>
            <span class="quest-desc">{{ q.desc }}</span>
            <span class="quest-reward">{{ q.reward_gold }}银币</span>
            <button @click="store.acceptQuest(id)">接受</button>
          </div>
          <div v-if="store.availableQuests.length === 0" class="empty">暂无可接任务</div>
        </div>
      </div>
    </div>

    <div v-if="store.loading" class="loading">正在连接世界...</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useGameStore } from './stores/game'
import GameMap from './components/GameMap.vue'

const store = useGameStore()
const playerName = ref('')

onMounted(() => store.init())

function createPlayer() {
  if (playerName.value) store.createPlayer(playerName.value)
}

function sendDialogue() {
  if (store.selectedNpc && store.dialogueInput) {
    store.talkToNpc(store.selectedNpc, store.dialogueInput)
    store.dialogueInput = ''
  }
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'PingFang SC', sans-serif; font-size: 13px; background: #f5f5f5; color: #222; }
.app { height: 100vh; display: flex; flex-direction: column; }
.header { display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; background: #2c3e50; color: #fff; }
.title { font-size: 15px; font-weight: 500; }
.info { font-size: 12px; display: flex; gap: 8px; align-items: center; }
.conn { padding: 2px 6px; border-radius: 4px; font-size: 11px; }
.conn.on { background: #27ae60; } .conn.off { background: #e74c3c; }
.create-player { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 60px; }
.create-player input { padding: 8px 12px; font-size: 14px; border: 1px solid #ccc; border-radius: 6px; width: 200px; }
.create-player button { padding: 8px 24px; font-size: 14px; background: #3498db; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.game-area { flex: 1; display: flex; overflow: hidden; }
.sidebar { width: 360px; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; background: #fff; border-left: 1px solid #ddd; }
.panel { border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; background: #fafafa; }
.panel h3 { font-size: 13px; font-weight: 500; margin-bottom: 8px; color: #2c3e50; }
.npc-item { display: flex; gap: 8px; align-items: center; padding: 6px 8px; border-radius: 6px; cursor: pointer; }
.npc-item:hover { background: #ecf0f1; }
.npc-item.active { background: #d4e6f5; }
.npc-name { font-weight: 500; }
.npc-prof { color: #7f8c8d; font-size: 11px; }
.npc-mood { margin-left: auto; font-size: 11px; color: #95a5a6; }
.empty { color: #bdc3c7; font-size: 12px; padding: 8px; }
.dialogue { flex: 1; display: flex; flex-direction: column; min-height: 200px; }
.dialogues { flex: 1; overflow-y: auto; padding: 4px; }
.dlg { margin-bottom: 8px; }
.dlg.me { text-align: right; }
.dlg .speaker { font-size: 11px; color: #7f8c8d; }
.dlg p { padding: 6px 10px; border-radius: 8px; font-size: 12px; }
.dlg.me p { background: #3498db; color: #fff; display: inline-block; }
.dlg.npc p { background: #ecf0f1; }
.dlg-input { display: flex; gap: 4px; padding-top: 8px; }
.dlg-input input { flex: 1; padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 12px; }
.dlg-input button { padding: 6px 12px; background: #3498db; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
.quest { display: flex; flex-direction: column; gap: 2px; padding: 6px; border-bottom: 1px solid #eee; }
.quest-title { font-weight: 500; font-size: 12px; }
.quest-desc { color: #7f8c8d; font-size: 11px; }
.quest-reward { color: #f39c12; font-size: 11px; }
.quest button { margin-top: 4px; padding: 3px 8px; background: #27ae60; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; align-self: flex-start; }
.loading { display: flex; justify-content: center; align-items: center; flex: 1; font-size: 14px; color: #7f8c8d; }
</style>
