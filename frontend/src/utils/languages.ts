export interface Language {
  code: string
  nativeName: string
  englishName: string
  flag: string
}

export const LANGUAGES: Language[] = [
  { code: 'en', nativeName: 'English', englishName: 'English', flag: '🇺🇸' },
  { code: 'es', nativeName: 'Español', englishName: 'Spanish', flag: '🇪🇸' },
  { code: 'pt', nativeName: 'Português', englishName: 'Portuguese', flag: '🇧🇷' },
  { code: 'fr', nativeName: 'Français', englishName: 'French', flag: '🇫🇷' },
  { code: 'de', nativeName: 'Deutsch', englishName: 'German', flag: '🇩🇪' },
  { code: 'it', nativeName: 'Italiano', englishName: 'Italian', flag: '🇮🇹' },
  { code: 'nl', nativeName: 'Nederlands', englishName: 'Dutch', flag: '🇳🇱' },
  { code: 'ru', nativeName: 'Русский', englishName: 'Russian', flag: '🇷🇺' },
  { code: 'zh-Hans', nativeName: '简体中文', englishName: 'Chinese (Simplified)', flag: '🇨🇳' },
  { code: 'zh-Hant', nativeName: '繁體中文', englishName: 'Chinese (Traditional)', flag: '🇹🇼' },
  { code: 'ja', nativeName: '日本語', englishName: 'Japanese', flag: '🇯🇵' },
  { code: 'ko', nativeName: '한국어', englishName: 'Korean', flag: '🇰🇷' },
  { code: 'ar', nativeName: 'العربية', englishName: 'Arabic', flag: '🇸🇦' },
  { code: 'fa', nativeName: 'فارسی', englishName: 'Persian', flag: '🇮🇷' },
  { code: 'hi', nativeName: 'हिन्दी', englishName: 'Hindi', flag: '🇮🇳' },
  { code: 'bn', nativeName: 'বাংলা', englishName: 'Bengali', flag: '🇧🇩' },
  { code: 'id', nativeName: 'Bahasa Indonesia', englishName: 'Indonesian', flag: '🇮🇩' },
  { code: 'th', nativeName: 'ไทย', englishName: 'Thai', flag: '🇹🇭' },
  { code: 'vi', nativeName: 'Tiếng Việt', englishName: 'Vietnamese', flag: '🇻🇳' },
  { code: 'tr', nativeName: 'Türkçe', englishName: 'Turkish', flag: '🇹🇷' },
  { code: 'pl', nativeName: 'Polski', englishName: 'Polish', flag: '🇵🇱' },
  { code: 'uk', nativeName: 'Українська', englishName: 'Ukrainian', flag: '🇺🇦' },
  { code: 'sv', nativeName: 'Svenska', englishName: 'Swedish', flag: '🇸🇪' },
  { code: 'no', nativeName: 'Norsk', englishName: 'Norwegian', flag: '🇳🇴' },
  { code: 'da', nativeName: 'Dansk', englishName: 'Danish', flag: '🇩🇰' },
  { code: 'fi', nativeName: 'Suomi', englishName: 'Finnish', flag: '🇫🇮' },
  { code: 'el', nativeName: 'Ελληνικά', englishName: 'Greek', flag: '🇬🇷' },
  { code: 'he', nativeName: 'עברית', englishName: 'Hebrew', flag: '🇮🇱' },
  { code: 'cs', nativeName: 'Čeština', englishName: 'Czech', flag: '🇨🇿' },
  { code: 'ro', nativeName: 'Română', englishName: 'Romanian', flag: '🇷🇴' },
  { code: 'hu', nativeName: 'Magyar', englishName: 'Hungarian', flag: '🇭🇺' },
]

export const STORAGE_KEY_LANGUAGE = 'enclavefree_language'
