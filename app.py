"""
大喜利ダジャレ回答ジェネレーター
New_oogiri_argアルゴリズムに基づくマルチステップダジャレ生成Webアプリ
"""

import os
import json
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from ai_steps import run_full_pipeline
from scraper import fetch_odai_list

app = Flask(__name__)

# 回答データベースをロード（参考用）
REFERENCE_ANSWERS = []
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "reference_answers.json")
if os.path.exists(DB_PATH):
    with open(DB_PATH, "r", encoding="utf-8") as f:
        REFERENCE_ANSWERS = json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """ダジャレ回答生成API（同期版）"""
    data = request.get_json()
    odai = data.get("odai", "").strip()

    if not odai:
        return jsonify({"error": "お題を入力してください"}), 400

    try:
        result = run_full_pipeline(
            odai=odai,
            reference_answers=REFERENCE_ANSWERS,
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"回答生成に失敗しました: {str(e)}"}), 500


@app.route("/generate-stream")
def generate_stream():
    """
    ダジャレ回答生成API（SSE ストリーム版）
    Server-Sent Events で各ステップの進捗をリアルタイム配信する。
    """
    odai = request.args.get("odai", "").strip()
    if not odai:
        return jsonify({"error": "お題を入力してください"}), 400

    def stream():
        events = []

        def on_progress(step, status, data=None):
            event = {
                "step": step,
                "status": status,
                "data": data or {},
                "timestamp": time.time(),
            }
            events.append(event)

        try:
            # パイプライン開始イベント
            yield f"data: {json.dumps({'step': 0, 'status': 'start', 'data': {'odai': odai}}, ensure_ascii=False)}\n\n"

            # 各ステップのコールバックで進捗を通知
            # （同期実行のため、コールバックで溜めて後で送信ではなく、
            #   パイプラインを分割して段階的に送信する）

            from ai_steps import (
                step1_parse_odai, step2_generate_clusters,
                step5_generate_answers
            )
            from dajare_engine import (
                calculate_all_combinations, format_combination
            )

            # Step 1
            yield f"data: {json.dumps({'step': 1, 'status': 'processing', 'data': {'message': 'お題を主語と修飾語に分解中...'}}, ensure_ascii=False)}\n\n"

            parsed = step1_parse_odai(odai)
            subject = parsed.get("subject", "")
            modifiers = parsed.get("modifiers", [])

            yield f"data: {json.dumps({'step': 1, 'status': 'done', 'data': {'subject': subject, 'modifiers': modifiers, 'reasoning': parsed.get('reasoning', '')}}, ensure_ascii=False)}\n\n"

            # Step 2
            modifier_str = '、'.join(modifiers)
            yield f"data: {json.dumps({'step': 2, 'status': 'processing', 'data': {'message': f'関連ワードクラスター生成中...（主語: {subject} / 修飾語: {modifier_str}）'}}, ensure_ascii=False)}\n\n"

            clusters = step2_generate_clusters(subject, modifiers)
            sub_cluster = clusters["subject_cluster"]
            mod_cluster = clusters["modifier_cluster"]

            step2_data = {
                "subject_cluster_size": len(sub_cluster),
                "modifier_cluster_size": len(mod_cluster),
                "subject_samples": [
                    {"text": w.text, "reading": w.reading, "score": w.score}
                    for w in sub_cluster[:5]
                ],
                "modifier_samples": [
                    {"text": w.text, "reading": w.reading, "score": w.score}
                    for w in mod_cluster[:5]
                ],
            }
            yield f"data: {json.dumps({'step': 2, 'status': 'done', 'data': step2_data}, ensure_ascii=False)}\n\n"

            # Step 3-4
            total_combos = len(sub_cluster) * len(mod_cluster)
            yield f"data: {json.dumps({'step': 3, 'status': 'processing', 'data': {'message': f'母音パターン変換 & {total_combos}通りの組み合わせを計算中...'}}, ensure_ascii=False)}\n\n"

            dajare_eggs = calculate_all_combinations(sub_cluster, mod_cluster)
            top_combos = [format_combination(c, i+1) for i, c in enumerate(dajare_eggs[:20])]

            step34_data = {
                "total_combinations": total_combos,
                "dajare_eggs_count": len(dajare_eggs),
                "top_combinations": top_combos[:10],
            }
            yield f"data: {json.dumps({'step': 3, 'status': 'done', 'data': step34_data}, ensure_ascii=False)}\n\n"

            # Step 5
            if not top_combos:
                yield f"data: {json.dumps({'step': 5, 'status': 'error', 'data': {'message': 'ダジャレの卵が見つかりませんでした'}}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {json.dumps({'step': 5, 'status': 'processing', 'data': {'message': 'ダジャレ回答を生成中...'}}, ensure_ascii=False)}\n\n"

            answers = step5_generate_answers(
                odai, subject, modifiers, top_combos, REFERENCE_ANSWERS
            )

            yield f"data: {json.dumps({'step': 5, 'status': 'done', 'data': {'answers': answers}}, ensure_ascii=False)}\n\n"

            # 完了
            yield f"data: {json.dumps({'step': 99, 'status': 'complete'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'step': -1, 'status': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/fetch-odai")
def fetch_odai():
    """oogiri.appからお題を取得するAPI"""
    page = request.args.get("page", 1, type=int)
    try:
        result = fetch_odai_list(page)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500
        return jsonify({"odai_list": result, "page": page})
    except Exception as e:
        return jsonify({"error": f"お題の取得に失敗しました: {str(e)}"}), 500


@app.route("/algorithm")
def show_algorithm():
    """アルゴリズム解説ページ"""
    return render_template("algorithm.html")


@app.route("/health")
def health():
    """ヘルスチェック"""
    has_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gemini = bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    return jsonify({
        "status": "ok",
        "claude_api": has_claude,
        "gemini_api": has_gemini,
        "reference_db_size": len(REFERENCE_ANSWERS),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
