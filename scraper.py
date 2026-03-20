"""
大喜利お題スクレイパー - oogiri.app/realtime からお題を取得

oogiri.appはSPA（シングルページアプリケーション）のため、
お題テキストはHTMLに直接含まれない。
アプローチ:
1. リストページからお題IDを取得
2. 各お題ページのog:titleメタタグからテキストを取得
"""

import requests
import re
import concurrent.futures


def _fetch_single_odai(odai_id: str, session: requests.Session) -> dict:
    """単一のお題ページからテキストを取得"""
    url = f"https://oogiri.app/realtime/odai/{odai_id}"
    try:
        resp = session.get(url, timeout=10)
        resp.encoding = 'utf-8'

        # og:title から取得（「回答一覧: お題テキスト」形式）
        match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', resp.text)
        if not match:
            match = re.search(r'<title>([^<]*)</title>', resp.text)

        if match:
            title = match.group(1)
            # 「回答一覧: 」プレフィックスを除去
            text = re.sub(r'^回答一覧:\s*', '', title).strip()
            if text:
                return {"id": odai_id, "text": text}
    except requests.RequestException:
        pass
    return None


def fetch_odai_list(page: int = 1) -> list:
    """
    oogiri.app/realtime からお題リストを取得する。

    Args:
        page: ページ番号（1始まり）

    Returns:
        [{"id": "...", "text": "お題テキスト"}, ...] or {"error": "..."}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.9",
    }

    session = requests.Session()
    session.headers.update(headers)

    # Step 1: リストページからお題IDを取得
    list_url = f"https://oogiri.app/realtime?page={page}"
    try:
        resp = session.get(list_url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"サイトへの接続に失敗しました: {str(e)}"}

    # /realtime/odai/[ID] パターンのリンクを抽出
    odai_ids = re.findall(r'"/realtime/odai/([a-zA-Z0-9]+)"', resp.text)

    # 重複除去して順序保持
    seen = set()
    unique_ids = []
    for oid in odai_ids:
        if oid not in seen:
            seen.add(oid)
            unique_ids.append(oid)

    if not unique_ids:
        return {"error": "お題IDを取得できませんでした。サイトの構造が変更された可能性があります。"}

    # Step 2: 各お題ページからテキストを並列取得
    odai_list = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_fetch_single_odai, oid, session): oid
            for oid in unique_ids[:10]
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                odai_list.append(result)

    # 元のリスト順に並べ直す
    id_order = {oid: i for i, oid in enumerate(unique_ids)}
    odai_list.sort(key=lambda x: id_order.get(x["id"], 999))

    if not odai_list:
        return {"error": "お題テキストの取得に失敗しました。"}

    return odai_list
