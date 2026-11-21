import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// Pages are lazy-loaded chunks; give the first import of each time to resolve.
configure({ asyncUtilTimeout: 5000 });

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
