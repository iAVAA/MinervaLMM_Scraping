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
    # 1. Base Token Level Metrics (Precision, Recall, F1)
    parsed_tokens = tokenize(parsed_text)
    gold_tokens = tokenize(gold_text)
    
    intersection = parsed_tokens.intersection(gold_tokens)
    
    precision = len(intersection) / len(parsed_tokens) if parsed_tokens else 0.0
    recall = len(intersection) / len(gold_tokens) if gold_tokens else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # 2. Jaccard Index (Character 3-grams)
    p_3grams = get_ngrams(parsed_text.lower(), 3)
    g_3grams = get_ngrams(gold_text.lower(), 3)
    inter_3g = p_3grams.intersection(g_3grams)
    union_3g = p_3grams.union(g_3grams)
    jaccard = len(inter_3g) / len(union_3g) if union_3g else 0.0

    # 3. ROUGE-L Score
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    g_str = normalize_text(gold_text)
    p_str = normalize_text(parsed_text)
    
    if not g_str:
        rouge_l = 0.0
        cer = 0.0
        wer = 0.0
    else:
        scores = scorer.score(g_str, p_str)
        rouge_l = scores['rougeL'].fmeasure
        
        # 4. Error Rates (CER / WER) via Levenshtein
        cer = Levenshtein.distance(p_str, g_str) / len(g_str)
        
        p_words = p_str.split()
        g_words = g_str.split()
        wer = Levenshtein.distance(p_words, g_words) / len(g_words) if g_words else 0.0
    # 5. Tag Leakage Rate (Heuristic Metric)
    # Cerca artefatti web rimasti nel payload: <tag>, class=, http://, &nbsp;, [] vuoti
    leakage_pattern = r'(<\/?\w+>|class=|http[s]?://|&\w+;|\[\s*\]|\(\s*\)|\{\s*\})'
    artifacts_found = len(re.findall(leakage_pattern, parsed_text, flags=re.IGNORECASE))
    p_words_count = len(parsed_tokens)
    leakage = artifacts_found / p_words_count if p_words_count > 0 else 0.0
    
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "jaccard": float(jaccard),
        "cer": float(cer),
        "wer": float(wer),
        "rouge_l": float(rouge_l),
        "leakage": float(leakage)
    }
