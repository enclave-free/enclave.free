import {
  applyDocumentTitle as applyInstanceTitle,
  applyFavicon as applyInstanceFavicon,
} from '../types/instance';
import { isPxDemo, PX_DEMO_NAME, PX_DEMO_FAVICON } from './pxDemo';

/** Presentation only: the provider continues to cache the unmodified config. */
export function applyDocumentTitle(name: string): void {
  applyInstanceTitle(isPxDemo ? PX_DEMO_NAME : name);
}

export function applyFavicon(url: string): void {
  applyInstanceFavicon(isPxDemo ? PX_DEMO_FAVICON : url);
}
