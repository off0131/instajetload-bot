from typing import Dict, Any

LANGUAGES = {
    "fa": {"name": "فارسی", "flag": "🇮🇷"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "ar": {"name": "العربية", "flag": "🇸🇦"},
    "ru": {"name": "Русский", "flag": "🇷🇺"},
    "zh": {"name": "中文", "flag": "🇨🇳"},
    "de": {"name": "Deutsch", "flag": "🇩🇪"},
    "es": {"name": "Español", "flag": "🇪🇸"},
    "fr": {"name": "Français", "flag": "🇫🇷"},
    "tr": {"name": "Türkçe", "flag": "🇹🇷"},
    "hi": {"name": "हिन्दी", "flag": "🇮🇳"},
}

TEXTS: Dict[str, Dict[str, str]] = {
    "welcome": {
        "fa": (
            "سلام {name} عزیز! خیلی خوش اومدی 🤩❤️✨\n\n"
            "من ربات همه‌کاره‌ی <b>InstaJetLoad</b> هستم؛ هر لینکی برام بفرستی با <b>بالاترین کیفیت و سرعت برق‌آسا</b> برات دانلود می‌کنم ⚡️🎯\n\n"
            "🔥 <b>پلتفرم‌های پشتیبانی‌شده:</b>\n"
            "▫️ <b>اینستاگرام (Instagram):</b> ریلز، پست، عکس با کیفیت اصلی 🎬\n"
            "▫️ <b>یوتیوب (YouTube):</b> انتخاب کیفیت دلخواه (1080p, 720p, ...) یا فایل صوتی MP3 📺\n"
            "▫️ <b>اسپاتیفای (Spotify):</b> دانلود مستقیم موزیک با کیفیت 320kbps 🎧\n"
            "▫️ <b>ساندکلاد (SoundCloud):</b> دانلود آهنگ با کیفیت بالا 🎵\n"
            "▫️ <b>تیک‌تاک (TikTok):</b> ویدیو بدون واترمرک 🚀\n"
            "▫️ <b>توییتر / اکس (Twitter / X) و پینترست (Pinterest)</b> 📌\n"
            "▫️ <b>متن کپشن:</b> با یک کلیک کپی کن همراه با هشتگ‌ها ✍️\n\n"
            "👇 <b>همین الان امتحانش کن:</b>\n"
            "فقط کافیه لینک مورد نظرت رو برام بفرستی! 😉🚀"
        ),
        "en": (
            "Hello {name}! Welcome to <b>InstaJetLoad</b> 🤩❤️✨\n\n"
            "I download media from popular platforms with <b>maximum quality and blazing-fast speed</b> ⚡️🎯\n\n"
            "🔥 <b>Supported Platforms:</b>\n"
            "▫️ <b>Instagram:</b> Reels, posts, stories, full-res photos 🎬\n"
            "▫️ <b>YouTube:</b> Quality selection (1080p, 720p, 480p) or MP3 audio 📺\n"
            "▫️ <b>Spotify:</b> High-quality tracks (320kbps) 🎧\n"
            "▫️ <b>SoundCloud:</b> Music tracks 🎵\n"
            "▫️ <b>TikTok:</b> Watermark-free videos 🚀\n"
            "▫️ <b>Twitter / X & Pinterest:</b> Photos & Videos 📌\n"
            "▫️ <b>Captions:</b> One-tap copy with hashtags ✍️\n\n"
            "👇 <b>Try it now:</b>\n"
            "Just send me any link and get your media in seconds! 😉🚀"
        ),
        "ar": (
            "أهلاً وسهلاً بك {name}! في بوت <b>InstaJetLoad</b> 🤩❤️✨\n\n"
            "أقوم بتحميل الوسائط من المنصات بأعلى <b>جودة وبسرعة فائقة</b> ⚡️🎯\n\n"
            "🔥 <b>المنصات المدعومة:</b>\n"
            "▫️ <b>إنستغرام (Instagram):</b> ريلز، منشورات، وصور بأعلى دقة 🎬\n"
            "▫️ <b>يوتيوب (YouTube):</b> باختيار الدقة (1080p, 720p) أو ملف صوتي MP3 📺\n"
            "▫️ <b>سبوتيفاي (Spotify):</b> تحميل أغاني بجودة 320kbps 🎧\n"
            "▫️ <b>ساوند كلاود (SoundCloud):</b> ملفات صوتية عالية الجودة 🎵\n"
            "▫️ <b>تيك توك (TikTok):</b> فيديو بدون علامة مائية 🚀\n"
            "▫️ <b>تويتر وبنتريست (Twitter & Pinterest)</b> 📌\n\n"
            "👇 <b>جرب الآن:</b> أرسل أي رابط وسأقوم بتحميله فوراً! 😉🚀"
        ),
        "ru": (
            "Привет, {name}! Добро пожаловать в <b>InstaJetLoad</b> 🤩❤️✨\n\n"
            "Я скачиваю видео и музыку в <b>максимальном качестве и на сверхзвуковой скорости</b> ⚡️🎯\n\n"
            "🔥 <b>Поддерживаемые платформы:</b>\n"
            "▫️ <b>Instagram:</b> Reels, посты, фото без потери качества 🎬\n"
            "▫️ <b>YouTube:</b> Выбор качества (1080p, 720p) или MP3 аудио 📺\n"
            "▫️ <b>Spotify:</b> Треки в высоком качестве (320kbps) 🎧\n"
            "▫️ <b>SoundCloud:</b> Музыка и аудиозаписи 🎵\n"
            "▫️ <b>TikTok:</b> Видео без водяного знака 🚀\n"
            "▫️ <b>Twitter (X) & Pinterest</b> 📌\n\n"
            "👇 <b>Попробуй прямо сейчас:</b>\n"
            "Просто отправь мне ссылку! 😉🚀"
        ),
        "zh": (
            "你好 {name}！欢迎使用 <b>InstaJetLoad</b> 机器人 🤩❤️✨\n\n"
            "我可以以<b>最高画质与极速</b>为您下载各大平台的媒体资源 ⚡️🎯\n\n"
            "🔥 <b>支持平台：</b>\n"
            "▫️ <b>Instagram：</b> Reels短视频、多图帖子、高清原图 🎬\n"
            "▫️ <b>YouTube：</b> 可选画质 (1080p, 720p) 或 MP3音频 📺\n"
            "▫️ <b>Spotify：</b> 320kbps高音质音乐 🎧\n"
            "▫️ <b>SoundCloud：</b> 高清音频 🎵\n"
            "▫️ <b>TikTok / 抖音：</b> 无水印高清视频 🚀\n"
            "▫️ <b>Twitter / X 与 Pinterest</b> 📌\n\n"
            "👇 <b>立即尝试：</b> 直接发送链接给我即可！😉🚀"
        ),
        "de": (
            "Hallo {name}! Willkommen bei <b>InstaJetLoad</b> 🤩❤️✨\n\n"
            "Ich lade Medien in <b>bester Qualität und blitzschneller Geschwindigkeit</b> herunter ⚡️🎯\n\n"
            "🔥 <b>Unterstützte Plattformen:</b>\n"
            "▫️ <b>Instagram:</b> Reels, Beiträge, Fotos in Originalauflösung 🎬\n"
            "▫️ <b>YouTube:</b> Qualitätsauswahl (1080p, 720p) oder MP3-Audio 📺\n"
            "▫️ <b>Spotify:</b> Musik in 320kbps Qualität 🎧\n"
            "▫️ <b>SoundCloud:</b> Musik & Audiotracks 🎵\n"
            "▫️ <b>TikTok:</b> Videos ohne Wasserzeichen 🚀\n"
            "▫️ <b>Twitter / X & Pinterest</b> 📌\n\n"
            "👇 <b>Jetzt ausprobieren:</b> Sende mir einfach einen Link! 😉🚀"
        ),
        "es": (
            "¡Hola {name}! Bienvenido a <b>InstaJetLoad</b> 🤩❤️✨\n\n"
            "Descargo contenido en <b>máxima calidad y a velocidad ultrarrápida</b> ⚡️🎯\n\n"
            "🔥 <b>Plataformas compatibles:</b>\n"
            "▫️ <b>Instagram:</b> Reels, publicaciones y fotos en calidad original 🎬\n"
            "▫️ <b>YouTube:</b> Elige calidad (1080p, 720p) o audio MP3 📺\n"
            "▫️ <b>Spotify:</b> Canciones en alta calidad (320kbps) 🎧\n"
            "▫️ <b>SoundCloud:</b> Pistas de audio 🎵\n"
            "▫️ <b>TikTok:</b> Videos sin marca de agua 🚀\n"
            "▫️ <b>Twitter / X y Pinterest</b> 📌\n\n"
            "👇 <b>Pruébalo ahora:</b> ¡Solo envíame un enlace! 😉🚀"
        ),
        "fr": (
            "Bonjour {name} ! Bienvenue sur <b>InstaJetLoad</b> 🤩❤️✨\n\n"
            "Téléchargez vos médias en <b>qualité maximale et vitesse éclair</b> ⚡️🎯\n\n"
            "🔥 <b>Plateformes supportées :</b>\n"
            "▫️ <b>Instagram :</b> Reels, publications, photos haute définition 🎬\n"
            "▫️ <b>YouTube :</b> Choix de qualité (1080p, 720p) ou audio MP3 📺\n"
            "▫️ <b>Spotify :</b> Musique haute fidélité (320kbps) 🎧\n"
            "▫️ <b>SoundCloud :</b> Pistes musicales 🎵\n"
            "▫️ <b>TikTok :</b> Vidéos sans filigrane 🚀\n"
            "▫️ <b>Twitter / X & Pinterest</b> 📌\n\n"
            "👇 <b>Essayez maintenant :</b> Envoyez simplement un lien ! 😉🚀"
        ),
        "tr": (
            "Merhaba {name}! <b>InstaJetLoad</b> botuna hoş geldin 🤩❤️✨\n\n"
            "Medyaları <b>en yüksek kalitede ve ışık hızında</b> indiriyorum ⚡️🎯\n\n"
            "🔥 <b>Desteklenen Platformlar:</b>\n"
            "▫️ <b>Instagram:</b> Reels, gönderiler, tam çözünürlüklü fotoğraflar 🎬\n"
            "▫️ <b>YouTube:</b> Kalite seçimi (1080p, 720p) veya MP3 ses 📺\n"
            "▫️ <b>Spotify:</b> Yüksek kaliteli müzik (320kbps) 🎧\n"
            "▫️ <b>SoundCloud:</b> Müzik parçaları 🎵\n"
            "▫️ <b>TikTok:</b> Filigransız video 🚀\n"
            "▫️ <b>Twitter / X ve Pinterest</b> 📌\n\n"
            "👇 <b>Hemen dene:</b> Linki gönder, saniyeler içinde indir! 😉🚀"
        ),
        "hi": (
            "नमस्ते {name}! <b>InstaJetLoad</b> में आपका स्वागत है 🤩❤️✨\n\n"
            "मैं <b>उच्चतम गुणवत्ता और सुपरफास्ट गति</b> के साथ मीडिया डाउनलोड करता हूँ ⚡️🎯\n\n"
            "🔥 <b>समर्थित प्लेटफॉर्म:</b>\n"
            "▫️ <b>Instagram:</b> Reels, पोस्ट और फोटो 🎬\n"
            "▫️ <b>YouTube:</b> रिज़ॉल्यूशन चुनें (1080p, 720p) या MP3 ऑडियो 📺\n"
            "▫️ <b>Spotify:</b> 320kbps हाई क्वालिटी गाने 🎧\n"
            "▫️ <b>SoundCloud:</b> म्यूज़िक ट्रैक्स 🎵\n"
            "▫️ <b>TikTok:</b> बिना वॉटरमार्क वीडियो 🚀\n"
            "▫️ <b>Twitter / X और Pinterest</b> 📌\n\n"
            "👇 <b>अभी आज़माएं:</b> बस मुझे लिंक भेजें! 😉🚀"
        ),
    },

    "choose_lang": {
        "fa": "🌐 لطفاً زبان مورد نظر خود را انتخاب کنید:\n\n🌐 Please choose your language:",
        "en": "🌐 Please choose your language:",
        "ar": "🌐 يرجى اختيار لغتك:",
        "ru": "🌐 Пожалуйста, выберите язык:",
        "zh": "🌐 请选择您的语言：",
        "de": "🌐 Bitte wählen Sie Ihre Sprache:",
        "es": "🌐 Por favor seleccione su idioma:",
        "fr": "🌐 Veuillez choisir votre langue :",
        "tr": "🌐 Lütfen dilinizi seçin:",
        "hi": "🌐 कृपया अपनी भाषा चुनें:",
    },

    "lang_updated": {
        "fa": "✅ زبان با موفقیت روی فارسی تنظیم شد! 🇮🇷",
        "en": "✅ Language successfully set to English! 🇺🇸",
        "ar": "✅ تم ضبط اللغة إلى العربية بنجاح! 🇸🇦",
        "ru": "✅ Язык успешно изменён на русский! 🇷🇺",
        "zh": "✅ 语言已成功设置为中文！🇨🇳",
        "de": "✅ Sprache erfolgreich auf Deutsch eingestellt! 🇩🇪",
        "es": "✅ ¡Idioma configurado en español con éxito! 🇪🇸",
        "fr": "✅ Langue définie sur français avec succès ! 🇫🇷",
        "tr": "✅ Dil başarıyla Türkçe olarak ayarlandı! 🇹🇷",
        "hi": "✅ भाषा सफलतापूर्वक हिन्दी में सेट हो गई! 🇮🇳",
    },

    "btn_server_status": {
        "fa": "⚡️ وضعیت سرور",
        "en": "⚡️ Server Status",
        "ar": "⚡️ حالة الخادم",
        "ru": "⚡️ Статус сервера",
        "zh": "⚡️ 服务器状态",
        "de": "⚡️ Serverstatus",
        "es": "⚡️ Estado del servidor",
        "fr": "⚡️ État du serveur",
        "tr": "⚡️ Sunucu Durumu",
        "hi": "⚡️ सर्वर स्थिति",
    },

    "btn_tips": {
        "fa": "💡 راهنما و نکات",
        "en": "💡 Tips & Help",
        "ar": "💡 نصائح ومساعدة",
        "ru": "💡 Советы и помощь",
        "zh": "💡 使用技巧",
        "de": "💡 Tipps & Hilfe",
        "es": "💡 Consejos y ayuda",
        "fr": "💡 Conseils & Aide",
        "tr": "💡 İpuçları ve Yardım",
        "hi": "💡 टिप्स और सहायता",
    },

    "btn_change_lang": {
        "fa": "🌐 تغییر زبان (Language)",
        "en": "🌐 Change Language",
        "ar": "🌐 تغيير اللغة",
        "ru": "🌐 Сменить язык",
        "zh": "🌐 切换语言",
        "de": "🌐 Sprache ändern",
        "es": "🌐 Cambiar idioma",
        "fr": "🌐 Changer de langue",
        "tr": "🌐 Dil Değiştir",
        "hi": "🌐 भाषा बदलें",
    },

    "btn_share": {
        "fa": "🚀 معرفی به دوستان",
        "en": "🚀 Share Bot",
        "ar": "🚀 مشاركة البوت",
        "ru": "🚀 Поделиться",
        "zh": "🚀 分享给好友",
        "de": "🚀 Bot teilen",
        "es": "🚀 Compartir bot",
        "fr": "🚀 Partager le bot",
        "tr": "🚀 Arkadaşlarla Paylaş",
        "hi": "🚀 बॉट शेयर करें",
    },

    "share_text": {
        "fa": "بهترین ربات دانلود سریع از اینستاگرام، یوتیوب و اسپاتیفای: @instajetloadbot 🔥",
        "en": "Fastest downloader for Instagram, YouTube & Spotify: @instajetloadbot 🔥",
        "ar": "أسرع بوت لتحميل إنستغرام، يوتيوب وسبوتيفاي: @instajetloadbot 🔥",
        "ru": "Самый быстрый бот для Instagram, YouTube и Spotify: @instajetloadbot 🔥",
        "zh": "极速Instagram、YouTube、Spotify下载机器人：@instajetloadbot 🔥",
        "de": "Der schnellste Downloader für Instagram, YouTube & Spotify: @instajetloadbot 🔥",
        "es": "El descargador más rápido para Instagram, YouTube y Spotify: @instajetloadbot 🔥",
        "fr": "Le téléchargeur le plus rapide pour Instagram, YouTube et Spotify : @instajetloadbot 🔥",
        "tr": "Instagram, YouTube ve Spotify için en hızlı indirici: @instajetloadbot 🔥",
        "hi": "इंस्टाग्राम, यूट्यूब और स्पॉटीफाई के लिए सबसे तेज़ डाउनलोडर: @instajetloadbot 🔥",
    },

    "ping_alert": {
        "fa": "🟢 سرور کاملاً بیداره و سرعت دانلود در حداکثر توان قرار داره! ⚡️🏎",
        "en": "🟢 Server is active & download speed is at maximum power! ⚡️🏎",
        "ar": "🟢 الخادم متصل ونشط وسرعة التحميل بأقصى كفاءة! ⚡️🏎",
        "ru": "🟢 Сервер активен, скорость загрузки на максимуме! ⚡️🏎",
        "zh": "🟢 服务器运行正常，极速下载就绪！⚡️🏎",
        "de": "🟢 Server online & Download-Geschwindigkeit auf Maximum! ⚡️🏎",
        "es": "🟢 ¡El servidor está activo y la velocidad de descarga al máximo! ⚡️🏎",
        "fr": "🟢 Serveur actif et vitesse de téléchargement maximale ! ⚡️🏎",
        "tr": "🟢 Sunucu aktif ve indirme hızı maksimum seviyede! ⚡️🏎",
        "hi": "🟢 सर्वर सक्रिय है और डाउनलोड गति अधिकतम है! ⚡️🏎",
    },

    "tips_content": {
        "fa": (
            "💡 <b>چند نکته برای استفاده راحت‌تر:</b> ✨\n\n"
            "۱. <b>اینستاگرام:</b> دکمه Share زیر ریلز یا پست رو بزن و Copy link رو انتخاب کن 📲\n\n"
            "۲. <b>یوتیوب:</b> هر لینکی بفرستی، کیفیت‌های مختلف (1080p, 720p, ...) به همراه نسخه صوتی MP3 بهت پیشنهاد داده میشه 📺\n\n"
            "۳. <b>اسپاتیفای و ساندکلاد:</b> لینک موزیک رو بفرست تا فایل صوتی کامل با بالاترین کیفیت برات ارسال بشه 🎧\n\n"
            "۴. <b>کش هوشمند:</b> فایل‌هایی که قبلاً دانلود شدن، آنی و در کمتر از یک ثانیه تحویلت داده میشن! ⚡️"
        ),
        "en": (
            "💡 <b>Helpful Tips:</b> ✨\n\n"
            "1. <b>Instagram:</b> Tap Share under any reel or post and choose Copy link 📲\n\n"
            "2. <b>YouTube:</b> Send a link to get quality options (1080p, 720p, ...) plus audio MP3 📺\n\n"
            "3. <b>Spotify & SoundCloud:</b> Send a track link to get 320kbps audio with metadata 🎧\n\n"
            "4. <b>Instant Cache:</b> Previously downloaded media is delivered in under a second! ⚡️"
        ),
        "ar": (
            "💡 <b>نصائح مفيدة:</b> ✨\n\n"
            "١. <b>إنستغرام:</b> اضغط على زر المشاركة واختر نسخ الرابط 📲\n\n"
            "٢. <b>يوتيوب:</b> أرسل الرابط لاختيار الجودة أو تنزيل ملف MP3 📺\n\n"
            "٣. <b>سبوتيفاي وساوند كلاود:</b> أرسل رابط الأغنية لتحميل الملف الصوتي بأعلى جودة 🎧\n\n"
            "٤. <b>تخزين فوري:</b> الوسائط المحملة سابقاً تُرسل في أقل من ثانية! ⚡️"
        ),
        "ru": (
            "💡 <b>Полезные советы:</b> ✨\n\n"
            "1. <b>Instagram:</b> Нажмите «Поделиться» под постом или Reels и скопируйте ссылку 📲\n\n"
            "2. <b>YouTube:</b> Отправьте ссылку для выбора качества (1080p, 720p) или MP3 📺\n\n"
            "3. <b>Spotify и SoundCloud:</b> Отправьте трек для загрузки в 320kbps 🎧\n\n"
            "4. <b>Умный кэш:</b> Уже скачанные файлы отправляются мгновенно! ⚡️"
        ),
        "zh": (
            "💡 <b>使用技巧：</b> ✨\n\n"
            "1. <b>Instagram：</b> 点击视频或帖子下方的分享并复制链接 📲\n\n"
            "2. <b>YouTube：</b> 发送链接即可自由选择清晰度或MP3音频 📺\n\n"
            "3. <b>Spotify 与 SoundCloud：</b> 发送单曲链接即可下载320kbps高品质音频 🎧\n\n"
            "4. <b>极速秒传：</b> 之前下载过的媒体将在1秒内瞬间送达！⚡️"
        ),
        "de": (
            "💡 <b>Hilfreiche Tipps:</b> ✨\n\n"
            "1. <b>Instagram:</b> Tippe auf Teilen unter dem Beitrag und wähle Link kopieren 📲\n\n"
            "2. <b>YouTube:</b> Link senden und Auflösung oder MP3 wählen 📺\n\n"
            "3. <b>Spotify & SoundCloud:</b> Musiklink senden für 320kbps Audio 🎧\n\n"
            "4. <b>Smart Cache:</b> Bereits heruntergeladene Inhalte werden sofort gesendet! ⚡️"
        ),
        "es": (
            "💡 <b>Consejos útiles:</b> ✨\n\n"
            "1. <b>Instagram:</b> Toca Compartir en el reel o post y selecciona Copiar enlace 📲\n\n"
            "2. <b>YouTube:</b> Envía el enlace para elegir resolución o audio MP3 📺\n\n"
            "3. <b>Spotify y SoundCloud:</b> Envía el enlace de la canción para audio a 320kbps 🎧\n\n"
            "4. <b>Caché instantánea:</b> ¡Archivos descargados anteriormente se envían al instante! ⚡️"
        ),
        "fr": (
            "💡 <b>Conseils utiles :</b> ✨\n\n"
            "1. <b>Instagram :</b> Cliquez sur Partager sous la vidéo et Copier le lien 📲\n\n"
            "2. <b>YouTube :</b> Envoyez le lien pour choisir la résolution ou le fichier MP3 📺\n\n"
            "3. <b>Spotify & SoundCloud :</b> Téléchargez des pistes en haute qualité 320kbps 🎧\n\n"
            "4. <b>Cache instantané :</b> Les fichiers déjà téléchargés sont livrés en une seconde ! ⚡️"
        ),
        "tr": (
            "💡 <b>Faydalı İpuçları:</b> ✨\n\n"
            "1. <b>Instagram:</b> Paylaş butonuna basıp Bağlantıyı kopyala seçeneğini kullanın 📲\n\n"
            "2. <b>YouTube:</b> Linki gönderin ve çözünürlük veya MP3 ses seçin 📺\n\n"
            "3. <b>Spotify & SoundCloud:</b> Şarkı linkini gönderip 320kbps kalitede indirin 🎧\n\n"
            "4. <b>Akıllı Önbellek:</b> Daha önce indirilen içerikler saniyeler içinde gelir! ⚡️"
        ),
        "hi": (
            "💡 <b>उपयोगी टिप्स:</b> ✨\n\n"
            "1. <b>Instagram:</b> रील या पोस्ट के नीचे शेयर दबाएं और कॉपी लिंक चुनें 📲\n\n"
            "2. <b>YouTube:</b> लिंक भेजें और क्वालिटी या MP3 ऑडियो चुनें 📺\n\n"
            "3. <b>Spotify और SoundCloud:</b> 320kbps में गाने डाउनलोड करें 🎧\n\n"
            "4. <b>स्मार्ट कैश:</b> पहले डाउनलोड किए गए फाइल 1 सेकंड में मिल जाते हैं! ⚡️"
        ),
    },

    "downloading_general": {
        "fa": "⚡️ دریافت شد! در حال دانلود با بالاترین کیفیت... لطفاً چند ثانیه صبر کن رفیق ⏳🏎",
        "en": "⚡️ Received! Downloading at maximum quality... Please wait a few seconds ⏳🏎",
        "ar": "⚡️ تم الاستلام! جارٍ التحميل بأعلى جودة... يرجى الانتظار بضع ثوانٍ ⏳🏎",
        "ru": "⚡️ Принято! Скачиваю в максимальном качестве... Пожалуйста, подождите ⏳🏎",
        "zh": "⚡️ 已接收！正在以最高画质下载... 请稍候 ⏳🏎",
        "de": "⚡️ Erhalten! Download in bester Qualität läuft... Bitte kurz warten ⏳🏎",
        "es": "⚡️ ¡Recibido! Descargando en máxima calidad... Por favor espera unos segundos ⏳🏎",
        "fr": "⚡️ Reçu ! Téléchargement en qualité maximale... Veuillez patienter ⏳🏎",
        "tr": "⚡️ Alındı! En yüksek kalitede indiriliyor... Lütfen birkaç saniye bekleyin ⏳🏎",
        "hi": "⚡️ लिंक प्राप्त हुआ! उच्चतम गुणवत्ता में डाउनलोड हो रहा है... कृपया प्रतीक्षा करें ⏳🏎",
    },

    "yt_fetching_info": {
        "fa": "⚡️ در حال دریافت اطلاعات ویدیو از یوتیوب... ⏳",
        "en": "⚡️ Fetching video info from YouTube... ⏳",
        "ar": "⚡️ جارٍ جلب معلومات الفيديو من يوتيوب... ⏳",
        "ru": "⚡️ Получаю информацию о видео с YouTube... ⏳",
        "zh": "⚡️ 正在获取YouTube视频信息... ⏳",
        "de": "⚡️ Lade Videoinformationen von YouTube... ⏳",
        "es": "⚡️ Obteniendo información de YouTube... ⏳",
        "fr": "⚡️ Récupération des informations YouTube... ⏳",
        "tr": "⚡️ YouTube video bilgileri alınıyor... ⏳",
        "hi": "⚡️ YouTube से वीडियो जानकारी प्राप्त की जा रही है... ⏳",
    },

    "yt_select_quality": {
        "fa": "👇 کیفیت مورد نظرت رو برای دانلود انتخاب کن:",
        "en": "👇 Select your preferred quality to download:",
        "ar": "👇 اختر الجودة المطلوبة للتحميل:",
        "ru": "👇 Выберите качество для загрузки:",
        "zh": "👇 请选择要下载的画质或音频：",
        "de": "👇 Wähle die gewünschte Qualität zum Herunterladen:",
        "es": "👇 Selecciona la calidad deseada para descargar:",
        "fr": "👇 Sélectionnez la qualité souhaitée :",
        "tr": "👇 İndirmek istediğiniz kaliteyi seçin:",
        "hi": "👇 डाउनलोड के लिए अपनी पसंदीदा क्वालिटी चुनें:",
    },

    "yt_audio_btn": {
        "fa": "🎵 دانلود صوتی (MP3)",
        "en": "🎵 Audio Only (MP3)",
        "ar": "🎵 تحميل صوتي فقط (MP3)",
        "ru": "🎵 Только аудио (MP3)",
        "zh": "🎵 仅音频 (MP3)",
        "de": "🎵 Nur Audio (MP3)",
        "es": "🎵 Solo audio (MP3)",
        "fr": "🎵 Audio seulement (MP3)",
        "tr": "🎵 Sadece Ses (MP3)",
        "hi": "🎵 केवल ऑडियो (MP3)",
    },

    "btn_cancel": {
        "fa": "❌ انصراف",
        "en": "❌ Cancel",
        "ar": "❌ إلغاء",
        "ru": "❌ Отмена",
        "zh": "❌ 取消",
        "de": "❌ Abbrechen",
        "es": "❌ Cancelar",
        "fr": "❌ Annuler",
        "tr": "❌ İptal",
        "hi": "❌ रद्द करें",
    },

    "yt_downloading": {
        "fa": "⚡️ در حال دانلود {quality} از یوتیوب... لطفاً چند لحظه صبر کن رفیق 🏎⏳",
        "en": "⚡️ Downloading {quality} from YouTube... Please wait a moment 🏎⏳",
        "ar": "⚡️ جارٍ تحميل {quality} من يوتيوب... يرجى الانتظار 🏎⏳",
        "ru": "⚡️ Скачиваю {quality} с YouTube... Пожалуйста, подождите 🏎⏳",
        "zh": "⚡️ 正在下载YouTube {quality}... 请稍候 🏎⏳",
        "de": "⚡️ Lade {quality} von YouTube herunter... Bitte kurz warten 🏎⏳",
        "es": "⚡️ Descargando {quality} de YouTube... Por favor espera 🏎⏳",
        "fr": "⚡️ Téléchargement de {quality} depuis YouTube... Veuillez patienter 🏎⏳",
        "tr": "⚡️ YouTube üzerinden {quality} indiriliyor... Lütfen bekleyin 🏎⏳",
        "hi": "⚡️ YouTube से {quality} डाउनलोड हो रहा है... कृपया प्रतीक्षा करें 🏎⏳",
    },

    "spotify_downloading": {
        "fa": "🎧 در حال دریافت و دانلود موزیک از اسپاتیفای با بالاترین کیفیت (320kbps)... ⚡️⏳",
        "en": "🎧 Downloading track from Spotify in high quality (320kbps)... ⚡️⏳",
        "ar": "🎧 جارٍ تحميل الأغنية من سبوتيفاي بأعلى جودة (320kbps)... ⚡️⏳",
        "ru": "🎧 Скачиваю трек из Spotify в лучшем качестве (320kbps)... ⚡️⏳",
        "zh": "🎧 正在从Spotify下载320kbps高品质音乐... ⚡️⏳",
        "de": "🎧 Lade Musiktitel von Spotify in 320kbps herunter... ⚡️⏳",
        "es": "🎧 Descargando canción de Spotify en alta calidad (320kbps)... ⚡️⏳",
        "fr": "🎧 Téléchargement depuis Spotify en haute qualité (320kbps)... ⚡️⏳",
        "tr": "🎧 Spotify üzerinden 320kbps yüksek kalitede indiriliyor... ⚡️⏳",
        "hi": "🎧 Spotify से 320kbps में संगीत डाउनलोड हो रहा है... ⚡️⏳",
    },

    "platform_downloading": {
        "fa": "⚡️ در حال دانلود محتوا از {platform}... لطفاً چند لحظه صبر کن ⏳🏎",
        "en": "⚡️ Downloading content from {platform}... Please wait a moment ⏳🏎",
        "ar": "⚡️ جارٍ التحميل من {platform}... يرجى الانتظار ⏳🏎",
        "ru": "⚡️ Скачиваю с {platform}... Пожалуйста, подождите ⏳🏎",
        "zh": "⚡️ 正在从 {platform} 下载内容... 请稍候 ⏳🏎",
        "de": "⚡️ Lade Inhalt von {platform} herunter... Bitte kurz warten ⏳🏎",
        "es": "⚡️ Descargando contenido de {platform}... Por favor espera ⏳🏎",
        "fr": "⚡️ Téléchargement depuis {platform}... Veuillez patienter ⏳🏎",
        "tr": "⚡️ {platform} üzerinden indiriliyor... Lütfen bekleyin ⏳🏎",
        "hi": "⚡️ {platform} से डाउनलोड हो रहा है... कृपया प्रतीक्षा करें ⏳🏎",
    },

    "err_private": {
        "fa": "🔒 <b>محتوا یا پیج خصوصیه (Private):</b>\n\nربات امکان دسترسی به پیج‌های قفل‌شده و پرایوت را ندارد. لطفاً مطمئن شوید پیج عمومیه (Public) 🥺💔",
        "en": "🔒 <b>Private Content / Account:</b>\n\nThis account or post is private. The bot can only download from public profiles 🥺💔",
        "ar": "🔒 <b>حساب أو منشور خاص (Private):</b>\n\nالبوت لا يمكنه تحميل المنشورات من الحسابات الخاصة. يرجى التأكد من أن الحساب عام 🥺💔",
        "ru": "🔒 <b>Приватный аккаунт или публикация:</b>\n\nБот не может скачивать из закрытых профилей. Убедитесь, что аккаунт публичный 🥺💔",
        "zh": "🔒 <b>私密账号或内容：</b>\n\n机器人无法下载私密账号的内容，请确保链接来自公开账号 🥺💔",
        "de": "🔒 <b>Privates Konto / Privater Inhalt:</b>\n\nDer Bot kann keine Inhalte von privaten Konten herunterladen 🥺💔",
        "es": "🔒 <b>Contenido o cuenta privada:</b>\n\nEl bot no puede descargar desde cuentas privadas. Asegúrate de que el perfil sea público 🥺💔",
        "fr": "🔒 <b>Contenu ou compte privé :</b>\n\nLe bot ne peut pas télécharger depuis des comptes privés 🥺💔",
        "tr": "🔒 <b>Gizli Hesap / İçerik:</b>\n\nBot gizli hesaplardan içerik indiremez. Lütfen hesabın herkese açık olduğundan emin olun 🥺💔",
        "hi": "🔒 <b>प्राइवेट अकाउंट या पोस्ट:</b>\n\nबॉट प्राइवेट प्रोफाइल से डाउनलोड नहीं कर सकता। कृपया सुनिश्चित करें कि अकाउंट पब्लिक है 🥺💔",
    },

    "err_general": {
        "fa": "⚠️ <b>یه مشکلی پیش اومد:</b>\n\nدانلود ناموفق بود یا سرور مبدا پاسخ نداد. لطفاً چند لحظه بعد دوباره امتحان کن 🔄❤️",
        "en": "⚠️ <b>Something went wrong:</b>\n\nDownload failed or the host server did not respond. Please try again in a few moments 🔄❤️",
        "ar": "⚠️ <b>حدث خطأ ما:</b>\n\nفشل التحميل أو الخادم لا يستجيب. يرجى المحاولة مرة أخرى بعد قليل 🔄❤️",
        "ru": "⚠️ <b>Произошла ошибка:</b>\n\nНе удалось скачать или сервер не отвечает. Пожалуйста, попробуйте еще раз позже 🔄❤️",
        "zh": "⚠️ <b>下载出错：</b>\n\n下载失败或源服务器未响应，请稍后重试 🔄❤️",
        "de": "⚠️ <b>Etwas ist schiefgelaufen:</b>\n\nDownload fehlgeschlagen oder Server antwortet nicht. Bitte später erneut versuchen 🔄❤️",
        "es": "⚠️ <b>Ocurrió un error:</b>\n\nFalló la descarga o el servidor no responde. Por favor inténtalo de nuevo más tarde 🔄❤️",
        "fr": "⚠️ <b>Une erreur est survenue :</b>\n\nLe téléchargement a échoué ou le serveur ne répond pas. Veuillez réessayer 🔄❤️",
        "tr": "⚠️ <b>Bir sorun oluştu:</b>\n\nİndirme başarısız oldu veya sunucu yanıt vermedi. Lütfen birazdan tekrar deneyin 🔄❤️",
        "hi": "⚠️ <b>कुछ गलत हो गया:</b>\n\nडाउनलोड विफल रहा या सर्वर ने जवाब नहीं दिया। कृपया कुछ समय बाद पुनः प्रयास करें 🔄❤️",
    },

    "help_unsupported": {
        "fa": (
            "👋 سلام رفیق!\n\n"
            "من ربات همه‌کاره‌ی دانلود هستم و لینک‌های زیر رو سریع برات دانلود می‌کنم ⚡️📱\n\n"
            "▫️ <b>اینستاگرام (Instagram):</b> ریلز، پست، عکس، استوری 🎬\n"
            "▫️ <b>یوتیوب (YouTube):</b> ویدیو با کیفیت دلخواه + نسخه صوتی 📺\n"
            "▫️ <b>اسپاتیفای (Spotify) و ساندکلاد (SoundCloud):</b> دانلود مستقیم موزیک 🎧\n"
            "▫️ <b>تیک‌تاک، توییتر و پینترست</b> 📌\n\n"
            "فقط کافیه لینک مورد نظرت رو برام بفرستی! 😉👇"
        ),
        "en": (
            "👋 Hello!\n\n"
            "I am an all-in-one media downloader bot. Send me links from: ⚡️📱\n\n"
            "▫️ <b>Instagram:</b> Reels, posts, stories & photos 🎬\n"
            "▫️ <b>YouTube:</b> Quality selection & MP3 audio 📺\n"
            "▫️ <b>Spotify & SoundCloud:</b> High quality music 🎧\n"
            "▫️ <b>TikTok, Twitter/X & Pinterest</b> 📌\n\n"
            "Just send me any link to download! 😉👇"
        ),
        "ar": (
            "👋 مرحباً!\n\n"
            "أنا بوت تحميل الوسائط المتكامل. يمكنك إرسال روابط من: ⚡️📱\n\n"
            "▫️ <b>إنستغرام:</b> ريلز، منشورات، ستوري وصور 🎬\n"
            "▫️ <b>يوتيوب:</b> جودات مختلفة وملفات MP3 📺\n"
            "▫️ <b>سبوتيفاي وساوند كلاود:</b> موسيقى بجودة عالية 🎧\n"
            "▫️ <b>تيك توك، تويتر وبنتريست</b> 📌\n\n"
            "فقط أرسل الرابط وسأقوم بتحميله فوراً! 😉👇"
        ),
        "ru": (
            "👋 Привет!\n\n"
            "Я универсальный бот для загрузки контента. Отправьте ссылку из: ⚡️📱\n\n"
            "▫️ <b>Instagram:</b> Reels, посты, фото и истории 🎬\n"
            "▫️ <b>YouTube:</b> Выбор качества и MP3 аудио 📺\n"
            "▫️ <b>Spotify и SoundCloud:</b> Музыка в высоком качестве 🎧\n"
            "▫️ <b>TikTok, Twitter (X) и Pinterest</b> 📌\n\n"
            "Просто отправьте ссылку! 😉👇"
        ),
        "zh": (
            "👋 您好！\n\n"
            "我是全能媒体下载机器人，支持以下平台：⚡️📱\n\n"
            "▫️ <b>Instagram：</b> Reels短视频、多图帖子、快拍与照片 🎬\n"
            "▫️ <b>YouTube：</b> 多分辨率视频及MP3音频 📺\n"
            "▫️ <b>Spotify 与 SoundCloud：</b> 高品质音乐 🎧\n"
            "▫️ <b>TikTok、Twitter / X 与 Pinterest</b> 📌\n\n"
            "只需发送链接给我即可立即下载！😉👇"
        ),
        "de": (
            "👋 Hallo!\n\n"
            "Ich bin dein All-in-One-Downloader. Sende mir Links von: ⚡️📱\n\n"
            "▫️ <b>Instagram:</b> Reels, Beiträge, Stories & Fotos 🎬\n"
            "▫️ <b>YouTube:</b> Qualitätswahl & MP3-Audio 📺\n"
            "▫️ <b>Spotify & SoundCloud:</b> Musik in bester Qualität 🎧\n"
            "▫️ <b>TikTok, Twitter/X & Pinterest</b> 📌\n\n"
            "Sende mir einfach einen Link! 😉👇"
        ),
        "es": (
            "👋 ¡Hola!\n\n"
            "Soy un bot descargador todo en uno. Envíame enlaces de: ⚡️📱\n\n"
            "▫️ <b>Instagram:</b> Reels, publicaciones, historias y fotos 🎬\n"
            "▫️ <b>YouTube:</b> Calidad a elegir y audio MP3 📺\n"
            "▫️ <b>Spotify y SoundCloud:</b> Música en alta calidad 🎧\n"
            "▫️ <b>TikTok, Twitter/X y Pinterest</b> 📌\n\n"
            "¡Solo envíame un enlace para descargar! 😉👇"
        ),
        "fr": (
            "👋 Bonjour !\n\n"
            "Je suis un bot de téléchargement tout-en-un. Envoyez-moi des liens de : ⚡️📱\n\n"
            "▫️ <b>Instagram :</b> Reels, publications, stories & photos 🎬\n"
            "▫️ <b>YouTube :</b> Choix de qualité et audio MP3 📺\n"
            "▫️ <b>Spotify & SoundCloud :</b> Musique en haute qualité 🎧\n"
            "▫️ <b>TikTok, Twitter/X & Pinterest</b> 📌\n\n"
            "Envoyez simplement un lien pour télécharger ! 😉👇"
        ),
        "tr": (
            "👋 Merhaba!\n\n"
            "Ben hepsi bir arada medya indirici botum. Desteklenen siteler: ⚡️📱\n\n"
            "▫️ <b>Instagram:</b> Reels, gönderi, hikaye ve fotoğraflar 🎬\n"
            "▫️ <b>YouTube:</b> Kalite seçeneği ve MP3 ses 📺\n"
            "▫️ <b>Spotify & SoundCloud:</b> Yüksek kaliteli müzikler 🎧\n"
            "▫️ <b>TikTok, Twitter/X ve Pinterest</b> 📌\n\n"
            "İndirmek için bağlantıyı göndermeniz yeterli! 😉👇"
        ),
        "hi": (
            "👋 नमस्ते!\n\n"
            "मैं ऑल-इन-वन मीडिया डाउनलोडर बॉट हूँ। इन प्लेटफॉर्म से लिंक भेजें: ⚡️📱\n\n"
            "▫️ <b>Instagram:</b> Reels, पोस्ट, स्टोरी और तस्वीरें 🎬\n"
            "▫️ <b>YouTube:</b> विभिन्न क्वालिटी और MP3 ऑडियो 📺\n"
            "▫️ <b>Spotify और SoundCloud:</b> हाई क्वालिटी संगीत 🎧\n"
            "▫️ <b>TikTok, Twitter/X और Pinterest</b> 📌\n\n"
            "डाउनलोड करने के लिए बस लिंक भेजें! 😉👇"
        ),
    },
}

def get_text(key: str, lang: str = "fa", **kwargs) -> str:
    lang_map = TEXTS.get(key, {})
    text = lang_map.get(lang) or lang_map.get("en") or lang_map.get("fa", "")
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
