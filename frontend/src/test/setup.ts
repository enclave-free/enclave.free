import '@testing-library/jest-dom/vitest';
import '../i18n';

const runtimeFetch = globalThis.fetch;
const runtimeHeaders = globalThis.Headers;
const runtimeRequest = globalThis.Request;
const runtimeResponse = globalThis.Response;
const jsdomWindow = globalThis.window as
  | (Window & typeof globalThis)
  | undefined;

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!globalThis.ResizeObserver) {
  Object.defineProperty(globalThis, 'ResizeObserver', {
    configurable: true,
    writable: true,
    value: TestResizeObserver,
  });
}

if (globalThis.Element && !Element.prototype.scrollTo) {
  Object.defineProperty(Element.prototype, 'scrollTo', {
    configurable: true,
    writable: true,
    value: () => undefined,
  });
}

if (jsdomWindow) {
  if (runtimeFetch && !jsdomWindow.fetch) {
    Object.defineProperty(jsdomWindow, 'fetch', {
      configurable: true,
      writable: true,
      value: runtimeFetch.bind(globalThis),
    });
  }
  if (runtimeHeaders && !jsdomWindow.Headers) {
    Object.defineProperty(jsdomWindow, 'Headers', {
      configurable: true,
      writable: true,
      value: runtimeHeaders,
    });
  }
  if (runtimeRequest && !jsdomWindow.Request) {
    Object.defineProperty(jsdomWindow, 'Request', {
      configurable: true,
      writable: true,
      value: runtimeRequest,
    });
  }
  if (runtimeResponse && !jsdomWindow.Response) {
    Object.defineProperty(jsdomWindow, 'Response', {
      configurable: true,
      writable: true,
      value: runtimeResponse,
    });
  }
  if (!jsdomWindow.ResizeObserver) {
    Object.defineProperty(jsdomWindow, 'ResizeObserver', {
      configurable: true,
      writable: true,
      value: TestResizeObserver,
    });
  }
}
