"""Prova a secco del notebook sulla CPU, con il modello piccolo (1.7B): carica, applica il LoRA,
fa due passi di addestramento su poche righe e controlla che la loss sia finita e scenda.

Non misura niente di utile sulla qualità: serve solo a scoprire errori prima di Kaggle.
  uv run --project ~/ai/rizzo-flow --with "transformers==4.57.1" --with "peft==0.21.0" --with torch --with jinja2 \\
      python addestramento/prova_cpu.py ~/ai/rizzo-flow
"""
import json
import sys
from pathlib import Path

import torch

QUI = Path(__file__).parent
sys.path.insert(0, str(Path(sys.argv[1]).expanduser() / "src"))
sys.path.insert(0, str(QUI))
import prepara  # noqa: E402
from peft import LoraConfig, get_peft_model  # noqa: E402
from rizzo_flow.prompts import compile_request  # noqa: E402
from rizzo_flow.schema import Request  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

MODELLO = "XHToken/Spark-X2.5-1.7B"
nb = json.loads((QUI / "protocollo_lora_kaggle.ipynb").read_text())
celle = [c["source"] for c in nb["cells"] if c["cell_type"] == "code"]
ambiente = {"DEVICE": "cpu", "torch": torch, "BATCH": 2, "MAX_BATCH_TOKEN": 4096, "log": print}
exec(next(c for c in celle if "def readout_batch" in c).replace("from collections", "from collections"), ambiente)
exec("from collections import defaultdict", ambiente)

tok = AutoTokenizer.from_pretrained(MODELLO)
righe = []
for riga in list((QUI.parent / "dati" / "protocollo-dati" / "train.jsonl").open())[:40]:
    doc = json.loads(riga)
    if len(doc["stato"]) > 1500:
        continue
    nomi = list(doc["etichette"])[:2]
    _, comp = compile_request(tok, Request.model_validate({"state": doc["stato"], "questions": {n: prepara.DOMANDE[n] for n in nomi}}), 2048)
    for c in comp:
        righe.append({"group": c.id, "tokens": c.tokens, "slots": c.slots,
                      "target": prepara.bersaglio(prepara.DOMANDE[c.id], doc["etichette"][c.id], len(c.slots))})
    if len(righe) >= 6:
        break
print(f"{len(righe)} righe, token {[len(r['tokens']) for r in righe]}")

modello = AutoModelForCausalLM.from_pretrained(MODELLO, trust_remote_code=True, dtype=torch.float32)
modello.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
modello.enable_input_require_grads()
modello.config.use_cache = False
targets = ["q_k_v_proj", "g_proj", "out_proj", "gate_proj", "up_proj", "down_proj"]
modello = get_peft_model(modello, LoraConfig(r=8, lora_alpha=16, target_modules=targets, bias="none", task_type="CAUSAL_LM"))
parametri = [p for p in modello.parameters() if p.requires_grad]
print(f"LoRA: {sum(p.numel() for p in parametri) / 1e6:.1f} M parametri addestrabili")
ottimizzatore = torch.optim.AdamW(parametri, lr=1e-3)
modello.train()
for passo in range(3):
    perdite = [ambiente["soft_ce"](l, r["target"]) for r, l in zip(righe, ambiente["readout_batch"](modello, righe))]
    loss = sum(perdite) / len(perdite)
    loss.backward()
    ottimizzatore.step()
    ottimizzatore.zero_grad()
    print(f"passo {passo}: loss {loss.item():.4f}")
    assert torch.isfinite(loss)
print("prova CPU riuscita")
