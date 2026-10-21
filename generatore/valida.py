"""Valida gli XML FatturaPA con lo schema ufficiale 1.2.2. Serve lxml.

Al primo avvio scarica lo schema dal sito FatturaPA e lo schema xmldsig dal W3C in xsd/.

Uso: uv run --with lxml python valida.py cartella_xml/
"""
import sys
import urllib.request
from pathlib import Path

from lxml import etree

XSD = Path(__file__).parent / "xsd"
FATTURAPA = "https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Schema_del_file_xml_FatturaPA_v1.2.2.xsd"
XMLDSIG = "http://www.w3.org/TR/2002/REC-xmldsig-core-20020212/xmldsig-core-schema.xsd"


def scarica():
    XSD.mkdir(exist_ok=True)
    if not (XSD / "xmldsig-core-schema.xsd").exists():
        urllib.request.urlretrieve(XMLDSIG.replace("http://", "https://"), XSD / "xmldsig-core-schema.xsd")
    if not (XSD / "fatturapa_v1.2.2.xsd").exists():
        testo = urllib.request.urlopen(FATTURAPA).read().decode("utf-8-sig")
        # lo schema importa xmldsig dal W3C: lo si fa puntare alla copia locale
        (XSD / "fatturapa_v1.2.2.xsd").write_text(testo.replace(XMLDSIG, "xmldsig-core-schema.xsd"))


scarica()
parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
schema = etree.XMLSchema(etree.parse(str(XSD / "fatturapa_v1.2.2.xsd"), parser))

validi, errori = 0, []
for f in sorted(Path(sys.argv[1]).glob("*.xml")):
    doc = etree.parse(str(f), parser)
    if schema.validate(doc):
        validi += 1
    else:
        errori.append((f.name, schema.error_log.last_error))
for nome, err in errori[:15]:
    print(f"✗ {nome}: riga {err.line}: {err.message}")
print(f"Validi {validi}/{validi + len(errori)}")
sys.exit(1 if errori else 0)
