import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const demo = vi.hoisted(() => ({ enabled: true }));
vi.mock('../../branding/pxDemo', () => ({
  get isPxDemo() {
    return demo.enabled;
  },
}));
vi.mock('../../branding/PxWelcome', () => ({
  PxWelcome: ({ children }: { children: React.ReactNode }) => (
    <section data-testid="welcome">{children}</section>
  ),
}));
vi.mock('../../branding/PxBrand', () => ({
  PxBrand: () => <div data-testid="compact-brand" />,
}));
vi.mock('../shared/InstanceLogo', () => ({
  InstanceLogo: () => <div data-testid="instance-logo" />,
}));
import { OnboardingCard } from './OnboardingCard';

afterEach(() => {
  cleanup();
  demo.enabled = true;
});
describe('entry presentation boundary', () => {
  it('keeps ordinary task cards out of the welcome layout and honors their size', () => {
    const { container } = render(
      <OnboardingCard size="xl" title="Configuration">
        Content
      </OnboardingCard>
    );
    expect(screen.queryByTestId('welcome')).toBeNull();
    expect(screen.getByTestId('compact-brand')).toBeInTheDocument();
    expect(container.querySelector('.px-onboarding')).toBeNull();
    expect(container.querySelector('.max-w-5xl')).toBeInTheDocument();
  });
  it('uses the welcome presentation only when explicitly requested', () => {
    const { container } = render(
      <OnboardingCard presentation="entry">Content</OnboardingCard>
    );
    expect(screen.getByTestId('welcome')).toBeInTheDocument();
    expect(screen.queryByTestId('compact-brand')).toBeNull();
    expect(container.querySelector('.px-onboarding')).toBeInTheDocument();
  });
  it('preserves the generic presentation when demo branding is disabled', () => {
    demo.enabled = false;
    const { container } = render(
      <OnboardingCard presentation="entry">Content</OnboardingCard>
    );
    expect(screen.queryByTestId('welcome')).toBeNull();
    expect(screen.getByTestId('instance-logo')).toBeInTheDocument();
    expect(container.querySelector('.px-onboarding')).toBeNull();
  });
});
