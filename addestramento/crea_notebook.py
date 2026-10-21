"""Scrive protocollo_lora_kaggle.ipynb: il fine-tuning LoRA di Protocollo su una GPU gratuita di Kaggle (T4).

Il codice di addestramento segue training/train_lora.py di Rizzo Flow (Apache-2.0): stesso prompt,
stessa lettura dei logit delle lettere, stessa loss (cross-entropy morbida). Differenze: si parte dai
pesi già addestrati di Rizzo Flow, la T4 non ha bf16 quindi si usa fp16 con GradScaler, e c'è un
tetto di ore misurato sulla velocità reale.

Uso: python3 addestramento/crea_notebook.py
"""
import json
from pathlib import Path

CELLE = []


def md(testo):
    CELLE.append({"cell_type": "markdown", "metadata": {}, "source": testo.strip("\n")})


def code(testo):
    CELLE.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": testo.strip("\n")})


md("""
# Protocollo: fine-tuning LoRA su Kaggle

Addestra [Protocollo](https://github.com/dacso-ai/protocollo) a smistare la posta di un'azienda italiana, partendo dal modello aperto [Rizzo Flow 4B](https://huggingface.co/rizzoaiacademy/rizzo-flow).

**Prima di lanciare**
1. *Settings → Accelerator*: **GPU T4 x2** (ne usiamo una).
2. *Settings → Internet*: **attivo** (scarica modello e dati da Hugging Face).
3. Facoltativo: *Add-ons → Secrets* → aggiungi `HF_TOKEN` (token Write di Hugging Face). Se c'è, l'adapter addestrato viene caricato su `dacso-ai/protocollo-4b-lora`; altrimenti lo trovi nella scheda *Output*.
4. In alto a destra **Save Version → Save & Run All (Commit)**: gira in background anche a browser chiuso, fino a 12 ore.

Il notebook misura la velocità nei primi minuti e sceglie quante righe usare per finire entro `ORE_MAX`.
""")

code("""
# Configurazione
MODELLO = "rizzoaiacademy/rizzo-flow"      # pesi già addestrati di Rizzo Flow 4B (Apache-2.0)
REVISIONE = "55633c8cbd2b826bd3eefdeb05310450996649df"  # versione fissa: il modello usa codice Python remoto
DATI = "dacso-ai/protocollo-train-righe"   # righe già compilate con il prompt di Rizzo Flow
REPO_ADAPTER = "dacso-ai/protocollo-4b-lora"
ORE_MAX = 9.5          # tempo massimo di addestramento (la sessione Kaggle dura al massimo 12 ore)
R, ALPHA, DROPOUT = 16, 32, 0.05
LR = 5e-5
GRAD_ACCUM = 16        # righe per passo dell'ottimizzatore
BATCH = 4              # righe per forward
MAX_BATCH_TOKEN = 3072 # token (con padding) per forward: abbassare se va in out of memory
WARMUP = 30            # passi
DEV_RIGHE = 800
SALVA_OGNI_MIN = 45
""")

code("""
!pip install -q "transformers==4.57.1" "peft==0.21.0" "accelerate==1.15.0" "safetensors" "huggingface_hub"
""")

code("""
import json, math, os, random, time
from collections import defaultdict
from pathlib import Path

import torch
from huggingface_hub import snapshot_download

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
assert torch.cuda.is_available(), "Attiva la GPU: Settings -> Accelerator -> GPU T4 x2"
print(torch.cuda.get_device_name(0), round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1), "GiB")
INIZIO = time.time()

def log(msg):
    print(f"[{(time.time() - INIZIO) / 60:6.1f} min] {msg}", flush=True)

cartella_modello = snapshot_download(MODELLO, revision=REVISIONE, allow_patterns=["*.json", "*.py", "*.safetensors", "*.jinja", "*.txt", "LICENSE"],
                                     ignore_patterns=["lora*/*", "training/*"])
cartella_dati = snapshot_download(DATI, repo_type="dataset")
log("modello e dati scaricati")

def leggi(p):
    with open(p) as f:
        return [json.loads(r) for r in f if r.strip()]

train = leggi(Path(cartella_dati) / "train.jsonl")
dev = leggi(Path(cartella_dati) / "dev.jsonl")
random.Random(1).shuffle(dev)
dev = dev[:DEV_RIGHE]
log(f"train {len(train)} righe, dev {len(dev)}")
""")

code("""
from transformers import AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

# La T4 non ha bf16: pesi in fp16, adapter LoRA in fp32, GradScaler sulla loss.
modello = AutoModelForCausalLM.from_pretrained(cartella_modello, trust_remote_code=True, dtype=torch.float16, device_map={"": 0})
modello.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
modello.enable_input_require_grads()
modello.config.use_cache = False
TARGETS = ["q_k_v_proj", "g_proj", "out_proj", "gate_proj", "up_proj", "down_proj"]  # come Rizzo Flow
modello = get_peft_model(modello, LoraConfig(r=R, lora_alpha=ALPHA, lora_dropout=DROPOUT, target_modules=TARGETS,
                                            bias="none", task_type="CAUSAL_LM"))
parametri = [p for p in modello.parameters() if p.requires_grad]
log(f"LoRA r={R}: {sum(p.numel() for p in parametri) / 1e6:.1f} M parametri addestrabili, GPU {torch.cuda.memory_allocated() / 2**30:.1f} GiB")
""")

code("""
# Dalla pipeline di Rizzo Flow (training/train_lora.py, Apache-2.0)
DEVICE = globals().get("DEVICE", "cuda")

def readout_batch(model, rows):
    \"\"\"Logit delle lettere di risposta all'ultima posizione di ogni prompt, in un solo forward.\"\"\"
    width = max(len(r["tokens"]) for r in rows)
    ids = torch.zeros((len(rows), width), dtype=torch.long, device=DEVICE)
    mask = torch.zeros_like(ids)
    for i, r in enumerate(rows):
        ids[i, : len(r["tokens"])] = torch.tensor(r["tokens"], device=DEVICE)
        mask[i, : len(r["tokens"])] = 1
    base = model.get_base_model()
    hidden = base.model(input_ids=ids, attention_mask=mask, use_cache=False).last_hidden_state
    last = torch.tensor([len(r["tokens"]) - 1 for r in rows], device=DEVICE)
    h = hidden[torch.arange(len(rows), device=DEVICE), last]
    weight = base.get_input_embeddings().weight if base.config.tie_word_embeddings else base.get_output_embeddings().weight
    return [(h[i].float() @ weight[r["slots"]].float().T) for i, r in enumerate(rows)]

def soft_ce(logits, target):
    t = torch.tensor(target, device=logits.device, dtype=torch.float32)
    return -(t * torch.log_softmax(logits, -1)).sum()

def batches(rows, batch, max_tokens, rng=None):
    \"\"\"Batch per lunghezze simili: meno padding.\"\"\"
    index = list(range(len(rows)))
    if rng:
        rng.shuffle(index)
    out, pool = [], batch * 64
    for start in range(0, len(index), pool):
        chunk = sorted(index[start : start + pool], key=lambda i: len(rows[i]["tokens"]))
        current = []
        for i in chunk:
            width = max([len(rows[j]["tokens"]) for j in current] + [len(rows[i]["tokens"])])
            if current and (len(current) == batch or width * (len(current) + 1) > max_tokens):
                out.append(current)
                current = []
            current.append(i)
        if current:
            out.append(current)
    if rng:
        rng.shuffle(out)
    return out

def valuta(model, rows, etichetta):
    model.eval()
    gruppi = defaultdict(lambda: [0, 0])
    with torch.inference_mode():
        for membri in batches(rows, BATCH * 2, MAX_BATCH_TOKEN * 2):
            chunk = [rows[i] for i in membri]
            for r, logits in zip(chunk, readout_batch(model, chunk)):
                g = gruppi[r["group"].split("/")[0]]
                g[0] += int(logits.argmax().item() == max(range(len(r["target"])), key=r["target"].__getitem__))
                g[1] += 1
    model.train()
    totale = sum(g[0] for g in gruppi.values()) / sum(g[1] for g in gruppi.values())
    log(f"valutazione {etichetta}: accuratezza {totale:.3f} | " + " ".join(f"{k} {g[0] / g[1]:.2f}" for k, g in sorted(gruppi.items())))
    return {"accuratezza": totale} | {k: g[0] / g[1] for k, g in gruppi.items()}
""")

code("""
storia = {"valutazioni": [{"passo": 0} | valuta(modello, dev, "prima dell'addestramento")], "log": []}
""")

code("""
ottimizzatore = torch.optim.AdamW(parametri, lr=LR, weight_decay=0.0)
scaler = torch.amp.GradScaler("cuda")
rng = random.Random(0)
piano, cursore = batches(train, BATCH, MAX_BATCH_TOKEN, rng), 0
out = Path("/kaggle/working/protocollo-4b-lora")
passi_totali = None  # deciso dopo la misura della velocità
passo, righe_viste, saltati = 0, 0, 0
inizio_train, ultimo_salvataggio = time.time(), time.time()
modello.train()

def lr_a(passo):
    if passo < WARMUP:
        return LR * (passo + 1) / WARMUP
    totale = passi_totali or 10**9
    return LR * 0.5 * (1 + math.cos(math.pi * min(1.0, (passo - WARMUP) / max(1, totale - WARMUP))))

while passi_totali is None or passo < passi_totali:
    for g in ottimizzatore.param_groups:
        g["lr"] = lr_a(passo)
    somma, prese = 0.0, 0
    while prese < GRAD_ACCUM:
        if cursore >= len(piano):
            piano, cursore = batches(train, BATCH, MAX_BATCH_TOKEN, rng), 0
        chunk = [train[i] for i in piano[cursore]]
        cursore += 1
        perdite = [soft_ce(l, r["target"]) for r, l in zip(chunk, readout_batch(modello, chunk))]
        scaler.scale(sum(perdite) / GRAD_ACCUM).backward()
        somma += sum(x.item() for x in perdite)
        prese += len(chunk)
    righe_viste += prese
    scaler.unscale_(ottimizzatore)
    norma = torch.nn.utils.clip_grad_norm_(parametri, 1.0)
    if not torch.isfinite(norma):
        saltati += 1  # overflow in fp16: GradScaler riduce la scala e si salta il passo
    scaler.step(ottimizzatore)
    scaler.update()
    ottimizzatore.zero_grad(set_to_none=True)
    passo += 1
    trascorso = time.time() - inizio_train
    if passo == 20 and passi_totali is None:
        righe_al_secondo = righe_viste / trascorso
        righe_possibili = int(righe_al_secondo * (ORE_MAX * 3600 - (time.time() - INIZIO)) * 0.92)
        passi_totali = max(passo + 1, min(len(train), righe_possibili) // GRAD_ACCUM)
        log(f"velocità {righe_al_secondo:.2f} righe/s: userò {passi_totali * GRAD_ACCUM} righe su {len(train)} ({passi_totali} passi)")
    if passo % 10 == 0:
        storia["log"].append({"passo": passo, "loss": somma / prese, "lr": lr_a(passo - 1), "secondi": trascorso})
        log(f"passo {passo}/{passi_totali or '?'} loss {somma / prese:.4f} lr {lr_a(passo - 1):.1e} saltati {saltati} "
            f"GPU {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")
    if time.time() - ultimo_salvataggio > SALVA_OGNI_MIN * 60:
        modello.save_pretrained(out / "ultimo")
        (out / "storia.json").write_text(json.dumps(storia, indent=1))
        ultimo_salvataggio = time.time()
        log("salvato un checkpoint")
""")

code("""
storia["valutazioni"].append({"passo": passo} | valuta(modello, dev, "dopo l'addestramento"))
storia |= {"passi": passo, "righe": righe_viste, "passi_saltati": saltati, "ore": (time.time() - inizio_train) / 3600,
           "modello_base": MODELLO, "dati": DATI, "r": R, "alpha": ALPHA, "lr": LR}
modello.save_pretrained(out / "finale")
(out / "storia.json").write_text(json.dumps(storia, indent=1))
log(f"adapter salvato in {out / 'finale'}")
""")

code("""
# Caricamento su Hugging Face, solo se c'è il segreto HF_TOKEN
try:
    from kaggle_secrets import UserSecretsClient
    token = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    token = None
if token:
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    api.create_repo(REPO_ADAPTER, exist_ok=True, private=True)
    api.upload_folder(folder_path=str(out), repo_id=REPO_ADAPTER, commit_message=f"LoRA dopo {passo} passi")
    log(f"caricato su https://huggingface.co/{REPO_ADAPTER} (privato)")
else:
    log("nessun HF_TOKEN: scarica la cartella protocollo-4b-lora dalla scheda Output")
""")

nb = {"cells": CELLE, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "language_info": {"name": "python"},
                                   "kaggle": {"accelerator": "nvidiaTeslaT4", "isInternetEnabled": True, "isGpuEnabled": True}},
      "nbformat": 4, "nbformat_minor": 5}
destinazione = Path(__file__).parent / "protocollo_lora_kaggle.ipynb"
destinazione.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
print(f"scritto {destinazione}")
