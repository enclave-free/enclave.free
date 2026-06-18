import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from './theme';
import { InstanceConfigProvider } from './context/InstanceConfigContext';
import App from './App';
import './i18n'; // Initialize i18n before rendering
import './index.css';
import { installSecureFetch } from './utils/secureFetch';

installSecureFetch();

if (import.meta.env.DEV) {
  void import('./utils/devNostrExtension').then(
    ({ installDevelopmentNostrExtensionForSmokeTests }) => {
      installDevelopmentNostrExtensionForSmokeTests();
    }
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <InstanceConfigProvider>
        <App />
      </InstanceConfigProvider>
    </ThemeProvider>
  </StrictMode>
);
