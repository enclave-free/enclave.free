import '@testing-library/jest-dom/vitest'
import '../i18n'

const runtimeFetch = globalThis.fetch
const runtimeHeaders = globalThis.Headers
const runtimeRequest = globalThis.Request
const runtimeResponse = globalThis.Response
const jsdomWindow = globalThis.window as (Window & typeof globalThis) | undefined

if (jsdomWindow) {
  if (runtimeFetch && !jsdomWindow.fetch) {
    Object.defineProperty(jsdomWindow, 'fetch', {
      configurable: true,
      value: runtimeFetch.bind(globalThis),
    })
  }
  if (runtimeHeaders && !jsdomWindow.Headers) {
    Object.defineProperty(jsdomWindow, 'Headers', {
      configurable: true,
      value: runtimeHeaders,
    })
  }
  if (runtimeRequest && !jsdomWindow.Request) {
    Object.defineProperty(jsdomWindow, 'Request', {
      configurable: true,
      value: runtimeRequest,
    })
  }
  if (runtimeResponse && !jsdomWindow.Response) {
    Object.defineProperty(jsdomWindow, 'Response', {
      configurable: true,
      value: runtimeResponse,
    })
  }
}
