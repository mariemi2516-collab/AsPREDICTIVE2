export type OfflineMutation = {
  id: string;
  method: 'POST' | 'PUT' | 'DELETE';
  path: string;
  body?: string;
  label: string;
  createdAt: string;
  entityKey?: string;
  baseVersion?: string;
};

export type OfflineConflict = OfflineMutation & {
  failedAt: string;
  message: string;
  statusCode?: number;
};

const DB_NAME = 'aspredictive-offline';
const DB_VERSION = 1;
const QUEUE_STORE = 'queue';
const CONFLICTS_STORE = 'conflicts';
const OFFLINE_QUEUE_EVENT = 'aspredictive-offline-queue-updated';
const META_QUEUE_COUNT_KEY = 'aspredictive_offline_queue_count';
const META_CONFLICT_COUNT_KEY = 'aspredictive_offline_conflict_count';
const LEGACY_QUEUE_KEY = 'aspredictive_offline_queue';
const LEGACY_CONFLICTS_KEY = 'aspredictive_offline_conflicts';

let migrationPromise: Promise<void> | null = null;

function emitQueueEvent() {
  window.dispatchEvent(new CustomEvent(OFFLINE_QUEUE_EVENT));
}

function setCountMetadata(queueCount: number, conflictCount: number) {
  localStorage.setItem(META_QUEUE_COUNT_KEY, String(queueCount));
  localStorage.setItem(META_CONFLICT_COUNT_KEY, String(conflictCount));
  emitQueueEvent();
}

function updateQueueCountMetadata(count: number) {
  localStorage.setItem(META_QUEUE_COUNT_KEY, String(count));
  emitQueueEvent();
}

function updateConflictCountMetadata(count: number) {
  localStorage.setItem(META_CONFLICT_COUNT_KEY, String(count));
  emitQueueEvent();
}

function getLegacyItems<T>(key: string): T[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function getDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        const queueStore = db.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
        queueStore.createIndex('createdAt', 'createdAt', { unique: false });
        queueStore.createIndex('entityKey', 'entityKey', { unique: false });
      }
      if (!db.objectStoreNames.contains(CONFLICTS_STORE)) {
        const conflictsStore = db.createObjectStore(CONFLICTS_STORE, { keyPath: 'id' });
        conflictsStore.createIndex('failedAt', 'failedAt', { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function promisifyRequest<T = unknown>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getAllFromStore<T>(storeName: string): Promise<T[]> {
  const db = await getDatabase();
  const tx = db.transaction(storeName, 'readonly');
  const store = tx.objectStore(storeName);
  const result = await promisifyRequest<T[]>(store.getAll());
  return result;
}

async function putInStore<T>(storeName: string, value: T): Promise<void> {
  const db = await getDatabase();
  const tx = db.transaction(storeName, 'readwrite');
  tx.objectStore(storeName).put(value);
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function deleteFromStore(storeName: string, key: string): Promise<void> {
  const db = await getDatabase();
  const tx = db.transaction(storeName, 'readwrite');
  tx.objectStore(storeName).delete(key);
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function clearStore(storeName: string): Promise<void> {
  const db = await getDatabase();
  const tx = db.transaction(storeName, 'readwrite');
  tx.objectStore(storeName).clear();
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function countStore(storeName: string): Promise<number> {
  const db = await getDatabase();
  const tx = db.transaction(storeName, 'readonly');
  const count = await promisifyRequest<number>(tx.objectStore(storeName).count());
  return count;
}

async function migrateLegacyStorage() {
  if (!migrationPromise) {
    migrationPromise = (async () => {
      const legacyQueue = getLegacyItems<OfflineMutation>(LEGACY_QUEUE_KEY);
      const legacyConflicts = getLegacyItems<OfflineConflict>(LEGACY_CONFLICTS_KEY);

      if (legacyQueue.length) {
        for (const item of legacyQueue) {
          await putInStore(QUEUE_STORE, item);
        }
        localStorage.removeItem(LEGACY_QUEUE_KEY);
      }

      if (legacyConflicts.length) {
        for (const item of legacyConflicts) {
          await putInStore(CONFLICTS_STORE, item);
        }
        localStorage.removeItem(LEGACY_CONFLICTS_KEY);
      }

      setCountMetadata(await countStore(QUEUE_STORE), await countStore(CONFLICTS_STORE));
    })();
  }

  await migrationPromise;
}

function buildEntityKey(path: string, method: string) {
  return `${method.toUpperCase()}:${path}`;
}

export async function getOfflineQueue() {
  await migrateLegacyStorage();
  const queue = await getAllFromStore<OfflineMutation>(QUEUE_STORE);
  return queue.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export async function getOfflineConflicts() {
  await migrateLegacyStorage();
  const conflicts = await getAllFromStore<OfflineConflict>(CONFLICTS_STORE);
  return conflicts.sort((a, b) => b.failedAt.localeCompare(a.failedAt));
}

export function getOfflineQueueSize() {
  return parseInt(localStorage.getItem(META_QUEUE_COUNT_KEY) || '0', 10);
}

export function getOfflineConflictCount() {
  return parseInt(localStorage.getItem(META_CONFLICT_COUNT_KEY) || '0', 10);
}

export async function enqueueOfflineMutation(mutation: Omit<OfflineMutation, 'id' | 'createdAt' | 'entityKey'>) {
  await migrateLegacyStorage();

  const entityKey = buildEntityKey(mutation.path, mutation.method);
  const queue = await getOfflineQueue();
  const previous = queue.find((item) => item.entityKey === entityKey);
  const nextItem: OfflineMutation = {
    ...mutation,
    id: previous?.id || crypto.randomUUID(),
    entityKey,
    createdAt: new Date().toISOString(),
  };

  await putInStore(QUEUE_STORE, nextItem);
  updateQueueCountMetadata(await countStore(QUEUE_STORE));
}

export async function removeOfflineMutation(id: string) {
  await migrateLegacyStorage();
  await deleteFromStore(QUEUE_STORE, id);
  updateQueueCountMetadata(await countStore(QUEUE_STORE));
}

export async function addOfflineConflict(conflict: Omit<OfflineConflict, 'failedAt'>) {
  await migrateLegacyStorage();
  const conflicts = await getOfflineConflicts();
  const existing = conflicts.find((item) => item.entityKey === conflict.entityKey);
  const nextConflict: OfflineConflict = {
    ...conflict,
    id: existing?.id || conflict.id,
    failedAt: new Date().toISOString(),
  };

  await putInStore(CONFLICTS_STORE, nextConflict);
  updateConflictCountMetadata(await countStore(CONFLICTS_STORE));
}

export async function removeOfflineConflict(id: string) {
  await migrateLegacyStorage();
  await deleteFromStore(CONFLICTS_STORE, id);
  updateConflictCountMetadata(await countStore(CONFLICTS_STORE));
}

export async function retryOfflineConflict(id: string) {
  await migrateLegacyStorage();
  const conflicts = await getOfflineConflicts();
  const conflict = conflicts.find((item) => item.id === id);
  if (!conflict) return;

  await enqueueOfflineMutation({
    method: conflict.method,
    path: conflict.path,
    body: conflict.body,
    label: conflict.label,
    baseVersion: conflict.baseVersion,
  });
  await removeOfflineConflict(id);
}

export async function clearOfflineQueue() {
  await migrateLegacyStorage();
  await clearStore(QUEUE_STORE);
  updateQueueCountMetadata(0);
}

export async function clearOfflineConflicts() {
  await migrateLegacyStorage();
  await clearStore(CONFLICTS_STORE);
  updateConflictCountMetadata(0);
}

export function subscribeOfflineQueue(listener: () => void) {
  const handler = () => listener();
  window.addEventListener(OFFLINE_QUEUE_EVENT, handler);
  return () => window.removeEventListener(OFFLINE_QUEUE_EVENT, handler);
}
