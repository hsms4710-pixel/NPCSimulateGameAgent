/** WebSocket 客户端 — 实时世界状态推送 */
export class GameSocket {
  private ws: WebSocket | null = null
  private url: string
  private listeners: ((data: any) => void)[] = []
  private reconnectTimer: number | null = null

  constructor(url: string = `ws://${location.host}/ws`) {
    this.url = url
  }

  connect() {
    this.ws = new WebSocket(this.url)
    this.ws.onopen = () => {
      console.log('[WS] connected')
      if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
    }
    this.ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        this.listeners.forEach(fn => fn(data))
      } catch (err) { console.error('[WS] parse error', err) }
    }
    this.ws.onclose = () => {
      console.log('[WS] disconnected, reconnect in 3s')
      this.reconnectTimer = window.setTimeout(() => this.connect(), 3000)
    }
    this.ws.onerror = () => this.ws?.close()
  }

  onMessage(fn: (data: any) => void) { this.listeners.push(fn) }

  send(data: any) { this.ws?.send(JSON.stringify(data)) }

  close() { this.ws?.close() }
}
