import type { ReactNode } from 'react';
import { useInstanceConfig } from '../context/InstanceConfigContext';
import { PxBrand } from './PxBrand';

export function PxWelcome({ children }: { children: ReactNode }) {
  const { config } = useInstanceConfig();
  return (
    <div className="px-welcome">
      <aside className="px-welcome-intro">
        <PxBrand large />
        {config.headerTagline?.trim() && (
          <p className="px-welcome-tagline" dir="auto">
            {config.headerTagline}
          </p>
        )}
        <div className="px-welcome-art" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
      </aside>
      <div className="px-welcome-content">{children}</div>
    </div>
  );
}
