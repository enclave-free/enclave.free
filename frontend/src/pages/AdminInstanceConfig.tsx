import { useState, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Paintbrush, Loader2, ArrowLeft } from 'lucide-react';
import { OnboardingCard } from '../components/onboarding/OnboardingCard';
import { ColorPicker } from '../components/onboarding/ColorPicker';
import { IconPicker } from '../components/onboarding/IconPicker';
import { DynamicIcon } from '../components/shared/DynamicIcon';
import {
  Button,
  Callout,
  Card,
  SectionHeader,
  TextField,
} from '../components/ui';
import { adminFetch, isAdminAuthenticated } from '../utils/adminApi';
import { subscribeAdminConfigChanges } from '../utils/adminConfigEvents';
import { useInstanceConfig } from '../context/InstanceConfigContext';
import { AccentColor } from '../types/instance';

function ConfigSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Card padding="md" className="bg-surface-overlay">
      <SectionHeader
        title={title}
        description={description}
        icon={<Paintbrush className="h-4 w-4" aria-hidden="true" />}
        className="mb-4"
      />
      {children}
    </Card>
  );
}

export function AdminInstanceConfig() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { config, updateConfig } = useInstanceConfig();

  const [instanceName, setInstanceName] = useState(config.name);
  const [publicEmailDisplayName, setPublicEmailDisplayName] = useState('');
  const publicEmailDisplayNameTouchedRef = useRef(false);
  const publicEmailDisplayNameLoadedRef = useRef(false);
  const publicEmailDisplayNameRunIdRef = useRef(0);
  // Preview state - only applies on save, not immediately
  const [previewAccentColor, setPreviewAccentColor] = useState<AccentColor>(
    config.accentColor
  );
  const [previewIcon, setPreviewIcon] = useState(config.icon);
  const [previewLogoUrl, setPreviewLogoUrl] = useState(config.logoUrl);
  const [previewFaviconUrl, setPreviewFaviconUrl] = useState(config.faviconUrl);
  const [previewAppleTouchIconUrl, setPreviewAppleTouchIconUrl] = useState(
    config.appleTouchIconUrl
  );
  const [logoPreviewError, setLogoPreviewError] = useState(false);
  const [previewAssistantIcon, setPreviewAssistantIcon] = useState(
    config.assistantIcon
  );
  const [previewUserIcon, setPreviewUserIcon] = useState(config.userIcon);
  const [previewAssistantName, setPreviewAssistantName] = useState(
    config.assistantName
  );
  const [previewUserLabel, setPreviewUserLabel] = useState(config.userLabel);
  const [previewHeaderLayout, setPreviewHeaderLayout] = useState(
    config.headerLayout
  );
  const [previewHeaderTagline, setPreviewHeaderTagline] = useState(
    config.headerTagline
  );
  const [previewChatBubbleStyle, setPreviewChatBubbleStyle] = useState(
    config.chatBubbleStyle
  );
  const [previewChatBubbleShadow, setPreviewChatBubbleShadow] = useState(
    config.chatBubbleShadow
  );
  const [previewSurfaceStyle, setPreviewSurfaceStyle] = useState(
    config.surfaceStyle
  );
  const [previewStatusIconSet, setPreviewStatusIconSet] = useState(
    config.statusIconSet
  );
  const [previewTypographyPreset, setPreviewTypographyPreset] = useState(
    config.typographyPreset
  );
  const [previewDefaultLanguage, setPreviewDefaultLanguage] = useState(
    config.defaultLanguage
  );
  const [previewDefaultTheme, setPreviewDefaultTheme] = useState(
    config.defaultTheme
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [hasExternalConflict, setHasExternalConflict] = useState(false);
  const isDirtyRef = useRef(false);
  const previousConfigRef = useRef(config);

  useEffect(() => {
    isDirtyRef.current = isDirty;
  }, [isDirty]);

  // Check if admin is logged in
  useEffect(() => {
    if (!isAdminAuthenticated()) {
      navigate('/admin');
    }
  }, [navigate]);

  useEffect(() => {
    let cancelled = false;

    async function loadPublicEmailDisplayName() {
      const runId = ++publicEmailDisplayNameRunIdRef.current;
      try {
        const response = await adminFetch('/admin/settings');
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled || runId !== publicEmailDisplayNameRunIdRef.current) {
          return;
        }
        publicEmailDisplayNameLoadedRef.current = true;
        if (!publicEmailDisplayNameTouchedRef.current) {
          setPublicEmailDisplayName(
            data.settings?.public_email_display_name ?? ''
          );
        }
      } catch {
        // Non-blocking: save will not overwrite this server value unless loaded or edited.
      }
    }

    void loadPublicEmailDisplayName();
    const unsubscribe = subscribeAdminConfigChanges(
      ['instance_settings'],
      () => {
        if (isDirtyRef.current) setHasExternalConflict(true);
        void loadPublicEmailDisplayName();
      }
    );

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  // Sync config (only on initial load or external changes, skip if user has made edits)
  useEffect(() => {
    if (previousConfigRef.current !== config && isDirty) {
      setHasExternalConflict(true);
    }
    previousConfigRef.current = config;
    if (!isDirty) {
      setInstanceName(config.name);
      setPreviewAccentColor(config.accentColor);
      setPreviewIcon(config.icon);
      setPreviewLogoUrl(config.logoUrl);
      setPreviewFaviconUrl(config.faviconUrl);
      setPreviewAppleTouchIconUrl(config.appleTouchIconUrl);
      setLogoPreviewError(false);
      setPreviewAssistantIcon(config.assistantIcon);
      setPreviewUserIcon(config.userIcon);
      setPreviewAssistantName(config.assistantName);
      setPreviewUserLabel(config.userLabel);
      setPreviewHeaderLayout(config.headerLayout);
      setPreviewHeaderTagline(config.headerTagline);
      setPreviewChatBubbleStyle(config.chatBubbleStyle);
      setPreviewChatBubbleShadow(config.chatBubbleShadow);
      setPreviewSurfaceStyle(config.surfaceStyle);
      setPreviewStatusIconSet(config.statusIconSet);
      setPreviewTypographyPreset(config.typographyPreset);
      setPreviewDefaultLanguage(config.defaultLanguage);
      setPreviewDefaultTheme(config.defaultTheme);
      setHasExternalConflict(false);
    }
  }, [config, isDirty]);

  // Preview handlers - only update local state, apply on save
  const handleColorChange = (color: AccentColor) => {
    setPreviewAccentColor(color);
    setIsDirty(true);
  };

  const handleIconChange = (newIcon: string) => {
    setPreviewIcon(newIcon);
    setIsDirty(true);
  };

  const handleLogoUrlChange = (value: string) => {
    setPreviewLogoUrl(value);
    setLogoPreviewError(false);
    setIsDirty(true);
  };

  const handleFaviconUrlChange = (value: string) => {
    setPreviewFaviconUrl(value);
    setIsDirty(true);
  };

  const handleAppleTouchIconUrlChange = (value: string) => {
    setPreviewAppleTouchIconUrl(value);
    setIsDirty(true);
  };

  const handleAssistantIconChange = (newIcon: string) => {
    setPreviewAssistantIcon(newIcon);
    setIsDirty(true);
  };

  const handleUserIconChange = (newIcon: string) => {
    setPreviewUserIcon(newIcon);
    setIsDirty(true);
  };

  const handleAssistantNameChange = (value: string) => {
    setPreviewAssistantName(value);
    setIsDirty(true);
  };

  const handleUserLabelChange = (value: string) => {
    setPreviewUserLabel(value);
    setIsDirty(true);
  };

  const handleHeaderLayoutChange = (value: typeof previewHeaderLayout) => {
    setPreviewHeaderLayout(value);
    setIsDirty(true);
  };

  const handleHeaderTaglineChange = (value: string) => {
    setPreviewHeaderTagline(value);
    setIsDirty(true);
  };

  const handleChatBubbleStyleChange = (
    value: typeof previewChatBubbleStyle
  ) => {
    setPreviewChatBubbleStyle(value);
    setIsDirty(true);
  };

  const handleChatBubbleShadowChange = (value: boolean) => {
    setPreviewChatBubbleShadow(value);
    setIsDirty(true);
  };

  const handleSurfaceStyleChange = (value: typeof previewSurfaceStyle) => {
    setPreviewSurfaceStyle(value);
    setIsDirty(true);
  };

  const handleStatusIconSetChange = (value: typeof previewStatusIconSet) => {
    setPreviewStatusIconSet(value);
    setIsDirty(true);
  };

  const handleTypographyPresetChange = (
    value: typeof previewTypographyPreset
  ) => {
    setPreviewTypographyPreset(value);
    setIsDirty(true);
  };

  const handleDefaultLanguageChange = (value: string) => {
    setPreviewDefaultLanguage(value);
    setIsDirty(true);
  };

  const handleDefaultThemeChange = (value: typeof previewDefaultTheme) => {
    setPreviewDefaultTheme(value);
    setIsDirty(true);
  };

  const handleSave = async () => {
    if (hasExternalConflict) {
      setSaveError(
        t(
          'admin.errors.externalConfigConflict',
          'Sage or another admin changed these settings while you were editing. Reload this page before saving so you do not overwrite the newer values.'
        )
      );
      return;
    }
    // Save instance config to local context (for immediate UI updates)
    const name = instanceName.trim() || t('admin.setup.defaultName');

    setIsSaving(true);
    setSaveError(null);

    // Persist to backend API
    try {
      const settingsPayload: Record<string, string> = {
        instance_name: name,
        primary_color: previewAccentColor,
        icon: previewIcon,
        logo_url: previewLogoUrl.trim(),
        favicon_url: previewFaviconUrl.trim(),
        apple_touch_icon_url: previewAppleTouchIconUrl.trim(),
        assistant_icon: previewAssistantIcon,
        user_icon: previewUserIcon,
        assistant_name: previewAssistantName.trim(),
        user_label: previewUserLabel.trim(),
        header_layout: previewHeaderLayout,
        header_tagline: previewHeaderTagline.trim(),
        chat_bubble_style: previewChatBubbleStyle,
        chat_bubble_shadow: String(previewChatBubbleShadow),
        surface_style: previewSurfaceStyle,
        status_icon_set: previewStatusIconSet,
        typography_preset: previewTypographyPreset,
        default_language: previewDefaultLanguage,
        default_theme: previewDefaultTheme,
      };
      if (
        publicEmailDisplayNameLoadedRef.current ||
        publicEmailDisplayNameTouchedRef.current
      ) {
        settingsPayload.public_email_display_name =
          publicEmailDisplayName.trim();
      }

      const response = await adminFetch('/admin/settings', {
        method: 'PUT',
        body: JSON.stringify(settingsPayload),
      });

      if (response.ok) {
        // Only update context after successful save
        updateConfig({
          name,
          accentColor: previewAccentColor,
          icon: previewIcon,
          logoUrl: previewLogoUrl.trim(),
          faviconUrl: previewFaviconUrl.trim(),
          appleTouchIconUrl: previewAppleTouchIconUrl.trim(),
          assistantIcon: previewAssistantIcon,
          userIcon: previewUserIcon,
          assistantName: previewAssistantName.trim() || '',
          userLabel: previewUserLabel.trim() || '',
          headerLayout: previewHeaderLayout,
          headerTagline: previewHeaderTagline.trim(),
          chatBubbleStyle: previewChatBubbleStyle,
          chatBubbleShadow: previewChatBubbleShadow,
          surfaceStyle: previewSurfaceStyle,
          statusIconSet: previewStatusIconSet,
          typographyPreset: previewTypographyPreset,
          defaultLanguage: previewDefaultLanguage,
          defaultTheme: previewDefaultTheme,
        });
        setIsDirty(false);
        navigate('/admin/setup');
      } else {
        console.error('Failed to save settings:', response.status);
        setSaveError(
          t(
            'admin.errors.saveFailed',
            'Failed to save settings. Please try again.'
          )
        );
      }
    } catch (err) {
      console.error('Error saving instance settings:', err);
      setSaveError(
        err instanceof Error
          ? err.message
          : t(
              'admin.errors.saveFailed',
              'Failed to save settings. Please try again.'
            )
      );
    } finally {
      setIsSaving(false);
    }
  };

  const footer = (
    <Link
      to="/admin/setup"
      className="text-text-muted hover:text-text transition-colors"
    >
      {t('common.backToAdminDashboard', 'Back to Admin Dashboard')}
    </Link>
  );

  const optionButtonClass = (active: boolean) =>
    `w-full text-left border rounded-lg px-3 py-2 text-sm transition-all ${
      active
        ? 'border-accent bg-accent/10 text-text'
        : 'border-border bg-surface hover:border-accent/40 text-text-muted hover:text-text'
    }`;

  const headerLayoutOptions = [
    {
      value: 'icon_name',
      title: t('admin.instanceConfig.headerLayoutIconName', 'Icon + Name'),
      description: t(
        'admin.instanceConfig.headerLayoutIconNameDesc',
        'Show both the icon and instance name.'
      ),
    },
    {
      value: 'icon_only',
      title: t('admin.instanceConfig.headerLayoutIconOnly', 'Icon Only'),
      description: t(
        'admin.instanceConfig.headerLayoutIconOnlyDesc',
        'Minimal header with just the icon.'
      ),
    },
    {
      value: 'name_only',
      title: t('admin.instanceConfig.headerLayoutNameOnly', 'Name Only'),
      description: t(
        'admin.instanceConfig.headerLayoutNameOnlyDesc',
        'Text-only header with the instance name.'
      ),
    },
  ];

  const bubbleStyleOptions = [
    {
      value: 'soft',
      title: t('admin.instanceConfig.bubbleStyleSoft', 'Soft'),
      description: t(
        'admin.instanceConfig.bubbleStyleSoftDesc',
        'Rounded corners with a subtle chat feel.'
      ),
    },
    {
      value: 'round',
      title: t('admin.instanceConfig.bubbleStyleRound', 'Round'),
      description: t(
        'admin.instanceConfig.bubbleStyleRoundDesc',
        'Extra-round bubbles with a friendly shape.'
      ),
    },
    {
      value: 'square',
      title: t('admin.instanceConfig.bubbleStyleSquare', 'Square'),
      description: t(
        'admin.instanceConfig.bubbleStyleSquareDesc',
        'Sharper corners for a structured look.'
      ),
    },
    {
      value: 'pill',
      title: t('admin.instanceConfig.bubbleStylePill', 'Pill'),
      description: t(
        'admin.instanceConfig.bubbleStylePillDesc',
        'Full pill style for a bold look.'
      ),
    },
  ];

  const surfaceStyleOptions = [
    {
      value: 'plain',
      title: t('admin.instanceConfig.surfacePlain', 'Plain'),
      description: t(
        'admin.instanceConfig.surfacePlainDesc',
        'Clean and minimal background.'
      ),
    },
    {
      value: 'gradient',
      title: t('admin.instanceConfig.surfaceGradient', 'Soft Gradient'),
      description: t(
        'admin.instanceConfig.surfaceGradientDesc',
        'Subtle gradient glow in the background.'
      ),
    },
    {
      value: 'noise',
      title: t('admin.instanceConfig.surfaceNoise', 'Paper Grain'),
      description: t(
        'admin.instanceConfig.surfaceNoiseDesc',
        'Gentle texture for warmth.'
      ),
    },
    {
      value: 'grid',
      title: t('admin.instanceConfig.surfaceGrid', 'Grid'),
      description: t(
        'admin.instanceConfig.surfaceGridDesc',
        'Faint grid for a technical vibe.'
      ),
    },
  ];

  const statusIconOptions = [
    {
      value: 'classic',
      title: t('admin.instanceConfig.statusIconsClassic', 'Classic'),
      description: t(
        'admin.instanceConfig.statusIconsClassicDesc',
        'Simple dots and symbols (○ ◐ ●).'
      ),
    },
    {
      value: 'minimal',
      title: t('admin.instanceConfig.statusIconsMinimal', 'Minimal'),
      description: t(
        'admin.instanceConfig.statusIconsMinimalDesc',
        'Tiny glyphs and arrows.'
      ),
    },
    {
      value: 'playful',
      title: t('admin.instanceConfig.statusIconsPlayful', 'Playful'),
      description: t(
        'admin.instanceConfig.statusIconsPlayfulDesc',
        'Emoji-style icons for friendly feedback.'
      ),
    },
  ];

  const typographyOptions = [
    {
      value: 'modern',
      title: t('admin.instanceConfig.typographyModern', 'Modern'),
      description: t(
        'admin.instanceConfig.typographyModernDesc',
        'Clean and familiar sans-serif.'
      ),
    },
    {
      value: 'grotesk',
      title: t('admin.instanceConfig.typographyGrotesk', 'Grotesk'),
      description: t(
        'admin.instanceConfig.typographyGroteskDesc',
        'Bold, contemporary type with personality.'
      ),
    },
    {
      value: 'humanist',
      title: t('admin.instanceConfig.typographyHumanist', 'Humanist'),
      description: t(
        'admin.instanceConfig.typographyHumanistDesc',
        'Warm, readable typography with clarity.'
      ),
    },
  ];

  const languageOptions = [
    { value: 'en', label: t('language.english', 'English') },
    { value: 'es', label: t('language.spanish', 'Spanish') },
    { value: 'fr', label: t('language.french', 'French') },
    { value: 'de', label: t('language.german', 'German') },
    { value: 'pt', label: t('language.portuguese', 'Portuguese') },
  ];

  const themeOptions = [
    { value: 'system', label: t('admin.instanceConfig.themeSystem', 'System') },
    { value: 'light', label: t('admin.instanceConfig.themeLight', 'Light') },
    { value: 'dark', label: t('admin.instanceConfig.themeDark', 'Dark') },
  ] as const;

  return (
    <OnboardingCard
      size="xl"
      title={t('admin.instanceConfig.title', 'Instance Configuration')}
      subtitle={t(
        'admin.instanceConfig.subtitle',
        'Set the name, icon, and colors shown across your instance.'
      )}
      footer={footer}
    >
      <div className="space-y-6 stagger-children">
        {/* Instance Branding Section */}
        <ConfigSection title={t('admin.setup.branding')}>
          <div className="space-y-4">
            {/* Instance Name */}
            <TextField
              id="instance-name"
              label={t('admin.setup.displayName')}
              value={instanceName}
              onChange={(e) => {
                setInstanceName(e.target.value);
                setIsDirty(true);
              }}
              placeholder={t('admin.setup.defaultName')}
              description={t('admin.setup.displayNameHint')}
            />

            <TextField
              id="public-email-display-name"
              label={t(
                'admin.instanceConfig.publicEmailDisplayNameLabel',
                'Public email display name (optional)'
              )}
              value={publicEmailDisplayName}
              onChange={(e) => {
                publicEmailDisplayNameTouchedRef.current = true;
                setPublicEmailDisplayName(e.target.value);
                setIsDirty(true);
              }}
              placeholder={instanceName.trim() || t('admin.setup.defaultName')}
              description={t(
                'admin.instanceConfig.publicEmailDisplayNameHint',
                'Used in magic-link sign-in emails. Leave blank to use the Instance name.'
              )}
            />

            {/* Icon */}
            <div>
              <span
                id="instance-icon-label"
                className="text-sm font-medium text-text mb-2 block"
              >
                {t('admin.setup.icon')}
              </span>
              <IconPicker
                value={previewIcon}
                onChange={handleIconChange}
                aria-labelledby="instance-icon-label"
              />
            </div>

            {/* Logo URL */}
            <div>
              <TextField
                id="logo-url"
                type="url"
                label={t('admin.instanceConfig.logoUrlLabel', 'Logo URL')}
                value={previewLogoUrl}
                onChange={(e) => handleLogoUrlChange(e.target.value)}
                placeholder={t(
                  'admin.instanceConfig.logoUrlPlaceholder',
                  'https://example.com/logo.png'
                )}
                description={t(
                  'admin.instanceConfig.logoUrlHint',
                  'Square image recommended (128x128 or 256x256).'
                )}
              />
              <div className="mt-3 flex items-center gap-3">
                <div className="w-12 h-12 rounded-lg border border-border bg-surface flex items-center justify-center overflow-hidden">
                  {previewLogoUrl.trim() && !logoPreviewError ? (
                    <img
                      src={previewLogoUrl.trim()}
                      alt={t(
                        'admin.instanceConfig.logoPreviewAlt',
                        'Logo preview'
                      )}
                      className="w-8 h-8 object-contain"
                      onError={() => setLogoPreviewError(true)}
                    />
                  ) : (
                    <DynamicIcon
                      name={previewIcon}
                      size={20}
                      className="text-text-muted"
                    />
                  )}
                </div>
                <span className="text-xs text-text-muted">
                  {t(
                    'admin.instanceConfig.logoPreviewHint',
                    'Preview (falls back to the selected icon).'
                  )}
                </span>
              </div>
            </div>

            {/* Favicon URL */}
            <TextField
              id="favicon-url"
              type="url"
              label={t('admin.instanceConfig.faviconLabel', 'Favicon URL')}
              value={previewFaviconUrl}
              onChange={(e) => handleFaviconUrlChange(e.target.value)}
              placeholder={t(
                'admin.instanceConfig.faviconPlaceholder',
                'https://example.com/favicon.png'
              )}
              description={t(
                'admin.instanceConfig.faviconHint',
                'Shown in the browser tab and bookmarks (recommended 32x32 or 64x64).'
              )}
            />

            {/* Apple Touch Icon URL */}
            <TextField
              id="apple-touch-icon-url"
              type="url"
              label={t(
                'admin.instanceConfig.appleTouchIconLabel',
                'Apple touch icon URL'
              )}
              value={previewAppleTouchIconUrl}
              onChange={(e) => handleAppleTouchIconUrlChange(e.target.value)}
              placeholder={t(
                'admin.instanceConfig.appleTouchIconPlaceholder',
                'https://example.com/apple-touch-icon.png'
              )}
              description={t(
                'admin.instanceConfig.appleTouchIconHint',
                'Used when adding to the iOS home screen (recommended 180x180).'
              )}
            />

            {/* Accent Color */}
            <div>
              <span
                id="accent-color-label"
                className="text-sm font-medium text-text mb-2 block"
              >
                {t('admin.setup.accentColor')}
              </span>
              <ColorPicker
                value={previewAccentColor}
                onChange={handleColorChange}
                aria-labelledby="accent-color-label"
              />
            </div>
          </div>
        </ConfigSection>

        {/* Chat Icons Section */}
        <ConfigSection
          title={t('admin.instanceConfig.chatIconsTitle', 'Chat Icons')}
          description={t(
            'admin.instanceConfig.chatIconsDesc',
            'Set the default icons used in chat messages.'
          )}
        >
          <div className="space-y-4">
            <div>
              <span
                id="assistant-icon-label"
                className="text-sm font-medium text-text mb-2 block"
              >
                {t(
                  'admin.instanceConfig.assistantIconLabel',
                  'AI assistant icon'
                )}
              </span>
              <IconPicker
                value={previewAssistantIcon}
                onChange={handleAssistantIconChange}
                aria-labelledby="assistant-icon-label"
              />
            </div>

            <div>
              <span
                id="user-icon-label"
                className="text-sm font-medium text-text mb-2 block"
              >
                {t('admin.instanceConfig.userIconLabel', 'User icon')}
              </span>
              <IconPicker
                value={previewUserIcon}
                onChange={handleUserIconChange}
                aria-labelledby="user-icon-label"
              />
            </div>
          </div>
        </ConfigSection>

        {/* Header Branding Section */}
        <ConfigSection
          title={t('admin.instanceConfig.headerTitle', 'Header Branding')}
          description={t(
            'admin.instanceConfig.headerDesc',
            'Control how your instance appears in the top header.'
          )}
        >
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-text mb-2 block">
                {t('admin.instanceConfig.headerLayoutLabel', 'Header layout')}
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {headerLayoutOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() =>
                      handleHeaderLayoutChange(
                        option.value as typeof previewHeaderLayout
                      )
                    }
                    className={optionButtonClass(
                      previewHeaderLayout === option.value
                    )}
                    aria-pressed={previewHeaderLayout === option.value}
                  >
                    <p className="text-sm font-medium text-text">
                      {option.title}
                    </p>
                    <p className="text-xs text-text-muted mt-1">
                      {option.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <TextField
              label={t(
                'admin.instanceConfig.headerTaglineLabel',
                'Tagline (optional)'
              )}
              value={previewHeaderTagline}
              onChange={(e) => handleHeaderTaglineChange(e.target.value)}
              placeholder={t(
                'admin.instanceConfig.headerTaglinePlaceholder',
                'Short descriptor shown under the name'
              )}
              description={t(
                'admin.instanceConfig.headerTaglineHint',
                'Leave blank to hide the tagline.'
              )}
            />
          </div>
        </ConfigSection>

        {/* Chat Identity Section */}
        <ConfigSection
          title={t('admin.instanceConfig.chatIdentityTitle', 'Chat Identity')}
          description={t(
            'admin.instanceConfig.chatIdentityDesc',
            'Set the labels shown above chat messages.'
          )}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <TextField
              label={t(
                'admin.instanceConfig.assistantNameLabel',
                'Assistant display name'
              )}
              value={previewAssistantName}
              onChange={(e) => handleAssistantNameChange(e.target.value)}
              placeholder={t(
                'admin.instanceConfig.assistantNamePlaceholder',
                'e.g., Enclave AI'
              )}
            />
            <TextField
              label={t('admin.instanceConfig.userLabelLabel', 'User label')}
              value={previewUserLabel}
              onChange={(e) => handleUserLabelChange(e.target.value)}
              placeholder={t(
                'admin.instanceConfig.userLabelPlaceholder',
                'e.g., You'
              )}
            />
          </div>
          <p className="text-xs text-text-muted mt-2">
            {t(
              'admin.instanceConfig.chatIdentityHint',
              'Leave a label empty to hide it.'
            )}
          </p>
        </ConfigSection>

        {/* Chat Bubble Style Section */}
        <ConfigSection
          title={t(
            'admin.instanceConfig.bubbleStyleTitle',
            'Chat Bubble Style'
          )}
          description={t(
            'admin.instanceConfig.bubbleStyleDesc',
            'Choose the shape and depth of chat bubbles.'
          )}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
            {bubbleStyleOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() =>
                  handleChatBubbleStyleChange(
                    option.value as typeof previewChatBubbleStyle
                  )
                }
                className={optionButtonClass(
                  previewChatBubbleStyle === option.value
                )}
                aria-pressed={previewChatBubbleStyle === option.value}
              >
                <p className="text-sm font-medium text-text">{option.title}</p>
                <p className="text-xs text-text-muted mt-1">
                  {option.description}
                </p>
              </button>
            ))}
          </div>

          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={previewChatBubbleShadow}
              onChange={(e) => handleChatBubbleShadowChange(e.target.checked)}
              className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
            />
            {t(
              'admin.instanceConfig.bubbleShadowLabel',
              'Add subtle bubble shadow'
            )}
          </label>
        </ConfigSection>

        {/* Surface Style Section */}
        <ConfigSection
          title={t('admin.instanceConfig.surfaceTitle', 'Background Style')}
          description={t(
            'admin.instanceConfig.surfaceDesc',
            'Pick the background texture for your instance.'
          )}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {surfaceStyleOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() =>
                  handleSurfaceStyleChange(
                    option.value as typeof previewSurfaceStyle
                  )
                }
                className={optionButtonClass(
                  previewSurfaceStyle === option.value
                )}
                aria-pressed={previewSurfaceStyle === option.value}
              >
                <p className="text-sm font-medium text-text">{option.title}</p>
                <p className="text-xs text-text-muted mt-1">
                  {option.description}
                </p>
              </button>
            ))}
          </div>
        </ConfigSection>

        {/* Status Icons Section */}
        <ConfigSection
          title={t('admin.instanceConfig.statusIconsTitle', 'Status Icons')}
          description={t(
            'admin.instanceConfig.statusIconsDesc',
            'Choose how status updates are displayed.'
          )}
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {statusIconOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() =>
                  handleStatusIconSetChange(
                    option.value as typeof previewStatusIconSet
                  )
                }
                className={optionButtonClass(
                  previewStatusIconSet === option.value
                )}
                aria-pressed={previewStatusIconSet === option.value}
              >
                <p className="text-sm font-medium text-text">{option.title}</p>
                <p className="text-xs text-text-muted mt-1">
                  {option.description}
                </p>
              </button>
            ))}
          </div>
        </ConfigSection>

        {/* Typography Section */}
        <ConfigSection
          title={t('admin.instanceConfig.typographyTitle', 'Typography')}
          description={t(
            'admin.instanceConfig.typographyDesc',
            'Pick a font pairing for the entire interface.'
          )}
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {typographyOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() =>
                  handleTypographyPresetChange(
                    option.value as typeof previewTypographyPreset
                  )
                }
                className={optionButtonClass(
                  previewTypographyPreset === option.value
                )}
                aria-pressed={previewTypographyPreset === option.value}
              >
                <p className="text-sm font-medium text-text">{option.title}</p>
                <p className="text-xs text-text-muted mt-1">
                  {option.description}
                </p>
              </button>
            ))}
          </div>
        </ConfigSection>

        <ConfigSection
          title={t('admin.instanceConfig.defaultsTitle', 'Instance Defaults')}
          description={t(
            'admin.instanceConfig.defaultsDesc',
            'Set the baseline language and theme used before any local browser controls apply.'
          )}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="flex flex-col gap-2 text-sm font-medium text-text">
              {t(
                'admin.instanceConfig.defaultLanguageLabel',
                'Default language'
              )}
              <select
                value={previewDefaultLanguage}
                onChange={(event) =>
                  handleDefaultLanguageChange(event.target.value)
                }
                className="input-field rounded-lg border border-border bg-surface px-3 py-2 text-sm"
              >
                {languageOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm font-medium text-text">
              {t('admin.instanceConfig.defaultThemeLabel', 'Default theme')}
              <select
                value={previewDefaultTheme}
                onChange={(event) =>
                  handleDefaultThemeChange(
                    event.target.value as typeof previewDefaultTheme
                  )
                }
                className="input-field rounded-lg border border-border bg-surface px-3 py-2 text-sm"
              >
                {themeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </ConfigSection>

        {/* Save Error display */}
        {saveError && (
          <Callout label={t('common.error', 'Error')} tone="error">
            <p className="text-sm text-error">{saveError}</p>
          </Callout>
        )}
        {hasExternalConflict && !saveError && (
          <Callout label={t('common.warning', 'Warning')} tone="warning">
            <p className="text-sm">
              {t(
                'admin.errors.externalConfigConflict',
                'Sage or another admin changed these settings while you were editing. Reload this page before saving so you do not overwrite the newer values.'
              )}
            </p>
          </Callout>
        )}

        {/* Navigation */}
        <div className="flex gap-3">
          <Link
            to="/admin/setup"
            className="flex-1 flex items-center justify-center gap-2 border border-border hover:border-accent/50 text-text rounded-xl px-4 py-3 text-sm font-medium transition-all hover:bg-surface"
          >
            <ArrowLeft className="w-4 h-4" />
            {t('common.backToAdminDashboard', 'Back to Admin Dashboard')}
          </Link>
          <Button
            onClick={handleSave}
            disabled={isSaving || hasExternalConflict}
            className="flex-1 disabled:opacity-50"
            leadingIcon={
              isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : undefined
            }
          >
            {isSaving ? t('common.saving', 'Saving...') : t('admin.setup.save')}
          </Button>
        </div>
      </div>
    </OnboardingCard>
  );
}
