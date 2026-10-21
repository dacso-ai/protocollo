"""Verifica i documenti di genera_llm.py con un secondo modello, diverso da quello che li ha scritti.

Il verificatore legge il documento senza vedere le etichette e risponde in JSON: tipo, scadenza,
giorni, phishing, dati sensibili. Il documento resta solo se le sue risposte coincidono con le
etichette decise dal programma (giorni con una tolleranza di 2). Così si scartano i testi in cui
il modello generatore non ha rispettato il prompt o è stato ambiguo. Le truffe che ingannano il
verificatore restano, segnate in meta come "difficile".

Uso: python3 verifica_llm.py ../dati/llm-ok.jsonl --ok ../dati/llm-verificati.jsonl --scarti ../dati/llm-scartati.jsonl
Si può interrompere e riprendere: i documenti già in --ok o --scarti vengono saltati.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI))
from genera_llm import SERVIZI, chiama, leggi_env  # noqa: E402

DOMANDE = json.loads((QUI.parent / "protocollo" / "domande.json").read_text())["domande"]
TIPI = "\n".join(f"- {o['id']}: {o['description']}" for o in DOMANDE["tipo"]["options"])

PROMPT = """Leggi questo documento ricevuto da un'azienda italiana e rispondi SOLO con un oggetto JSON, senza altro testo:
{{"tipo": "...", "scadenza": true/false, "giorni": numero o null, "phishing": true/false, "dati_sensibili": true/false}}

- tipo: uno di questi id
{tipi}
- scadenza: il documento indica un termine o una data entro cui l'azienda deve fare qualcosa (pagare, rispondere, restituire, firmare, impugnare)?
- giorni: quanti giorni mancano a quel termine contando dalla data "Ricevuto il" in alto; null se non c'è un termine o non si può calcolare
- phishing: è una truffa (finto ente, finto fornitore, link sospetti, cambio IBAN, richiesta di credenziali o bonifici urgenti)?
- dati_sensibili: contiene dati sulla salute, dati giudiziari di una persona, dati di minori o copia di un documento d'identità?

DOCUMENTO:
{documento}"""


def leggi_json(testo):
    testo = re.sub(r"<think>.*?</think>", "", testo, flags=re.S)
    m = re.search(r"\{.*\}", testo, re.S)
    return json.loads(m.group()) if m else None


def confronta(etichette, risposta):
    motivi = []
    for chiave in ("tipo", "phishing", "dati_sensibili", "scadenza"):
        if chiave in etichette and risposta.get(chiave) != etichette[chiave]:
            motivi.append(f"{chiave}: {risposta.get(chiave)} invece di {etichette[chiave]}")
    if "giorni" in etichette:
        atteso, visto = etichette["giorni"], risposta.get("giorni")
        if atteso is None and visto is not None and etichette.get("scadenza") is False:
            motivi.append(f"giorni: {visto} invece di nessuna scadenza")
        elif atteso is not None and (not isinstance(visto, (int, float)) or abs(visto - atteso) > 2):
            motivi.append(f"giorni: {visto} invece di {atteso}")
    return motivi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ingresso", type=Path)
    ap.add_argument("--ok", type=Path, required=True)
    ap.add_argument("--scarti", type=Path, required=True)
    ap.add_argument("--servizio", choices=SERVIZI, default="openrouter")
    ap.add_argument("--modello", default="mistralai/mistral-small-3.2-24b-instruct")
    ap.add_argument("--ragionamento", action="store_true", help="lascia ragionare il modello (più lento e costoso)")
    ap.add_argument("--paralleli", type=int, default=8)
    ap.add_argument("--max-dollari", type=float, default=2.0)
    ap.add_argument("--limite", type=int, help="verifica solo i primi N documenti")
    a = ap.parse_args()
    base, nome_chiave, _ = SERVIZI[a.servizio]
    leggi_env()
    chiave = os.environ.get(nome_chiave) or sys.exit(f"Manca {nome_chiave} in .env")

    fatti = set()
    for f in (a.ok, a.scarti):
        if f.exists():
            fatti |= {json.loads(riga)["id"] for riga in f.open()}
    docs = [json.loads(riga) for riga in a.ingresso.open()]
    docs = [d for d in docs if d["id"] not in fatti][: a.limite]
    print(f"{len(docs)} documenti da verificare con {a.modello} ({len(fatti)} già fatti)")

    spesa, buoni, scartati = 0.0, 0, 0
    with a.ok.open("a") as ok, a.scarti.open("a") as scarti, ThreadPoolExecutor(a.paralleli) as pool:
        futuri = {pool.submit(chiama, base, chiave, a.modello, PROMPT.format(tipi=TIPI, documento=d["stato"]),
                              temperatura=0, ragionamento=a.ragionamento): d for d in docs}
        for k, fut in enumerate(as_completed(futuri), 1):
            d = futuri[fut]
            try:
                risposta = fut.result()
                spesa += float(risposta.get("usage", {}).get("cost") or 0)
                letto = leggi_json(risposta["choices"][0]["message"].get("content") or "")
            except Exception as e:  # errore di rete o JSON illeggibile: si riprova alla prossima esecuzione
                print(f"[{k}] {d['id']} errore: {str(e)[:150]}", flush=True)
                continue
            if letto is None:
                print(f"[{k}] {d['id']} risposta senza JSON", flush=True)
                continue
            motivi = confronta(d["etichette"], letto)
            # una truffa che inganna il verificatore è un esempio difficile, non un errore: l'etichetta è certa
            # per costruzione (mittente falso scelto dal programma), quindi resta e viene segnata
            if d["etichette"].get("phishing") and motivi and all(m.startswith(("tipo:", "phishing:")) for m in motivi):
                d["meta"]["difficile"] = True
                motivi = []
            d["meta"]["verifica_modello"] = {"modello": a.modello, "risposta": letto, "esito": motivi or "ok"}
            (scarti if motivi else ok).write(json.dumps(d, ensure_ascii=False) + "\n")
            buoni += not motivi
            scartati += bool(motivi)
            if k % 200 == 0 or motivi and scartati <= 20:
                print(f"[{k}/{len(docs)}] {d['id']} {d['fonte']}: {'; '.join(motivi) or 'ok'} · spesa {spesa:.3f} $", flush=True)
            if spesa > a.max_dollari:
                print(f"Superato il tetto di {a.max_dollari} $: mi fermo.")
                pool.shutdown(cancel_futures=True)
                break
    print(f"Passano {buoni}, scartati {scartati}. Spesa {spesa:.3f} $")


if __name__ == "__main__":
    main()
