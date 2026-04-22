"""
Percorso relativo: backend/src/evaluation.py
Corso: Laboratorio di ingegneria informatica
Corso di Laurea: Ingegneria informatica e automatica
Ateneo: Sapienza Università di Roma
Data: Aprile 2026
Autori: Matricole 2114420, 2115153, 2056502

Descrizione:
Questo modulo implementa una suite di funzioni di valutazione per misurare
la qualità e la fedeltà del testo estratto dai vari parser web (parsed_text) 
confrontandolo con una golden truth di riferimento (gold_text). 
Fornisce metriche eterogenee, tra cui F1-Score a livello di token, Indice di Jaccard 
sui n-grammi, ROUGE-L, Character Error Rate (CER), Word Error Rate (WER) e una 
metrica customizzata definita "Tag Leakage" per rilevare artefatti spuri.
"""

import mistune
from bs4 import BeautifulSoup
import Levenshtein
from rouge_score import rouge_scorer
import re

def normalize_text(text: str) -> str:
    """
    Normalizza la stringa di input rimuovendo la formattazione Markdown e HTML,
    e standardizzando le spaziature per preparare il testo all'analisi metrica.

    Args:
        text (str): La stringa di testo grezzo da elaborare.

    Returns:
        str: Il testo depurato da tag, collassato negli spazi e convertito in minuscolo.
             Ritorna una stringa vuota se l'input è nullo o vuoto.
    """
    if not text:
        return ""
    
    # Converte il Markdown in HTML e utilizza BeautifulSoup per estrarre solo il testo puro
    html = mistune.html(text)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        tag.unwrap()
        
    text = re.sub(r'[ \t]+', ' ', str(soup))    # Collassa spazi orizzontali e tabulazioni in un singolo spazio
    text = re.sub(r'\n+', '\n', text)  # Collassa sequenze di interruzioni di riga in una singola newline
    text = text.strip()
    
    return text.lower()

def tokenize(text: str) -> set:
    """
    Tokenizza una stringa in un insieme (set) di parole univoche,
    applicando preventivamente la normalizzazione.

    Args:
        text (str): Il testo di input da tokenizzare.

    Returns:
        set: Un insieme non ordinato di token (parole) univoci.
    """
    norm = normalize_text(text)
    if not norm:
        return set()
    return set(norm.split())

def get_ngrams(text: str, n: int) -> set:
    """
    Genera un insieme di n-grammi di caratteri a partire dalla stringa normalizzata,
    utile per valutazioni di similarità sub-word.

    Args:
        text (str): Il testo sorgente.
        n (int): La lunghezza (numero di caratteri) di ciascun n-gramma.

    Returns:
        set: L'insieme degli n-grammi generati. Restituisce un set vuoto se
             il testo è più corto di 'n'.
    """
    norm = normalize_text(text)
    if not norm or len(norm) < n:
        return set()
    return set(norm[i:i+n] for i in range(len(norm)-n+1))

def token_level_eval(parsed_text: str, gold_text: str) -> dict:
    """
    Esegue una pipeline di valutazione completa calcolando molteplici metriche
    di distanza e similarità tra il documento estratto e il ground truth.

    Args:
        parsed_text (str): Il testo finale prodotto dal processo di parsing.
        gold_text (str): Il testo di riferimento ideale (Golden Truth).

    Returns:
        dict: Un dizionario contenente i punteggi float per le seguenti metriche:
              precision, recall, f1, jaccard, cer, wer, rouge_l, leakage.
    """
    # Normalizzazione eseguita una singola volta per ottimizzare le performance
    g_str = normalize_text(gold_text)
    p_str = normalize_text(parsed_text)

    # 1. Calcolo delle metriche a livello di token (Precision, Recall, F1-Score)
    parsed_tokens = tokenize(parsed_text)
    gold_tokens   = tokenize(gold_text)
    intersection  = parsed_tokens & gold_tokens

    precision = len(intersection) / len(parsed_tokens) if parsed_tokens else 0.0
    recall    = len(intersection) / len(gold_tokens)   if gold_tokens   else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    # 2. Calcolo dell'indice di Jaccard operante sui 3-grammi di caratteri (su stringhe pre-normalizzate)
    p_3grams = get_ngrams(p_str, 3)
    g_3grams = get_ngrams(g_str, 3)
    union_3g  = p_3grams | g_3grams
    jaccard   = len(p_3grams & g_3grams) / len(union_3g) if union_3g else 0.0

    # Condizione di guardia: se non vi è ground truth, le metriche di distanza vengono azzerate
    if not g_str:
        rouge_l = cer = wer = 0.0
    else:
        # 3. Calcolo metrica ROUGE-L (Longest Common Subsequence) tramite libreria standard
        scorer  = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        rouge_l = scorer.score(g_str, p_str)['rougeL'].fmeasure

        # 4. Calcolo del CER (Character Error Rate) normalizzato sulla lunghezza del gold_text
        cer = Levenshtein.distance(p_str, g_str) / len(g_str)

        # 5. Calcolo del WER (Word Error Rate) utilizzando rapidfuzz per il supporto esplicito alle liste di token
        from rapidfuzz.distance import Levenshtein as RLev
        p_words = p_str.split()
        g_words = g_str.split()
        wer = RLev.distance(p_words, g_words) / len(g_words) if g_words else 0.0

    # 6. Analisi del "Tag Leakage": stima degli artefatti spuri (tag HTML residui, entità, link) sfuggiti alla pulizia
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