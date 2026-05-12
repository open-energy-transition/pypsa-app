const MIN_WIDTH = 360;
const MAX_WIDTH = 1200;
const DEFAULT_WIDTH = 480;

class ChatModalStore {
  #open = $state(false);
  #width = $state(DEFAULT_WIDTH);

  get open() { return this.#open; }
  set open(v: boolean) {
    this.#open = v;
    try { localStorage.setItem('chat-modal-open', v ? 'true' : 'false'); } catch {}
  }

  get width() { return this.#width; }
  set width(v: number) {
    const clamped = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, v));
    this.#width = clamped;
    try { localStorage.setItem('chat-modal-width', String(clamped)); } catch {}
  }

  init() {
    try {
      this.#open = localStorage.getItem('chat-modal-open') === 'true';
      const w = Number(localStorage.getItem('chat-modal-width'));
      if (Number.isFinite(w) && w > 0) this.#width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, w));
    } catch {}
  }

  toggle() { this.open = !this.#open; }
}

export const chatModalStore = new ChatModalStore();
