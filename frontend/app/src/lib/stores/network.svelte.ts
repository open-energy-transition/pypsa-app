class NetworkStore {
  #current = $state<{ id: string; name: string | null } | null>(null);

  get current() {
    return this.#current;
  }
  set current(v: { id: string; name: string | null } | null) {
    this.#current = v;
  }
}

export const networkStore = new NetworkStore();
