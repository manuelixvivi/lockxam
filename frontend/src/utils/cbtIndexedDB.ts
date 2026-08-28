/**
 * Equigrade v3 — IndexedDB Sole Resilient Exam Store
 * Key schema: [attempt_id, question_id]
 */

export interface CachedAnswer {
  attempt_id: number;
  question_id: number;
  selected_option?: string | null;
  text_answer?: string | null;
  is_flagged?: boolean;
  updated_at: number;
}

const DB_NAME = "equigrade_cbt_resilient_db";
const DB_VERSION = 1;
const STORE_NAME = "answers";

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !window.indexedDB) {
      reject(new Error("IndexedDB is not supported"));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: ["attempt_id", "question_id"] });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export const cbtIndexedDB = {
  saveAnswer: async (answer: CachedAnswer): Promise<void> => {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      store.put(answer);
      return new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (err) {
      console.warn("IndexedDB save error:", err);
    }
  },

  getAnswersByAttempt: async (attemptId: number): Promise<Record<number, CachedAnswer>> => {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, "readonly");
      const store = tx.objectStore(STORE_NAME);
      const request = store.getAll();

      return new Promise((resolve, reject) => {
        request.onsuccess = () => {
          const items: CachedAnswer[] = request.result || [];
          const result: Record<number, CachedAnswer> = {};
          items.forEach((item) => {
            if (item.attempt_id === attemptId) {
              result[item.question_id] = item;
            }
          });
          resolve(result);
        };
        request.onerror = () => reject(request.error);
      });
    } catch (err) {
      console.warn("IndexedDB get error:", err);
      return {};
    }
  },

  clearAttempt: async (attemptId: number): Promise<void> => {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const request = store.openCursor();

      request.onsuccess = (e) => {
        const cursor = (e.target as IDBRequest<IDBCursorWithValue>).result;
        if (cursor) {
          if (cursor.value.attempt_id === attemptId) {
            cursor.delete();
          }
          cursor.continue();
        }
      };
    } catch (err) {
      console.warn("IndexedDB clear error:", err);
    }
  },
};
