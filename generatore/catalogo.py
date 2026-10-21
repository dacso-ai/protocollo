"""Catalogo degli scenari per i documenti scritti da un modello linguistico.

Il modello scrive solo il testo. Tutto ciò che diventa un'etichetta lo decide il programma e lo
impone nel prompt: il tipo di documento, se c'è un termine e di quanti giorni, se ci sono dati
sensibili, il mittente (compresi i domini falsi delle truffe). Le etichette che dipendono da una
scelta di procedura (per esempio se un avviso bonario si "inoltra" o si "paga") sono quelle della
tabella sotto e vanno confermate dai professionisti del benchmark.

Ogni scenario: tipo, descrizione per il prompt, etichette fisse, termine, canale, stili ammessi.
Un'etichetta assente non viene valutata (risposta discutibile per quello scenario).
"""
import random

# termine: None = nessuna scadenza; (min, max) = giorni dalla ricezione scelti a caso;
# "dentro" = il termine c'è ma i giorni non si possono calcolare (es. data dell'udienza);
# "libero" = il testo può avere date (es. consegna richiesta) ma scadenza e giorni non si valutano
SCENARI = [
    # ---------------------------------------------------------------- Fisco e riscossione
    {"id": "avviso_36bis", "tipo": "avviso_bonario", "canale": "pec_ade",
     "descrizione": "Comunicazione di irregolarità dell'Agenzia delle Entrate ai sensi dell'art. 36-bis DPR 600/73 (controllo automatizzato della dichiarazione): imposta non versata, sanzioni ridotte, interessi, totale dovuto, possibilità di pagare con F24 o di chiedere la rettifica tramite CIVIS.",
     "etichette": {"ufficio": "commercialista", "azione": "inoltrare", "rischio": 2}, "termine": (30, 30), "stili": "ente"},
    {"id": "avviso_36ter", "tipo": "avviso_bonario", "canale": "pec_ade",
     "descrizione": "Richiesta dell'Agenzia delle Entrate di documenti per il controllo formale della dichiarazione (art. 36-ter DPR 600/73): elenco di ricevute, fatture o certificazioni da presentare.",
     "etichette": {"ufficio": "commercialista", "azione": "inoltrare", "rischio": 2}, "termine": (30, 30), "stili": "ente"},
    {"id": "avviso_compliance", "tipo": "avviso_bonario", "canale": "pec_ade",
     "descrizione": "Lettera di compliance dell'Agenzia delle Entrate (promozione dell'adempimento spontaneo): segnala possibili anomalie tra dati in possesso dell'Agenzia e dichiarazione, invita a regolarizzare con il ravvedimento o a fornire chiarimenti. Non fissa un termine.",
     "etichette": {"ufficio": "commercialista", "azione": "inoltrare", "rischio": 2}, "termine": None, "stili": "ente"},
    {"id": "cartella", "tipo": "cartella", "canale": "pec_ader",
     "descrizione": "Cartella di pagamento dell'Agenzia delle Entrate-Riscossione notificata via PEC: ente creditore, tributo e anno, importo a ruolo, diritti di notifica, totale; avverte che dopo il termine partono interessi di mora e procedure di recupero; si può chiedere la rateizzazione o fare ricorso.",
     "etichette": {"ufficio": "commercialista", "azione": "inoltrare", "rischio": 2}, "termine": (60, 60), "stili": "ente"},
    {"id": "intimazione", "tipo": "cartella", "canale": "pec_ader",
     "descrizione": "Intimazione di pagamento dell'Agenzia delle Entrate-Riscossione per cartelle già notificate e non pagate: avverte che, trascorso il termine, si procederà con pignoramento o fermo amministrativo senza ulteriore avviso.",
     "etichette": {"ufficio": "commercialista", "azione": "inoltrare", "rischio": 3}, "termine": (5, 5), "stili": "ente"},
    {"id": "rata_definizione", "tipo": "cartella", "canale": "mail_ader",
     "descrizione": "Promemoria dell'Agenzia delle Entrate-Riscossione per la prossima rata della definizione agevolata (rottamazione) delle cartelle: importo della rata, data di scadenza, codice RAV, avvertenza che il mancato pagamento fa decadere dal beneficio.",
     "etichette": {"ufficio": "amministrazione", "azione": "pagare", "rischio": 2}, "termine": (5, 40), "stili": "ente"},
    # ---------------------------------------------------------------- INPS e INAIL
    {"id": "inps_durc", "tipo": "inps", "canale": "pec_inps",
     "descrizione": "Invito dell'INPS a regolarizzare la posizione contributiva dopo una richiesta di DURC: elenco dei mesi con contributi non versati e importi; se non si regolarizza il DURC sarà negativo.",
     "etichette": {"ufficio": "personale", "azione": "pagare", "rischio": 2}, "termine": (15, 15), "stili": "ente"},
    {"id": "inps_addebito", "tipo": "inps", "canale": "pec_inps",
     "descrizione": "Avviso di addebito INPS con valore di titolo esecutivo per contributi non versati: periodo, importo, sanzioni civili, avvertenza che dopo il termine si procederà a esecuzione forzata.",
     "etichette": {"ufficio": "personale", "azione": "pagare", "rischio": 2}, "termine": (60, 60), "stili": "ente"},
    {"id": "inps_info", "tipo": "inps", "canale": "mail_inps",
     "descrizione": "Messaggio informativo dell'INPS ai datori di lavoro su una novità procedurale (UniEmens, conguagli, nuove causali): nessuna azione richiesta a chi si avvale di un intermediario.",
     "etichette": {"azione": "archiviare", "rischio": 0}, "termine": None, "stili": "ente"},
    {"id": "inail_autoliquidazione", "tipo": "inail", "canale": "pec_inail",
     "descrizione": "Comunicazione INAIL sull'autoliquidazione del premio: basi di calcolo disponibili online, scadenza del versamento con F24 e della dichiarazione delle retribuzioni.",
     "etichette": {"ufficio": "personale", "azione": "pagare", "rischio": 2}, "termine": (10, 45), "stili": "ente"},
    {"id": "inail_infortunio", "tipo": "inail", "canale": "pec_inail",
     "descrizione": "Richiesta INAIL al datore di lavoro di integrare la denuncia di infortunio di un dipendente: nome del lavoratore, diagnosi del pronto soccorso, giorni di prognosi, documenti da inviare.",
     "etichette": {"ufficio": "personale", "azione": "rispondere", "rischio": 2}, "termine": (10, 15), "stili": "ente",
     "sensibili": True},
    # ---------------------------------------------------------------- legale
    {"id": "diffida_credito", "tipo": "diffida", "canale": "pec_avvocato",
     "descrizione": "Diffida e messa in mora di un avvocato per conto di un fornitore: fatture non pagate con numeri, date e importi, interessi di mora D.Lgs. 231/2002, minaccia di azione giudiziale senza ulteriore avviso.",
     "etichette": {"ufficio": "avvocato", "azione": "inoltrare", "rischio": 3}, "termine": (7, 15), "stili": "legale"},
    {"id": "diffida_vizi", "tipo": "diffida", "canale": "pec_avvocato",
     "descrizione": "Lettera di un avvocato per conto di un cliente che contesta formalmente vizi della merce o del lavoro consegnato, chiede sostituzione o riduzione del prezzo e il risarcimento dei danni, altrimenti agirà in giudizio.",
     "etichette": {"ufficio": "avvocato", "azione": "inoltrare", "rischio": 3}, "termine": (8, 20), "stili": "legale"},
    {"id": "decreto_ingiuntivo", "tipo": "atto_giudiziario", "canale": "pec_avvocato",
     "descrizione": "Notifica via PEC (L. 53/1994) di un decreto ingiuntivo del Tribunale: ricorrente, somma ingiunta, spese liquidate, termine per pagare o proporre opposizione, avvertenza che senza opposizione diventa esecutivo.",
     "etichette": {"ufficio": "avvocato", "azione": "inoltrare", "rischio": 3}, "termine": (40, 40), "stili": "legale"},
    {"id": "citazione", "tipo": "atto_giudiziario", "canale": "pec_avvocato",
     "descrizione": "Atto di citazione in giudizio davanti al Tribunale notificato via PEC: parti, fatti, domande, data dell'udienza di comparizione tra alcuni mesi e invito a costituirsi nei termini di legge.",
     "etichette": {"ufficio": "avvocato", "azione": "inoltrare", "rischio": 3}, "termine": "dentro", "stili": "legale"},
    {"id": "pignoramento_terzi", "tipo": "atto_giudiziario", "canale": "pec_unep",
     "descrizione": "Atto di pignoramento presso terzi notificato all'azienda come datore di lavoro di un dipendente debitore: dati del dipendente, creditore, ordine di trattenere lo stipendio nei limiti di legge e di rendere la dichiarazione del terzo.",
     "etichette": {"ufficio": "avvocato", "azione": "inoltrare", "rischio": 3}, "termine": (10, 10), "stili": "legale",
     "sensibili": True},
    # ---------------------------------------------------------------- fornitori e contratti
    {"id": "sollecito", "tipo": "sollecito", "canale": "mail_azienda",
     "descrizione": "Sollecito di pagamento di un fornitore per una o più fatture scadute (numero, data, importo, scadenza originaria), con richiesta di pagare o comunicare la data del bonifico.",
     "etichette": {"ufficio": "amministrazione", "azione": "pagare", "rischio": 1}, "termine": (5, 15), "stili": "azienda"},
    {"id": "sollecito_sospensione", "tipo": "sollecito", "canale": "mail_azienda",
     "descrizione": "Secondo sollecito di un fornitore: avverte che se le fatture scadute non vengono pagate le forniture saranno sospese e la pratica passata al legale.",
     "etichette": {"ufficio": "amministrazione", "azione": "pagare", "rischio": 1}, "termine": (3, 10), "stili": "azienda"},
    {"id": "preventivo_fornitore", "tipo": "preventivo", "canale": "mail_azienda",
     "descrizione": "Offerta commerciale di un fornitore in risposta a una richiesta dell'azienda: articoli, quantità, prezzi, sconti, tempi di consegna, condizioni di pagamento e data di validità dell'offerta.",
     "etichette": {"rischio": 0}, "termine": (7, 30), "stili": "azienda"},
    {"id": "conferma_ordine", "tipo": "conferma_ordine", "canale": "mail_azienda",
     "descrizione": "Conferma d'ordine di un fornitore: riferimento all'ordine dell'azienda, articoli, prezzi, settimana di consegna prevista, condizioni di pagamento. Non chiede nulla.",
     "etichette": {"azione": "archiviare", "rischio": 0}, "termine": None, "stili": "azienda"},
    {"id": "contratto_firma", "tipo": "contratto", "canale": "mail_azienda",
     "descrizione": "Invio di un contratto da firmare e restituire (noleggio, manutenzione, fornitura di energia, software): oggetto, durata, canone, data entro cui restituirlo firmato per mantenere le condizioni.",
     "etichette": {"ufficio": "direzione", "azione": "firmare", "rischio": 1}, "termine": (5, 20), "stili": "azienda"},
    {"id": "contratto_rinnovo", "tipo": "contratto", "canale": "mail_azienda",
     "descrizione": "Comunicazione di un fornitore che il contratto si rinnoverà automaticamente con un nuovo prezzo, salvo disdetta da inviare entro una certa data.",
     "etichette": {"ufficio": "direzione", "rischio": 1}, "termine": (15, 60), "stili": "azienda"},
    # ---------------------------------------------------------------- clienti
    {"id": "reclamo_merce", "tipo": "reclamo", "canale": "cliente",
     "descrizione": "Reclamo di un cliente per merce arrivata danneggiata, sbagliata o incompleta: numero d'ordine, cosa non va, richiesta di sostituzione o rimborso.",
     "etichette": {"ufficio": "assistenza", "azione": "rispondere", "rischio": 1}, "termine": None, "stili": "cliente"},
    {"id": "reclamo_ritardo", "tipo": "reclamo", "canale": "cliente",
     "descrizione": "Lamentela di un cliente per una consegna o un intervento in ritardo, con richiesta di sapere quando arriverà.",
     "etichette": {"ufficio": "assistenza", "azione": "rispondere", "rischio": 1}, "termine": None, "stili": "cliente"},
    {"id": "reclamo_guasto", "tipo": "reclamo", "canale": "cliente",
     "descrizione": "Reclamo di un cliente per un prodotto o un impianto che si è guastato poco dopo l'acquisto o l'intervento, con richiesta di assistenza in garanzia.",
     "etichette": {"ufficio": "assistenza", "azione": "rispondere", "rischio": 1}, "termine": None, "stili": "cliente"},
    {"id": "richiesta_preventivo", "tipo": "richiesta_cliente", "canale": "cliente",
     "descrizione": "Richiesta di preventivo di un potenziale cliente: cosa gli serve, quantità, luogo di consegna o di intervento.",
     "etichette": {"ufficio": "commerciale", "azione": "rispondere", "rischio": 1}, "termine": None, "stili": "cliente"},
    {"id": "richiesta_info", "tipo": "richiesta_cliente", "canale": "cliente",
     "descrizione": "Domanda di un cliente su orari, disponibilità di un prodotto, tempi di consegna o zone servite.",
     "etichette": {"ufficio": "commerciale", "azione": "rispondere", "rischio": 1}, "termine": None, "stili": "cliente"},
    {"id": "ordine_cliente", "tipo": "ordine", "canale": "mail_cliente_azienda",
     "descrizione": "Ordine di acquisto di un cliente azienda: numero e data dell'ordine, codici, descrizioni, quantità, prezzi concordati, data di consegna richiesta, richiesta di conferma d'ordine.",
     "etichette": {"ufficio": "commerciale", "azione": "rispondere", "rischio": 1}, "termine": "libero", "stili": "azienda"},
    # ---------------------------------------------------------------- personale
    {"id": "candidatura", "tipo": "candidatura", "canale": "candidato",
     "descrizione": "Candidatura spontanea o in risposta a un annuncio, con breve lettera e curriculum nel corpo della mail: studi, esperienze, competenze.",
     "etichette": {"ufficio": "personale", "azione": "rispondere", "rischio": 0}, "termine": None, "stili": "cliente"},
    {"id": "candidatura_protetta", "tipo": "candidatura", "canale": "candidato",
     "descrizione": "Candidatura con curriculum in cui il candidato dichiara di appartenere alle categorie protette (L. 68/1999) indicando la percentuale di invalidità e allegando verbale medico e documento d'identità.",
     "etichette": {"ufficio": "personale", "azione": "rispondere", "rischio": 0}, "termine": None, "stili": "cliente",
     "sensibili": True},
    # ---------------------------------------------------------------- pubblicità
    {"id": "newsletter", "tipo": "pubblicita", "canale": "newsletter",
     "descrizione": "Newsletter promozionale (fiera, webinar, corso, offerta di un servizio) con link per iscriversi e per cancellarsi dalla lista.",
     "etichette": {"ufficio": "nessuno", "azione": "cestinare", "rischio": 0}, "termine": None, "stili": "promo"},
    {"id": "offerta_non_richiesta", "tipo": "pubblicita", "canale": "newsletter",
     "descrizione": "Mail commerciale non richiesta di un'azienda che propone i suoi servizi (consulenza, marketing, energia, software) e chiede una call conoscitiva.",
     "etichette": {"ufficio": "nessuno", "azione": "cestinare", "rischio": 0}, "termine": None, "stili": "promo"},
    # ---------------------------------------------------------------- truffe
    {"id": "phishing_rimborso", "tipo": "phishing", "canale": "phishing_ente",
     "descrizione": "Truffa: finta mail dell'Agenzia delle Entrate che annuncia un rimborso fiscale e chiede di confermare i dati bancari cliccando un link entro poche ore.",
     "etichette": {"phishing": True, "ufficio": "nessuno", "azione": "cestinare"}, "termine": "truffa", "stili": "truffa"},
    {"id": "phishing_fattura_link", "tipo": "phishing", "canale": "phishing_generico",
     "descrizione": "Truffa: finta notifica di una fattura scaduta o di un documento PEC disponibile solo online, con link da cliccare per scaricarlo e minaccia di passare la pratica al legale.",
     "etichette": {"phishing": True, "ufficio": "nessuno", "azione": "cestinare"}, "termine": "truffa", "stili": "truffa"},
    {"id": "phishing_iban", "tipo": "phishing", "canale": "phishing_fornitore",
     "descrizione": "Truffa del cambio IBAN: un finto fornitore abituale comunica che il conto bancario è cambiato (spesso un IBAN estero), chiede di pagare le fatture aperte sul nuovo conto, di non contattare la banca e di confermare via mail.",
     "etichette": {"phishing": True, "ufficio": "nessuno", "azione": "cestinare"}, "termine": "truffa", "stili": "truffa"},
    {"id": "phishing_ceo", "tipo": "phishing", "canale": "phishing_titolare",
     "descrizione": "Truffa del finto titolare: una mail che sembra del titolare o dell'amministratore chiede all'amministrazione un bonifico urgente e riservato per un'operazione importante, chiedendo di non parlarne con nessuno.",
     "etichette": {"phishing": True, "ufficio": "nessuno", "azione": "cestinare"}, "termine": "truffa", "stili": "truffa"},
    {"id": "phishing_inps", "tipo": "phishing", "canale": "phishing_ente",
     "descrizione": "Truffa: finto messaggio dell'INPS su un bonus o un rimborso contributivo da richiedere inserendo i dati della carta o dell'IBAN su un sito.",
     "etichette": {"phishing": True, "ufficio": "nessuno", "azione": "cestinare"}, "termine": "truffa", "stili": "truffa"},
    {"id": "phishing_casella", "tipo": "phishing", "canale": "phishing_generico",
     "descrizione": "Truffa: finto avviso del gestore della posta o della PEC che la casella è piena o sta per essere disattivata e chiede di accedere da un link con nome utente e password.",
     "etichette": {"phishing": True, "ufficio": "nessuno", "azione": "cestinare"}, "termine": "truffa", "stili": "truffa"},
]

STILI = {
    "ente": ["formale e burocratico, come i documenti ufficiali", "testo estratto con OCR da una scansione: qualche carattere sbagliato, a capo spezzati, intestazioni ripetute",
             "inoltrato da un collega con una riga sopra (es. \"Inoltro, vedi tu\") e poi il testo originale"],
    "legale": ["formale e giuridico, da studio legale o da cancelleria", "testo estratto con OCR da un PDF firmato digitalmente: qualche carattere sbagliato e a capo spezzati"],
    "azienda": ["formale e cortese, da ufficio amministrativo", "breve e diretto, poche righe", "con firma aziendale lunga e disclaimer sulla privacy in fondo",
                "inoltrato internamente con una riga sopra e poi il testo originale"],
    "cliente": ["cortese e ordinato", "frettoloso, frasi corte e qualche errore di battitura", "colloquiale da WhatsApp: niente maiuscole, abbreviazioni, emoji",
                "agitato o arrabbiato, con punti esclamativi", "lungo e confuso, con dettagli inutili", "testo trascritto da un messaggio vocale: niente punteggiatura, ripetizioni"],
    "promo": ["entusiasta da marketing, con elenchi puntati", "sobrio e professionale"],
    "truffa": ["formale ma con qualche errore di italiano o traduzione automatica", "urgente e minaccioso", "credibile e curato, quasi identico a una comunicazione vera"],
}

ENTI = {
    "pec_ade": ["dp.{prov}.ufficiocontrolli@pce.agenziaentrate.it", "cop.{prov}@pce.agenziaentrate.it"],
    "pec_ader": ["notifica.acc.{regione}@pec.agenziariscossione.gov.it"],
    "mail_ader": ["noreply@agenziaentrateriscossione.gov.it"],
    "pec_inps": ["direzione.provinciale.{prov}@postacert.inps.gov.it"],
    "mail_inps": ["comunicazioni@inps.it"],
    "pec_inail": ["{prov}@postacert.inail.it"],
    "pec_unep": ["unep.tribunale.{prov}@giustiziacert.it"],
}
DOMINI_TRUFFA = [".com", ".info", ".top", ".online", ".net", "-it.com"]


def mittente(r, canale, noi, altro, persona):
    """Indirizzo del mittente e nome da usare nel testo. Lo decide il programma, truffe comprese."""
    prov = noi["sede"]["comune"].lower()
    if canale in ENTI:
        indirizzo = r.choice(ENTI[canale]).format(prov=prov, regione="lombardia")
        return indirizzo, "PEC" if canale.startswith("pec") else "mail"
    if canale == "pec_avvocato":
        return f"avv.{persona['cognome'].lower()}@pec.ordineavvocati{r.choice(['milano', 'brescia', 'bergamo', 'cremona'])}.it", "PEC"
    if canale in ("mail_azienda", "mail_cliente_azienda"):
        return altro["mail"].replace("info@", r.choice(["amministrazione@", "info@", "vendite@", "ordini@"])), "mail"
    if canale == "cliente":
        if r.random() < 0.3:
            return f"+39 3{r.randint(20, 49)} {r.randint(100, 999)} {r.randint(1000, 9999)}", "WhatsApp"
        return f"{persona['nome'].lower()}.{persona['cognome'].lower()}{r.randint(1, 99)}@{r.choice(['gmail.com', 'libero.it', 'outlook.it', 'hotmail.it'])}", "mail"
    if canale == "candidato":
        return f"{persona['nome'].lower()}{persona['cognome'].lower()}{r.randint(70, 99)}@gmail.com", "mail"
    if canale == "newsletter":
        return f"newsletter@{r.choice(['fiera', 'eventi', 'formazione', 'offerte', 'energia'])}{r.choice(['lombardia', 'pmi', 'impresa', 'italia'])}.it", "mail"
    if canale == "phishing_ente":
        return f"{r.choice(['rimborsi', 'servizi', 'avvisi', 'noreply'])}@{r.choice(['agenziaentrate', 'inps', 'inps-servizi', 'agenzia-entrate'])}-{r.choice(['online', 'rimborsi', 'verifica', 'italia'])}{r.choice(DOMINI_TRUFFA)}", "mail"
    if canale == "phishing_fornitore":
        dominio = altro["mail"].split("@")[1].removesuffix(".it")
        return f"amministrazione@{dominio}{r.choice(['-srl.com', '-spa.com', '.it.com', '-italia.net'])}", "mail"
    if canale == "phishing_titolare":
        return f"{persona['nome'].lower()}.{persona['cognome'].lower()}.{r.choice(['direzione', 'ceo', 'ufficio'])}@{r.choice(['gmail.com', 'outlook.com', 'proton.me'])}", "mail"
    return f"{r.choice(['noreply', 'notifiche', 'fatturazione', 'pec-service'])}@{r.choice(['fatture-pec', 'docs-pec', 'posta-certificata', 'webmail-aruba'])}{r.choice(DOMINI_TRUFFA)}", "mail"


def scegli(r, scenario_id=None):
    return next(s for s in SCENARI if s["id"] == scenario_id) if scenario_id else r.choice(SCENARI)
