<template>
  <div class="map-container">
    <canvas ref="canvas" @click="handleClick" @mousemove="handleHover"></canvas>
    <div v-if="tooltip" class="tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
      {{ tooltip.text }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useGameStore } from '../stores/game'

const store = useGameStore()
const canvas = ref<HTMLCanvasElement | null>(null)
const tooltip = ref<{ x: number; y: number; text: string } | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let animFrame: number | null = null

const W = 600, H = 500

onMounted(() => {
  const c = canvas.value!
  c.width = W; c.height = H
  ctx = c.getContext('2d')!
  draw()
  animFrame = requestAnimationFrame(loop)
})

onUnmounted(() => { if (animFrame) cancelAnimationFrame(animFrame) })

function loop() { draw(); animFrame = requestAnimationFrame(loop) }

watch(() => store.state, () => {}, { deep: true })

function getPos(name: string): [number, number] {
  const loc = store.state.locations?.[name]
  if (!loc?.position) return [W / 2, H / 2]
  const [x, y] = loc.position
  return [W / 2 + x * 8, H / 2 + y * 8]
}

function draw() {
  if (!ctx || !store.state.locations) return
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#1a1a2e'
  ctx.fillRect(0, 0, W, H)

  // 连接线
  ctx.strokeStyle = '#2d2d5e'
  ctx.lineWidth = 1.5
  for (const [name, loc] of Object.entries(store.state.locations)) {
    const [x1, y1] = getPos(name)
    for (const conn of (loc as any).connections || []) {
      if (store.state.locations[conn]) {
        const [x2, y2] = getPos(conn)
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
      }
    }
  }

  // 位置
  for (const [name, loc] of Object.entries(store.state.locations)) {
    const [x, y] = getPos(name)
    const npcs = (loc as any).npcs || []
    const isPlayer = store.state.player?.location === name

    // 位置圆圈
    ctx.beginPath()
    ctx.arc(x, y, 20, 0, Math.PI * 2)
    ctx.fillStyle = isPlayer ? '#e74c3c' : '#3498db'
    ctx.fill()
    ctx.strokeStyle = '#5dade2'
    ctx.lineWidth = 2
    ctx.stroke()

    // 位置名
    ctx.fillStyle = '#fff'
    ctx.font = '11px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(name, x, y - 28)

    // NPC 图标
    npcs.forEach((npc: string, i: number) => {
      const nx = x + Math.cos(i * 2.5) * 30
      const ny = y + Math.sin(i * 2.5) * 30
      ctx.beginPath()
      ctx.arc(nx, ny, 8, 0, Math.PI * 2)
      ctx.fillStyle = '#2ecc71'
      ctx.fill()
      ctx.strokeStyle = '#27ae60'
      ctx.stroke()
      // NPC 名
      ctx.fillStyle = '#ecf0f1'
      ctx.font = '9px sans-serif'
      ctx.fillText(npc.slice(0, 4), nx, ny - 12)
    })
  }

  // 玩家
  if (store.state.player) {
    const [px, py] = getPos(store.state.player.location)
    ctx.beginPath()
    ctx.arc(px, py, 10, 0, Math.PI * 2)
    ctx.fillStyle = '#f39c12'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 10px sans-serif'
    ctx.fillText('你', px, py + 3)
  }

  // 时间
  if (store.state.time) {
    ctx.fillStyle = '#fff'
    ctx.font = '12px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText(store.state.time.display, 12, 20)
  }
}

function handleClick(e: MouseEvent) {
  const rect = canvas.value!.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  if (!store.state.locations) return
  for (const name of Object.keys(store.state.locations)) {
    const [x, y] = getPos(name)
    const dx = mx - x, dy = my - y
    if (dx * dx + dy * dy < 400) {
      if (store.state.player) {
        store.movePlayer(name)
      }
      return
    }
  }
}

function handleHover(e: MouseEvent) {
  const rect = canvas.value!.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  if (!store.state.locations) { tooltip.value = null; return }
  for (const [name, loc] of Object.entries(store.state.locations)) {
    const [x, y] = getPos(name)
    const dx = mx - x, dy = my - y
    if (dx * dx + dy * dy < 400) {
      const npcs = (loc as any).npcs || []
      tooltip.value = { x: e.clientX, y: e.clientY, text: `${name} (${npcs.length}人)` }
      return
    }
  }
  tooltip.value = null
}
</script>

<style scoped>
.map-container { flex: 1; display: flex; justify-content: center; align-items: center; position: relative; background: #1a1a2e; }
canvas { border-radius: 8px; cursor: pointer; }
.tooltip { position: fixed; background: rgba(0,0,0,0.8); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; pointer-events: none; z-index: 100; }
</style>
