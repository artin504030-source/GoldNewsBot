# راه‌اندازی ارسال تلگرامی Gold Market

## معماری اجرا

- زمان‌بندی با cron-job.org انجام می‌شود؛ در GitHub Actions هیچ cron یا schedule تعریف نشده است.
- Cron-job.org با یک درخواست HTTP از نوع POST، اجرای دستی workflow با نام `Gold Market Telegram Delivery` را در شاخه `feat/gold-market-foundation` آغاز می‌کند.
- فایل workflow فقط با `workflow_dispatch` اجرا می‌شود و گزارش را می‌سازد و به تلگرام می‌فرستد.
- این workflow از توکن و مقصد اختصاصی Gold Market استفاده می‌کند و از اسرار Gold News و Gold Prices استفاده نمی‌کند.

## اسرار موردنیاز GitHub

در Settings → Secrets and variables → Actions این دو secret را بسازید:

- `GOLD_MARKET_BOT_TOKEN`: توکن ربات اختصاصی Gold Market
- `GOLD_MARKET_CHAT_ID`: شناسه کانال یا گروه مقصد Gold Market

`FRED_API_KEY` نیز مانند مراحل قبلی برای داده‌های FRED استفاده می‌شود. هیچ توکن یا شناسه‌ای را در کد یا فایل workflow قرار ندهید.

## تنظیم Cron-job.org

یک Job با روش POST و نشانی زیر بسازید:

`https://api.github.com/repos/artin504030-source/GoldNewsBot/actions/workflows/gold_market_telegram.yml/dispatches`

Headerها:

- `Accept: application/vnd.github+json`
- `Authorization: Bearer <GITHUB_FINE_GRAINED_TOKEN>`
- `X-GitHub-Api-Version: 2022-11-28`
- `Content-Type: application/json`

Body:

`{"ref":"feat/gold-market-foundation"}`

برای توکن GitHub از Fine-grained personal access token با دسترسی فقط به همین repository و مجوز Actions: Read and write استفاده کنید. مقدار توکن را فقط در بخش امن Headerهای Cron-job.org وارد کنید؛ آن را در گفتگو یا کد ذخیره نکنید.

بازه زمانی Job را در Cron-job.org تعیین کنید. نسخه فعلی گزارش برای اجرای ساعتی طراحی شده است.

## جلوگیری از ارسال تکراری

Workflow اجراها را پشت سر هم پردازش می‌کند و با GitHub Actions cache برای هر ساعت UTC یک کلید جداگانه نگه می‌دارد. اگر در همان ساعت دوباره فراخوانی شود و نشانگر موجود باشد، ارسال را رد می‌کند. این محافظ در برابر اجرای تکراری معمول است؛ cache دائمی یا تضمین ریاضی exactly-once نیست.

## اجرای دستی کنترل‌شده

از Actions → Gold Market Telegram Delivery → Run workflow می‌توان یک اجرای دستی انجام داد. تا زمانی که دو secret اختصاصی اضافه نشده‌اند، ارسال به‌صورت امن با خطای تنظیمات متوقف می‌شود.

## مرزهای ایمنی

- گزارش با روند `UNAVAILABLE` ارسال نمی‌شود.
- پیام‌ها با HTML escape‌شده و در اندازه مجاز تلگرام تولید می‌شوند.
- خطای Telegram یا پاسخ نامعتبر باعث fail شدن workflow می‌شود.
- هیچ زمان‌بندی GitHub Actions اضافه نشده است.
- هیچ تغییری در ربات‌ها و workflowهای Gold News و Gold Prices انجام نمی‌شود.
