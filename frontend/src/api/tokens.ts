/**
 * JWT storage.
 *
 * By default a sign-in lasts for the browser session (sessionStorage): closing the tab or
 * browser signs you out, so a shared or demo computer doesn't stay logged in.
 * "Keep me signed in" stores the tokens in localStorage instead (survives restarts until the
 * 7-day refresh token expires). A refresh keeps using whichever storage the login chose.
 */
const ACCESS = 'leadpilot-access';
const REFRESH = 'leadpilot-refresh';
const REMEMBER = 'leadpilot-remember';

type Store = 'local' | 'session';

function storage(store: Store): Storage | null {
  try {
    return store === 'local' ? window.localStorage : window.sessionStorage;
  } catch {
    return null; // storage blocked (private mode): the session won't survive a reload
  }
}

function get(store: Store, key: string): string | null {
  try {
    return storage(store)?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function put(store: Store, key: string, value: string | null) {
  try {
    const s = storage(store);
    if (!s) return;
    if (value === null) s.removeItem(key);
    else s.setItem(key, value);
  } catch {
    // Ignore: storage full or blocked.
  }
}

function clearStore(store: Store) {
  put(store, ACCESS, null);
  put(store, REFRESH, null);
  if (store === 'local') put(store, REMEMBER, null);
}

/** Sessions saved before "Keep me signed in" existed are signed out once. */
function dropUnrememberedLocalTokens() {
  if (get('local', ACCESS) && get('local', REMEMBER) !== '1') clearStore('local');
}
dropUnrememberedLocalTokens();

/** Where the current tokens live: session wins (it's the default). */
function activeStore(): Store {
  if (get('session', ACCESS) || get('session', REFRESH)) return 'session';
  if (get('local', REMEMBER) === '1') return 'local';
  return 'session';
}

export const tokens = {
  get access() {
    return get(activeStore(), ACCESS);
  },
  get refresh() {
    return get(activeStore(), REFRESH);
  },
  /** True when the current sign-in survives closing the browser. */
  get remembered() {
    return activeStore() === 'local';
  },
  /**
   * Save tokens. Pass `remember` on login to pick the storage; token refreshes omit it and
   * keep the storage the login chose.
   */
  set(access: string, refresh?: string, remember?: boolean) {
    let store: Store = activeStore();
    if (remember !== undefined) {
      store = remember ? 'local' : 'session';
      clearStore(store === 'local' ? 'session' : 'local');
      if (remember) put('local', REMEMBER, '1');
    }
    put(store, ACCESS, access);
    if (refresh) put(store, REFRESH, refresh);
  },
  clear() {
    clearStore('session');
    clearStore('local');
  },
};
