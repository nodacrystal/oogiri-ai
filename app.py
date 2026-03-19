"""
大喜利回答ジェネレーター - Webアプリケーション
Flask + Claude API による大喜利回答生成ツール
"""

import os
import json
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic
from algorithm import OOGIRI_ALGORITHM, build_prompt, classify_odai

app = Flask(__name__)

# Claude APIクライアント
client = None

def get_client():
    global client
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY環境変数が設定されていません")
        client = Anthropic(api_key=api_key)
    return client


def generate_answers(odai: str, num_answers: int = 3, style: str = "バランス") -> dict:
    """Claude APIを使って大喜利の回答を生成する"""
    c = get_client()
    user_prompt = build_prompt(odai, num_answers, style)

    message = c.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=OOGIRI_ALGORITHM,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    response_text = message.content[0].text.strip()

    # JSONブロックを抽出（```json...```で囲まれている場合に対応）
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        result = {
            "answers": [
                {
                    "answer": response_text,
                    "technique": "不明",
                    "explanation": "JSON解析に失敗しました"
                }
            ]
        }

    result["odai_pattern"] = classify_odai(odai)
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    odai = data.get("odai", "").strip()
    num_answers = data.get("num_answers", 3)
    style = data.get("style", "バランス")

    if not odai:
        return jsonify({"error": "お題を入力してください"}), 400

    if num_answers < 1 or num_answers > 10:
        num_answers = 3

    try:
        result = generate_answers(odai, num_answers, style)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"回答生成に失敗しました: {str(e)}"}), 500


@app.route("/algorithm")
def show_algorithm():
    """アルゴリズムの説明ページ"""
    return render_template("algorithm.html", algorithm=OOGIRI_ALGORITHM)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
