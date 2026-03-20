"""
大喜利お題スクレイパー - oogiri.app/realtime からお題を取得

oogiri.appはSPA（JavaScript描画）のため、
リストページからお題IDを取得し、各お題ページのog:titleからテキストを取得する。
"""

import requests
import re


def _get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "ja,en;q=0.9",
    })
    return s


def fetch_odai_list(page: int = 1):
    """
    oogiri.app/realtime からお題リストを取得する。

    Returns:
        list[dict] or dict with "error" key
    """
    session = _get_session()

    # 1. リストページからお題IDを取得
    try:
        resp = session.get(
            f"https://oogiri.app/realtime?page={page}",
            timeout=15
        )
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"oogiri.appに接続できません: {e}"}

    ids = re.findall(r'"/realtime/odai/([a-zA-Z0-9]+)"', resp.text)

    # 重複除去 (順序保持)
    seen = set()
    unique_ids = []
    for oid in ids:
        if oid not in seen:
            seen.add(oid)
            unique_ids.append(oid)

    if not unique_ids:
        return {"error": "お題一覧を取得できませんでした"}

    # 2. 各お題ページの <title> からテキスト取得（直列で安全に）
    result = []
    for oid in unique_ids[:10]:
        try:
            r = session.get(
                f"https://oogiri.app/realtime/odai/{oid}",
                timeout=10
            )
            r.encoding = "utf-8"
            m = re.search(r"<title>([^<]+)</title>", r.text)
            if m:
                text = re.sub(r"^回答一覧:\s*", "", m.group(1)).strip()
                if text:
                    result.append({"id": oid, "text": text})
        except Exception:
            continue

    return result if result else {"error": "お題テキストを取得できませんでした"}
