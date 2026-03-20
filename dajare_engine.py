"""
ダジャレエンジン - 母音変換・一致率計算の純粋Pythonモジュール
New_oogiri_argアルゴリズムのSTEP5,6,7を担当
"""

from dataclasses import dataclass, field


# ============================================================
# かな → (子音, 母音番号) マッピング
# 母音番号: a=1, i=2, u=3, e=4, o=5, ん=6, ー=7, っ=8
# ============================================================

# 拗音（2文字組み合わせ）を先にチェック
COMBO_KANA = {
    # きゃ行
    'きゃ': ('ky', 1), 'きゅ': ('ky', 3), 'きょ': ('ky', 5),
    'ぎゃ': ('gy', 1), 'ぎゅ': ('gy', 3), 'ぎょ': ('gy', 5),
    # しゃ行
    'しゃ': ('sh', 1), 'しゅ': ('sh', 3), 'しょ': ('sh', 5),
    'じゃ': ('j', 1), 'じゅ': ('j', 3), 'じょ': ('j', 5),
    # ちゃ行
    'ちゃ': ('ch', 1), 'ちゅ': ('ch', 3), 'ちょ': ('ch', 5),
    # にゃ行
    'にゃ': ('ny', 1), 'にゅ': ('ny', 3), 'にょ': ('ny', 5),
    # ひゃ行
    'ひゃ': ('hy', 1), 'ひゅ': ('hy', 3), 'ひょ': ('hy', 5),
    'びゃ': ('by', 1), 'びゅ': ('by', 3), 'びょ': ('by', 5),
    'ぴゃ': ('py', 1), 'ぴゅ': ('py', 3), 'ぴょ': ('py', 5),
    # みゃ行
    'みゃ': ('my', 1), 'みゅ': ('my', 3), 'みょ': ('my', 5),
    # りゃ行
    'りゃ': ('ry', 1), 'りゅ': ('ry', 3), 'りょ': ('ry', 5),
    # カタカナ拗音
    'キャ': ('ky', 1), 'キュ': ('ky', 3), 'キョ': ('ky', 5),
    'ギャ': ('gy', 1), 'ギュ': ('gy', 3), 'ギョ': ('gy', 5),
    'シャ': ('sh', 1), 'シュ': ('sh', 3), 'ショ': ('sh', 5),
    'ジャ': ('j', 1), 'ジュ': ('j', 3), 'ジョ': ('j', 5),
    'チャ': ('ch', 1), 'チュ': ('ch', 3), 'チョ': ('ch', 5),
    'ニャ': ('ny', 1), 'ニュ': ('ny', 3), 'ニョ': ('ny', 5),
    'ヒャ': ('hy', 1), 'ヒュ': ('hy', 3), 'ヒョ': ('hy', 5),
    'ビャ': ('by', 1), 'ビュ': ('by', 3), 'ビョ': ('by', 5),
    'ピャ': ('py', 1), 'ピュ': ('py', 3), 'ピョ': ('py', 5),
    'ミャ': ('my', 1), 'ミュ': ('my', 3), 'ミョ': ('my', 5),
    'リャ': ('ry', 1), 'リュ': ('ry', 3), 'リョ': ('ry', 5),
    # 外来語系
    'ティ': ('t', 2), 'ディ': ('d', 2),
    'ファ': ('f', 1), 'フィ': ('f', 2), 'フェ': ('f', 4), 'フォ': ('f', 5),
    'ヴァ': ('v', 1), 'ヴィ': ('v', 2), 'ヴ': ('v', 3), 'ヴェ': ('v', 4), 'ヴォ': ('v', 5),
    'ウィ': ('w', 2), 'ウェ': ('w', 4), 'ウォ': ('w', 5),
    'ツァ': ('ts', 1), 'ツィ': ('ts', 2), 'ツェ': ('ts', 4), 'ツォ': ('ts', 5),
    'デュ': ('dy', 3), 'テュ': ('ty', 3),
}

# 単一かな
SINGLE_KANA = {
    # ひらがな
    'あ': ('', 1), 'い': ('', 2), 'う': ('', 3), 'え': ('', 4), 'お': ('', 5),
    'か': ('k', 1), 'き': ('k', 2), 'く': ('k', 3), 'け': ('k', 4), 'こ': ('k', 5),
    'さ': ('s', 1), 'し': ('sh', 2), 'す': ('s', 3), 'せ': ('s', 4), 'そ': ('s', 5),
    'た': ('t', 1), 'ち': ('ch', 2), 'つ': ('ts', 3), 'て': ('t', 4), 'と': ('t', 5),
    'な': ('n', 1), 'に': ('n', 2), 'ぬ': ('n', 3), 'ね': ('n', 4), 'の': ('n', 5),
    'は': ('h', 1), 'ひ': ('h', 2), 'ふ': ('h', 3), 'へ': ('h', 4), 'ほ': ('h', 5),
    'ま': ('m', 1), 'み': ('m', 2), 'む': ('m', 3), 'め': ('m', 4), 'も': ('m', 5),
    'や': ('y', 1), 'ゆ': ('y', 3), 'よ': ('y', 5),
    'ら': ('r', 1), 'り': ('r', 2), 'る': ('r', 3), 'れ': ('r', 4), 'ろ': ('r', 5),
    'わ': ('w', 1), 'を': ('w', 5),
    'ん': ('n', 6),
    'っ': ('', 8),
    'ー': ('', 7),
    # 濁音
    'が': ('g', 1), 'ぎ': ('g', 2), 'ぐ': ('g', 3), 'げ': ('g', 4), 'ご': ('g', 5),
    'ざ': ('z', 1), 'じ': ('z', 2), 'ず': ('z', 3), 'ぜ': ('z', 4), 'ぞ': ('z', 5),
    'だ': ('d', 1), 'ぢ': ('d', 2), 'づ': ('d', 3), 'で': ('d', 4), 'ど': ('d', 5),
    'ば': ('b', 1), 'び': ('b', 2), 'ぶ': ('b', 3), 'べ': ('b', 4), 'ぼ': ('b', 5),
    # 半濁音
    'ぱ': ('p', 1), 'ぴ': ('p', 2), 'ぷ': ('p', 3), 'ぺ': ('p', 4), 'ぽ': ('p', 5),
    # カタカナ
    'ア': ('', 1), 'イ': ('', 2), 'ウ': ('', 3), 'エ': ('', 4), 'オ': ('', 5),
    'カ': ('k', 1), 'キ': ('k', 2), 'ク': ('k', 3), 'ケ': ('k', 4), 'コ': ('k', 5),
    'サ': ('s', 1), 'シ': ('sh', 2), 'ス': ('s', 3), 'セ': ('s', 4), 'ソ': ('s', 5),
    'タ': ('t', 1), 'チ': ('ch', 2), 'ツ': ('ts', 3), 'テ': ('t', 4), 'ト': ('t', 5),
    'ナ': ('n', 1), 'ニ': ('n', 2), 'ヌ': ('n', 3), 'ネ': ('n', 4), 'ノ': ('n', 5),
    'ハ': ('h', 1), 'ヒ': ('h', 2), 'フ': ('h', 3), 'ヘ': ('h', 4), 'ホ': ('h', 5),
    'マ': ('m', 1), 'ミ': ('m', 2), 'ム': ('m', 3), 'メ': ('m', 4), 'モ': ('m', 5),
    'ヤ': ('y', 1), 'ユ': ('y', 3), 'ヨ': ('y', 5),
    'ラ': ('r', 1), 'リ': ('r', 2), 'ル': ('r', 3), 'レ': ('r', 4), 'ロ': ('r', 5),
    'ワ': ('w', 1), 'ヲ': ('w', 5),
    'ン': ('n', 6),
    'ッ': ('', 8),
    'ー': ('', 7),
    # カタカナ濁音
    'ガ': ('g', 1), 'ギ': ('g', 2), 'グ': ('g', 3), 'ゲ': ('g', 4), 'ゴ': ('g', 5),
    'ザ': ('z', 1), 'ジ': ('z', 2), 'ズ': ('z', 3), 'ゼ': ('z', 4), 'ゾ': ('z', 5),
    'ダ': ('d', 1), 'ヂ': ('d', 2), 'ヅ': ('d', 3), 'デ': ('d', 4), 'ド': ('d', 5),
    'バ': ('b', 1), 'ビ': ('b', 2), 'ブ': ('b', 3), 'ベ': ('b', 4), 'ボ': ('b', 5),
    # カタカナ半濁音
    'パ': ('p', 1), 'ピ': ('p', 2), 'プ': ('p', 3), 'ペ': ('p', 4), 'ポ': ('p', 5),
}


@dataclass
class WordData:
    """単語データ"""
    text: str                # 元テキスト（漢字・カタカナ等）
    reading: str             # かな読み
    consonants: list = field(default_factory=list)  # 子音リスト
    vowel_pattern: list = field(default_factory=list)  # 母音番号パターン
    score: int = 0           # 連想スコア（0-100）
    source: str = ""         # "subject" or "modifier"
    number: int = 0          # クラスター内番号


@dataclass
class Combination:
    """ワード組み合わせ"""
    word_a: WordData         # 主語クラスターの単語
    word_b: WordData         # 修飾語クラスターの単語
    association_score: float # 連想値組み合わせスコア F(x1,x2)
    vowel_match_rate: float  # 母音一致率（%）
    vowel_match_count: int   # 母音一致数
    total_vowels: int        # 合計母音数
    match_positions: list = field(default_factory=list)  # 一致箇所
    total_score: float = 0.0 # 総合ランキングスコア
    dajare_condition: int = 0  # 達成したダジャレ一致条件（1,2,3 or 0）


def kana_to_vowel_pattern(reading: str) -> tuple:
    """
    かな文字列を(子音リスト, 母音番号リスト)に変換する。
    例: 'タイマン' → (['t','','m','n'], [1,2,1,6])
    """
    consonants = []
    vowels = []
    i = 0
    while i < len(reading):
        # 2文字の拗音を先にチェック
        if i + 1 < len(reading):
            two_char = reading[i:i+2]
            if two_char in COMBO_KANA:
                c, v = COMBO_KANA[two_char]
                consonants.append(c)
                vowels.append(v)
                i += 2
                continue

        # 1文字のかな
        char = reading[i]
        if char in SINGLE_KANA:
            c, v = SINGLE_KANA[char]
            consonants.append(c)
            vowels.append(v)
        else:
            # 変換できない文字はスキップ（スペース、記号等）
            pass
        i += 1

    return consonants, vowels


def convert_word(text: str, reading: str, score: int = 0,
                 source: str = "", number: int = 0) -> WordData:
    """単語をWordDataに変換"""
    consonants, vowels = kana_to_vowel_pattern(reading)
    return WordData(
        text=text,
        reading=reading,
        consonants=consonants,
        vowel_pattern=vowels,
        score=score,
        source=source,
        number=number,
    )


def find_consecutive_matches(pattern_a: list, pattern_b: list) -> list:
    """
    2つの母音パターン間の連続一致を見つける。
    アルゴリズム仕様: 2文字以上連続しない一致はカウント対象外。
    短い方を基準に、全てのオフセットでスライドして最良の一致を探す。

    Returns: 一致位置のリスト [(a_idx, b_idx), ...]
    """
    if not pattern_a or not pattern_b:
        return []

    best_matches = []
    len_a = len(pattern_a)
    len_b = len(pattern_b)

    # pattern_aをpattern_bの各位置にアラインして比較
    for offset in range(-(len_a - 1), len_b):
        current_run = []
        matches_in_this_alignment = []

        for i in range(len_a):
            j = i + offset
            if 0 <= j < len_b:
                if pattern_a[i] == pattern_b[j]:
                    current_run.append((i, j))
                else:
                    if len(current_run) >= 2:
                        matches_in_this_alignment.extend(current_run)
                    current_run = []
            else:
                if len(current_run) >= 2:
                    matches_in_this_alignment.extend(current_run)
                current_run = []

        # 最後のランを処理
        if len(current_run) >= 2:
            matches_in_this_alignment.extend(current_run)

        if len(matches_in_this_alignment) > len(best_matches):
            best_matches = matches_in_this_alignment

    return best_matches


def calculate_vowel_match(word_a: WordData, word_b: WordData) -> dict:
    """
    2つの単語の母音一致率を計算する。

    Returns: {
        'match_count': int,      # 一致数
        'total_vowels': int,     # 合計母音数（分母）
        'match_rate': float,     # 一致率（%）
        'match_positions': list, # 一致位置
        'a_coverage': float,     # Aの母音カバー率（%）
        'b_coverage': float,     # Bの母音カバー率（%）
    }
    """
    pa = word_a.vowel_pattern
    pb = word_b.vowel_pattern

    if not pa or not pb:
        return {
            'match_count': 0, 'total_vowels': 0,
            'match_rate': 0.0, 'match_positions': [],
            'a_coverage': 0.0, 'b_coverage': 0.0,
        }

    matches = find_consecutive_matches(pa, pb)
    match_count = len(matches)
    total = len(pa) + len(pb)

    # 各単語のカバー率
    a_matched = len(set(m[0] for m in matches))
    b_matched = len(set(m[1] for m in matches))

    return {
        'match_count': match_count,
        'total_vowels': total,
        'match_rate': (match_count * 2 / total * 100) if total > 0 else 0.0,
        'match_positions': matches,
        'a_coverage': (a_matched / len(pa) * 100) if pa else 0.0,
        'b_coverage': (b_matched / len(pb) * 100) if pb else 0.0,
    }


def association_combination_score(score_a: int, score_b: int) -> float:
    """
    連想値の組み合わせスコアを計算する。
    F(x1, x2) = (x1 + x2) * |x1 - x2|

    このスコアは「2つの単語の合計の勢い」に「ギャップ（意外性）」を
    掛け合わせた構造。A+B（高連想+低連想）が最高スコアになり、
    A+A（高同士）やC+C（中同士）は低くなる。
    """
    return (score_a + score_b) * abs(score_a - score_b)


def check_dajare_condition(match_info: dict) -> int:
    """
    ダジャレ一致条件3項目のどれを達成しているか判定。

    条件1: 母音一致率50%以上
    条件2: どちらかの単語の母音カバー率が100%
    条件3: 母音一致数が6以上

    Returns: 達成した条件番号(1,2,3) or 0(未達成)
    """
    if match_info['match_rate'] >= 50:
        return 1
    if match_info['a_coverage'] >= 100 or match_info['b_coverage'] >= 100:
        return 2
    if match_info['match_count'] >= 6:
        return 3
    return 0


def calculate_all_combinations(
    subject_cluster: list[WordData],
    modifier_cluster: list[WordData],
) -> list[Combination]:
    """
    全クラスターの組み合わせを計算し、ダジャレの卵を抽出する。

    Args:
        subject_cluster: 主語クラスター（WordDataリスト）
        modifier_cluster: 修飾語クラスター（WordDataリスト）

    Returns:
        ダジャレ一致条件を満たす組み合わせのリスト（スコア順）
    """
    dajare_eggs = []

    for wa in subject_cluster:
        for wb in modifier_cluster:
            # 母音一致率計算
            match_info = calculate_vowel_match(wa, wb)

            # ダジャレ一致条件チェック
            condition = check_dajare_condition(match_info)
            if condition == 0:
                continue

            # 連想値組み合わせスコア
            assoc_score = association_combination_score(wa.score, wb.score)

            # 総合スコア = 連想値スコア × 母音一致率の重み付け
            # 母音一致率が高いほどダジャレとして成立しやすい
            match_weight = 1 + (match_info['match_rate'] / 100)
            total_score = assoc_score * match_weight

            combo = Combination(
                word_a=wa,
                word_b=wb,
                association_score=assoc_score,
                vowel_match_rate=match_info['match_rate'],
                vowel_match_count=match_info['match_count'],
                total_vowels=match_info['total_vowels'],
                match_positions=match_info['match_positions'],
                total_score=total_score,
                dajare_condition=condition,
            )
            dajare_eggs.append(combo)

    # 総合スコアで降順ソート
    dajare_eggs.sort(key=lambda c: c.total_score, reverse=True)
    return dajare_eggs


def determine_technique(combo: Combination) -> str:
    """
    ダジャレ技法を判定する。

    - 一致率100%（完全一致）: 掛け言葉
    - 片方のカバー率100%: 造語
    - 一致率50%以上で子音も一致: 連結
    - その他: ダブルミーニング / 布団が吹っ飛んだ形式
    """
    match_info = calculate_vowel_match(combo.word_a, combo.word_b)

    if match_info['match_rate'] >= 95:
        return "掛け言葉"

    if match_info['a_coverage'] >= 100 or match_info['b_coverage'] >= 100:
        return "造語"

    if match_info['match_rate'] >= 50:
        # 子音一致もチェック
        has_consonant_match = False
        for pos_a, pos_b in match_info['match_positions']:
            if (pos_a < len(combo.word_a.consonants) and
                pos_b < len(combo.word_b.consonants)):
                if combo.word_a.consonants[pos_a] == combo.word_b.consonants[pos_b]:
                    has_consonant_match = True
                    break
        if has_consonant_match:
            return "連結"
        return "ダブルミーニング"

    return "布団が吹っ飛んだ形式"


def format_vowel_pattern(word: WordData) -> str:
    """母音パターンを文字列で表示（デバッグ用）"""
    return "-".join(str(v) for v in word.vowel_pattern)


def format_combination(combo: Combination, rank: int = 0) -> dict:
    """組み合わせを表示用辞書に変換"""
    technique = determine_technique(combo)
    return {
        "rank": rank,
        "subject_word": combo.word_a.text,
        "subject_reading": combo.word_a.reading,
        "subject_vowels": format_vowel_pattern(combo.word_a),
        "subject_score": combo.word_a.score,
        "modifier_word": combo.word_b.text,
        "modifier_reading": combo.word_b.reading,
        "modifier_vowels": format_vowel_pattern(combo.word_b),
        "modifier_score": combo.word_b.score,
        "association_score": combo.association_score,
        "vowel_match_rate": round(combo.vowel_match_rate, 1),
        "vowel_match_count": combo.vowel_match_count,
        "total_score": round(combo.total_score, 1),
        "technique": technique,
        "dajare_condition": combo.dajare_condition,
    }
