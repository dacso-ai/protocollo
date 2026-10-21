"""Costruisce i 50 documenti della prova zero: 28 dal generatore (composizione fissa) + 22 scritti a mano.

Uso: python3 costruisci.py   ->   documenti.jsonl
"""
import json
import random
import sys
from pathlib import Path

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI.parent / "generatore"))
import genera  # noqa: E402

r = random.Random(2026)
docs = []


def aggiungi(fonte, gruppi, doc):
    docs.append(genera.documento(f"gen-{len(docs) + 1:02d}", fonte, gruppi, doc))


# 12 fatture: un tipo ciascuna più due ordinarie, metà XML e metà PDF
tipi = list(genera.TIPI_FATTURA) + ["ordinaria", "ordinaria"]
for i, tipo in enumerate(tipi):
    aggiungi(f"fattura/{tipo}", ["documento", "fattura"], genera.fattura(r, tipo, "xml" if i % 2 == 0 else "pdf"))
# 4 coppie: 2 doppioni veri, 2 falsi (numero diverso, canone mensile)
for doppione, variante in [(True, None), (True, None), (False, "altro_numero"), (False, "canone")]:
    aggiungi("coppia", ["coppia"], genera.coppia(r, doppione, variante))
# 6 F24 e 6 DDT
for quietanza in [False, False, False, False, True, True]:
    aggiungi("f24/" + ("quietanza" if quietanza else "delega"), ["documento"], genera.f24(r, quietanza))
for causale in ["Vendita", "Vendita", "Reso", "Conto lavorazione", "Conto visione", "Conto visione"]:
    aggiungi("ddt/" + causale.lower().replace(" ", "_"), ["documento"], genera.ddt(r, causale))

for m in json.loads((QUI / "manuali.json").read_text()):
    docs.append({**m, "gruppi": ["documento"]})

with (QUI / "documenti.jsonl").open("w") as out:
    for d in docs:
        out.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
print(f"{len(docs)} documenti in documenti.jsonl")
