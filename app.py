"""
大喜利ダジャレ回答ジェネレーター
New_oogiri_argアルゴリズムに基づくマルチステップダジャレ生成Webアプリ
"""

import os
import json
import time
import traceback
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)

# 回答データベースをロード（参考用）
REFERENCE_ANSWERS = []
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "reference_answers.json")
try:
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            REFERENCE_ANSWERS = json.load(f)
except Exception:
    pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """ダジャレ回答生成API（同期版）"""
    from ai_steps import run_full_pipeline

    data = request.get_json()
    odai = data.get("odai", "").strip()

    if not odai:
        return jsonify({"error": "お題を入力してください"}), 400

    try:
        result = run_full_pipeline(odai=odai, reference_answers=REFERENCE_ANSWERS)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"回答生成に失敗しました: {e}"}), 500


@app.route("/generate-stream")
def generate_stream():
    """SSEストリームで各ステップの進捗をリアルタイム配信"""
    odai = request.args.get("odai", "").strip()
    if not odai:
        return jsonify({"error": "お題を入力してください"}), 400

    def _event(step, status, data=None):
        return f"data: {json.dumps({'step': step, 'status': status, 'data': data or {}}, ensure_ascii=False)}\n\n"

    def stream():
        try:
            from ai_steps import step1_parse_odai, step2_generate_clusters, step5_generate_answers
            from dajare_engine import calculate_all_combinations, format_combination

            yield _event(0, "start", {"odai": odai})

            # Step 1: お題解析
            yield _event(1, "processing", {"message": "お題を主語と修飾語に分解中..."})
            parsed = step1_parse_odai(odai)
            subject = parsed.get("subject", "")
            modifiers = parsed.get("modifiers", [])
            yield _event(1, "done", {"subject": subject, "modifiers": modifiers, "reasoning": parsed.get("reasoning", "")})

            # Step 2: クラスター生成
            yield _event(2, "processing", {"message": f"関連ワードクラスター生成中... (主語:{subject} 修飾語:{'、'.join(modifiers)})"})
            clusters = step2_generate_clusters(subject, modifiers)
            sub_c = clusters["subject_cluster"]
            mod_c = clusters["modifier_cluster"]
            yield _event(2, "done", {
                "subject_cluster_size": len(sub_c),
                "modifier_cluster_size": len(mod_c),
                "subject_samples": [{"text": w.text, "reading": w.reading, "score": w.score} for w in sub_c[:5]],
                "modifier_samples": [{"text": w.text, "reading": w.reading, "score": w.score} for w in mod_c[:5]],
            })

            # Step 3-4: 母音解析 & 組み合わせ
            total = len(sub_c) * len(mod_c)
            yield _event(3, "processing", {"message": f"母音解析 & {total}通りの組み合わせを計算中..."})
            eggs = calculate_all_combinations(sub_c, mod_c)
            top = [format_combination(c, i+1) for i, c in enumerate(eggs[:20])]
            yield _event(3, "done", {
                "total_combinations": total,
                "dajare_eggs_count": len(eggs),
                "top_combinations": top[:10],
            })

            # Step 5: 回答生成
            if not top:
                yield _event(5, "error", {"message": "ダジャレの卵が見つかりませんでした"})
                return
            yield _event(5, "processing", {"message": "ダジャレ回答を生成中..."})
            answers = step5_generate_answers(odai, subject, modifiers, top, REFERENCE_ANSWERS)
            yield _event(5, "done", {"answers": answers})

            yield _event(99, "complete")

        except Exception as e:
            yield _event(-1, "error", {"message": f"{e}\n{traceback.format_exc()}"})

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/fetch-odai")
def fetch_odai():
    """oogiri.appからお題を取得"""
    from scraper import fetch_odai_list

    page = request.args.get("page", 1, type=int)
    try:
        result = fetch_odai_list(page)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500
        return jsonify({"odai_list": result, "page": page})
    except Exception as e:
        return jsonify({"error": f"お題取得エラー: {e}"}), 500


@app.route("/algorithm")
def show_algorithm():
    return render_template("algorithm.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "claude_api": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gemini_api": bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")),
        "reference_db_size": len(REFERENCE_ANSWERS),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
