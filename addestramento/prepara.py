"""Trasforma protocollo-dati in righe di addestramento per il LoRA, nel formato di Rizzo Flow.

Ogni riga è una coppia (documento, domanda): i token del prompt compilati con lo stesso codice del
server Rizzo Flow (prompt spark-decisions-v3), i token delle lettere di risposta e la distribuzione
attesa su quelle lettere. Così il modello addestrato si serve con `rizzo serve` senza modifiche.

Per stare nei tempi di una GPU gratuita non si usano tutte le domande di ogni documento: se ne
scelgono --per-doc, preferendo quelle difficili (tipo, azione, ufficio, scadenza, giorni, truffa).
Le righe sono mescolate, quindi prenderne le prime N dà comunque un campione equilibrato.

Uso (serve il codice di Rizzo Flow, https://github.com/Rizzo-AI-Academy/rizzo-flow):
  uv run --project ~/ai/rizzo-flow --with transformers --with jinja2 \\
      python addestramento/prepara.py --dati dati/protocollo-dati --rizzo ~/ai/rizzo-flow --out dati/train-righe
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

QUI = Path(__file__).parent
DOMANDE = json.loads((QUI.parent / "protocollo" / "domande.json").read_text())["domande"]
PESI = {"tipo": 4, "azione": 3, "ufficio": 3, "scadenza": 3, "giorni": 3, "phishing": 3, "rischio": 2,
        "doppione": 3, "dati_sensibili": 1, "codice_td": 2, "split_payment": 1, "reverse_charge": 1, "ritenuta": 1}
MAX_TOKEN = 2048  # prompt più lunghi scartati, mai troncati (come Rizzo Flow)
LISCIATURA = 0.02  # le etichette sono esatte: solo un minimo per non spingere i logit all'infinito


def bersaglio(domanda, valore, n_slot):
    """Distribuzione attesa sulle lettere, nell'ordine di rizzo_flow.decisions.candidates."""
    t = [0.0] * n_slot
    astieni = n_slot - 1  # __insufficient__ è sempre l'ultima opzione (allow_abstain predefinito)
    tipo = domanda["type"]
    if valore is None:
        t[astieni] = 1.0
    elif tipo == "boolean":
        t[1 if valore else 0] = 1.0
    elif tipo == "choice":
        t[[o["id"] for o in domanda["options"]].index(valore)] = 1.0
    elif tipo == "score":
        t[int(valore)] = 1.0
    elif tipo == "numeric":
        ancore = [a["value"] for a in domanda["anchors"]]
        sotto, sopra = len(ancore), len(ancore) + 1
        if valore < ancore[0]:
            t[sotto] = 1.0
        elif valore > ancore[-1]:
            t[sopra] = 1.0
        else:  # tra due ancore: probabilità divisa in modo che la media sia il valore vero
            for i in range(len(ancore) - 1):
                if ancore[i] <= valore <= ancore[i + 1]:
                    p = (valore - ancore[i]) / (ancore[i + 1] - ancore[i])
                    t[i] += 1 - p
                    t[i + 1] += p
                    break
    k = len(t)
    return [(1 - LISCIATURA) * x + LISCIATURA / k for x in t]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dati", type=Path, required=True)
    ap.add_argument("--rizzo", type=Path, required=True, help="cartella del codice Rizzo Flow")
    ap.add_argument("--modello", default="XHToken/Spark-X2.5-4B")
    ap.add_argument("--per-doc", type=int, default=2)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    sys.path.insert(0, str(a.rizzo / "src"))
    from rizzo_flow.prompts import compile_request
    from rizzo_flow.schema import Request
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(a.modello)
    rng = random.Random(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    for split, nome in (("train", "train"), ("validation", "dev")):
        righe, scarti = [], Counter()
        for riga in (a.dati / f"{split}.jsonl").open():
            doc = json.loads(riga)
            nomi = list(doc["etichette"])
            # scelta pesata senza ripetizioni delle domande di questo documento
            scelte = []
            while nomi and len(scelte) < a.per_doc:
                n = rng.choices(nomi, weights=[PESI.get(x, 1) for x in nomi])[0]
                scelte.append(n)
                nomi.remove(n)
            richiesta = Request.model_validate({"state": doc["stato"], "questions": {n: DOMANDE[n] for n in scelte}})
            try:
                _, compilati = compile_request(tok, richiesta, MAX_TOKEN)
            except ValueError:
                scarti["troppo lungo"] += 1
                continue
            for c in compilati:
                righe.append({"group": f"{c.id}/{doc['fonte'].split('/')[0]}", "id": f"{doc['id']}/{c.id}",
                              "tokens": c.tokens, "slots": c.slots,
                              "target": bersaglio(DOMANDE[c.id], doc["etichette"][c.id], len(c.slots))})
        rng.shuffle(righe)
        with (a.out / f"{nome}.jsonl").open("w") as f:
            f.writelines(json.dumps(r) + "\n" for r in righe)
        lunghezze = sorted(len(r["tokens"]) for r in righe)
        per_domanda = Counter(r["group"].split("/")[0] for r in righe)
        print(f"{nome}: {len(righe)} righe, {sum(lunghezze) / 1e6:.1f} M token, mediana {lunghezze[len(lunghezze) // 2]}, "
              f"massimo {lunghezze[-1]}, scartati {dict(scarti)}")
        print("   per domanda:", dict(per_domanda.most_common()))


if __name__ == "__main__":
    main()
