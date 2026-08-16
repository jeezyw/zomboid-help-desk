import { useEffect, useRef } from "react";

/** Runs `fn` immediately and then every `intervalMs` while the calling component is
 * mounted and `enabled` is true. Guards against overlapping calls if `fn` is slower
 * than the interval. */
export function usePolling(fn: () => void | Promise<void>, intervalMs: number, enabled = true) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let running = false;

    async function tick() {
      if (running || cancelled) return;
      running = true;
      try {
        await fnRef.current();
      } finally {
        running = false;
      }
    }

    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, enabled]);
}
