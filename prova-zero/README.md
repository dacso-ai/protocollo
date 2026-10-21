# Prova zero

Il "prima" di Protocollo: quanto sa fare un modello aperto generico (Rizzo Flow 4B Q8_0, 20/10/2026) sui documenti di un'azienda italiana, prima del nostro addestramento.

- `manuali.json`: 22 documenti scritti a mano (avvisi del Fisco, INPS, INAIL, diffide, atti, contratti, candidature, reclami, ordini, 3 truffe).
- `costruisci.py`: aggiunge 28 documenti dal generatore (12 fatture, 4 coppie, 6 F24, 6 DDT) e scrive `documenti.jsonl`.
- `valuta.py`: manda i documenti a un server compatibile con Rizzo Flow e scrive `risultati/<nome>.md`.

```bash
python3 costruisci.py
python3 valuta.py --url http://127.0.0.1:8017 --nome rizzo-flow-4b-q8
```

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
