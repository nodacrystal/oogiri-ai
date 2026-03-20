"""
AI連携ステップ - Claude/Gemini/GPTを使ったダジャレ生成パイプライン
New_oogiri_argアルゴリズムのSTEP1-4,8を担当
"""

import os
import json
import re
from anthropic import Anthropic
from dajare_engine import (
    WordData, Combination, convert_word,
    calculate_all_combinations, format_combination, determine_technique,
)

# ==========================================================
# APIクライアント初期化
# ==========================================================

_claude_client = None
_gemini_model = None


def get_claude():
    global _claude_client
    if _claude_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません。Replit の Secrets に追加してください。")
        _claude_client = Anthropic(api_key=api_key)
    return _claude_client


def get_gemini():
    """Gemini APIクライアント（任意。なければClaudeで代替）"""
    global _gemini_model
    if _gemini_model is None:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        except ImportError:
            return None
    return _gemini_model


def _call_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """Claude API呼び出しのヘルパー"""
    c = get_claude()
    msg = c.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def _call_gemini(prompt: str) -> str:
    """Gemini API呼び出し。利用不可ならNone"""
    model = get_gemini()
    if model is None:
        return None
    try:
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception:
        return None


def _extract_json(text: str) -> dict:
    """レスポンスからJSON部分を抽出"""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSONが壊れている場合のフォールバック
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


# ==========================================================
# STEP 1: お題を主語と修飾語に分解（Claude）
# ==========================================================

def step1_parse_odai(odai: str) -> dict:
    """
    お題から「主語（核）」と「修飾語（アテンション）」を抽出する。

    主語: お題の中心となる名詞（1つに絞る）
    修飾語: 主語を修飾・制限する要素（主語に関連するワードは除外）

    例: "こんな子守歌はイヤだ！どんな子守歌？"
    → 主語: "子守歌", 修飾語: ["嫌なこと"]
    """
    system = """あなたは大喜利の回答を生成するためのアルゴリズムの一部です。
お題を「主語（核）」と「修飾語」に分解してください。

【主語のルール】
- 単語を1つに絞ること
- お題の中心となる名詞を選ぶ
- 最もキーとなる言葉のみを抽出

【修飾語のルール】
- 主語を切り離した時に残る要素
- 主語に関連する言葉が修飾語に含まれる場合は削除する
- ワードは最小限に切り取る
- 疑問詞は含めない

【例外処理】
主語と修飾語の両方に同じワードが含まれる場合:
→ 修飾語からそのワードを削除する
理由: 同じ単語からダジャレを作っても意味がない

必ず以下のJSON形式で返してください:
{"subject": "主語", "modifiers": ["修飾語1", "修飾語2"], "reasoning": "分解の理由"}"""

    result = _call_claude(system, f"お題: {odai}")
    parsed = _extract_json(result)
    if not parsed:
        return {"subject": odai, "modifiers": [], "reasoning": "解析失敗"}
    return parsed


# ==========================================================
# STEP 2: 関連ワードクラスター生成（Gemini優先、Claude代替）
# ==========================================================

def _build_cluster_prompt(word: str, cluster_type: str, count: int,
                          exclude_words: list = None) -> str:
    """クラスター生成プロンプトを構築"""
    exclude_str = ""
    if exclude_words:
        exclude_str = f"\n【除外ワード】以下の言葉と意味が同じ/近すぎるワードは除外: {', '.join(exclude_words)}"

    return f"""あなたは大喜利ダジャレ生成アルゴリズムの一部です。
「{word}」に関連するワードを{count}個生成してください。

【生成ルール】
- 連想性の高い言葉を中心に、見た目、状況、トレンド、関連商品名、印象など多角的に
- 難しい言葉や専門用語は除外（小学生でもわかるレベル）
- 「{word}」を聞いた時に連想するワード、象徴するワードを高スコアに
- 「{word}」そのもの及びその別名は100点
- お題で使われている単語から直感的に連想できるワードを高得点に
- 専門知識が必要で直感的に連想できないワードは低得点に
{exclude_str}

【スコア基準（連想スコア）】
- 100点: 「{word}」そのもの、またはその別名
- 90-99点: 「{word}」と聞いて即座に連想する象徴的ワード
- 70-89点: 強く関連するが、他の意味も持つワード
- 50-69点: 関連はあるが、やや遠い連想
- 30-49点: 遠い連想だがダジャレの材料として面白い可能性あり
- 10-29点: かなり遠い連想

各ワードには必ず「かな読み」をカタカナで付けてください。

以下のJSON形式で返してください:
{{"words": [{{"text": "ワード", "reading": "カタカナヨミ", "score": 85, "reason": "理由"}}]}}"""


def step2_generate_clusters(subject: str, modifiers: list,
                            subject_count: int = 15,
                            modifier_count: int = 75) -> dict:
    """
    主語クラスターと修飾語クラスターを生成する。

    Gemini APIが利用可能ならGeminiを使用（大量生成が得意）。
    利用不可ならClaudeで代替。
    """
    modifier_str = "、".join(modifiers) if modifiers else "なし"

    # 主語クラスター生成
    sub_prompt = _build_cluster_prompt(subject, "主語", subject_count)
    mod_prompt = _build_cluster_prompt(
        modifier_str, "修飾語", modifier_count,
        exclude_words=[subject]  # 主語と重複するワードを除外
    )

    # Geminiを試行、失敗時はClaudeで代替
    sub_result = _call_gemini(sub_prompt)
    mod_result = _call_gemini(mod_prompt)

    if sub_result is None:
        sub_result = _call_claude(
            "大喜利ダジャレ生成アルゴリズムのワード生成エンジンです。指示に従いJSONのみ出力してください。",
            sub_prompt, max_tokens=4096
        )
    if mod_result is None:
        mod_result = _call_claude(
            "大喜利ダジャレ生成アルゴリズムのワード生成エンジンです。指示に従いJSONのみ出力してください。",
            mod_prompt, max_tokens=8192
        )

    sub_parsed = _extract_json(sub_result)
    mod_parsed = _extract_json(mod_result)

    # WordDataに変換
    subject_cluster = []
    if sub_parsed and "words" in sub_parsed:
        for i, w in enumerate(sub_parsed["words"][:subject_count]):
            wd = convert_word(
                text=w.get("text", ""),
                reading=w.get("reading", ""),
                score=w.get("score", 50),
                source="subject",
                number=i + 1,
            )
            subject_cluster.append(wd)

    modifier_cluster = []
    if mod_parsed and "words" in mod_parsed:
        for i, w in enumerate(mod_parsed["words"][:modifier_count]):
            wd = convert_word(
                text=w.get("text", ""),
                reading=w.get("reading", ""),
                score=w.get("score", 50),
                source="modifier",
                number=i + 1,
            )
            modifier_cluster.append(wd)

    return {
        "subject_cluster": subject_cluster,
        "modifier_cluster": modifier_cluster,
        "subject_raw": sub_parsed,
        "modifier_raw": mod_parsed,
    }


# ==========================================================
# STEP 3-4: 母音一致率計算 & ランキング（Python）
# → dajare_engine.py の calculate_all_combinations() が担当
# ==========================================================


# ==========================================================
# STEP 5: ダジャレ技法適用 & 大喜利回答生成（Claude）
# ==========================================================

def step5_generate_answers(odai: str, subject: str, modifiers: list,
                           top_combinations: list[dict],
                           reference_answers: list = None) -> list:
    """
    上位の組み合わせからダジャレを使った大喜利回答を生成する。

    NG技法:
    1. 回答にダジャレの元となる単語をフリとして入れない
    2. 回答に「（）」を使わない（読み方の説明禁止）
    """
    combos_text = ""
    for i, c in enumerate(top_combinations[:15]):
        combos_text += (
            f"{i+1}. [{c['subject_word']}({c['subject_reading']})] + "
            f"[{c['modifier_word']}({c['modifier_reading']})] "
            f"連想スコア:{c['association_score']:.0f} "
            f"母音一致率:{c['vowel_match_rate']}% "
            f"技法:{c['technique']}\n"
        )

    ref_text = ""
    if reference_answers:
        ref_text = "\n【参考：高評価の大喜利回答例】\n"
        for r in reference_answers[:10]:
            ref_text += f"お題: {r['odai']} → 回答: {r['answer']} (得票:{r['votes']})\n"

    system = """あなたは大喜利のダジャレ回答を生成する天才です。
与えられた「ワードの組み合わせ」からダジャレを作り、大喜利の回答として成立させてください。

【ダジャレ技法】
1. 掛け言葉（完全一致）: 主語クラスターの単語を修飾語クラスターに置き換えて文章作成
   例: 主語「秋」修飾語「飽き」→「飽きが来た」
2. 造語（片方100%一致）: 一致率100%の単語をもう片方に無理やり置き換え
   例: 主語「呂布カルマ」修飾語「祖父」→「祖父カルマ」
3. 連結（50%以上で子音一致）: 完全一致箇所をまとめて造語
   例: 主語「露天風呂」修飾語「ところてん」→「ところてん風呂」
4. ダブルミーニング: 同じ字面で異なる意味を利用
5. 布団が吹っ飛んだ形式: 音の類似性を活かした言葉遊び

【絶対NG】
NG1: 回答にダジャレの元となる単語をフリとして入れない
  NG例: 「こんな布団は嫌。どんなの？」→「布団が吹っ飛んだ」（×）
  OK例: 「こんな布団は嫌。どんなの？」→「布っ団だ」（○）
NG2: 回答に「（）」を一切使わない
  NG例: 「まぁいっかー（マイカー）」（×）
NG3: 説明しすぎない。回答は短く、わかりやすく。句読点不要な長さが理想。

【大喜利の回答ルール】
- 回答だけで元のダジャレの単語が1秒以内に理解できること
- お題の回答として成立していること
- くだらなければくだらないほど良い（低俗ほど高価）
- 短い方が良い"""

    user = f"""お題: {odai}
主語: {subject}
修飾語: {', '.join(modifiers)}

【ダジャレの卵（ワード組み合わせ上位）】
{combos_text}
{ref_text}

上記の組み合わせを使って、大喜利の回答を生成してください。
全ての組み合わせを試し、最も面白い回答を5つ選んでください。

以下のJSON形式で出力してください:
{{"answers": [
  {{
    "answer": "回答テキスト",
    "source_combo": "使用した組み合わせ番号",
    "technique": "使用した技法名",
    "dajare_words": "ダジャレの元となった2つのワード",
    "explanation": "なぜ面白いか（20文字以内）",
    "self_check": "NG技法に該当していないか確認結果"
  }}
]}}"""

    result = _call_claude(system, user, max_tokens=4096)
    parsed = _extract_json(result)
    if not parsed:
        return [{"answer": "生成に失敗しました", "technique": "なし", "explanation": "JSON解析エラー"}]
    return parsed.get("answers", [])


# ==========================================================
# 全ステップ統合: パイプライン実行
# ==========================================================

def run_full_pipeline(odai: str, reference_answers: list = None,
                      on_progress=None) -> dict:
    """
    New_oogiri_argアルゴリズムの全ステップを実行する。

    Args:
        odai: お題テキスト
        reference_answers: 参考回答データベース
        on_progress: 進捗コールバック fn(step, status, data)

    Returns:
        完全な結果辞書
    """
    def notify(step, status, data=None):
        if on_progress:
            on_progress(step, status, data)

    result = {"odai": odai, "steps": {}}

    # ── STEP 1: お題解析 ──
    notify(1, "processing", {"message": "お題を主語と修飾語に分解中..."})
    parsed = step1_parse_odai(odai)
    subject = parsed.get("subject", "")
    modifiers = parsed.get("modifiers", [])
    result["steps"]["step1"] = {
        "subject": subject,
        "modifiers": modifiers,
        "reasoning": parsed.get("reasoning", ""),
    }
    notify(1, "done", result["steps"]["step1"])

    # ── STEP 2: クラスター生成 ──
    notify(2, "processing", {"message": f"「{subject}」と「{'、'.join(modifiers)}」の関連ワードを生成中..."})
    clusters = step2_generate_clusters(subject, modifiers)
    sub_cluster = clusters["subject_cluster"]
    mod_cluster = clusters["modifier_cluster"]
    result["steps"]["step2"] = {
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
    notify(2, "done", result["steps"]["step2"])

    # ── STEP 3-4: 母音変換 & 組み合わせ計算 ──
    total_combos = len(sub_cluster) * len(mod_cluster)
    notify(3, "processing", {"message": f"母音パターン変換 & {total_combos}通りの組み合わせを計算中..."})

    dajare_eggs = calculate_all_combinations(sub_cluster, mod_cluster)

    # 上位の組み合わせを表示用に変換
    top_combos = [format_combination(c, i+1) for i, c in enumerate(dajare_eggs[:20])]

    result["steps"]["step3_4"] = {
        "total_combinations": total_combos,
        "dajare_eggs_count": len(dajare_eggs),
        "top_combinations": top_combos,
    }
    notify(3, "done", result["steps"]["step3_4"])

    # ── STEP 5: ダジャレ回答生成 ──
    if not top_combos:
        notify(5, "error", {"message": "ダジャレの卵が見つかりませんでした"})
        result["answers"] = []
        return result

    notify(5, "processing", {"message": f"上位{min(15, len(top_combos))}個の組み合わせからダジャレ回答を生成中..."})
    answers = step5_generate_answers(
        odai, subject, modifiers, top_combos, reference_answers
    )
    result["answers"] = answers
    notify(5, "done", {"answers": answers})

    return result
