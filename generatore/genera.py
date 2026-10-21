"""Genera documenti italiani sintetici (FatturaPA, F24, DDT) con etichette esatte per Protocollo.

Le etichette non vengono da un modello: sono le scelte fatte dal generatore (tipo di fattura,
regime IVA, scadenza...), quindi sono giuste per costruzione. Gli id delle risposte sono quelli
di protocollo/domande.json.

Ogni documento è un dict {"id", "fonte", "gruppi", "stato", "etichette"} e una riga del JSONL.
Un'etichetta None vuol dire "la risposta giusta è non si può dire" (es. giorni senza scadenza).

Uso:
  python3 genera.py --n 1000 --seed 1 --out dati.jsonl
  python3 genera.py --n 20 --seed 1 --xml-dir xml/     # salva anche gli XML, per validarli con l'XSD
"""
import argparse
import json
import random
import zlib
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
ET.register_namespace("p", NS)
ET.register_namespace("ds", "http://www.w3.org/2000/09/xmldsig#")

# ---------------------------------------------------------------- anagrafiche

COMUNI = [  # nome, CAP, provincia, codice catastale
    ("Crema", "26013", "CR", "D142"), ("Cremona", "26100", "CR", "D150"), ("Lodi", "26900", "LO", "E648"),
    ("Brescia", "25121", "BS", "B157"), ("Bergamo", "24121", "BG", "A794"), ("Milano", "20121", "MI", "F205"),
    ("Treviglio", "24047", "BG", "L400"), ("Piacenza", "29121", "PC", "G535"), ("Monza", "20900", "MB", "F704"),
    ("Pavia", "27100", "PV", "G388"), ("Lecco", "23900", "LC", "E507"), ("Mantova", "46100", "MN", "E897"),
]
VIE = ["Via Roma", "Via Garibaldi", "Via Mazzini", "Viale Europa", "Via dell'Industria", "Via degli Artigiani",
       "Via Milano", "Via Cavour", "Via Matteotti", "Via dei Mille", "Via Indipendenza", "Via Bergamo"]
NOMI = ["Marco", "Giulia", "Luca", "Francesca", "Andrea", "Chiara", "Paolo", "Elena", "Stefano", "Sara",
        "Davide", "Laura", "Matteo", "Silvia", "Alessandro", "Federica", "Roberto", "Valentina"]
COGNOMI = ["Rossi", "Bianchi", "Ferrari", "Colombo", "Ricci", "Marino", "Galli", "Conti", "Bruno", "Fontana",
           "Moretti", "Barbieri", "Lombardi", "Gatti", "Mariani", "Rinaldi", "Cattaneo", "Pellegrini"]
PREFISSI = ["Officine", "Tecno", "Meccanica", "Plastiche", "Edil", "Termoidraulica", "Agri", "Elettro",
            "Logistica", "Arredi", "Ferramenta", "Alimentari", "Serramenti", "Grafiche", "Impianti", "Carpenteria"]
SUFFISSI = ["Lombarda", "Padana", "del Serio", "Cremasca", "Bresciana", "Nord", "dell'Adda", "Italia",
            "dell'Oglio", "Po", "Orobica", "Brianza"]
FORME = ["S.r.l.", "S.r.l.", "S.r.l.", "S.p.A.", "S.n.c.", "S.a.s.", "S.r.l.s."]
BANCHE = ["Banca del Territorio Lombardo", "Credito Padano", "Cassa Rurale dell'Adda", "Banca Popolare Orobica"]
VETTORI = ["Trasporti Padani S.r.l.", "Autotrasporti Serio S.n.c.", "Spedizioni Lombarde S.p.A."]

# prodotti e servizi: descrizione, unità di misura, prezzo min, prezzo max, aliquota IVA
BENI = {  # settore: [(descrizione, unità di misura, prezzo min, prezzo max, aliquota IVA)]
    "ferramenta": [("Viti autofilettanti 4x40 conf. 500 pz", "CF", 8, 15, 22), ("Tubo multistrato 16x2 rotolo 100 m", "RT", 90, 160, 22),
                   ("Pannello OSB 18 mm 250x125", "PZ", 18, 30, 22), ("Guanti da lavoro in nitrile tg. L", "CF", 6, 12, 22),
                   ("Olio idraulico ISO 46 fusto 20 L", "PZ", 60, 110, 22), ("Silicone sigillante trasparente 310 ml", "PZ", 3, 7, 22)],
    "ufficio": [("Toner compatibile nero", "PZ", 25, 60, 22), ("Carta A4 80 g risma 500 fogli", "RS", 3, 6, 22),
                ("Raccoglitore ad anelli dorso 8 cm", "PZ", 2, 5, 22), ("Bancale EPAL 80x120 usato", "PZ", 7, 14, 22)],
    "alimentari": [("Grana Padano DOP stagionato 16 mesi", "KG", 9, 15, 4), ("Farina di grano tenero tipo 00 sacco 25 kg", "PZ", 12, 20, 4),
                   ("Prosciutto cotto alta qualità", "KG", 10, 18, 10), ("Acqua minerale naturale 1,5 L x 6", "CF", 2, 4, 22),
                   ("Salame cremasco", "KG", 12, 20, 10)],
    "agricoltura": [("Pellet di abete certificato sacco 15 kg", "PZ", 4, 7, 22), ("Mangime per bovini da latte", "QL", 30, 45, 10),
                    ("Seme di mais ibrido sacco 50.000 semi", "PZ", 90, 160, 10), ("Telo pacciamante nero rotolo", "RT", 40, 80, 22)],
}
SERVIZI = [
    ("Manutenzione ordinaria impianto di climatizzazione", 120, 900), ("Assistenza tecnica su macchina CNC", 200, 1500),
    ("Servizio di pulizia uffici mese di {mese}", 300, 1200), ("Noleggio carrello elevatore mese di {mese}", 400, 900),
    ("Canone software gestionale mese di {mese}", 50, 300), ("Trasporto merce Crema-Milano", 150, 600),
]
PROFESSIONI = [  # titolo, servizio, tipo cassa, aliquota cassa
    ("Dott.", "Consulenza fiscale e tenuta contabilità mese di {mese}", "TC04", "4.00"),
    ("Dott.", "Elaborazione cedolini paga mese di {mese}", "TC04", "4.00"),
    ("Ing.", "Progettazione impianto elettrico capannone", "TC02", "4.00"),
    ("Geom.", "Pratica edilizia SCIA e direzione lavori", "TC03", "5.00"),
]
LAVORI_EDILI = ["Lavori di tinteggiatura cantiere {via}", "Posa pavimenti in subappalto cantiere {via}",
                "Opere di cartongesso cantiere {via}", "Installazione impianto idraulico cantiere {via}"]
SERVIZI_ESTERI = [("Nordcloud Services Ltd", "IE", "Dublin", "Servizio cloud hosting {mese}"),
                  ("Adsphere Europe B.V.", "NL", "Amsterdam", "Campagna pubblicitaria online {mese}"),
                  ("Softwerk GmbH", "DE", "München", "Licenza software in abbonamento {mese}")]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]

DUE = Decimal("0.01")


def d2(x):
    return Decimal(x).quantize(DUE, rounding=ROUND_HALF_UP)


def euro(x):
    """1234.5 -> '1.234,50'"""
    s = f"{d2(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def gg(d):
    return d.strftime("%d/%m/%Y")


def piva(r):
    cifre = [r.randint(0, 9) for _ in range(7)] + [int(c) for c in f"{r.randint(1, 120):03d}"]
    somma = 0
    for i, c in enumerate(cifre):
        if i % 2 == 0:
            somma += c
        else:
            somma += c * 2 - 9 if c * 2 > 9 else c * 2
    return "".join(map(str, cifre)) + str((10 - somma % 10) % 10)


def iban(r):
    bban = r.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + "".join(str(r.randint(0, 9)) for _ in range(10)) + \
        "".join(str(r.randint(0, 9)) for _ in range(12))
    numeri = "".join(str(int(c, 36)) for c in bban + "IT00")
    return f"IT{98 - int(numeri) % 97:02d}{bban}"


def alfanum(r, n):
    return "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(n))


def luogo(r):
    comune, cap, prov, catasto = r.choice(COMUNI)
    return {"via": f"{r.choice(VIE)} {r.randint(1, 120)}", "cap": cap, "comune": comune, "prov": prov,
            "catasto": catasto, "nazione": "IT"}


def azienda(r):
    if r.random() < 0.2:
        nome = f"{r.choice(COGNOMI)} & Figli {r.choice(['S.n.c.', 'S.a.s.'])}"
    else:
        nome = f"{r.choice(PREFISSI)} {r.choice(SUFFISSI)} {r.choice(FORME)}"
    p = piva(r)
    dominio = nome.split()[0].lower().replace("'", "") + r.choice(["srl", "group", "", "italia"]) + ".it"
    return {"denominazione": nome, "piva": p, "cf": p, "sede": luogo(r), "pec": f"amministrazione@pec.{dominio}",
            "mail": f"info@{dominio}", "iban": iban(r), "regime": "RF01"}


FEMMINILI = {"Giulia", "Francesca", "Chiara", "Elena", "Sara", "Laura", "Silvia", "Federica", "Valentina"}


def persona(r, titolo=""):
    nome, cognome = r.choice(NOMI), r.choice(COGNOMI)
    if nome in FEMMINILI and titolo == "Dott.":
        titolo = "Dott.ssa"
    return {"nome": nome, "cognome": cognome, "titolo": titolo, "piva": piva(r), "sede": luogo(r),
            "denominazione": f"{titolo} {nome} {cognome}".strip(), "regime": "RF01", "iban": iban(r),
            "pec": f"{nome.lower()}.{cognome.lower()}@pec.it", "mail": f"studio.{cognome.lower()}@mail.it"}


def comune_pa(r):
    sede = luogo(r)
    return {"denominazione": f"Comune di {sede['comune']}", "cf": f"00{r.randint(100000000, 999999999)}",
            "sede": {**sede, "via": "Piazza del Municipio 1"}, "codice_ufficio": alfanum(r, 6)}


def data_ricezione(r):
    return date(2026, 9, 1) + timedelta(days=r.randint(0, 110))


# ---------------------------------------------------------------- fatture

TIPI_FATTURA = {  # tipo: peso nel generatore casuale
    "ordinaria": 30, "professionista": 10, "parcella_avvocato": 6, "forfettario": 8, "reverse_charge": 8,
    "split_payment": 8, "nota_credito": 8, "differita": 8, "estero": 5, "acconto": 3,
}


def fattura(r, tipo, formato=None, ricevuta=None):
    """Una fattura passiva (ricevuta dall'azienda) di un certo tipo, in XML o come testo di un PDF."""
    formato = formato or r.choice(["xml", "pdf"])
    ricevuta = ricevuta or data_ricezione(r)
    data_doc = ricevuta - timedelta(days=r.randint(0, 6))
    mese = MESI[(data_doc.month - 2) % 12]
    noi = azienda(r)
    f = {"tipo": tipo, "td": "TD01", "data": data_doc, "numero": f"{r.randint(1, 980)}{r.choice(['', '/26', '/FE', '-2026'])}",
         "cedente": azienda(r), "cessionario": noi, "righe": [], "ritenuta": None, "cassa": None, "bollo": False,
         "esigibilita": "I", "collegata": None, "ddt": [], "pagamento": True, "formato_sdi": "FPR12", "cig": None,
         "emittente": None, "causale": None}

    if tipo in ("ordinaria", "acconto", "differita", "nota_credito", "split_payment"):
        settore = r.choice(list(BENI))
        for _ in range(r.randint(1, 5)):
            if r.random() < 0.7:
                desc, um, pmin, pmax, aliq = r.choice(BENI[settore])
                q = d2(r.randint(1, 40))
            else:
                desc, pmin, pmax = r.choice(SERVIZI)
                desc, um, aliq, q = desc.format(mese=mese), None, 22, d2(1)
            f["righe"].append({"desc": desc, "um": um, "q": q, "prezzo": d2(r.uniform(pmin, pmax)), "aliq": aliq})
    if tipo == "acconto":
        f["td"] = "TD02"
        f["causale"] = "Acconto del 30% su ordine " + str(r.randint(100, 900))
    if tipo == "differita":
        f["td"] = "TD24"
        for _ in range(r.randint(1, 3)):
            f["ddt"].append((f"{r.randint(100, 2000)}/26", data_doc - timedelta(days=r.randint(3, 28))))
    if tipo == "nota_credito":
        f["td"] = "TD04"
        f["pagamento"] = False
        f["collegata"] = (f"{r.randint(1, 900)}/26", data_doc - timedelta(days=r.randint(10, 60)))
        f["causale"] = r.choice(["Storno per reso merce non conforme", "Sconto concordato su fattura precedente",
                                 "Storno totale per errata fatturazione"])
    if tipo == "split_payment":
        f["cessionario"] = comune_pa(r)
        f["esigibilita"] = "S"
        f["formato_sdi"] = "FPA12"
        f["cig"] = alfanum(r, 10)
    if tipo in ("professionista", "parcella_avvocato"):
        if tipo == "parcella_avvocato":
            f["td"] = "TD06" if r.random() < 0.7 else "TD01"
            f["cedente"] = persona(r, "Avv.")
            desc, cassa, al_cassa = "Assistenza legale stragiudiziale pratica recupero crediti", "TC01", "4.00"
        else:
            titolo, desc, cassa, al_cassa = r.choice(PROFESSIONI)
            f["cedente"] = persona(r, titolo)
            desc = desc.format(mese=mese)
        compenso = d2(r.uniform(300, 3500))
        f["righe"].append({"desc": desc, "um": None, "q": d2(1), "prezzo": compenso, "aliq": 22, "ritenuta": True})
        f["cassa"] = {"tipo": cassa, "al": Decimal(al_cassa), "imponibile": compenso,
                      "importo": d2(compenso * Decimal(al_cassa) / 100)}
        f["ritenuta"] = {"aliquota": Decimal("20.00"), "importo": d2(compenso * Decimal("0.20"))}
    if tipo == "forfettario":
        f["cedente"] = persona(r, r.choice(["", "", "Dott.", "Geom."]))
        f["cedente"]["regime"] = "RF19"
        desc, pmin, pmax = r.choice(SERVIZI)
        f["righe"].append({"desc": desc.format(mese=mese), "um": None, "q": d2(1), "prezzo": d2(r.uniform(150, 2500)),
                           "aliq": 0, "natura": "N2.2"})
        f["righe"].append({"desc": "Rimborso imposta di bollo", "um": None, "q": d2(1), "prezzo": d2(2), "aliq": 0,
                           "natura": "N1"})
        f["bollo"] = True
    if tipo == "reverse_charge":
        desc = r.choice(LAVORI_EDILI).format(via=r.choice(VIE))
        f["righe"].append({"desc": desc, "um": None, "q": d2(1), "prezzo": d2(r.uniform(800, 12000)), "aliq": 0,
                           "natura": "N6.3"})
    if tipo == "estero":
        nome, paese, citta, desc = r.choice(SERVIZI_ESTERI)
        f["td"] = "TD17"
        f["pagamento"] = False
        f["cedente"] = {"denominazione": nome, "piva": paese + alfanum(r, 9), "paese": paese, "regime": "RF18",
                        "sede": {"via": "Main Street 10", "cap": "00000", "comune": citta, "prov": None, "nazione": paese}}
        f["emittente"] = "CC"
        f["collegata"] = (f"INV-{r.randint(10000, 99999)}", data_doc - timedelta(days=r.randint(1, 20)))
        f["righe"].append({"desc": desc.format(mese=mese), "um": None, "q": d2(1), "prezzo": d2(r.uniform(40, 3000)),
                           "aliq": 22})

    calcola(f)
    if f["pagamento"]:
        giorni_termine = r.choice([0, 30, 30, 60, 60, 90, "fm30", "fm60"])
        if isinstance(giorni_termine, str):
            base = data_doc + timedelta(days=int(giorni_termine[2:]))
            scadenza = date(base.year + base.month // 12, base.month % 12 + 1, 1) - timedelta(days=1)
        else:
            scadenza = data_doc + timedelta(days=giorni_termine)
        f["scadenza"] = scadenza
        f["modalita"] = r.choice(["MP05", "MP05", "MP05", "MP12"])
    else:
        f["scadenza"] = None

    testo = fattura_xml(f) if formato == "xml" else fattura_testo(f, r)
    if formato == "xml":
        nome_file = f"IT{f['cedente']['piva'][-11:]}_{alfanum(r, 5)}.xml"
        intestazione = f"Ricevuto il {gg(ricevuta)} tramite SDI\nFile: {nome_file}\n\n"
    else:
        mittente = f["cedente"].get("pec") or f["cedente"].get("mail") or "billing@" + f["cedente"]["denominazione"].split()[0].lower() + ".com"
        intestazione = (f"Ricevuto il {gg(ricevuta)} via PEC da {mittente}\nOggetto: Invio documento n. {f['numero']}\n"
                        f"Allegato: documento_{f['numero'].replace('/', '-')}.pdf (testo estratto)\n\n")
    return {"stato": intestazione + testo, "etichette": etichette_fattura(f, ricevuta), "xml": testo if formato == "xml" else None,
            "fattura": f}


def calcola(f):
    riepilogo = {}
    for riga in f["righe"]:
        riga["totale"] = d2(riga["q"] * riga["prezzo"])
        chiave = (riga["aliq"], riga.get("natura"))
        riepilogo[chiave] = riepilogo.get(chiave, Decimal(0)) + riga["totale"]
    if f["cassa"]:
        riepilogo[(22, None)] = riepilogo.get((22, None), Decimal(0)) + f["cassa"]["importo"]
    f["riepilogo"] = []
    for (aliq, natura), imponibile in riepilogo.items():
        imposta = d2(imponibile * aliq / 100)
        f["riepilogo"].append({"aliq": aliq, "natura": natura, "imponibile": d2(imponibile), "imposta": imposta})
    f["imponibile"] = sum(x["imponibile"] for x in f["riepilogo"])
    f["iva"] = sum(x["imposta"] for x in f["riepilogo"])
    f["totale"] = f["imponibile"] + f["iva"]
    netto = f["totale"] - (f["ritenuta"]["importo"] if f["ritenuta"] else 0)
    if f["esigibilita"] == "S":
        netto -= f["iva"]
    f["netto"] = d2(netto)


def etichette_fattura(f, ricevuta):
    da_pagare = f["pagamento"]
    giorni = (f["scadenza"] - ricevuta).days if da_pagare else None
    if f["td"] == "TD04":
        tipo = "nota_credito"
    elif f["tipo"] in ("professionista", "parcella_avvocato"):
        tipo = "parcella"
    else:
        tipo = "fattura"
    return {
        "tipo": tipo, "ufficio": "amministrazione", "azione": "pagare" if da_pagare else "archiviare",
        "scadenza": da_pagare, "giorni": giorni, "rischio": 1 if da_pagare else 0,
        "phishing": False, "dati_sensibili": False,
        "codice_td": f["td"] if f["td"] in ("TD01", "TD04", "TD06", "TD17", "TD24") else "altro",
        "split_payment": f["esigibilita"] == "S",
        "reverse_charge": any((x.get("natura") or "").startswith("N6") for x in f["righe"]),
        "ritenuta": f["ritenuta"] is not None,
    }


def sub(padre, tag, testo=None):
    e = ET.SubElement(padre, tag)
    if testo is not None:
        e.text = str(testo)
    return e


def anagrafica_xml(padre, s, cedente):
    da = sub(padre, "DatiAnagrafici")
    if "paese" in s:
        idf = sub(da, "IdFiscaleIVA")
        sub(idf, "IdPaese", s["paese"])
        sub(idf, "IdCodice", s["piva"][2:])
    elif "piva" in s:
        idf = sub(da, "IdFiscaleIVA")
        sub(idf, "IdPaese", "IT")
        sub(idf, "IdCodice", s["piva"])
    if "cf" in s:
        sub(da, "CodiceFiscale", s["cf"])
    an = sub(da, "Anagrafica")
    if "nome" in s:
        sub(an, "Nome", s["nome"])
        sub(an, "Cognome", s["cognome"])
        if s["titolo"]:
            sub(an, "Titolo", s["titolo"])
    else:
        sub(an, "Denominazione", s["denominazione"])
    if cedente:
        sub(da, "RegimeFiscale", s["regime"])
    sede = sub(padre, "Sede")
    sub(sede, "Indirizzo", s["sede"]["via"])
    sub(sede, "CAP", s["sede"]["cap"])
    sub(sede, "Comune", s["sede"]["comune"])
    if s["sede"].get("prov"):
        sub(sede, "Provincia", s["sede"]["prov"])
    sub(sede, "Nazione", s["sede"]["nazione"])


def fattura_xml(f):
    radice = ET.Element(f"{{{NS}}}FatturaElettronica", {"versione": f["formato_sdi"]})
    testa = sub(radice, "FatturaElettronicaHeader")
    dt = sub(testa, "DatiTrasmissione")
    idt = sub(dt, "IdTrasmittente")
    trasmittente = f["cessionario"] if f["emittente"] == "CC" else f["cedente"]
    sub(idt, "IdPaese", "IT")
    sub(idt, "IdCodice", trasmittente.get("piva") or trasmittente["cf"])
    sub(dt, "ProgressivoInvio", f"{zlib.crc32(f['numero'].encode()) % 99999:05d}")
    sub(dt, "FormatoTrasmissione", f["formato_sdi"])
    sub(dt, "CodiceDestinatario", f["cessionario"]["codice_ufficio"] if f["formato_sdi"] == "FPA12" else "0000000")
    if f["formato_sdi"] == "FPR12":
        sub(dt, "PECDestinatario", f["cessionario"]["pec"])
    anagrafica_xml(sub(testa, "CedentePrestatore"), f["cedente"], True)
    cess = dict(f["cessionario"])
    if f["formato_sdi"] == "FPA12":
        cess.pop("piva", None)
    anagrafica_xml(sub(testa, "CessionarioCommittente"), cess, False)
    if f["emittente"]:
        sub(testa, "SoggettoEmittente", f["emittente"])

    corpo = sub(radice, "FatturaElettronicaBody")
    dg = sub(corpo, "DatiGenerali")
    dgd = sub(dg, "DatiGeneraliDocumento")
    sub(dgd, "TipoDocumento", f["td"])
    sub(dgd, "Divisa", "EUR")
    sub(dgd, "Data", f["data"].isoformat())
    sub(dgd, "Numero", f["numero"])
    if f["ritenuta"]:
        rit = sub(dgd, "DatiRitenuta")
        sub(rit, "TipoRitenuta", "RT01")
        sub(rit, "ImportoRitenuta", f["ritenuta"]["importo"])
        sub(rit, "AliquotaRitenuta", f["ritenuta"]["aliquota"])
        sub(rit, "CausalePagamento", "A")
    if f["bollo"]:
        b = sub(dgd, "DatiBollo")
        sub(b, "BolloVirtuale", "SI")
        sub(b, "ImportoBollo", "2.00")
    if f["cassa"]:
        c = sub(dgd, "DatiCassaPrevidenziale")
        sub(c, "TipoCassa", f["cassa"]["tipo"])
        sub(c, "AlCassa", f["cassa"]["al"])
        sub(c, "ImportoContributoCassa", f["cassa"]["importo"])
        sub(c, "ImponibileCassa", f["cassa"]["imponibile"])
        sub(c, "AliquotaIVA", "22.00")
    sub(dgd, "ImportoTotaleDocumento", f["totale"])
    if f["causale"]:
        sub(dgd, "Causale", f["causale"])
    if f["cig"]:
        oa = sub(dg, "DatiOrdineAcquisto")
        sub(oa, "IdDocumento", f"Determina {f['data'].year}/{len(f['cig'])}")
        sub(oa, "CodiceCIG", f["cig"])
    if f["collegata"]:
        fc = sub(dg, "DatiFattureCollegate")
        sub(fc, "IdDocumento", f["collegata"][0])
        sub(fc, "Data", f["collegata"][1].isoformat())
    for numero, data_ddt in f["ddt"]:
        dd = sub(dg, "DatiDDT")
        sub(dd, "NumeroDDT", numero)
        sub(dd, "DataDDT", data_ddt.isoformat())

    dbs = sub(corpo, "DatiBeniServizi")
    for i, riga in enumerate(f["righe"], 1):
        dl = sub(dbs, "DettaglioLinee")
        sub(dl, "NumeroLinea", i)
        sub(dl, "Descrizione", riga["desc"])
        sub(dl, "Quantita", riga["q"])
        if riga["um"]:
            sub(dl, "UnitaMisura", riga["um"])
        sub(dl, "PrezzoUnitario", riga["prezzo"])
        sub(dl, "PrezzoTotale", riga["totale"])
        sub(dl, "AliquotaIVA", d2(riga["aliq"]))
        if riga.get("ritenuta"):
            sub(dl, "Ritenuta", "SI")
        if riga.get("natura"):
            sub(dl, "Natura", riga["natura"])
    for x in f["riepilogo"]:
        rp = sub(dbs, "DatiRiepilogo")
        sub(rp, "AliquotaIVA", d2(x["aliq"]))
        if x["natura"]:
            sub(rp, "Natura", x["natura"])
        sub(rp, "ImponibileImporto", x["imponibile"])
        sub(rp, "Imposta", x["imposta"])
        if not x["natura"]:
            sub(rp, "EsigibilitaIVA", f["esigibilita"])
        if x["natura"]:
            sub(rp, "RiferimentoNormativo", NORME[x["natura"]])
        elif f["esigibilita"] == "S":
            sub(rp, "RiferimentoNormativo", "Scissione dei pagamenti art. 17-ter DPR 633/72")

    if f["pagamento"]:
        dp = sub(corpo, "DatiPagamento")
        sub(dp, "CondizioniPagamento", "TP02")
        det = sub(dp, "DettaglioPagamento")
        sub(det, "ModalitaPagamento", f["modalita"])
        sub(det, "DataScadenzaPagamento", f["scadenza"].isoformat())
        sub(det, "ImportoPagamento", f["netto"])
        if f["modalita"] == "MP05":
            sub(det, "IstitutoFinanziario", BANCHE[int(f["cedente"]["piva"][-1]) % len(BANCHE)])
            sub(det, "IBAN", f["cedente"]["iban"])
    ET.indent(radice)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(radice, encoding="unicode")


NORME = {
    "N1": "Escluse ex art. 15 DPR 633/72",
    "N2.2": "Operazione in franchigia da IVA ai sensi dell'art. 1, commi 54-89, L. 190/2014 (regime forfettario)",
    "N6.3": "Inversione contabile - art. 17, comma 6, lett. a), DPR 633/72 (subappalto nel settore edile)",
}
TITOLI_TD = {"TD01": "FATTURA", "TD02": "FATTURA DI ACCONTO", "TD04": "NOTA DI CREDITO", "TD06": "PARCELLA",
             "TD17": "INTEGRAZIONE / AUTOFATTURA PER ACQUISTO SERVIZI DALL'ESTERO", "TD24": "FATTURA DIFFERITA"}
CASSE = {"TC01": "Cassa Forense", "TC02": "Inarcassa", "TC03": "Cassa Geometri", "TC04": "Cassa Dottori Commercialisti"}


def soggetto_testo(s):
    sede = s["sede"]
    prov = f" ({sede['prov']})" if sede.get("prov") else f" - {sede['nazione']}"
    ident = f"P.IVA {s['piva']}" if "piva" in s else f"C.F. {s['cf']}"
    return f"{s['denominazione']}\n{sede['via']} - {sede['cap']} {sede['comune']}{prov}\n{ident}"


def fattura_testo(f, r):
    """Il testo che si estrae dal PDF di cortesia di un gestionale qualunque."""
    righe = [f"{TITOLI_TD[f['td']]} N. {f['numero']} DEL {gg(f['data'])}"]
    if r.random() < 0.6:
        righe.append(f"Tipo documento: {f['td']}")
    righe += ["", "Fornitore:", soggetto_testo(f["cedente"]), "", "Cliente:", soggetto_testo(f["cessionario"]), ""]
    if f["cig"]:
        righe.append(f"CIG: {f['cig']}")
    if f["collegata"]:
        righe.append(f"Rif. fattura n. {f['collegata'][0]} del {gg(f['collegata'][1])}")
    for numero, data_ddt in f["ddt"]:
        righe.append(f"Rif. DDT n. {numero} del {gg(data_ddt)}")
    if f["causale"]:
        righe.append(f["causale"])
    righe += ["", "Descrizione | Q.tà | Prezzo | Importo | IVA"]
    for riga in f["righe"]:
        iva = riga.get("natura") or f"{riga['aliq']}%"
        righe.append(f"{riga['desc']} | {euro(riga['q'])} {riga['um'] or ''} | {euro(riga['prezzo'])} | {euro(riga['totale'])} | {iva}")
    righe.append("")
    if f["cassa"]:
        righe.append(f"Contributo {CASSE[f['cassa']['tipo']]} {f['cassa']['al']}%: {euro(f['cassa']['importo'])}")
    for x in f["riepilogo"]:
        etichetta = x["natura"] or f"IVA {x['aliq']}%"
        righe.append(f"Imponibile {etichetta}: {euro(x['imponibile'])}   Imposta: {euro(x['imposta'])}")
        if x["natura"]:
            righe.append(NORME[x["natura"]])
    if f["esigibilita"] == "S":
        righe.append("Scissione dei pagamenti art. 17-ter DPR 633/72: IVA da versare a cura del committente")
    if f["bollo"]:
        righe.append("Imposta di bollo assolta in modo virtuale: 2,00")
    righe.append(f"TOTALE DOCUMENTO: € {euro(f['totale'])}")
    if f["ritenuta"]:
        righe.append(f"Ritenuta d'acconto {f['ritenuta']['aliquota']}%: - {euro(f['ritenuta']['importo'])}")
    if f["pagamento"]:
        righe.append(f"NETTO A PAGARE: € {euro(f['netto'])}")
        if f["modalita"] == "MP05":
            righe.append(f"Pagamento: bonifico bancario su IBAN {f['cedente']['iban']} - scadenza {gg(f['scadenza'])}")
        else:
            righe.append(f"Pagamento: Ri.Ba. con scadenza {gg(f['scadenza'])}")
    elif f["td"] == "TD04":
        righe.append("Documento non soggetto a pagamento: l'importo verrà compensato o rimborsato.")
    else:
        righe.append("Documento emesso dal committente ai fini dell'integrazione IVA: nessun pagamento al fornitore.")
    return "\n".join(righe)


def coppia(r, doppione, variante=None):
    """Due fatture nella stessa casella: stessa fattura due volte, oppure due fatture simili ma diverse."""
    ricevuta = data_ricezione(r)
    seme = r.random()
    uno = fattura(random.Random(seme), "ordinaria", "pdf", ricevuta)
    if doppione:
        due = fattura(random.Random(seme), "ordinaria", "pdf", ricevuta)
        # stessa fattura, arrivata una volta da SDI e una via mail: cambia solo l'intestazione
        due["stato"] = due["stato"].replace("via PEC da", "via mail da").replace("Oggetto: Invio documento", "Oggetto: Copia di cortesia documento")
    else:
        variante = variante or r.choice(["altro_numero", "canone"])
        f1 = uno["fattura"]
        rr = random.Random(seme)
        due = fattura(rr, "ordinaria", "pdf", ricevuta)
        f2 = due["fattura"]
        if variante == "canone":
            # stesso fornitore e stesso importo, ma mese diverso: canone mensile, non un doppione
            nuovo = f"{int(''.join(c for c in f1['numero'] if c.isdigit())[:3] or 1) + 1}/26"
            mese_prima = MESI[(f1['data'].month - 3) % 12]
            mese_ora = MESI[(f1['data'].month - 2) % 12]
            testo = due["stato"].replace(f"N. {f1['numero']} DEL", f"N. {nuovo} DEL").replace(mese_ora, mese_prima)
            testo = testo.replace(gg(f1["data"]), gg(f1["data"] - timedelta(days=30)))
            due["stato"] = testo
        else:
            f2["numero"] = f"{r.randint(1, 980)}/26"
            for riga in f2["righe"]:
                riga["q"] = d2(riga["q"] + r.randint(1, 5))
            calcola(f2)
            due["stato"] = uno["stato"].split("\n\n", 1)[0] + "\n\n" + fattura_testo(f2, r)
    stato = "Documento 1:\n" + uno["stato"] + "\n\n-----\n\nDocumento 2:\n" + due["stato"]
    return {"stato": stato, "etichette": {"doppione": doppione}}


# ---------------------------------------------------------------- F24

TRIBUTI_ERARIO = [("1001", "Ritenute su retribuzioni lavoro dipendente"), ("1040", "Ritenute su redditi di lavoro autonomo"),
                  ("1012", "Ritenute su indennità di fine rapporto"), ("6000+", "Versamento IVA mensile")]


def f24(r, quietanza=False):
    contribuente = azienda(r)
    ricevuta = data_ricezione(r)
    if quietanza:
        pagata = date(ricevuta.year, ricevuta.month, 16)
        if pagata > ricevuta:
            pagata = date(ricevuta.year if ricevuta.month > 1 else ricevuta.year - 1, (ricevuta.month - 2) % 12 + 1, 16)
        rif = pagata
    else:
        scadenza = date(ricevuta.year, ricevuta.month, 16)
        if scadenza < ricevuta:
            scadenza = date(ricevuta.year + ricevuta.month // 12, ricevuta.month % 12 + 1, 16)
        rif = scadenza
    mese_rif = (rif.month - 2) % 12 + 1
    anno_rif = rif.year if rif.month > 1 else rif.year - 1
    righe_erario, totale = [], Decimal(0)
    for codice, _ in r.sample(TRIBUTI_ERARIO, r.randint(1, 3)):
        if codice == "6000+":
            codice = f"60{mese_rif:02d}"
        importo = d2(r.uniform(150, 9000))
        totale += importo
        righe_erario.append(f"{codice}   {mese_rif:04d}   {anno_rif}   {euro(importo)}")
    righe_inps = []
    if r.random() < 0.6:
        importo = d2(r.uniform(800, 12000))
        totale += importo
        righe_inps.append(f"{r.randint(4000, 6900)}   DM10   {r.randint(1000000000, 9999999999)}   {mese_rif:02d}/{anno_rif}   {euro(importo)}")
    righe_imu = []
    if r.random() < 0.2:
        importo = d2(r.uniform(300, 4000))
        totale += importo
        righe_imu.append(f"{contribuente['sede']['catasto']}   3918   {anno_rif}   {euro(importo)}")

    banca = r.choice(BANCHE)
    testo = []
    if quietanza:
        mittente = f"notifiche@{banca.split()[0].lower()}{banca.split()[-1].lower()}.it"
        testo += [f"Ricevuto il {gg(ricevuta)} via mail da {mittente}", "Oggetto: Quietanza di pagamento F24", "",
                  "QUIETANZA DI PAGAMENTO - MODELLO F24", f"{banca}",
                  f"Pagamento eseguito il {gg(pagata)} con addebito sul conto del contribuente.",
                  f"Protocollo telematico: {r.randint(10**16, 10**17 - 1)}", "Esito: ESEGUITO", ""]
    else:
        studio = persona(r, "Dott.")
        testo += [f"Ricevuto il {gg(ricevuta)} via mail da {studio['mail']}", "Oggetto: F24 in scadenza", "",
                  f"Buongiorno, in allegato il modello F24 da pagare entro il {gg(scadenza)}. Cordiali saluti, {studio['denominazione']}",
                  "", "MODELLO DI PAGAMENTO UNIFICATO F24", f"DELEGA IRREVOCABILE A: {banca}", ""]
    testo += ["CONTRIBUENTE", f"CODICE FISCALE: {contribuente['cf']}", f"RAGIONE SOCIALE: {contribuente['denominazione']}",
              f"DOMICILIO FISCALE: {contribuente['sede']['comune']} ({contribuente['sede']['prov']})", "",
              "SEZIONE ERARIO", "codice tributo | rateazione/mese rif. | anno di riferimento | importi a debito versati"]
    testo += righe_erario
    if righe_inps:
        testo += ["", "SEZIONE INPS", "codice sede | causale contributo | matricola INPS | periodo di riferimento | importi a debito versati"]
        testo += righe_inps
    if righe_imu:
        testo += ["", "SEZIONE IMU E ALTRI TRIBUTI LOCALI", "codice ente | codice tributo | anno di riferimento | importi a debito versati"]
        testo += righe_imu
    testo += ["", f"SALDO FINALE: EURO {euro(totale)}"]
    testo.append(f"DATA DI PAGAMENTO: {gg(pagata)}" if quietanza else f"SCADENZA: {gg(scadenza)}")
    etichette = {"tipo": "f24", "ufficio": "amministrazione", "phishing": False, "dati_sensibili": False}
    if quietanza:
        etichette |= {"azione": "archiviare", "scadenza": False, "giorni": None, "rischio": 0}
    else:
        etichette |= {"azione": "pagare", "scadenza": True, "giorni": (scadenza - ricevuta).days, "rischio": 2}
    return {"stato": "\n".join(testo), "etichette": etichette}


# ---------------------------------------------------------------- DDT

CAUSALI_DDT = ["Vendita", "Vendita", "Reso", "Conto lavorazione", "Conto visione"]


def ddt(r, causale=None):
    causale = causale or r.choice(CAUSALI_DDT)
    mittente, destinatario = azienda(r), azienda(r)
    ricevuta = data_ricezione(r)
    data_doc = ricevuta - timedelta(days=r.randint(0, 3))
    a_cura = r.choice(["Mittente", "Destinatario", "Vettore"])
    testo = [f"Ricevuto il {gg(ricevuta)} via mail da {mittente['mail'].replace('info@', 'logistica@')}",
             "Oggetto: DDT spedizione", "",
             f"DOCUMENTO DI TRASPORTO N. {r.randint(100, 3000)}/26 DEL {gg(data_doc)}", "(D.P.R. 472 del 14/08/1996)", "",
             "Mittente:", soggetto_testo(mittente), "", "Destinatario:", soggetto_testo(destinatario), "",
             f"Luogo di destinazione: {destinatario['sede']['via']} - {destinatario['sede']['comune']}",
             f"Causale del trasporto: {causale}", f"Trasporto a cura del: {a_cura}"]
    if a_cura == "Vettore":
        testo.append(f"Vettore: {r.choice(VETTORI)}")
    testo += [f"Data e ora inizio trasporto: {gg(data_doc)} ore {r.randint(7, 17)}:{r.choice(['00', '15', '30', '45'])}",
              f"Aspetto esteriore dei beni: {r.choice(['Scatole', 'Bancali', 'Sfuso', 'Fusti'])}",
              f"N. colli: {r.randint(1, 12)}   Peso kg: {r.randint(5, 900)}", "", "Codice | Descrizione | U.M. | Quantità"]
    settore = r.choice(list(BENI))
    for _ in range(r.randint(1, 5)):
        desc, um, *_ = r.choice(BENI[settore])
        testo.append(f"{alfanum(r, 6)} | {desc} | {um} | {r.randint(1, 50)}")
    etichette = {"tipo": "ddt", "ufficio": "logistica", "phishing": False, "dati_sensibili": False}
    if causale == "Conto visione":
        restituzione = data_doc + timedelta(days=r.choice([15, 30, 45]))
        testo += ["", f"Merce in conto visione: da restituire o confermare l'acquisto entro il {gg(restituzione)}."]
        etichette |= {"scadenza": True, "giorni": (restituzione - ricevuta).days, "rischio": 1}
    else:
        etichette |= {"azione": "archiviare", "scadenza": False, "giorni": None, "rischio": 0}
    testo += ["", "Firma conducente: ____________   Firma destinatario: ____________"]
    return {"stato": "\n".join(testo), "etichette": etichette}


# ---------------------------------------------------------------- uscita

def documento(id_, fonte, gruppi, doc):
    return {"id": id_, "fonte": fonte, "gruppi": gruppi, "stato": doc["stato"], "etichette": doc["etichette"]}


def casuale(r, i, seed):
    """Un documento qualunque, con le proporzioni del dataset di addestramento."""
    x = r.random()
    id_ = f"gen-{seed}-{i:06d}"
    if x < 0.6:
        tipo = r.choices(list(TIPI_FATTURA), weights=list(TIPI_FATTURA.values()))[0]
        return documento(id_, f"fattura/{tipo}", ["documento", "fattura"], fattura(r, tipo))
    if x < 0.7:
        return documento(id_, "coppia", ["coppia"], coppia(r, r.random() < 0.5))
    if x < 0.85:
        quietanza = r.random() < 0.35
        return documento(id_, "f24/" + ("quietanza" if quietanza else "delega"), ["documento"], f24(r, quietanza))
    causale = r.choice(CAUSALI_DDT)
    return documento(id_, "ddt/" + causale.lower().replace(" ", "_"), ["documento"], ddt(r, causale))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("dati.jsonl"))
    ap.add_argument("--xml-dir", type=Path, help="salva anche le fatture XML (per la validazione con l'XSD)")
    a = ap.parse_args()
    r = random.Random(a.seed)
    if a.xml_dir:
        a.xml_dir.mkdir(parents=True, exist_ok=True)
    with a.out.open("w") as out:
        for i in range(a.n):
            doc = casuale(r, i, a.seed)
            out.write(json.dumps(doc, ensure_ascii=False, default=str) + "\n")
            if a.xml_dir and doc["stato"].split("\n", 1)[0].endswith("tramite SDI"):
                (a.xml_dir / f"{doc['id']}.xml").write_text(doc["stato"].split("\n\n", 1)[1])
    print(f"{a.n} documenti in {a.out}")


if __name__ == "__main__":
    main()
