"""Manda i documenti a un server compatibile con Rizzo Flow (/v1/decisions) e misura le risposte.

Si fanno solo le domande che hanno un'etichetta nel documento. Un'etichetta None vuol dire che la
risposta giusta è l'astensione ("non si può dire").

Uso: python3 valuta.py [--url http://127.0.0.1:8017] [--nome rizzo-flow-4b-q8] [documenti.jsonl]
Scrive risultati/<nome>.jsonl (risposte grezze) e risultati/<nome>.md (riepilogo).
"""
import argparse
import json
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

QUI = Path(__file__).parent
DOMANDE = json.loads((QUI.parent / "protocollo" / "domande.json").read_text())["domande"]

ap = argparse.ArgumentParser()
ap.add_argument("documenti", nargs="?", type=Path, default=QUI / "documenti.jsonl")
ap.add_argument("--url", default="http://127.0.0.1:8017")
ap.add_argument("--nome", default="rizzo-flow")
a = ap.parse_args()


def chiedi(stato, domande):
    corpo = json.dumps({"state": stato, "questions": domande}).encode()
    req = urllib.request.Request(a.url + "/v1/decisions", corpo, {"Content-Type": "application/json"})
    inizio = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as risposta:
        return json.load(risposta), time.perf_counter() - inizio


def previsione(nome, ans):
    """La risposta del modello nello stesso formato delle etichette (id, bool, indice del livello, numero o None)."""
    if ans["status"] != "ok" and ans["type"] != "numeric":
        return None
    if ans["type"] == "choice":
        return ans["choice"]
    if ans["type"] == "boolean":
        return ans["value"]
    if ans["type"] == "score":
        p = {k: v for k, v in ans["probabilities"].items() if not k.startswith("__")}
        livello = ans["legend"][max(p, key=p.get)]
        return DOMANDE[nome]["levels"].index(livello)
    return ans["value"]


def giusta(nome, atteso, previsto, ans):
    if DOMANDE[nome]["type"] != "numeric":
        return previsto == atteso
    if atteso is None:  # nessuna scadenza: deve astenersi
        return previsto is None
    if atteso < 0:  # già scaduto: va bene "sotto il minimo" o un valore vicino a zero
        return ans["status"] == "out_of_range" or (previsto is not None and previsto <= 3)
    return previsto is not None and abs(previsto - atteso) <= max(3, 0.25 * atteso)


docs = [json.loads(riga) for riga in a.documenti.open()]
(QUI / "risultati").mkdir(exist_ok=True)
grezzi = (QUI / "risultati" / f"{a.nome}.jsonl").open("w")
per_domanda = defaultdict(lambda: [0, 0])
per_fonte = defaultdict(lambda: [0, 0])
scadenze_mancate, phishing_non_visti, falsi_phishing, errori, tempi = [], [], [], [], []

for i, d in enumerate(docs, 1):
    domande = {n: DOMANDE[n] for n in d["etichette"]}
    risposta, secondi = chiedi(d["stato"], domande)
    tempi.append(secondi)
    riga = {"id": d["id"], "fonte": d["fonte"], "secondi": round(secondi, 2), "risposte": {}}
    sbagliate = []
    for nome, atteso in d["etichette"].items():
        ans = risposta["answers"][nome]
        previsto = previsione(nome, ans)
        ok = giusta(nome, atteso, previsto, ans)
        per_domanda[nome][0] += ok
        per_domanda[nome][1] += 1
        fonte = d["fonte"].split("/")[0] if d["fonte"].startswith(("fattura", "f24", "ddt")) else d["fonte"]
        per_fonte[fonte][0] += ok
        per_fonte[fonte][1] += 1
        riga["risposte"][nome] = {"atteso": atteso, "previsto": previsto, "ok": ok, "status": ans["status"],
                                  "probabilita": ans.get("probabilities")}
        if not ok:
            sbagliate.append(f"{nome}: {previsto} invece di {atteso}")
    e = d["etichette"]
    if e.get("scadenza") is True and riga["risposte"]["scadenza"]["previsto"] is not True:
        scadenze_mancate.append(d["id"])
    if e.get("phishing") is True and riga["risposte"]["phishing"]["previsto"] is not True:
        phishing_non_visti.append(d["id"])
    if e.get("phishing") is False and riga["risposte"]["phishing"]["previsto"] is True:
        falsi_phishing.append(d["id"])
    if sbagliate:
        errori.append(f"- **{d['id']}** ({d['fonte']}): " + "; ".join(sbagliate))
    grezzi.write(json.dumps(riga, ensure_ascii=False) + "\n")
    grezzi.flush()
    print(f"[{i}/{len(docs)}] {d['id']} {d['fonte']}: {len(d['etichette']) - len(sbagliate)}/{len(d['etichette'])} in {secondi:.1f} s", flush=True)

giuste = sum(v[0] for v in per_domanda.values())
totali = sum(v[1] for v in per_domanda.values())
con_scadenza = sum(1 for d in docs if d["etichette"].get("scadenza") is True)
truffe = sum(1 for d in docs if d["etichette"].get("phishing") is True)
tempi.sort()
md = [f"# Prova zero: {a.nome}", "",
      f"{len(docs)} documenti, {totali} decisioni. Server {a.url}.", "",
      f"- **Decisioni giuste: {giuste}/{totali} ({giuste / totali:.0%})**",
      f"- **Scadenze mancate: {len(scadenze_mancate)} su {con_scadenza}** {' '.join(scadenze_mancate)}",
      f"- **Phishing non visto: {len(phishing_non_visti)} su {truffe}** {' '.join(phishing_non_visti)}",
      f"- Documenti veri scambiati per phishing: {len(falsi_phishing)} {' '.join(falsi_phishing)}",
      f"- Tempo per documento: mediana {tempi[len(tempi) // 2]:.1f} s, massimo {tempi[-1]:.1f} s", "",
      "## Per domanda", "", "| Domanda | Giuste |", "|---|---|"]
md += [f"| {n} | {g}/{t} ({g / t:.0%}) |" for n, (g, t) in per_domanda.items()]
md += ["", "## Per fonte", "", "| Fonte | Giuste |", "|---|---|"]
md += [f"| {n} | {g}/{t} ({g / t:.0%}) |" for n, (g, t) in sorted(per_fonte.items())]
md += ["", "## Errori", ""] + errori
(QUI / "risultati" / f"{a.nome}.md").write_text("\n".join(md) + "\n")
print("\n".join(md[:9]))
