import mistune
from bs4 import BeautifulSoup
import Levenshtein
from rouge_score import rouge_scorer
import re

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Remove the markdown using mistune and BeautifulSoup
    html = mistune.html(text)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        tag.unwrap()
    text = re.sub(r'[ \t]+', ' ', str(soup))    # collassa spazi orizzontali (non \n)
    text = re.sub(r'\n+', '\n', text)  # collassa nuove linee multiple in una sola
    text = text.strip()
    return text.lower()

def tokenize(text: str) -> set:
    norm = normalize_text(text)
    if not norm:
        return set()
    return set(norm.split())

def get_ngrams(text: str, n: int) -> set:
    norm = normalize_text(text)
    if not norm or len(norm) < n:
        return set()
    return set(norm[i:i+n] for i in range(len(norm)-n+1))

def token_level_eval(parsed_text: str, gold_text: str) -> dict:
    # Normalizza una volta sola e riusa
    g_str = normalize_text(gold_text)
    p_str = normalize_text(parsed_text)

    # 1. Token-level metrics (Precision, Recall, F1) — obbligatori
    parsed_tokens = tokenize(parsed_text)
    gold_tokens   = tokenize(gold_text)
    intersection  = parsed_tokens & gold_tokens

    precision = len(intersection) / len(parsed_tokens) if parsed_tokens else 0.0
    recall    = len(intersection) / len(gold_tokens)   if gold_tokens   else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    # 2. Jaccard su 3-grammi (FIX: usa p_str/g_str già normalizzati)
    p_3grams = get_ngrams(p_str, 3)
    g_3grams = get_ngrams(g_str, 3)
    union_3g  = p_3grams | g_3grams
    jaccard   = len(p_3grams & g_3grams) / len(union_3g) if union_3g else 0.0

    if not g_str:
        rouge_l = cer = wer = 0.0
    else:
        # 3. ROUGE-L
        scorer  = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        rouge_l = scorer.score(g_str, p_str)['rougeL'].fmeasure

        # 4. CER
        cer = Levenshtein.distance(p_str, g_str) / len(g_str)

        # 5. WER (FIX: rapidfuzz supporta liste, python-Levenshtein no)
        from rapidfuzz.distance import Levenshtein as RLev
        p_words = p_str.split()
        g_words = g_str.split()
        wer = RLev.distance(p_words, g_words) / len(g_words) if g_words else 0.0

    # 6. Tag leakage
    leakage_pattern = r'(<\/?\w+>|class=|http[s]?://|&\w+;|\[\s*\]|\(\s*\)|\{\s*\})'
    artifacts       = len(re.findall(leakage_pattern, parsed_text, flags=re.IGNORECASE))
    leakage         = artifacts / len(parsed_tokens) if parsed_tokens else 0.0

    return {
        "precision": float(precision),
        "recall":    float(recall),
        "f1":        float(f1),
        "jaccard":   float(jaccard),
        "cer":       float(cer),
        "wer":       float(wer),
        "rouge_l":   float(rouge_l),
        "leakage":   float(leakage),
    }