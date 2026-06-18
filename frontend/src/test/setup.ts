import '@testing-library/jest-dom/vitest';
import '../i18n';

const runtimeFetch = globalThis.fetch;
const runtimeHeaders = globalThis.Headers;
const runtimeRequest = globalThis.Request;
const runtimeResponse = globalThis.Response;
const RuntimeTextEncoder = globalThis.TextEncoder;
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

if (RuntimeTextEncoder) {
  class TestTextEncoder {
    readonly encoding = 'utf-8';

    private readonly encoder = new RuntimeTextEncoder();

    encode(input = ''): Uint8Array {
      return new Uint8Array(this.encoder.encode(input));
    }

    encodeInto(
      input: string,
      destination: Uint8Array
    ): { read: number; written: number } {
      if (typeof this.encoder.encodeInto === 'function') {
        return this.encoder.encodeInto(input, destination);
      }

      const bytes = this.encode(input);
      const writable = bytes.subarray(0, destination.byteLength);
      destination.set(writable);
      return { read: input.length, written: writable.byteLength };
    }
  }

  Object.defineProperty(globalThis, 'TextEncoder', {
    configurable: true,
    writable: true,
    value: TestTextEncoder,
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
