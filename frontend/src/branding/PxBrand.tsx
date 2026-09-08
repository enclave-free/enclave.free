import { Link } from 'react-router-dom';
import { PX_DEMO_NAME } from './pxDemo';

/** LIBERATOR treatment (historical PX module name), using WLC's palette; not the WLC wordmark. */
export function PxBrand({ large = false }: { large?: boolean }) {
  return (
    <Link
      to="/"
      dir="ltr"
      className={`px-brand focus-ring${large ? ' px-brand-large' : ''}`}
    >
      <span className="px-brand-colors" aria-hidden="true">
        <i />
        <i />
        <i />
        <i />
      </span>
      <span>{PX_DEMO_NAME}</span>
    </Link>
  );
}
