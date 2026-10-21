"""Pubblica una cartella di dati (train/validation/test + README.md) come dataset su Hugging Face.

Il token si legge da HF_TOKEN in .env (token "Write", creato dall'utente). Serve huggingface_hub:
  uv run --with huggingface_hub python pubblica_hf.py ../dati/protocollo-dati dacso-ai/protocollo-dati
"""
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

sys.path.insert(0, str(Path(__file__).parent))
from genera_llm import leggi_env  # noqa: E402

cartella, repo = Path(sys.argv[1]), sys.argv[2]
leggi_env()
token = os.environ.get("HF_TOKEN") or sys.exit("Manca HF_TOKEN in .env")
api = HfApi(token=token)
api.create_repo(repo, repo_type="dataset", exist_ok=True, private=False)
api.upload_folder(folder_path=str(cartella), repo_id=repo, repo_type="dataset",
                  commit_message="Protocollo dati v0.1", allow_patterns=["*.jsonl", "*.json", "README.md"])
print(f"https://huggingface.co/datasets/{repo}")
