#!/usr/bin/env python3
"""بديل وهمي لـ cloudflared في الاختبارات: يطبع رابط نفق ثم ينتظر. الاسم يُقرأ من ملف بجانبه ليتغير بين تشغيل وآخر."""
import sys
import time
from pathlib import Path

f = Path(__file__).with_name("fake_tunnel_name.txt")
name = f.read_text().strip() if f.exists() else "alpha-beta"
print("2026-10-03T00:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...", flush=True)
print(f"2026-10-03T00:00:01Z INF |  https://{name}.trycloudflare.com  |", flush=True)
if "--url" not in sys.argv:
    sys.exit(2)
time.sleep(600)
