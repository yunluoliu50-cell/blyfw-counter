#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blyfw-counter fetcher
Logs into my.blyfw.cn developer center and reads the cumulative access_total,
then writes it to count.json for the app to display.

Credentials come from environment (GitHub Actions Secrets), never hardcoded.
"""
import json
import os
import sys
import time
import re
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "http://my.blyfw.cn"
USER = os.environ.get("MY_USER", "")
PASS = os.environ.get("MY_PASS", "")
OUT = "count.json"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def make_opener():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar)
    )
    opener.addheaders = [("User-Agent", UA)]
    return opener, jar


def http_get(opener, url, timeout=25):
    req = urllib.request.Request(url)
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.geturl()


def http_post(opener, url, data, timeout=25):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.geturl()


def extract_csrf(html):
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    return m.group(1) if m else None


def login(opener):
    # 1. GET login page to obtain csrf + session cookie
    html, _ = http_get(opener, BASE + "/login.php")
    csrf = extract_csrf(html)
    if not csrf:
        raise RuntimeError("could not find _csrf token on login page")
    # 2. POST credentials
    _, final = http_post(opener, BASE + "/login.php", {
        "_csrf": csrf,
        "username": USER,
        "password": PASS,
    })
    # success normally redirects into /user/*
    if "/user/" not in final:
        raise RuntimeError("login failed (landed on: %s)" % final)


def fetch_total(opener):
    raw, _ = http_get(opener, BASE + "/mimap-dev/geo_api.php?range=all")
    data = json.loads(raw)
    if data.get("code") == 0:
        raise RuntimeError("not logged in: " + data.get("msg", ""))
    total = data.get("access_total")
    if total is None:
        total = data.get("auth_total", 0)
    return int(total or 0), data


def main():
    if not USER or not PASS:
        print("Missing MY_USER/MY_PASS environment", file=sys.stderr)
        return 1
    opener, _ = make_opener()
    login(opener)
    total, data = fetch_total(opener)
    payload = {
        "total": total,
        "unit": "次",
        "label": "历史启动",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "geo_api?range=all",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("total =", total)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
