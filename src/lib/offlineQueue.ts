export type OfflineMutation = {
  id: string;
  method: 'POST' | 'PUT' | 'DELETE';
  path: string;
  body?: string;
  label: string;
  createdAt: string;
};

const OFFLINE_QUEUE_KEY = 'aspredictive_offline_queue';
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

function writeQueue(queue: OfflineMutation[]) {
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
  emitQueueEvent();
}

export function getOfflineQueue() {
  return readQueue();
}

export function getOfflineQueueSize() {
  return readQueue().length;
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

export function clearOfflineQueue() {
  writeQueue([]);
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
