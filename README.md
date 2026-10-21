# Protocollo

**Un modello AI aperto che protocolla la posta di un'azienda italiana: PEC, fatture elettroniche, avvisi del Fisco, mail dei clienti. Gira in locale, senza mandare dati fuori.**

Ogni mattina qualcuno apre la PEC e deve capire: è una fattura o un avviso dell'Agenzia delle Entrate? C'è una scadenza? Va al commercialista? È una truffa? Protocollo risponde a queste domande con decisioni a scelta chiusa e probabilità, senza generare testo. È la stessa idea dei modelli "System One" come [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) e del progetto aperto [Rizzo Flow](https://github.com/Rizzo-AI-Academy/rizzo-flow), applicata a quello che solo un'azienda italiana riceve: FatturaPA e codici TD, split payment, reverse charge, F24, avvisi bonari, cartelle, PEC.

> **Stato: v0.0, preparazione.** Il repository contiene oggi le domande, il generatore di documenti con etichette esatte e la "prova zero", cioè quanto sa fare un modello aperto generico prima del nostro addestramento. Il modello addestrato e il benchmark etichettato da professionisti arrivano con la v0.1, prevista per novembre 2026.

> **Avvertenza.** Protocollo smista e segnala. Non sostituisce il commercialista o l'avvocato.

## Le domande

Lo stato è il testo del documento: corpo della PEC, testo del PDF allegato, XML della fattura, mail o messaggio. Le domande, in [protocollo/domande.json](protocollo/domande.json), sono nel formato `/v1/decisions` di Rizzo Flow:

| Gruppo | Domanda | Risposte |
|---|---|---|
| documento | `tipo` | fattura, nota di credito, parcella, DDT, ordine, conferma d'ordine, preventivo, sollecito, avviso bonario, cartella, INPS, INAIL, F24, diffida, atto giudiziario, contratto, candidatura, reclamo, richiesta cliente, pubblicità, phishing |
| | `ufficio` | amministrazione, commerciale, assistenza, logistica, personale, direzione, commercialista, avvocato, nessuno |
| | `azione` | pagare, rispondere, firmare, inoltrare a un professionista, archiviare, cestinare |
| | `scadenza`, `giorni` | c'è un termine? quanti giorni mancano dalla ricezione? |
| | `rischio` | niente, costo, sanzioni fiscali o contributive, conseguenze legali |
| | `phishing`, `dati_sensibili` | truffa? dati sanitari, giudiziari, di minori o documenti d'identità? |
| fattura | `codice_td`, `split_payment`, `reverse_charge`, `ritenuta` | TD01, TD04, TD06, TD17, TD24, altro; sì/no |
| coppia | `doppione` | due documenti: è la stessa fattura ricevuta due volte? |

## Il generatore

[generatore/genera.py](generatore/genera.py) crea documenti sintetici con **etichette esatte per costruzione**: le risposte giuste sono le scelte fatte dal programma, non il giudizio di un modello. Usa solo la libreria standard di Python.

- **Fatture elettroniche** di 10 tipi (ordinaria, professionista con cassa e ritenuta, parcella, forfettario con bollo, reverse charge edile, split payment verso un Comune, nota di credito, differita con DDT, integrazione per servizi esteri, acconto), in XML FatturaPA o come testo di un PDF di cortesia.
- **Coppie di fatture**: la stessa fattura ricevuta due volte, oppure due fatture simili ma diverse (per esempio un canone mensile).
- **F24** da pagare e quietanze, **DDT** (vendita, reso, conto lavorazione, conto visione).

```bash
python3 generatore/genera.py --n 1000 --seed 1 --out dati.jsonl --xml-dir xml/
uv run --with lxml python generatore/valida.py xml/
```

Gli XML generati vengono validati con lo **schema ufficiale FatturaPA 1.2.2**, che `valida.py` scarica da fatturapa.gov.it al primo avvio. Lo schema controlla la struttura, non tutte le regole dello SDI. I totali sono coerenti per costruzione.

Ogni documento è una riga JSONL:

```json
{"id": "gen-1-000042", "fonte": "fattura/reverse_charge", "gruppi": ["documento", "fattura"],
 "stato": "Ricevuto il 14/10/2026 tramite SDI\n...",
 "etichette": {"tipo": "fattura", "azione": "pagare", "scadenza": true, "giorni": 46,
               "reverse_charge": true, "split_payment": false, "...": "..."}}
```

### Documenti scritti da un modello linguistico

Avvisi del Fisco, cartelle, INPS e INAIL, diffide, atti giudiziari, contratti, reclami, ordini, candidature, pubblicità e truffe li scrive un modello a licenza aperta, seguendo i 38 scenari di [generatore/catalogo.py](generatore/catalogo.py). Il modello scrive solo il testo. **Le etichette le decide il programma** e le impone nel prompt: tipo di documento, termine esatto ("entro 30 giorni" o "entro il 14/11/2026"), presenza di dati sensibili, mittente (compresi i domini falsi delle truffe). [generatore/verifica.py](generatore/verifica.py) scarta i testi che non rispettano il prompt.

```bash
python3 generatore/genera_llm.py --n 5 --a-secco             # prompt e stima dei costi, senza chiamate
python3 generatore/genera_llm.py --n 50 --out dati/llm.jsonl # serve una chiave in .env (OpenRouter, Groq o Cerebras)
python3 generatore/verifica.py dati/llm.jsonl --ok dati/ok.jsonl --scarti dati/scarti.jsonl
```

Usiamo solo modelli la cui licenza permette di addestrare altri modelli sulle risposte (per esempio NVIDIA Nemotron, Qwen, gpt-oss, DeepSeek, Mistral). [generatore/verifica_llm.py](generatore/verifica_llm.py) fa rileggere ogni testo a un secondo modello che non vede le etichette.

### Il dataset

**[dacso-ai/protocollo-dati](https://huggingface.co/datasets/dacso-ai/protocollo-dati)** su Hugging Face: **17.459 documenti e 141.471 decisioni**. Sono 6.000 documenti dal generatore e 11.459 scritti da DeepSeek V4 Flash, sopravvissuti alle regole fisse e alla rilettura cieca di Mistral Small 3.2 (su 14.000 generati). Divisi in train 15.713, validation 873 e test 873. Costo totale di generazione e verifica: circa 2,40 $.

## La prova zero

[prova-zero/](prova-zero/) misura un modello aperto generico, prima di qualsiasi addestramento, su 50 documenti: 28 dal generatore e 22 scritti a mano (avvisi del Fisco, cartella, INPS, INAIL, diffida, decreto ingiuntivo, pignoramento, contratto, candidatura, reclami, ordini, 3 truffe).

Rizzo Flow 4B (Q8_0), 20/10/2026:

| | |
|---|---|
| Decisioni giuste | **328/399 (82%)** |
| Scadenze mancate | 0 su 25 |
| Truffe non viste | 1 su 3 (il cambio di IBAN di un finto fornitore) |
| Giorni alla scadenza giusti | 13/39 (33%) |
| Azione giusta | 26/44 (59%) |

L'82% è gonfiato dalle domande facili. Il modello generico sbaglia proprio dove serve conoscere l'Italia: manda a pagare avvisi bonari, cartelle, diffide e decreti ingiuntivi invece di passarli al professionista, tratta una nota di credito come una fattura da pagare e non riconosce come truffa la richiesta di cambiare IBAN. Dettagli ed errori uno per uno in [prova-zero/README.md](prova-zero/README.md).

```bash
cd prova-zero
python3 costruisci.py
python3 valuta.py --url http://127.0.0.1:8017 --nome rizzo-flow-4b-q8   # un server Rizzo Flow acceso
```

## Prossimi passi

1. Dataset di circa 20.000 documenti: metà dal generatore, metà (PEC, avvisi, truffe, mail) generata con modelli a licenza aperta.
2. Fine-tuning LoRA di un modello aperto da 4B, partendo da Rizzo Flow.
3. Benchmark pubblico di 600 documenti etichettati da commercialisti, un avvocato e un responsabile amministrativo, con due metriche nostre: **scadenze mancate** e **truffe non viste**.
4. `protocollo-pec`: uno script che legge una casella PEC in sola lettura e mette un'etichetta a ogni messaggio.

## Dati inventati

Aziende, persone, indirizzi, partite IVA, IBAN, domini e numeri di protocollo sono inventati o generati a caso. Le partite IVA e gli IBAN hanno cifre di controllo valide, ma non corrispondono a soggetti reali, se non per coincidenza. Nessun documento proviene da clienti reali.

## Licenza e crediti

Codice e dati: [Apache-2.0](LICENSE).

L'idea dei modelli "System One" è di [TypeSafe](https://typesafe.ai) (Jev). Il formato delle domande e il server usati nella prova zero sono di [Rizzo Flow](https://github.com/Rizzo-AI-Academy/rizzo-flow) (Apache-2.0), ispirato a [SemIf](https://github.com/TheoLeeCJ/SemIf). Protocollo non è affiliato a nessuno dei due progetti.

Un progetto di [DACSO](https://dacso.it), Crema.

---

## In English

**Protocollo** is an open model that triages the incoming mail of an Italian business (certified e-mail/PEC, FatturaPA e-invoices, tax notices, F24 payment forms, customer e-mails) into typed decisions with probabilities, running locally. This repository currently holds the question schema, a generator of synthetic Italian business documents with exact labels (FatturaPA XML validated against the official 1.2.2 schema), and a baseline: a generic open 4B decision model scores 82% overall but only 33% on days-to-deadline and 59% on next action, pays a credit note, and misses an IBAN-change fraud. The fine-tuned model and a professionally labelled benchmark are planned for v0.1 (November 2026). Apache-2.0.
