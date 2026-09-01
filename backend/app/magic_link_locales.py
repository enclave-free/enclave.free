"""Localized static copy for User magic-link emails.

The locale list intentionally mirrors the Enclave Control Plane's Advertised
Locale set. The messages use the same three interpolation placeholders in every
locale so the renderer can enforce a single safe template contract.
"""

from __future__ import annotations

from string import Formatter
from typing import Final, TypedDict


class MagicLinkMessages(TypedDict):
    subject: str
    heading: str
    explanation: str
    button: str
    expiry: str
    unsolicited: str
    copy_link: str


MAGIC_LINK_TRANSLATION_FIELDS: Final[tuple[str, ...]] = (
    "subject",
    "heading",
    "explanation",
    "button",
    "expiry",
    "unsolicited",
    "copy_link",
)

# Keep this explicit rather than deriving it from request/browser metadata.
# These are the 31 locale codes advertised by the Enclave Control Plane.
SUPPORTED_MAGIC_LINK_LOCALES: Final[tuple[str, ...]] = (
    "en", "es", "pt", "fr", "de", "it", "nl", "ru", "zh-Hans", "zh-Hant",
    "ja", "ko", "ar", "fa", "hi", "bn", "id", "th", "vi", "tr", "pl", "uk",
    "sv", "no", "da", "fi", "el", "he", "cs", "ro", "hu",
)


MAGIC_LINK_TRANSLATIONS: Final[dict[str, MagicLinkMessages]] = {
    "en": {
        "subject": "Sign in to {display_name}",
        "heading": "Sign in to {display_name}",
        "explanation": "Click the button below to sign in.",
        "button": "Sign in to {display_name}",
        "expiry": "This link will expire in {minutes} minutes.",
        "unsolicited": "If you didn't request this email, you can safely ignore it.",
        "copy_link": "Or copy this link: {verify_url}",
    },
    "es": {
        "subject": "Inicia sesión en {display_name}",
        "heading": "Inicia sesión en {display_name}",
        "explanation": "Haz clic en el botón de abajo para iniciar sesión.",
        "button": "Iniciar sesión en {display_name}",
        "expiry": "Este enlace caducará en {minutes} minutos.",
        "unsolicited": "Si no solicitaste este correo electrónico, puedes ignorarlo sin problemas.",
        "copy_link": "O copia este enlace: {verify_url}",
    },
    "pt": {
        "subject": "Entrar em {display_name}",
        "heading": "Entrar em {display_name}",
        "explanation": "Clique no botão abaixo para entrar.",
        "button": "Entrar em {display_name}",
        "expiry": "Este link expirará em {minutes} minutos.",
        "unsolicited": "Se você não solicitou este e-mail, pode ignorá-lo com segurança.",
        "copy_link": "Ou copie este link: {verify_url}",
    },
    "fr": {
        "subject": "Se connecter à {display_name}",
        "heading": "Se connecter à {display_name}",
        "explanation": "Cliquez sur le bouton ci-dessous pour vous connecter.",
        "button": "Se connecter à {display_name}",
        "expiry": "Ce lien expirera dans {minutes} minutes.",
        "unsolicited": "Si vous n'avez pas demandé cet e-mail, vous pouvez l'ignorer en toute sécurité.",
        "copy_link": "Ou copiez ce lien : {verify_url}",
    },
    "de": {
        "subject": "Bei {display_name} anmelden",
        "heading": "Bei {display_name} anmelden",
        "explanation": "Klicke auf die Schaltfläche unten, um dich anzumelden.",
        "button": "Bei {display_name} anmelden",
        "expiry": "Dieser Link läuft in {minutes} Minuten ab.",
        "unsolicited": "Wenn du diese E-Mail nicht angefordert hast, kannst du sie sicher ignorieren.",
        "copy_link": "Oder kopiere diesen Link: {verify_url}",
    },
    "it": {
        "subject": "Accedi a {display_name}",
        "heading": "Accedi a {display_name}",
        "explanation": "Fai clic sul pulsante qui sotto per accedere.",
        "button": "Accedi a {display_name}",
        "expiry": "Questo link scadrà tra {minutes} minuti.",
        "unsolicited": "Se non hai richiesto questa e-mail, puoi ignorarla tranquillamente.",
        "copy_link": "Oppure copia questo link: {verify_url}",
    },
    "nl": {
        "subject": "Inloggen bij {display_name}",
        "heading": "Inloggen bij {display_name}",
        "explanation": "Klik op de knop hieronder om in te loggen.",
        "button": "Inloggen bij {display_name}",
        "expiry": "Deze link verloopt over {minutes} minuten.",
        "unsolicited": "Als je deze e-mail niet hebt aangevraagd, kun je hem veilig negeren.",
        "copy_link": "Of kopieer deze link: {verify_url}",
    },
    "ru": {
        "subject": "Войти в {display_name}",
        "heading": "Войти в {display_name}",
        "explanation": "Нажмите кнопку ниже, чтобы войти.",
        "button": "Войти в {display_name}",
        "expiry": "Срок действия этой ссылки истечёт через {minutes} минут.",
        "unsolicited": "Если вы не запрашивали это письмо, его можно спокойно проигнорировать.",
        "copy_link": "Или скопируйте эту ссылку: {verify_url}",
    },
    "zh-Hans": {
        "subject": "登录 {display_name}",
        "heading": "登录 {display_name}",
        "explanation": "点击下面的按钮登录。",
        "button": "登录 {display_name}",
        "expiry": "此链接将在 {minutes} 分钟后失效。",
        "unsolicited": "如果您没有请求此邮件，可以放心忽略。",
        "copy_link": "或复制此链接：{verify_url}",
    },
    "zh-Hant": {
        "subject": "登入 {display_name}",
        "heading": "登入 {display_name}",
        "explanation": "點擊下方按鈕即可登入。",
        "button": "登入 {display_name}",
        "expiry": "此連結將在 {minutes} 分鐘後失效。",
        "unsolicited": "如果您沒有要求此電子郵件，可以放心忽略。",
        "copy_link": "或複製此連結：{verify_url}",
    },
    "ja": {
        "subject": "{display_name} にサインイン",
        "heading": "{display_name} にサインイン",
        "explanation": "下のボタンをクリックしてサインインしてください。",
        "button": "{display_name} にサインイン",
        "expiry": "このリンクは {minutes} 分で有効期限が切れます。",
        "unsolicited": "このメールをリクエストしていない場合は、安全に無視できます。",
        "copy_link": "またはこのリンクをコピーしてください: {verify_url}",
    },
    "ko": {
        "subject": "{display_name}에 로그인",
        "heading": "{display_name}에 로그인",
        "explanation": "아래 버튼을 클릭하여 로그인하세요.",
        "button": "{display_name}에 로그인",
        "expiry": "이 링크는 {minutes}분 후에 만료됩니다.",
        "unsolicited": "이 이메일을 요청하지 않았다면 안전하게 무시해도 됩니다.",
        "copy_link": "또는 이 링크를 복사하세요: {verify_url}",
    },
    "ar": {
        "subject": "تسجيل الدخول إلى {display_name}",
        "heading": "تسجيل الدخول إلى {display_name}",
        "explanation": "انقر على الزر أدناه لتسجيل الدخول.",
        "button": "تسجيل الدخول إلى {display_name}",
        "expiry": "ستنتهي صلاحية هذا الرابط خلال {minutes} دقيقة.",
        "unsolicited": "إذا لم تطلب هذا البريد الإلكتروني، يمكنك تجاهله بأمان.",
        "copy_link": "أو انسخ هذا الرابط: {verify_url}",
    },
    "fa": {
        "subject": "ورود به {display_name}",
        "heading": "ورود به {display_name}",
        "explanation": "برای ورود روی دکمه زیر کلیک کنید.",
        "button": "ورود به {display_name}",
        "expiry": "این پیوند تا {minutes} دقیقه دیگر منقضی می‌شود.",
        "unsolicited": "اگر این ایمیل را درخواست نکرده‌اید، می‌توانید با خیال راحت آن را نادیده بگیرید.",
        "copy_link": "یا این پیوند را کپی کنید: {verify_url}",
    },
    "hi": {
        "subject": "{display_name} में साइन इन करें",
        "heading": "{display_name} में साइन इन करें",
        "explanation": "साइन इन करने के लिए नीचे दिए गए बटन पर क्लिक करें।",
        "button": "{display_name} में साइन इन करें",
        "expiry": "यह लिंक {minutes} मिनट में समाप्त हो जाएगा।",
        "unsolicited": "अगर आपने इस ईमेल का अनुरोध नहीं किया है, तो आप इसे सुरक्षित रूप से अनदेखा कर सकते हैं।",
        "copy_link": "या इस लिंक को कॉपी करें: {verify_url}",
    },
    "bn": {
        "subject": "{display_name}-এ সাইন ইন করুন",
        "heading": "{display_name}-এ সাইন ইন করুন",
        "explanation": "সাইন ইন করতে নিচের বোতামে ক্লিক করুন।",
        "button": "{display_name}-এ সাইন ইন করুন",
        "expiry": "এই লিংকের মেয়াদ {minutes} মিনিটের মধ্যে শেষ হবে।",
        "unsolicited": "আপনি এই ইমেলটি অনুরোধ না করলে নিরাপদে উপেক্ষা করতে পারেন।",
        "copy_link": "অথবা এই লিংকটি কপি করুন: {verify_url}",
    },
    "id": {
        "subject": "Masuk ke {display_name}",
        "heading": "Masuk ke {display_name}",
        "explanation": "Klik tombol di bawah untuk masuk.",
        "button": "Masuk ke {display_name}",
        "expiry": "Tautan ini akan kedaluwarsa dalam {minutes} menit.",
        "unsolicited": "Jika Anda tidak meminta email ini, Anda dapat mengabaikannya dengan aman.",
        "copy_link": "Atau salin tautan ini: {verify_url}",
    },
    "th": {
        "subject": "ลงชื่อเข้าใช้ {display_name}",
        "heading": "ลงชื่อเข้าใช้ {display_name}",
        "explanation": "คลิกปุ่มด้านล่างเพื่อเข้าสู่ระบบ",
        "button": "ลงชื่อเข้าใช้ {display_name}",
        "expiry": "ลิงก์นี้จะหมดอายุใน {minutes} นาที",
        "unsolicited": "หากคุณไม่ได้ขออีเมลนี้ คุณสามารถละเว้นได้อย่างปลอดภัย",
        "copy_link": "หรือคัดลอกลิงก์นี้: {verify_url}",
    },
    "vi": {
        "subject": "Đăng nhập vào {display_name}",
        "heading": "Đăng nhập vào {display_name}",
        "explanation": "Nhấp vào nút bên dưới để đăng nhập.",
        "button": "Đăng nhập vào {display_name}",
        "expiry": "Liên kết này sẽ hết hạn sau {minutes} phút.",
        "unsolicited": "Nếu bạn không yêu cầu email này, bạn có thể yên tâm bỏ qua.",
        "copy_link": "Hoặc sao chép liên kết này: {verify_url}",
    },
    "tr": {
        "subject": "{display_name} hesabında oturum açın",
        "heading": "{display_name} hesabında oturum açın",
        "explanation": "Oturum açmak için aşağıdaki düğmeye tıklayın.",
        "button": "{display_name} hesabında oturum açın",
        "expiry": "Bu bağlantının süresi {minutes} dakika içinde dolacak.",
        "unsolicited": "Bu e-postayı siz istemediyseniz güvenle yok sayabilirsiniz.",
        "copy_link": "Veya bu bağlantıyı kopyalayın: {verify_url}",
    },
    "pl": {
        "subject": "Zaloguj się do {display_name}",
        "heading": "Zaloguj się do {display_name}",
        "explanation": "Kliknij przycisk poniżej, aby się zalogować.",
        "button": "Zaloguj się do {display_name}",
        "expiry": "Ten link wygaśnie za {minutes} minut.",
        "unsolicited": "Jeśli nie prosiłeś(-aś) o tę wiadomość, możesz ją bezpiecznie zignorować.",
        "copy_link": "Lub skopiuj ten link: {verify_url}",
    },
    "uk": {
        "subject": "Увійти до {display_name}",
        "heading": "Увійти до {display_name}",
        "explanation": "Натисніть кнопку нижче, щоб увійти.",
        "button": "Увійти до {display_name}",
        "expiry": "Термін дії цього посилання завершиться через {minutes} хвилин.",
        "unsolicited": "Якщо ви не запитували цей лист, його можна безпечно проігнорувати.",
        "copy_link": "Або скопіюйте це посилання: {verify_url}",
    },
    "sv": {
        "subject": "Logga in på {display_name}",
        "heading": "Logga in på {display_name}",
        "explanation": "Klicka på knappen nedan för att logga in.",
        "button": "Logga in på {display_name}",
        "expiry": "Den här länken upphör att gälla om {minutes} minuter.",
        "unsolicited": "Om du inte begärde det här e-postmeddelandet kan du tryggt ignorera det.",
        "copy_link": "Eller kopiera den här länken: {verify_url}",
    },
    "no": {
        "subject": "Logg inn på {display_name}",
        "heading": "Logg inn på {display_name}",
        "explanation": "Klikk på knappen nedenfor for å logge inn.",
        "button": "Logg inn på {display_name}",
        "expiry": "Denne lenken utløper om {minutes} minutter.",
        "unsolicited": "Hvis du ikke ba om denne e-posten, kan du trygt ignorere den.",
        "copy_link": "Eller kopier denne lenken: {verify_url}",
    },
    "da": {
        "subject": "Log ind på {display_name}",
        "heading": "Log ind på {display_name}",
        "explanation": "Klik på knappen nedenfor for at logge ind.",
        "button": "Log ind på {display_name}",
        "expiry": "Dette link udløber om {minutes} minutter.",
        "unsolicited": "Hvis du ikke har anmodet om denne e-mail, kan du roligt ignorere den.",
        "copy_link": "Eller kopiér dette link: {verify_url}",
    },
    "fi": {
        "subject": "Kirjaudu palveluun {display_name}",
        "heading": "Kirjaudu palveluun {display_name}",
        "explanation": "Kirjaudu napsauttamalla alla olevaa painiketta.",
        "button": "Kirjaudu palveluun {display_name}",
        "expiry": "Tämä linkki vanhenee {minutes} minuutin kuluttua.",
        "unsolicited": "Jos et pyytänyt tätä sähköpostia, voit ohittaa sen turvallisesti.",
        "copy_link": "Tai kopioi tämä linkki: {verify_url}",
    },
    "el": {
        "subject": "Συνδεθείτε στο {display_name}",
        "heading": "Συνδεθείτε στο {display_name}",
        "explanation": "Κάντε κλικ στο παρακάτω κουμπί για να συνδεθείτε.",
        "button": "Συνδεθείτε στο {display_name}",
        "expiry": "Αυτός ο σύνδεσμος θα λήξει σε {minutes} λεπτά.",
        "unsolicited": "Αν δεν ζητήσατε αυτό το email, μπορείτε να το αγνοήσετε με ασφάλεια.",
        "copy_link": "Ή αντιγράψτε αυτόν τον σύνδεσμο: {verify_url}",
    },
    "he": {
        "subject": "התחברות אל {display_name}",
        "heading": "התחברות אל {display_name}",
        "explanation": "לחצו על הכפתור למטה כדי להתחבר.",
        "button": "התחברות אל {display_name}",
        "expiry": "תוקף הקישור יפוג בעוד {minutes} דקות.",
        "unsolicited": "אם לא ביקשתם את האימייל הזה, אפשר להתעלם ממנו בבטחה.",
        "copy_link": "או העתיקו את הקישור הזה: {verify_url}",
    },
    "cs": {
        "subject": "Přihlaste se do {display_name}",
        "heading": "Přihlaste se do {display_name}",
        "explanation": "Kliknutím na tlačítko níže se přihlásíte.",
        "button": "Přihlásit se do {display_name}",
        "expiry": "Platnost tohoto odkazu vyprší za {minutes} minut.",
        "unsolicited": "Pokud jste o tento e-mail nepožádali, můžete ho bezpečně ignorovat.",
        "copy_link": "Nebo tento odkaz zkopírujte: {verify_url}",
    },
    "ro": {
        "subject": "Conectează-te la {display_name}",
        "heading": "Conectează-te la {display_name}",
        "explanation": "Apasă butonul de mai jos pentru a te conecta.",
        "button": "Conectează-te la {display_name}",
        "expiry": "Acest link va expira în {minutes} minute.",
        "unsolicited": "Dacă nu ai solicitat acest e-mail, îl poți ignora în siguranță.",
        "copy_link": "Sau copiază acest link: {verify_url}",
    },
    "hu": {
        "subject": "Bejelentkezés ide: {display_name}",
        "heading": "Bejelentkezés ide: {display_name}",
        "explanation": "A bejelentkezéshez kattints az alábbi gombra.",
        "button": "Bejelentkezés ide: {display_name}",
        "expiry": "Ez a hivatkozás {minutes} perc múlva lejár.",
        "unsolicited": "Ha nem kérted ezt az e-mailt, nyugodtan figyelmen kívül hagyhatod.",
        "copy_link": "Vagy másold ki ezt a hivatkozást: {verify_url}",
    },
}


_EXPECTED_PLACEHOLDERS: Final[dict[str, frozenset[str]]] = {
    "subject": frozenset({"display_name"}),
    "heading": frozenset({"display_name"}),
    "explanation": frozenset(),
    "button": frozenset({"display_name"}),
    "expiry": frozenset({"minutes"}),
    "unsolicited": frozenset(),
    "copy_link": frozenset({"verify_url"}),
}


def validate_magic_link_translation_catalog() -> None:
    """Validate exact message fields and interpolation placeholders for every locale."""
    expected_fields = set(MAGIC_LINK_TRANSLATION_FIELDS)
    formatter = Formatter()
    for locale, messages in MAGIC_LINK_TRANSLATIONS.items():
        if set(messages) != expected_fields:
            raise ValueError(f"Magic-link locale {locale} has an unexpected message field")
        for field in MAGIC_LINK_TRANSLATION_FIELDS:
            try:
                parsed = list(formatter.parse(messages[field]))
            except ValueError as error:
                raise ValueError(f"Magic-link locale {locale}.{field} has invalid format syntax") from error
            placeholders = frozenset(
                field_name
                for _, field_name, format_spec, conversion in parsed
                if field_name is not None
                and not format_spec
                and not conversion
            )
            malformed = any(
                field_name is not None and (format_spec or conversion)
                for _, field_name, format_spec, conversion in parsed
            )
            if malformed or placeholders != _EXPECTED_PLACEHOLDERS[field]:
                raise ValueError(f"Magic-link locale {locale}.{field} has incorrect placeholders")


validate_magic_link_translation_catalog()


def normalize_magic_link_locale(locale: object) -> str:
    """Return an advertised locale, falling back to English for any invalid value."""
    if isinstance(locale, str):
        candidate = locale.strip()
        if candidate in MAGIC_LINK_TRANSLATIONS:
            return candidate
    return "en"
