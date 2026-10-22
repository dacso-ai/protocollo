"""Unisce l'adapter LoRA di Protocollo ai pesi di Rizzo Flow ed esporta i GGUF per llama.cpp (rizzo serve).

Passi (come training/export_gguf.py di Rizzo Flow, ma sulla CPU): unione in bf16, salvataggio del
checkpoint Hugging Face, convert_hf_to_gguf.py di llama.cpp b11081 in BF16, llama-quantize.

  uv run --with "transformers==4.57.1" --with "peft==0.21.0" --with torch --with sentencepiece --with "numpy<2" \\
      python addestramento/esporta.py --base ~/ai/protocollo-modelli/rizzo-flow-hf \\
      --adapter dacso-ai/protocollo-4b-lora --nome protocollo-4b --out ~/ai/protocollo-modelli
  ... --adapter-vuoto --nome prova-vuoto     # LoRA con B=0: il modello esportato deve essere identico alla base

--adapter può essere una cartella locale o un repo Hugging Face (con HF_TOKEN in .env se è privato);
--sottocartella sceglie quale cartella del repo usare (predefinita "finale").
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

QUI = Path(__file__).parent
COPIA = ["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.json", "merges.txt",
         "chat_template.jinja", "generation_config.json", "configuration_spark.py", "modeling_spark.py", "LICENSE"]
TARGETS = ["q_k_v_proj", "g_proj", "out_proj", "gate_proj", "up_proj", "down_proj"]
INIZIO = time.time()


def log(msg):
    print(f"[{time.time() - INIZIO:6.0f} s] {msg}", flush=True)


def sha256(percorso):
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def adapter_locale(adapter, sottocartella):
    if Path(adapter).expanduser().exists():
        return Path(adapter).expanduser()
    from huggingface_hub import snapshot_download

    env = QUI.parent / ".env"
    if env.exists():
        for riga in env.read_text().splitlines():
            if riga.startswith("HF_TOKEN="):
                os.environ.setdefault("HF_TOKEN", riga.split("=", 1)[1].strip())
    cartella = snapshot_download(adapter, allow_patterns=[f"{sottocartella}/*", "storia.json"])
    return Path(cartella) / sottocartella


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True, help="checkpoint HF di Rizzo Flow")
    ap.add_argument("--adapter")
    ap.add_argument("--sottocartella", default="finale")
    ap.add_argument("--adapter-vuoto", action="store_true", help="prova: LoRA con B=0, nessun cambiamento")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--out", type=Path, default=Path("~/ai/protocollo-modelli").expanduser())
    ap.add_argument("--llama", type=Path, default=Path("~/ai/protocollo-modelli/llama.cpp-b11081").expanduser())
    ap.add_argument("--quantize", type=Path,
                    default=Path("~/ai/rizzo-flow/runtimes/llama-b11081-darwin-x64-cpu/llama-quantize").expanduser())
    ap.add_argument("--quant", nargs="+", default=["q8_0", "q4_k_m"])
    a = ap.parse_args()
    if bool(a.adapter) == a.adapter_vuoto:
        ap.error("serve --adapter oppure --adapter-vuoto")

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM

    dest = a.out / a.nome
    dest.mkdir(parents=True, exist_ok=False)  # mai sovrascrivere un'esportazione
    hf = dest / "hf"

    log(f"1/4 carico la base {a.base}")
    modello = AutoModelForCausalLM.from_pretrained(a.base, trust_remote_code=True, dtype=torch.bfloat16)
    if a.adapter_vuoto:
        modello = get_peft_model(modello, LoraConfig(r=16, lora_alpha=32, target_modules=TARGETS, task_type="CAUSAL_LM"))
    else:
        cartella = adapter_locale(a.adapter, a.sottocartella)
        log(f"   adapter da {cartella}")
        modello = PeftModel.from_pretrained(modello, cartella)
    modello = modello.merge_and_unload()

    log(f"2/4 salvo il checkpoint HF in {hf}")
    modello.save_pretrained(hf, safe_serialization=True, max_shard_size="2GB")
    del modello
    for nome in COPIA:
        if (a.base / nome).exists():
            shutil.copy2(a.base / nome, hf / nome)
    # come Rizzo Flow: senza il template minificato in tokenizer_config, il GGUF prende chat_template.jinja
    config = json.loads((hf / "tokenizer_config.json").read_text())
    config.pop("chat_template", None)
    (hf / "tokenizer_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))

    bf16 = dest / f"{a.nome}-bf16.gguf"
    log(f"3/4 converto in {bf16.name}")
    subprocess.run([sys.executable, str(a.llama / "convert_hf_to_gguf.py"), str(hf), "--outtype", "bf16", "--outfile", str(bf16)],
                   check=True, env={**os.environ, "PYTHONPATH": str(a.llama / "gguf-py")})
    file_finali = [bf16]
    for q in a.quant:
        uscita = dest / f"{a.nome}-{q}.gguf"
        log(f"4/4 quantizzo in {uscita.name}")
        subprocess.run([str(a.quantize), str(bf16), str(uscita), q.upper()], check=True, capture_output=True)
        file_finali.append(uscita)
    for f in file_finali:
        log(f"{f.name}: {f.stat().st_size / 2**30:.2f} GiB, sha256 {sha256(f)}")
    log("fatto")


if __name__ == "__main__":
    main()
