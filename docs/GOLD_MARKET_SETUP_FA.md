# Gold Market — مراحل B و C

## تصمیم مرحله B
- XAUUSD و DXY: Yahoo Finance Chart غیررسمی، برچسب DELAYED؛ تأخیر دقیق تضمین نمی‌شود.
- US10Y: FRED DGS10، روزانه.
- US02Y: FRED DGS2، روزانه.
- USOIL: FRED DCOILWTICO، روزانه و مربوط به WTI.
- SPX: FRED SP500، روزانه.
- VIX: FRED VIXCLS، روزانه.

DTWEXBGS معادل دقیق DXY نیست و GC=F نیز جایگزین Spot XAUUSD نمی‌شود.

## مرحله C
providers.py شامل آداپتورهای FRED و Yahoo است. collector.py هفت شاخص را جمع‌آوری و خطای هر شاخص را جدا نگه می‌دارد. اجرای python -m apps.gold_market فقط خروجی JSON تشخیصی می‌دهد و پیام تلگرام ارسال نمی‌کند.

تنظیم لازم: FRED_API_KEY. توکن تلگرام در این مرحله لازم نیست. اجرای تست: python -m unittest discover -s tests -p 'test_gold_market_*.py' -v

Yahoo منبع غیررسمی است؛ شرایط استفاده، پایداری و تأخیر آن تضمین نشده است. داده‌های FRED در این سری‌ها روزانه‌اند. در نبود داده، مقدار ساختگی تولید نمی‌شود و وضعیت UNAVAILABLE ثبت می‌شود. تشخیص STALE، تحلیل و Market Bias در مراحل بعدی تکمیل خواهند شد.
