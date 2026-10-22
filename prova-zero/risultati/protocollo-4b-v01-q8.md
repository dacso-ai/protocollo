# Prova zero: protocollo-4b-v01-q8

50 documenti, 399 decisioni. Server http://127.0.0.1:8020.

- **Decisioni giuste: 394/399 (99%)**
- **Scadenze mancate: 0 su 25** 
- **Phishing non visto: 0 su 3** 
- Documenti veri scambiati per phishing: 0 
- Tempo per documento: mediana 22.0 s, massimo 47.1 s

## Per domanda

| Domanda | Giuste |
|---|---|
| tipo | 46/46 (100%) |
| ufficio | 43/44 (98%) |
| azione | 43/44 (98%) |
| scadenza | 39/39 (100%) |
| giorni | 37/39 (95%) |
| rischio | 43/43 (100%) |
| phishing | 46/46 (100%) |
| dati_sensibili | 46/46 (100%) |
| codice_td | 11/12 (92%) |
| split_payment | 12/12 (100%) |
| reverse_charge | 12/12 (100%) |
| ritenuta | 12/12 (100%) |
| doppione | 4/4 (100%) |

## Per fonte

| Fonte | Giuste |
|---|---|
| coppia | 4/4 (100%) |
| ddt | 45/46 (98%) |
| f24 | 48/48 (100%) |
| fattura | 143/144 (99%) |
| manuale/atto_giudiziario | 16/16 (100%) |
| manuale/avviso_bonario | 16/16 (100%) |
| manuale/candidatura | 8/8 (100%) |
| manuale/cartella | 8/8 (100%) |
| manuale/conferma_ordine | 6/7 (86%) |
| manuale/contratto | 7/8 (88%) |
| manuale/diffida | 8/8 (100%) |
| manuale/inail | 8/8 (100%) |
| manuale/inps | 15/15 (100%) |
| manuale/ordine | 6/6 (100%) |
| manuale/phishing | 15/15 (100%) |
| manuale/pubblicita | 6/6 (100%) |
| manuale/reclamo | 13/14 (93%) |
| manuale/richiesta_cliente | 14/14 (100%) |
| manuale/sollecito | 8/8 (100%) |

## Errori

- **gen-10** (fattura/acconto): codice_td: TD01 invece di altro
- **gen-28** (ddt/conto_visione): giorni: 58.02041290900387 invece di 43
- **man-09** (manuale/contratto): giorni: 16.419955743431686 invece di 11
- **man-12** (manuale/reclamo): ufficio: commerciale invece di assistenza
- **man-16** (manuale/conferma_ordine): azione: pagare invece di archiviare
