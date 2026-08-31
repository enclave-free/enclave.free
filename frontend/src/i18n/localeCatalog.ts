import ar from './locales/ar.json';
import bn from './locales/bn.json';
import cs from './locales/cs.json';
import da from './locales/da.json';
import de from './locales/de.json';
import el from './locales/el.json';
import en from './locales/en.json';
import es from './locales/es.json';
import fa from './locales/fa.json';
import fi from './locales/fi.json';
import fr from './locales/fr.json';
import he from './locales/he.json';
import hi from './locales/hi.json';
import hu from './locales/hu.json';
import id from './locales/id.json';
import it from './locales/it.json';
import ja from './locales/ja.json';
import ko from './locales/ko.json';
import nl from './locales/nl.json';
import no from './locales/no.json';
import pl from './locales/pl.json';
import pt from './locales/pt.json';
import ro from './locales/ro.json';
import ru from './locales/ru.json';
import sv from './locales/sv.json';
import th from './locales/th.json';
import tr from './locales/tr.json';
import uk from './locales/uk.json';
import vi from './locales/vi.json';
import zhHans from './locales/zh-Hans.json';
import zhHant from './locales/zh-Hant.json';

export type LocaleMessages = Record<string, unknown>;

interface LocaleCatalogDefinition {
  code: string;
  nativeName: string;
  englishName: string;
  flag: string;
  translation: LocaleMessages;
  advertised: boolean;
}

// Order is intentional and drives every language selector. It is a
// product/mission decision, not alphabetical; see issue #496.
export const localeCatalog = [
  // Priority set — highest likely need for at-risk users.
  {
    code: 'es',
    nativeName: 'Español',
    englishName: 'Spanish',
    flag: '🇪🇸',
    translation: es,
    advertised: true,
  },
  {
    code: 'en',
    nativeName: 'English',
    englishName: 'English',
    flag: '🇺🇸',
    translation: en,
    advertised: true,
  },
  {
    code: 'fr',
    nativeName: 'Français',
    englishName: 'French',
    flag: '🇫🇷',
    translation: fr,
    advertised: true,
  },
  {
    code: 'ru',
    nativeName: 'Русский',
    englishName: 'Russian',
    flag: '🇷🇺',
    translation: ru,
    advertised: true,
  },
  {
    code: 'ar',
    nativeName: 'العربية',
    englishName: 'Arabic',
    flag: '🇸🇦',
    translation: ar,
    advertised: true,
  },
  {
    code: 'zh-Hans',
    nativeName: '简体中文',
    englishName: 'Chinese (Simplified)',
    flag: '🇨🇳',
    translation: zhHans,
    advertised: true,
  },

  // High-need — large populations facing serious human-rights / authoritarian pressure.
  {
    code: 'fa',
    nativeName: 'فارسی',
    englishName: 'Persian',
    flag: '🇮🇷',
    translation: fa,
    advertised: true,
  },
  {
    code: 'zh-Hant',
    nativeName: '繁體中文',
    englishName: 'Chinese (Traditional)',
    flag: '🇹🇼',
    translation: zhHant,
    advertised: true,
  },
  {
    code: 'uk',
    nativeName: 'Українська',
    englishName: 'Ukrainian',
    flag: '🇺🇦',
    translation: uk,
    advertised: true,
  },
  {
    code: 'tr',
    nativeName: 'Türkçe',
    englishName: 'Turkish',
    flag: '🇹🇷',
    translation: tr,
    advertised: true,
  },
  {
    code: 'hi',
    nativeName: 'हिन्दी',
    englishName: 'Hindi',
    flag: '🇮🇳',
    translation: hi,
    advertised: true,
  },
  {
    code: 'bn',
    nativeName: 'বাংলা',
    englishName: 'Bengali',
    flag: '🇧🇩',
    translation: bn,
    advertised: true,
  },
  {
    code: 'id',
    nativeName: 'Bahasa Indonesia',
    englishName: 'Indonesian',
    flag: '🇮🇩',
    translation: id,
    advertised: true,
  },
  {
    code: 'vi',
    nativeName: 'Tiếng Việt',
    englishName: 'Vietnamese',
    flag: '🇻🇳',
    translation: vi,
    advertised: true,
  },
  {
    code: 'th',
    nativeName: 'ไทย',
    englishName: 'Thai',
    flag: '🇹🇭',
    translation: th,
    advertised: true,
  },
  {
    code: 'he',
    nativeName: 'עברית',
    englishName: 'Hebrew',
    flag: '🇮🇱',
    translation: he,
    advertised: true,
  },
  {
    code: 'ko',
    nativeName: '한국어',
    englishName: 'Korean',
    flag: '🇰🇷',
    translation: ko,
    advertised: true,
  },
  {
    code: 'pt',
    nativeName: 'Português',
    englishName: 'Portuguese',
    flag: '🇧🇷',
    translation: pt,
    advertised: true,
  },
  {
    code: 'ja',
    nativeName: '日本語',
    englishName: 'Japanese',
    flag: '🇯🇵',
    translation: ja,
    advertised: true,
  },

  // Lower-priority — spoken predominantly in stable, low-risk regions.
  {
    code: 'pl',
    nativeName: 'Polski',
    englishName: 'Polish',
    flag: '🇵🇱',
    translation: pl,
    advertised: true,
  },
  {
    code: 'de',
    nativeName: 'Deutsch',
    englishName: 'German',
    flag: '🇩🇪',
    translation: de,
    advertised: true,
  },
  {
    code: 'it',
    nativeName: 'Italiano',
    englishName: 'Italian',
    flag: '🇮🇹',
    translation: it,
    advertised: true,
  },
  {
    code: 'nl',
    nativeName: 'Nederlands',
    englishName: 'Dutch',
    flag: '🇳🇱',
    translation: nl,
    advertised: true,
  },
  {
    code: 'cs',
    nativeName: 'Čeština',
    englishName: 'Czech',
    flag: '🇨🇿',
    translation: cs,
    advertised: true,
  },
  {
    code: 'ro',
    nativeName: 'Română',
    englishName: 'Romanian',
    flag: '🇷🇴',
    translation: ro,
    advertised: true,
  },
  {
    code: 'hu',
    nativeName: 'Magyar',
    englishName: 'Hungarian',
    flag: '🇭🇺',
    translation: hu,
    advertised: true,
  },
  {
    code: 'el',
    nativeName: 'Ελληνικά',
    englishName: 'Greek',
    flag: '🇬🇷',
    translation: el,
    advertised: true,
  },
  {
    code: 'sv',
    nativeName: 'Svenska',
    englishName: 'Swedish',
    flag: '🇸🇪',
    translation: sv,
    advertised: true,
  },
  {
    code: 'no',
    nativeName: 'Norsk',
    englishName: 'Norwegian',
    flag: '🇳🇴',
    translation: no,
    advertised: true,
  },
  {
    code: 'da',
    nativeName: 'Dansk',
    englishName: 'Danish',
    flag: '🇩🇰',
    translation: da,
    advertised: true,
  },
  {
    code: 'fi',
    nativeName: 'Suomi',
    englishName: 'Finnish',
    flag: '🇫🇮',
    translation: fi,
    advertised: true,
  },
] as const satisfies readonly LocaleCatalogDefinition[];

type LocaleCatalogEntry = (typeof localeCatalog)[number];
export type AdvertisedLocale = Extract<
  LocaleCatalogEntry,
  { advertised: true }
>;

export const advertisedLocales = localeCatalog.filter(
  (locale): locale is AdvertisedLocale => locale.advertised
);
export type AdvertisedLocaleCode = AdvertisedLocale['code'];

export const advertisedLocaleCodes = advertisedLocales.map(
  ({ code }) => code
) as AdvertisedLocaleCode[];

const resourcesByLocale: Partial<
  Record<AdvertisedLocaleCode, { translation: LocaleMessages }>
> = {};
for (const { code, translation } of advertisedLocales) {
  resourcesByLocale[code] = { translation };
}

export const localeResources = resourcesByLocale as Record<
  AdvertisedLocaleCode,
  { translation: LocaleMessages }
>;
