// Cache in-memory semplice per Fly.io free tier
let cache = new Map();

class SimpleCache {
  constructor() {
    this.data = new Map();
  }

  set(key, value, ttlMs = 15 * 60 * 1000) { // Default 15 minuti
    const expiry = Date.now() + ttlMs;
    this.data.set(key, {
      value,
      expiry
    });
  }

  get(key) {
    const item = this.data.get(key);

    if (!item) {
      return null;
    }

    if (Date.now() > item.expiry) {
      this.data.delete(key);
      return null;
    }

    return item.value;
  }

  has(key) {
    return this.get(key) !== null;
  }

  clear() {
    this.data.clear();
  }

  // Cleanup expired entries per liberare memoria
  cleanup() {
    const now = Date.now();
    for (const [key, item] of this.data.entries()) {
      if (now > item.expiry) {
        this.data.delete(key);
      }
    }
  }

  // Info per debug
  size() {
    return this.data.size;
  }
}

// Istanza singleton
const globalCache = new SimpleCache();

// Cleanup periodico ogni 10 minuti
setInterval(() => {
  globalCache.cleanup();
}, 10 * 60 * 1000);

module.exports = globalCache;