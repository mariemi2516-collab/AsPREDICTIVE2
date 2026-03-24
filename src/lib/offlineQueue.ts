export type OfflineMutation = {
  id: string;
  method: 'POST' | 'PUT' | 'DELETE';
  path: string;
  body?: string;
  label: string;
  createdAt: string;
};

export type OfflineConflict = OfflineMutation & {
  failedAt: string;
  message: string;
  statusCode?: number;
};

const OFFLINE_QUEUE_KEY = 'aspredictive_offline_queue';
const OFFLINE_CONFLICTS_KEY = 'aspredictive_offline_conflicts';
const OFFLINE_QUEUE_EVENT = 'aspredictive-offline-queue-updated';

function emitQueueEvent() {
  window.dispatchEvent(new CustomEvent(OFFLINE_QUEUE_EVENT));
}

function readQueue(): OfflineMutation[] {
  try {
    const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function readConflicts(): OfflineConflict[] {
  try {
    const raw = localStorage.getItem(OFFLINE_CONFLICTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeQueue(queue: OfflineMutation[]) {
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
  emitQueueEvent();
}

function writeConflicts(conflicts: OfflineConflict[]) {
  localStorage.setItem(OFFLINE_CONFLICTS_KEY, JSON.stringify(conflicts));
  emitQueueEvent();
}

export function getOfflineQueue() {
  return readQueue();
}

export function getOfflineQueueSize() {
  return readQueue().length;
}

export function getOfflineConflicts() {
  return readConflicts();
}

export function getOfflineConflictCount() {
  return readConflicts().length;
}

export function enqueueOfflineMutation(mutation: Omit<OfflineMutation, 'id' | 'createdAt'>) {
  const queue = readQueue();
  queue.push({
    ...mutation,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  });
  writeQueue(queue);
}

export function removeOfflineMutation(id: string) {
  const queue = readQueue().filter((item) => item.id !== id);
  writeQueue(queue);
}

export function addOfflineConflict(conflict: Omit<OfflineConflict, 'failedAt'>) {
  const conflicts = readConflicts();
  conflicts.unshift({
    ...conflict,
    failedAt: new Date().toISOString(),
  });
  writeConflicts(conflicts.slice(0, 50));
}

export function removeOfflineConflict(id: string) {
  const conflicts = readConflicts().filter((item) => item.id !== id);
  writeConflicts(conflicts);
}

export function retryOfflineConflict(id: string) {
  const conflicts = readConflicts();
  const conflict = conflicts.find((item) => item.id === id);
  if (!conflict) return;

  enqueueOfflineMutation({
    method: conflict.method,
    path: conflict.path,
    body: conflict.body,
    label: conflict.label,
  });
  removeOfflineConflict(id);
}

export function clearOfflineQueue() {
  writeQueue([]);
}

export function clearOfflineConflicts() {
  writeConflicts([]);
}

export function subscribeOfflineQueue(listener: () => void) {
  const handler = () => listener();
  window.addEventListener(OFFLINE_QUEUE_EVENT, handler);
  return () => window.removeEventListener(OFFLINE_QUEUE_EVENT, handler);
}

export function isQueueableMutation(path: string, method: string) {
  const normalizedMethod = method.toUpperCase();
  if (!['POST', 'PUT', 'DELETE'].includes(normalizedMethod)) return false;

  return (
    path.startsWith('/incidentes') ||
    path.startsWith('/alertas/') ||
    path.startsWith('/institutional/inspections') ||
    path.startsWith('/institutional/corrective-actions') ||
    path.startsWith('/institutional/notifications/')
  );
}
