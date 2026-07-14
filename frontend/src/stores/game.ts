/** 游戏状态管理 — Pinia store */
import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import { GameSocket } from '../api/ws'

export interface WorldState {
  time: { day: number; hour: number; minute: number; display: string }
  player: { name: string; profession: string; location: string; gold: number; inventory: Record<string, number> } | null
  locations: Record<string, { type: string; description: string; npcs: string[]; connections: string[]; position: [number, number]; services: string[] }>
  npcs: Record<string, { name: string; profession: string; location: string; energy: number; mood: string; activity: string; memory: any }>
  quests: Record<string, { title: string; desc: string; status: string; reward_gold: number }>
  economy: { balances: Record<string, number>; items: Record<string, any> }
  tick_updates?: Record<string, any>
}

export const useGameStore = defineStore('game', () => {
  const state = reactive<WorldState>({} as any)
  const dialogues = ref<{ speaker: string; message: string; time: string }[]>([])
  const selectedNpc = ref<string | null>(null)
  const dialogueInput = ref('')
  const connected = ref(false)
  const loading = ref(true)
  let socket: GameSocket | null = null

  function init() {
    socket = new GameSocket()
    socket.onMessage((data) => {
      Object.assign(state, data)
      connected.value = true
      loading.value = false
    })
    socket.connect()
    // 初始获取
    fetch('/api/world').then(r => r.json()).then(data => {
      Object.assign(state, data)
      loading.value = false
    })
  }

  async function createPlayer(name: string, profession: string = '旅行者') {
    const r = await fetch('/api/player/create', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, profession })
    })
    const data = await r.json()
    if (data.name) state.player = data
    return data
  }

  async function movePlayer(location: string) {
    const r = await fetch('/api/player/move', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ location })
    })
    return r.json()
  }

  async function talkToNpc(npcName: string, message: string) {
    dialogues.value.push({ speaker: state.player?.name || '玩家', message, time: state.time?.display || '' })
    const r = await fetch('/api/dialogue', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ npc_name: npcName, message })
    })
    const data = await r.json()
    if (data.ok && data.reply) {
      dialogues.value.push({ speaker: npcName, message: data.reply, time: state.time?.display || '' })
    }
    return data
  }

  async function trade(npcName: string, item: string, action: string) {
    const r = await fetch('/api/trade', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ npc_name: npcName, item, action })
    })
    return r.json()
  }

  async function acceptQuest(questId: string) {
    const r = await fetch('/api/quest/accept', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quest_id: questId })
    })
    return r.json()
  }

  const playerLocation = computed(() => state.player?.location || '镇中心广场')
  const npcsAtPlayerLocation = computed(() => state.locations?.[playerLocation.value]?.npcs || [])
  const availableQuests = computed(() => Object.entries(state.quests || {}).filter(([, q]: any) => q.status === 'available'))

  return { state, dialogues, selectedNpc, dialogueInput, connected, loading,
    init, createPlayer, movePlayer, talkToNpc, trade, acceptQuest,
    playerLocation, npcsAtPlayerLocation, availableQuests }
})
