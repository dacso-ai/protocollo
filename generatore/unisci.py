"""Unisce i documenti del generatore (fatture, F24, DDT, coppie) e quelli scritti dal modello e verificati,
li mescola e li divide in train / validation / test.

La divisione è per documento, con un seme fisso. I documenti della prova zero non c'entrano: vengono
da semi e testi diversi e restano un banco di prova a parte.

Uso: python3 unisci.py --llm ../dati/llm-verificati.jsonl --n-generati 6000 --out ../dati/protocollo-dati
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI))
import genera  # noqa: E402

CAMPI_META = ("scenario", "stile", "canale", "modello", "difficile")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", type=Path, nargs="+", required=True)
    ap.add_argument("--n-generati", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--quote", default="0.90,0.05,0.05", help="train, validation, test")
    a = ap.parse_args()

    r = random.Random(a.seed)
    docs = [genera.casuale(r, i, a.seed) for i in range(a.n_generati)]
    for d in docs:
        d["meta"] = {"generatore": "genera.py"}
    for f in a.llm:
        for riga in f.open():
            d = json.loads(riga)
            d["meta"] = {k: v for k, v in d["meta"].items() if k in CAMPI_META}
            docs.append(d)
    r.shuffle(docs)

    quote = [float(x) for x in a.quote.split(",")]
    n = len(docs)
    tagli = [0, int(n * quote[0]), int(n * (quote[0] + quote[1])), n]
    a.out.mkdir(parents=True, exist_ok=True)
    for nome, (i, j) in zip(("train", "validation", "test"), zip(tagli, tagli[1:])):
        with (a.out / f"{nome}.jsonl").open("w") as out:
            for d in docs[i:j]:
                out.write(json.dumps({k: d[k] for k in ("id", "fonte", "gruppi", "stato", "etichette", "meta")},
                                     ensure_ascii=False, default=str) + "\n")
        print(f"{nome}: {j - i} documenti")
    tipi = Counter(d["etichette"].get("tipo", "coppia") for d in docs)
    decisioni = sum(len(d["etichette"]) for d in docs)
    print(f"Totale {n} documenti, {decisioni} decisioni")
    print("Per tipo:", ", ".join(f"{k} {v}" for k, v in tipi.most_common()))
    (a.out / "statistiche.json").write_text(json.dumps({"documenti": n, "decisioni": decisioni, "per_tipo": tipi}, indent=1))


if __name__ == "__main__":
    main()
