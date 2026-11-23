*** Update File: /tmp/GoldNewsBot-check/apps/gold_prices/bot.py
@@
 import urllib.parse
 import urllib.request
+import urllib.error
@@
-    with urllib.request.urlopen(request, timeout=20) as response:
-        result = json.loads(response.read().decode())
+    try:
+        with urllib.request.urlopen(request, timeout=20) as response:
+            result = json.loads(response.read().decode())
+    except urllib.error.HTTPError as exc:
+        detail = exc.read().decode("utf-8", errors="replace")
+        raise RuntimeError(f"Telegram API HTTP {exc.code}: {detail}") from exc
