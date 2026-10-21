# Prova zero: rizzo-flow-4b-q8

50 documenti, 399 decisioni. Server http://127.0.0.1:8017.

- **Decisioni giuste: 328/399 (82%)**
- **Scadenze mancate: 0 su 25** 
- **Phishing non visto: 1 su 3** man-21
- Documenti veri scambiati per phishing: 0 
- Tempo per documento: mediana 18.8 s, massimo 41.5 s

## Per domanda

| Domanda | Giuste |
|---|---|
| tipo | 40/46 (87%) |
| ufficio | 36/44 (82%) |
| azione | 26/44 (59%) |
| scadenza | 38/39 (97%) |
| giorni | 13/39 (33%) |
| rischio | 33/43 (77%) |
| phishing | 45/46 (98%) |
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
| ddt | 32/46 (70%) |
| f24 | 44/48 (92%) |
| fattura | 127/144 (88%) |
| manuale/atto_giudiziario | 12/16 (75%) |
| manuale/avviso_bonario | 14/16 (88%) |
| manuale/candidatura | 7/8 (88%) |
| manuale/cartella | 5/8 (62%) |
| manuale/conferma_ordine | 3/7 (43%) |
| manuale/contratto | 8/8 (100%) |
| manuale/diffida | 7/8 (88%) |
| manuale/inail | 6/8 (75%) |
| manuale/inps | 14/15 (93%) |
| manuale/ordine | 6/6 (100%) |
| manuale/phishing | 6/15 (40%) |
| manuale/pubblicita | 3/6 (50%) |
| manuale/reclamo | 10/14 (71%) |
| manuale/richiesta_cliente | 14/14 (100%) |
| manuale/sollecito | 6/8 (75%) |

## Errori

- **gen-01** (fattura/ordinaria): giorni: 22.15155813720604 invece di 58
- **gen-02** (fattura/professionista): giorni: 14.436992034452395 invece di 28
- **gen-03** (fattura/parcella_avvocato): tipo: fattura invece di parcella; giorni: 31.609687868485437 invece di 73
- **gen-04** (fattura/forfettario): giorni: 23.68305982266165 invece di 53
- **gen-05** (fattura/reverse_charge): giorni: 38.58014024349424 invece di 84
- **gen-06** (fattura/split_payment): giorni: 28.795837094340158 invece di 81
- **gen-07** (fattura/nota_credito): tipo: fattura invece di nota_credito; azione: pagare invece di archiviare; rischio: 1 invece di 0
- **gen-08** (fattura/differita): giorni: 12.924593453672221 invece di 25
- **gen-09** (fattura/estero): azione: pagare invece di archiviare; rischio: 1 invece di 0
- **gen-10** (fattura/acconto): giorni: 29.889285083262152 invece di 84; codice_td: TD01 invece di altro
- **gen-11** (fattura/ordinaria): giorni: 24.338686496062607 invece di 55
- **gen-12** (fattura/ordinaria): giorni: 23.66076620640292 invece di 54
- **gen-17** (f24/delega): giorni: 9.929370865821708 invece di 5
- **gen-20** (f24/delega): giorni: 10.061836752461433 invece di 7
- **gen-21** (f24/quietanza): giorni: 3.731408470328474 invece di None
- **gen-22** (f24/quietanza): giorni: 8.030411962387785 invece di None
- **gen-23** (ddt/vendita): azione: firmare invece di archiviare; giorni: 7.318046560132967 invece di None; rischio: 1 invece di 0
- **gen-24** (ddt/vendita): azione: firmare invece di archiviare; giorni: 6.825405005148959 invece di None; rischio: 1 invece di 0
- **gen-25** (ddt/reso): azione: firmare invece di archiviare; giorni: 5.726060065301302 invece di None; rischio: 1 invece di 0
- **gen-26** (ddt/conto_lavorazione): azione: firmare invece di archiviare; giorni: 2.2052473879500436 invece di None; rischio: 1 invece di 0
- **gen-27** (ddt/conto_visione): giorni: 11.005117686216705 invece di 15
- **gen-28** (ddt/conto_visione): giorni: 20.61174262097549 invece di 43
- **man-01** (manuale/avviso_bonario): azione: pagare invece di inoltrare
- **man-02** (manuale/avviso_bonario): azione: rispondere invece di inoltrare
- **man-03** (manuale/cartella): azione: pagare invece di inoltrare; giorni: 38.9451762061251 invece di 60; rischio: 3 invece di 2
- **man-04** (manuale/inps): ufficio: amministrazione invece di personale
- **man-06** (manuale/inail): ufficio: amministrazione invece di personale; giorni: 16.42274166194742 invece di 27
- **man-07** (manuale/diffida): azione: pagare invece di inoltrare
- **man-08** (manuale/atto_giudiziario): azione: pagare invece di inoltrare; giorni: 12.343902279179595 invece di 40
- **man-10** (manuale/candidatura): rischio: 1 invece di 0
- **man-11** (manuale/reclamo): tipo: fattura invece di reclamo; ufficio: amministrazione invece di assistenza
- **man-12** (manuale/reclamo): tipo: ordine invece di reclamo; ufficio: logistica invece di assistenza
- **man-16** (manuale/conferma_ordine): azione: pagare invece di archiviare; scadenza: True invece di False; giorni: 18.483069089549303 invece di None; rischio: 1 invece di 0
- **man-17** (manuale/sollecito): azione: rispondere invece di pagare; giorni: None invece di 10
- **man-18** (manuale/pubblicita): ufficio: commerciale invece di nessuno; azione: archiviare invece di cestinare; rischio: 1 invece di 0
- **man-19** (manuale/phishing): tipo: nota_credito invece di phishing; ufficio: commercialista invece di nessuno; azione: firmare invece di cestinare
- **man-20** (manuale/phishing): tipo: fattura invece di phishing; ufficio: amministrazione invece di nessuno; azione: inoltrare invece di cestinare
- **man-21** (manuale/phishing): ufficio: amministrazione invece di nessuno; azione: rispondere invece di cestinare; phishing: False invece di True
- **man-22** (manuale/atto_giudiziario): azione: rispondere invece di inoltrare; giorni: 5.102916471068735 invece di 10
