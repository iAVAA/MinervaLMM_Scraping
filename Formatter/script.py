import json
import re
import os

def clean_parsed_text(text: str) -> str:
    """
    Ripulisce il testo da note, link e rimpiazza i ritorni a capo con spazi.
    """
    # 1. Rimuove le note (es. [1], [12], ecc.)
    text = re.sub(r'\[\d+\]', '', text)
    
    # 2. Rimuove i link formattati in Markdown [Testo](https://...) -> lascia solo "Testo"
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 3. Rimuove eventuali URL nudi (http:// o https://) rimasti nel testo
    text = re.sub(r'https?://[^\s]+', '', text)
    
    # 4. Sostituisce TUTTI i ritorni a capo (\n) con uno spazio
    text = text.replace('\n', ' ')
    
    # 5. Pulizia estetica finale: rimuove gli spazi multipli che si formano
    # quando si sostituiscono i \n, riducendoli a uno spazio singolo.
    text = re.sub(r'\s{2,}', ' ', text).strip()
    
    return text

def main():
    # Definisce i percorsi dei file nella stessa cartella dello script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    html_path = os.path.join(base_dir, 'raw_html.txt')
    text_path = os.path.join(base_dir, 'raw_text.txt')
    output_path = os.path.join(base_dir, 'output.json')

    # Legge l'HTML esattamente com'è
    try:
        with open(html_path, 'r', encoding='utf-8') as f_html:
            raw_html_content = f_html.read()
    except FileNotFoundError:
        print(f"Errore: Il file {html_path} non è stato trovato.")
        return

    # Legge il Testo grezzo
    try:
        with open(text_path, 'r', encoding='utf-8') as f_text:
            raw_text_content = f_text.read()
    except FileNotFoundError:
        print(f"Errore: Il file {text_path} non è stato trovato.")
        return

    # Applica solo al testo la pulizia da link, note e \n
    cleaned_text = clean_parsed_text(raw_text_content)

    # Prepara la struttura dati
    data = {
        "html_text": raw_html_content, # Qui l'HTML è intatto
        "gold_text": cleaned_text    # Qui il testo è stato pulito
    }

    # Crea il JSON: json.dump applica gli slash (escaping) automaticamente e in modo sicuro
    with open(output_path, 'w', encoding='utf-8') as f_out:
        json.dump(data, f_out, ensure_ascii=False, indent=4)
    
    print(f"Fatto! JSON generato correttamente in: {output_path}")

if __name__ == "__main__":
    main()