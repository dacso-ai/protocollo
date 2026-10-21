"""Controlla con regole fisse che i documenti scritti dal modello rispettino il prompt.

Per ogni documento di genera_llm.py:
- se l'etichetta dice "scade tra N giorni", nel testo deve esserci "N giorni" (anche in lettere) o la data esatta;
- se dice "nessuna scadenza", nel testo non devono comparire espressioni come "entro il 12/11" o "scadenza";
- niente segnaposto tra parentesi quadre, niente markdown, lunghezza ragionevole.
I documenti che passano vanno in --ok, gli altri in --scarti con il motivo.

Uso: python3 verifica.py ../dati/pilota.jsonl --ok ../dati/pilota-ok.jsonl --scarti ../dati/pilota-scarti.jsonl
"""
import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

NUMERI = {3: "tre", 5: "cinque", 7: "sette", 8: "otto", 10: "dieci", 15: "quindici", 20: "venti", 30: "trenta",
          40: "quaranta", 45: "quarantacinque", 60: "sessanta", 90: "novanta"}
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]
TERMINE = re.compile(r"\bentro\s+(il|e non oltre|i?\s*\d|\d+\s*(giorni|gg)|la data|le ore)|\bscadenz|\btermine (di|perentorio)\b", re.I)


def date_possibili(d):
    return {d.strftime("%d/%m/%Y"), f"{d.day}/{d.month}/{d.year}", d.strftime("%d.%m.%Y"), d.strftime("%d-%m-%Y"),
            f"{d.day} {MESI[d.month - 1]} {d.year}", d.strftime("%d/%m/%y")}


def problemi(doc):
    intestazione, _, corpo = doc["stato"].partition("\n")
    testo = corpo.lower()
    motivi = []
    e = doc["etichette"]
    if e.get("scadenza") is True and e.get("giorni") is not None:
        n = e["giorni"]
        ricevuta = datetime.strptime(re.search(r"\d{2}/\d{2}/\d{4}", intestazione).group(), "%d/%m/%Y")
        trovato = re.search(rf"\b{n}\s*(giorni|gg|gg\.)", testo) or (n in NUMERI and re.search(rf"\b{NUMERI[n]}\b", testo))
        trovato = trovato or any(x in testo for x in date_possibili(ricevuta + timedelta(days=n)))
        if not trovato:
            motivi.append(f"non trovo il termine di {n} giorni né la data esatta")
    if e.get("scadenza") is False and TERMINE.search(testo):
        motivi.append(f"dovrebbe essere senza scadenza ma c'è \"{TERMINE.search(testo).group()}\"")
    if re.search(r"\[[^\]]{2,40}\]", corpo):
        motivi.append("segnaposto tra parentesi quadre")
    if re.search(r"(^|\n)#{1,3} |\*\*", corpo):
        motivi.append("markdown")
    if len(corpo.split()) < 8:
        motivi.append("troppo corto")
    return motivi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ingresso", type=Path)
    ap.add_argument("--ok", type=Path, required=True)
    ap.add_argument("--scarti", type=Path, required=True)
    a = ap.parse_args()
    buoni = scartati = 0
    with a.ok.open("w") as ok, a.scarti.open("w") as scarti:
        for riga in a.ingresso.open():
            doc = json.loads(riga)
            motivi = problemi(doc)
            doc["meta"]["verifica_regole"] = motivi or "ok"
            if motivi:
                scartati += 1
                scarti.write(json.dumps(doc, ensure_ascii=False) + "\n")
                print(f"✗ {doc['id']} {doc['fonte']}: {'; '.join(motivi)}")
            else:
                buoni += 1
                ok.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"Passano {buoni}, scartati {scartati}")


if __name__ == "__main__":
    main()
