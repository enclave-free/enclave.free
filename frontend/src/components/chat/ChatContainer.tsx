import { ReactNode, useState } from 'react';

interface ChatContainerProps {
  children: ReactNode;
  header?: ReactNode;
  sidebar?: ReactNode;
}

export function ChatContainer({
  children,
  header,
  sidebar,
}: ChatContainerProps) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="h-screen flex flex-col bg-surface">
      {header && (
        <header className="border-b border-border bg-surface-raised shrink-0">
          {header}
        </header>
      )}
      <div className="flex-1 flex overflow-hidden">
        {sidebar && (
          <>
            <aside className="w-64 border-r border-border bg-surface-raised shrink-0 hidden md:block overflow-y-auto">
              {sidebar}
            </aside>
            <div className="md:hidden fixed left-3 bottom-24 z-40">
              <button
                type="button"
                aria-label="Open chat sessions"
                onClick={() => setMobileSidebarOpen(true)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface-raised text-text shadow-lg"
              >
                <span aria-hidden="true" className="flex flex-col gap-1">
                  <span className="block h-0.5 w-4 rounded bg-current" />
                  <span className="block h-0.5 w-4 rounded bg-current" />
                  <span className="block h-0.5 w-4 rounded bg-current" />
                </span>
              </button>
            </div>
            {mobileSidebarOpen && (
              <div className="fixed inset-0 z-50 md:hidden">
                <button
                  type="button"
                  aria-label="Close chat sessions"
                  className="absolute inset-0 bg-black/30"
                  onClick={() => setMobileSidebarOpen(false)}
                />
                <aside
                  className="relative h-full w-72 max-w-[85vw] overflow-y-auto border-r border-border bg-surface-raised shadow-2xl"
                  onClickCapture={(event) => {
                    if (
                      event.target instanceof Element &&
                      event.target.closest('[data-dismiss-sidebar="true"]')
                    ) {
                      setMobileSidebarOpen(false);
                    }
                  }}
                >
                  {sidebar}
                </aside>
              </div>
            )}
          </>
        )}
        <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
