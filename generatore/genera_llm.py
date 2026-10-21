"""Genera documenti (avvisi, atti, mail, truffe...) con un modello linguistico, a partire da catalogo.py.

Il modello scrive solo il corpo del documento. Intestazione (data di ricezione, canale, mittente) ed
etichette le decide il programma. Funziona con qualunque servizio compatibile con le API di OpenAI:
OpenRouter (anche i modelli :free), Groq, Cerebras.

La chiave si legge da .env nella cartella del progetto (mai nel codice):
  OPENROUTER_API_KEY=...      oppure GROQ_API_KEY=... / CEREBRAS_API_KEY=...

Uso:
  python3 genera_llm.py --n 5 --a-secco                      # mostra i prompt e la stima dei costi, senza chiamate
  python3 genera_llm.py --n 50 --out pilota.jsonl            # pilota con il modello predefinito
  python3 genera_llm.py --n 50 --servizio groq --modello openai/gpt-oss-120b
I documenti già presenti in --out vengono saltati: si può interrompere e riprendere.
Licenza del modello: usare solo modelli che permettono di addestrare altri modelli sulle risposte
(Apache-2.0, MIT, NVIDIA Open Model License...). Niente Claude, GPT, Gemini o Gemma.
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI))
import catalogo  # noqa: E402
import genera  # noqa: E402

SERVIZI = {
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "gpt-oss-120b"),
}


def leggi_env():
    env = QUI.parent / ".env"
    if env.exists():
        for riga in env.read_text().splitlines():
            if "=" in riga and not riga.lstrip().startswith("#"):
                k, v = riga.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def prepara(r, i, seed, scenario_id=None):
    """Sceglie scenario e parametri, costruisce prompt, intestazione ed etichette."""
    s = catalogo.scegli(r, scenario_id)
    noi, altro = genera.azienda(r), genera.azienda(r)
    persona = genera.persona(r)
    ricevuta = genera.data_ricezione(r)
    indirizzo, canale = catalogo.mittente(r, s["canale"], noi, altro, persona)
    stile = r.choice(catalogo.STILI[s["stili"]])
    parole = r.choice([60, 100, 150, 220, 320]) if s["stili"] != "cliente" else r.choice([15, 30, 60, 120])

    etichette = {"tipo": s["tipo"], **s["etichette"], "phishing": s["etichette"].get("phishing", False),
                 "dati_sensibili": bool(s.get("sensibili"))}
    termine = s["termine"]
    if termine is None:
        regola_termine = "Il documento NON deve indicare nessuna scadenza, termine o data entro cui fare qualcosa."
        etichette |= {"scadenza": False, "giorni": None}
    elif termine == "dentro":
        regola_termine = "Il documento indica la data dell'udienza, tra quattro-sei mesi, e i termini di legge per costituirsi."
        etichette["scadenza"] = True
    elif termine == "libero":
        regola_termine = "Può indicare date (per esempio la consegna richiesta) come in un documento vero."
    elif termine == "truffa":
        regola_termine = "Può mettere fretta (ore o pochi giorni) come fanno le truffe."
    else:
        giorni = r.randint(*termine)
        if r.random() < 0.5:
            regola_termine = f"Il termine è di {giorni} giorni dal ricevimento o dalla notifica: scrivilo in questa forma, senza indicare la data esatta."
        else:
            regola_termine = f"Il termine è il {genera.gg(ricevuta + timedelta(days=giorni))}: indica questa data esatta."
        etichette |= {"scadenza": True, "giorni": giorni}
    if s.get("sensibili"):
        regola_dati = "Deve contenere dati personali particolari come indicato nella descrizione (salute, dati giudiziari o documento d'identità)."
    else:
        regola_dati = "Non deve contenere dati sulla salute, dati giudiziari di persone, dati di minori né copie di documenti d'identità."

    prompt = f"""Scrivi il testo di un documento ricevuto da un'azienda italiana. Rispondi SOLO con il testo del documento: niente commenti, niente titoli tuoi, niente markdown, niente segnaposto tra parentesi quadre.

Cos'è: {s['descrizione']}
Destinatario: {noi['denominazione']}, {noi['sede']['via']}, {noi['sede']['cap']} {noi['sede']['comune']} ({noi['sede']['prov']}), P.IVA {noi['piva']}.
Mittente: il testo deve essere coerente con l'indirizzo {indirizzo}. Se serve un nome di persona usa {persona['denominazione']}; se serve un'altra azienda usa {altro['denominazione']} di {altro['sede']['comune']}.
Ricevuto il: {genera.gg(ricevuta)} (le date nel testo devono essere coerenti con questa).
Termine: {regola_termine}
Dati personali: {regola_dati}
Stile: {stile}.
Lunghezza: circa {parole} parole.
Importi, numeri di protocollo, codici e nomi devono essere verosimili ma inventati.
Regole: usa esattamente i nomi indicati sopra (niente Mario Rossi o nomi d'esempio); niente codici finti come 01234567890 o 12345; niente grassetto, asterischi o altro markdown; non scrivere mai etichette che spiegano il documento (per esempio "dati sensibili", "truffa", "scadenza:") se un documento vero non le avrebbe."""
    if canale == "WhatsApp":
        intestazione = f"Ricevuto il {genera.gg(ricevuta)} via WhatsApp da {indirizzo}\n\n"
    else:
        intestazione = f"Ricevuto il {genera.gg(ricevuta)} via {canale} da {indirizzo}\n"
    return {"id": f"llm-{seed}-{i:06d}", "fonte": f"llm/{s['tipo']}/{s['id']}", "gruppi": ["documento"],
            "prompt": prompt, "intestazione": intestazione, "etichette": etichette,
            "meta": {"scenario": s["id"], "stile": stile, "parole": parole, "canale": canale}}


def chiama(base, chiave, modello, prompt, tentativi=5):
    corpo = {"model": modello, "messages": [{"role": "user", "content": prompt}], "temperature": 0.9, "max_tokens": 2500}
    if "openrouter" in base:
        corpo["usage"] = {"include": True}
    req = urllib.request.Request(base + "/chat/completions", json.dumps(corpo).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {chiave}",
                                  "HTTP-Referer": "https://github.com/dacso-ai/protocollo", "X-Title": "Protocollo"})
    for n in range(tentativi):
        try:
            with urllib.request.urlopen(req, timeout=180) as risposta:
                return json.load(risposta)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < tentativi - 1:
                time.sleep(min(60, 5 * 2 ** n))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}") from None
        except (urllib.error.URLError, TimeoutError):
            if n == tentativi - 1:
                raise
            time.sleep(5 * 2 ** n)


def pulisci(testo):
    testo = re.sub(r"<think>.*?</think>", "", testo, flags=re.S).strip()
    testo = re.sub(r"^```\w*\n|\n```$", "", testo).strip()
    testo = re.sub(r"\*\*(.+?)\*\*", r"\1", testo)  # grassetto markdown
    return re.sub(r"[ \t]+\n", "\n", testo)


def prezzi(modello):
    try:
        dati = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20))["data"]
        m = next(x for x in dati if x["id"] == modello)
        return float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("llm.jsonl"))
    ap.add_argument("--servizio", choices=SERVIZI, default="openrouter")
    ap.add_argument("--modello", help="predefinito: quello gratuito del servizio")
    ap.add_argument("--scenario", help="un solo scenario del catalogo (id)")
    ap.add_argument("--paralleli", type=int, default=2, help="richieste contemporanee (i piani gratuiti ne vogliono poche)")
    ap.add_argument("--max-dollari", type=float, default=2.0, help="si ferma se la spesa riportata supera questa cifra")
    ap.add_argument("--a-secco", action="store_true", help="mostra prompt e stima, senza chiamare il servizio")
    a = ap.parse_args()
    base, nome_chiave, predefinito = SERVIZI[a.servizio]
    modello = a.modello or predefinito

    r = random.Random(a.seed)
    lavori = [prepara(r, i, a.seed, a.scenario) for i in range(a.n)]

    if a.a_secco:
        for lav in lavori[:3]:
            print("=" * 70, lav["fonte"], json.dumps(lav["etichette"], ensure_ascii=False), sep="\n")
            print(lav["intestazione"] + lav["prompt"])
        token_in = sum(len(x["prompt"]) for x in lavori) / 3.5
        token_out = sum(x["meta"]["parole"] for x in lavori) * 1.7
        p = prezzi(modello)
        stima = f"circa {(token_in * p[0] + token_out * p[1]):.3f} $" if p else "prezzo non trovato su OpenRouter"
        print(f"\n{a.n} documenti, ~{token_in / 1e3:.0f}k token in ingresso e ~{token_out / 1e3:.0f}k in uscita con {modello}: {stima}")
        return

    leggi_env()
    chiave = os.environ.get(nome_chiave)
    if not chiave:
        sys.exit(f"Manca {nome_chiave} in {QUI.parent / '.env'}")
    fatti = set()
    if a.out.exists():
        fatti = {json.loads(riga)["id"] for riga in a.out.open()}
    da_fare = [x for x in lavori if x["id"] not in fatti]
    print(f"{len(da_fare)} documenti da generare con {modello} ({len(fatti)} già fatti)")

    spesa, errori = 0.0, 0
    with a.out.open("a") as out, ThreadPoolExecutor(a.paralleli) as pool:
        futuri = {pool.submit(chiama, base, chiave, modello, x["prompt"]): x for x in da_fare}
        for k, fut in enumerate(as_completed(futuri), 1):
            lav = futuri[fut]
            try:
                risposta = fut.result()
            except Exception as e:
                errori += 1
                print(f"[{k}/{len(da_fare)}] {lav['id']} errore: {e}", flush=True)
                continue
            testo = pulisci(risposta["choices"][0]["message"].get("content") or "")
            uso = risposta.get("usage", {})
            spesa += float(uso.get("cost") or 0)
            if len(testo) < 20:
                errori += 1
                print(f"[{k}/{len(da_fare)}] {lav['id']} risposta vuota", flush=True)
                continue
            doc = {"id": lav["id"], "fonte": lav["fonte"], "gruppi": lav["gruppi"],
                   "stato": lav["intestazione"] + testo, "etichette": lav["etichette"],
                   "meta": {**lav["meta"], "modello": modello, "servizio": a.servizio,
                            "token": [uso.get("prompt_tokens"), uso.get("completion_tokens")], "verificato": False}}
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{k}/{len(da_fare)}] {lav['id']} {lav['fonte']} ok · spesa {spesa:.4f} $", flush=True)
            if spesa > a.max_dollari:
                print(f"Superato il tetto di {a.max_dollari} $: mi fermo.")
                pool.shutdown(cancel_futures=True)
                break
    print(f"Fatto. Errori: {errori}. Spesa riportata dal servizio: {spesa:.4f} $")


if __name__ == "__main__":
    main()
