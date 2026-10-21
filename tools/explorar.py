import re, sys, requests
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
for url in sys.argv[1:]:
    print("=" * 30, url)
    try:
        r = requests.get(url, headers=H, timeout=60)
        print("status", r.status_code, r.headers.get("content-type"))
        t = r.text
        if "json" in r.headers.get("content-type", ""):
            print(t[:3000]); continue
        t = re.sub(r"(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>", "", t)
        t = re.sub(r"(?s)<!--.*?-->", "", t)
        m = re.search(r"(?s)<main.*?</main>", t)
        t = m.group(0) if m else t
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r'<(\w+)[^>]*?(class="[^"]*")?[^>]*>', lambda m: f"<{m.group(1)} {m.group(2) or ''}>", t)
        print(t[:9000])
    except Exception as e:
        print("ERR", e)
