# Prova zero

Il "prima" di Protocollo: quanto sa fare un modello aperto generico (Rizzo Flow 4B Q8_0, 20/10/2026) sui documenti di un'azienda italiana, prima del nostro addestramento.

- `manuali.json`: 22 documenti scritti a mano (avvisi del Fisco, INPS, INAIL, diffide, atti, contratti, candidature, reclami, ordini, 3 truffe).
- `costruisci.py`: aggiunge 28 documenti dal generatore (12 fatture, 4 coppie, 6 F24, 6 DDT) e scrive `documenti.jsonl`.
- `valuta.py`: manda i documenti a un server compatibile con Rizzo Flow e scrive `risultati/<nome>.md`.

```bash
python3 costruisci.py
python3 valuta.py --url http://127.0.0.1:8017 --nome rizzo-flow-4b-q8
```

## Prima e dopo

| Modello | Decisioni giuste | Documenti scritti a mano | Documenti generati | Scadenze mancate | Truffe non viste |
|---|---|---|---|---|---|
| Rizzo Flow 4B Q8_0 (20/10/2026) | 328/399 (82%) | 121/157 (77%) | 207/242 (86%) | 0 su 25 | 1 su 3 |
| **Protocollo 4B v0.1 Q8_0** (22/10/2026) | **394/399 (99%)** | **154/157 (98%)** | **240/242 (99%)** | 0 su 25 | **0 su 3** |

Stessi 50 documenti, stesso server (`rizzo serve`, llama.cpp b11081, Mac Pro solo CPU). Protocollo v0.1 è Rizzo Flow 4B con un LoRA (r 16) addestrato per 9,4 ore su una T4 di Kaggle con 13.082 domande di [protocollo-train-righe](https://huggingface.co/datasets/dacso-ai/protocollo-train-righe). Dettaglio in [risultati/protocollo-4b-v01-q8.md](risultati/protocollo-4b-v01-q8.md).

I tre errori del primo modello:

| Documento | Rizzo Flow | Protocollo v0.1 |
|---|---|---|
| Nota di credito | fattura, da pagare | nota di credito, archiviare |
| Decreto ingiuntivo (40 giorni) | da pagare, scade tra 12 giorni | inoltrare all'avvocato, scade tra 35 giorni |
| Cambio IBAN da un dominio simile | rispondere, non è una truffa | truffa, cestinare |

**Come leggere il 99%.** È un buon segnale, non ancora una prova. I 28 documenti generati vengono dallo stesso generatore dell'addestramento, anche se con semi diversi. I 22 scritti a mano sono stati scritti da chi ha disegnato anche gli scenari del dataset. In più le etichette di procedura (per esempio "inoltrare" un avviso bonario al commercialista) le abbiamo scelte noi, e il modello ha imparato le nostre scelte. La misura indipendente sarà il benchmark etichettato da professionisti, su documenti che non abbiamo scritto noi.

Restano 5 errori: un acconto letto come TD01, due conteggi di giorni (58 invece di 43, 16 invece di 11), un reclamo per ritardo mandato al commerciale, una conferma d'ordine da "pagare".

## Risultato del 20/10/2026 (Rizzo Flow 4B Q8_0, Mac Pro solo CPU)

**328/399 decisioni giuste (82%)**, nessuna scadenza persa su 25, 1 truffa su 3 non vista. Circa 19 s a documento. Dettaglio in [risultati/rizzo-flow-4b-q8.md](risultati/rizzo-flow-4b-q8.md).

La misura è stata fatta su una versione di `documenti.jsonl` identica a quella di oggi tranne il campo `ProgressivoInvio` degli XML, che allora cambiava a ogni esecuzione e ora è fisso.

L'82% è gonfiato dalle domande facili (dati sensibili, split payment, reverse charge, ritenuta, doppioni: tutte al 100%). Dove sbaglia è proprio dove serve conoscere l'Italia:

| Problema | Esempio |
|---|---|
| **Non sa contare i giorni** (33%) | fattura che scade tra 58 giorni → 22; decreto ingiuntivo a 40 giorni → 12 |
| **Paga tutto** (azione 59%) | avviso bonario, cartella, diffida e decreto ingiuntivo → "pagare" invece di passarli al commercialista o all'avvocato |
| **Paga una nota di credito** | TD04 letta come fattura da pagare |
| **Non riconosce le truffe come tipo** (0/3) | finto rimborso dell'Agenzia → "nota di credito"; finta fattura con link → "fattura" |
| **La truffa del cambio IBAN passa** | fornitore con dominio diverso e IBAN lituano → non è phishing, "rispondere" |
| **DDT da firmare** | 4 DDT su 4 → "firmare" invece di archiviare |
| **Reclami scambiati** | merce rotta → "fattura"; ritardo di consegna → "ordine" |

Alcune etichette vanno confermate dai professionisti del benchmark: per esempio se un avviso bonario si "inoltra" al commercialista o si "paga", e se INPS e INAIL vanno a "personale" o ad "amministrazione". Le etichette delle fatture, degli F24 e dei DDT generati invece sono esatte per costruzione.
