#!/usr/bin/env python3
"""
Walidator / korektor plików XML sprawozdania KT-1 (GUS - "Instrukcja dla dostawców oprogramowania 2026").

Sprawdza pliki XML z miesięcznym sprawozdaniem KT-1 turystycznych obiektów noclegowych,
wypisuje wszystkie znalezione problemy, tworzy raport HTML i opcjonalnie (--fix)
zapisuje poprawioną kopię pliku.

Obsługiwane formaty
  * format podstawowy  <Sprawozdanie xmlns="http://ps.stat.gov.pl/ps/schema/sprawozdanie">
                       z elementami <Pole id="..." wartosc="..."/> (wysyłany do portalu)
  * format "przyjazny" <Survey xmlns="http://ps.stat.gov.pl/ps/schema/sprawozdanie/kt1">
                       (PL_MONTHLY_XML.xsd, transformowany przez PL_MONTHLY_XML.XSL)

Kontrole
  [XML]    poprawność składni XML (np. niezakodowany '&')
  [KOD]    kodowanie (usługa sieciowa wymaga UTF-8)
  [XSD]    schemat: pełna walidacja XSD gdy zainstalowano lxml, w przeciwnym razie
           wbudowana kontrola struktury równoważna sprawozdanie.xsd
  [NAGŁ]   formularzSymbol / formularzWersja / numerSprawozdania
  [POLE]   nieznane / powtórzone pola, typy danych, długości, wartości dozwolone,
           e-mail, suma kontrolna REGON, symbol TERYT, kod pocztowy
  [WYM]    pola wymagane (liczba wystąpień 1..1 w instrukcji)
  [R1]..[R41]  reguły z rozdziału "Walidacje" instrukcji
  [MS]     multisekcja turystów zagranicznych (indeks, MultiSekcja, d8_lp, sumy)

Wymagana jest tylko biblioteka standardowa Pythona 3.8+ (opcjonalnie lxml).
"""

from __future__ import annotations

import argparse
import calendar
import copy
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field as dc_field
from typing import Optional

__version__ = "1.1.0"

NS_SPR = "http://ps.stat.gov.pl/ps/schema/sprawozdanie"
NS_KT1 = "http://ps.stat.gov.pl/ps/schema/sprawozdanie/kt1"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_XS = "http://www.w3.org/2001/XMLSchema"


def q(tag: str) -> str:
    return "{%s}%s" % (NS_SPR, tag)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Display names of severities (internal keys stay ERROR / WARNING / INFO, also in JSON output)
SEV_PL = {"ERROR": "BŁĄD", "WARNING": "OSTRZEŻENIE", "INFO": "INFO"}

# --------------------------------------------------------------------------------------
# ISO 3166-1 (numeric, alpha-2, alpha-3, Polish name) - 249 officially assigned codes
# --------------------------------------------------------------------------------------
ISO_DATA = """\
004 AF AFG Afganistan
248 AX ALA Wyspy Alandzkie
008 AL ALB Albania
012 DZ DZA Algieria
016 AS ASM Samoa Amerykańskie
020 AD AND Andora
024 AO AGO Angola
660 AI AIA Anguilla
010 AQ ATA Antarktyda
028 AG ATG Antigua i Barbuda
032 AR ARG Argentyna
051 AM ARM Armenia
533 AW ABW Aruba
036 AU AUS Australia
040 AT AUT Austria
031 AZ AZE Azerbejdżan
044 BS BHS Bahamy
048 BH BHR Bahrajn
050 BD BGD Bangladesz
052 BB BRB Barbados
112 BY BLR Białoruś
056 BE BEL Belgia
084 BZ BLZ Belize
204 BJ BEN Benin
060 BM BMU Bermudy
064 BT BTN Bhutan
068 BO BOL Boliwia
535 BQ BES Bonaire, Sint Eustatius i Saba
070 BA BIH Bośnia i Hercegowina
072 BW BWA Botswana
074 BV BVT Wyspa Bouveta
076 BR BRA Brazylia
086 IO IOT Brytyjskie Terytorium Oceanu Indyjskiego
096 BN BRN Brunei
100 BG BGR Bułgaria
854 BF BFA Burkina Faso
108 BI BDI Burundi
132 CV CPV Republika Zielonego Przylądka
116 KH KHM Kambodża
120 CM CMR Kamerun
124 CA CAN Kanada
136 KY CYM Kajmany
140 CF CAF Republika Środkowoafrykańska
148 TD TCD Czad
152 CL CHL Chile
156 CN CHN Chiny
162 CX CXR Wyspa Bożego Narodzenia
166 CC CCK Wyspy Kokosowe
170 CO COL Kolumbia
174 KM COM Komory
178 CG COG Kongo
180 CD COD Demokratyczna Republika Konga
184 CK COK Wyspy Cooka
188 CR CRI Kostaryka
384 CI CIV Wybrzeże Kości Słoniowej
191 HR HRV Chorwacja
192 CU CUB Kuba
531 CW CUW Curaçao
196 CY CYP Cypr
203 CZ CZE Czechy
208 DK DNK Dania
262 DJ DJI Dżibuti
212 DM DMA Dominika
214 DO DOM Dominikana
218 EC ECU Ekwador
818 EG EGY Egipt
222 SV SLV Salwador
226 GQ GNQ Gwinea Równikowa
232 ER ERI Erytrea
233 EE EST Estonia
748 SZ SWZ Eswatini
231 ET ETH Etiopia
238 FK FLK Falklandy
234 FO FRO Wyspy Owcze
242 FJ FJI Fidżi
246 FI FIN Finlandia
250 FR FRA Francja
254 GF GUF Gujana Francuska
258 PF PYF Polinezja Francuska
260 TF ATF Francuskie Terytoria Południowe
266 GA GAB Gabon
270 GM GMB Gambia
268 GE GEO Gruzja
276 DE DEU Niemcy
288 GH GHA Ghana
292 GI GIB Gibraltar
300 GR GRC Grecja
304 GL GRL Grenlandia
308 GD GRD Grenada
312 GP GLP Gwadelupa
316 GU GUM Guam
320 GT GTM Gwatemala
831 GG GGY Guernsey
324 GN GIN Gwinea
624 GW GNB Gwinea Bissau
328 GY GUY Gujana
332 HT HTI Haiti
334 HM HMD Wyspy Heard i McDonalda
336 VA VAT Watykan
340 HN HND Honduras
344 HK HKG Hongkong
348 HU HUN Węgry
352 IS ISL Islandia
356 IN IND Indie
360 ID IDN Indonezja
364 IR IRN Iran
368 IQ IRQ Irak
372 IE IRL Irlandia
833 IM IMN Wyspa Man
376 IL ISR Izrael
380 IT ITA Włochy
388 JM JAM Jamajka
392 JP JPN Japonia
832 JE JEY Jersey
400 JO JOR Jordania
398 KZ KAZ Kazachstan
404 KE KEN Kenia
296 KI KIR Kiribati
408 KP PRK Korea Północna
410 KR KOR Korea Południowa
414 KW KWT Kuwejt
417 KG KGZ Kirgistan
418 LA LAO Laos
428 LV LVA Łotwa
422 LB LBN Liban
426 LS LSO Lesotho
430 LR LBR Liberia
434 LY LBY Libia
438 LI LIE Liechtenstein
440 LT LTU Litwa
442 LU LUX Luksemburg
446 MO MAC Makau
450 MG MDG Madagaskar
454 MW MWI Malawi
458 MY MYS Malezja
462 MV MDV Malediwy
466 ML MLI Mali
470 MT MLT Malta
584 MH MHL Wyspy Marshalla
474 MQ MTQ Martynika
478 MR MRT Mauretania
480 MU MUS Mauritius
175 YT MYT Majotta
484 MX MEX Meksyk
583 FM FSM Mikronezja
498 MD MDA Mołdawia
492 MC MCO Monako
496 MN MNG Mongolia
499 ME MNE Czarnogóra
500 MS MSR Montserrat
504 MA MAR Maroko
508 MZ MOZ Mozambik
104 MM MMR Mjanma
516 NA NAM Namibia
520 NR NRU Nauru
524 NP NPL Nepal
528 NL NLD Holandia
540 NC NCL Nowa Kaledonia
554 NZ NZL Nowa Zelandia
558 NI NIC Nikaragua
562 NE NER Niger
566 NG NGA Nigeria
570 NU NIU Niue
574 NF NFK Norfolk
807 MK MKD Macedonia Północna
580 MP MNP Mariany Północne
578 NO NOR Norwegia
512 OM OMN Oman
586 PK PAK Pakistan
585 PW PLW Palau
275 PS PSE Palestyna
591 PA PAN Panama
598 PG PNG Papua-Nowa Gwinea
600 PY PRY Paragwaj
604 PE PER Peru
608 PH PHL Filipiny
612 PN PCN Pitcairn
616 PL POL Polska
620 PT PRT Portugalia
630 PR PRI Portoryko
634 QA QAT Katar
638 RE REU Reunion
642 RO ROU Rumunia
643 RU RUS Rosja
646 RW RWA Rwanda
652 BL BLM Saint-Barthélemy
654 SH SHN Wyspa Świętej Heleny, Wyspa Wniebowstąpienia i Tristan da Cunha
659 KN KNA Saint Kitts i Nevis
662 LC LCA Saint Lucia
663 MF MAF Saint-Martin
666 PM SPM Saint-Pierre i Miquelon
670 VC VCT Saint Vincent i Grenadyny
882 WS WSM Samoa
674 SM SMR San Marino
678 ST STP Wyspy Świętego Tomasza i Książęca
682 SA SAU Arabia Saudyjska
686 SN SEN Senegal
688 RS SRB Serbia
690 SC SYC Seszele
694 SL SLE Sierra Leone
702 SG SGP Singapur
534 SX SXM Sint Maarten
703 SK SVK Słowacja
705 SI SVN Słowenia
090 SB SLB Wyspy Salomona
706 SO SOM Somalia
710 ZA ZAF Republika Południowej Afryki
239 GS SGS Georgia Południowa i Sandwich Południowy
728 SS SSD Sudan Południowy
724 ES ESP Hiszpania
144 LK LKA Sri Lanka
729 SD SDN Sudan
740 SR SUR Surinam
744 SJ SJM Svalbard i Jan Mayen
752 SE SWE Szwecja
756 CH CHE Szwajcaria
760 SY SYR Syria
158 TW TWN Tajwan
762 TJ TJK Tadżykistan
834 TZ TZA Tanzania
764 TH THA Tajlandia
626 TL TLS Timor Wschodni
768 TG TGO Togo
772 TK TKL Tokelau
776 TO TON Tonga
780 TT TTO Trynidad i Tobago
788 TN TUN Tunezja
792 TR TUR Turcja
795 TM TKM Turkmenistan
796 TC TCA Turks i Caicos
798 TV TUV Tuvalu
800 UG UGA Uganda
804 UA UKR Ukraina
784 AE ARE Zjednoczone Emiraty Arabskie
826 GB GBR Wielka Brytania
840 US USA Stany Zjednoczone
581 UM UMI Dalekie Wyspy Mniejsze Stanów Zjednoczonych
858 UY URY Urugwaj
860 UZ UZB Uzbekistan
548 VU VUT Vanuatu
862 VE VEN Wenezuela
704 VN VNM Wietnam
092 VG VGB Brytyjskie Wyspy Dziewicze
850 VI VIR Wyspy Dziewicze Stanów Zjednoczonych
876 WF WLF Wallis i Futuna
732 EH ESH Sahara Zachodnia
887 YE YEM Jemen
894 ZM ZMB Zambia
716 ZW ZWE Zimbabwe
"""

ISO_NAME: dict[str, str] = {}
ISO_ALPHA: dict[str, str] = {}
for _line in ISO_DATA.splitlines():
    _num, _a2, _a3, _name = _line.split(" ", 3)
    ISO_NAME[_num] = _name
    ISO_ALPHA[_a2] = _num
    ISO_ALPHA[_a3] = _num
ISO_ALPHA["UK"] = "826"  # common non-ISO alias of GB
UNKNOWN_COUNTRY = "999"
ISO_NAME[UNKNOWN_COUNTRY] = "kraj nieustalony / bezpaństwowiec"
POLAND = "616"


def country_name(code: str) -> str:
    return ISO_NAME.get(code, "?")


# --------------------------------------------------------------------------------------
# KT-1 field list (instruction 2026, table of <Pole> identifiers)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Spec:
    type: str  # str | int | p3 | country | email | phone | regon | teryt
    length: int = 0  # max chars (str) / max digits (int); 0 = no limit
    required: bool = False
    desc: str = ""
    allowed: tuple = ()  # allowed integer values (empty = any)


R = lambda a, b: tuple(range(a, b + 1))  # noqa: E731

SPEC: dict[str, Spec] = {
    "n_imie": Spec("str", 120, False, "Imię"),
    "n_nazwisko": Spec("str", 120, False, "Nazwisko"),
    "n_telefon": Spec("phone", 0, False, "Telefon"),
    "n_email_sprawozdawca": Spec("email", 0, False, "E-mail osoby sporządzającej sprawozdanie"),
    "n_email_firma": Spec("email", 0, False, "E-mail sekretariatu dyrektora/prezesa firmy"),
    "jsbad": Spec("regon", 16, False, "Identyfikator jednostki (REGON)"),
    "mc": Spec("int", 2, False, "Miesiąc", R(1, 12)),
    "rok": Spec("int", 4, False, "Rok"),
    "p1": Spec("str", 120, True, "Nazwa obiektu"),
    "sym": Spec("teryt", 8, True, "Miejscowość (TERYT)"),
    "p2_adres": Spec("str", 120, True, "Ul. i nr domu"),
    "p2_poczta": Spec("str", 120, True, "Kod pocztowy i poczta"),
    "p3": Spec("p3", 2, True, "Rodzaj obiektu", R(1, 20)),
    "p4": Spec("int", 1, False, "Rezerwacje przez platformy rezerwacyjne (1 tak, 2 nie)", (1, 2)),
    "p5": Spec("int", 1, False, "Kategoria obiektu", R(1, 9)),
    "p6": Spec("int", 1, True, "Czy obiekt jest całoroczny (1 całoroczny, 2 sezonowy)", (1, 2)),
    "p6a": Spec("int", 2, False, "Miesiące działania obiektu sezonowego", R(1, 12)),
    "d2r1": Spec("int", 2, False, "Restauracje"),
    "d2r2": Spec("int", 2, False, "Bary (w tym kawiarnie)"),
    "d2r3": Spec("int", 2, False, "Stołówki"),
    "d2r4": Spec("int", 2, False, "Punkty gastronomiczne"),
    "d3r1": Spec("int", 5, False, "Pokoje ogółem"),
    "d3r2": Spec("int", 5, False, "Pokoje z pełnym węzłem higieniczno-sanitarnym"),
    "d3r3": Spec("int", 5, False, "Pokoje przystosowane dla osób niepełnosprawnych"),
    "d3r4": Spec("int", 5, False, "Miejsca noclegowe ogółem"),
    "d3r5": Spec("int", 5, False, "Miejsca noclegowe całoroczne"),
    "d3r6": Spec("int", 5, False, "Miejsca noclegowe sezonowe"),
    "d7w1": Spec("int", 2, True, "Liczba dni działalności obiektu"),
    "d7w2": Spec("int", 5, True, "Nominalna liczba miejsc noclegowych"),
    "d7w3": Spec("int", 5, False, "Nominalna liczba pokoi"),
    "d7w4r1": Spec("int", 5, True, "Turyści korzystający z noclegów - ogółem"),
    "d7w4r2": Spec("int", 5, True, "Turyści korzystający z noclegów - zagraniczni"),
    "d7w5r1": Spec("int", 5, True, "Udzielone noclegi - ogółem"),
    "d7w5r2": Spec("int", 5, True, "Udzielone noclegi - turyści zagraniczni"),
    "d7w5ar1": Spec("int", 5, True, "Noclegi ogółem zarezerwowane przez platformy"),
    "d7w5ar2": Spec("int", 5, True, "Noclegi turystów zagr. zarezerwowane przez platformy"),
    "d7w6r1": Spec("int", 5, False, "Wynajęte pokoje - ogółem"),
    "d7w6r2": Spec("int", 5, False, "Wynajęte pokoje - turyści zagraniczni"),
    "d7aw1": Spec("int", 5, False, "Nominalna liczba miejsc dla uchodźców"),
    "d7aw2": Spec("int", 5, True, "Uchodźcy korzystający z noclegów"),
    "d7aw3": Spec("int", 5, True, "Noclegi udzielone uchodźcom"),
    "d8r2w0": Spec("int", 0, False, "Suma turystów zagranicznych (auto)"),
    "d8r3w0": Spec("int", 0, False, "Suma noclegów turystów zagranicznych (auto)"),
    "d8_lp": Spec("int", 0, False, "Lp. (auto)"),
    "d8r1": Spec("country", 3, False, "Kraj zamieszkania turysty zagranicznego"),
    "d8r2": Spec("int", 6, False, "Turyści zagraniczni z kraju"),
    "d8r3": Spec("int", 6, False, "Noclegi turystów z kraju"),
}

JULY_ONLY = ["p4", "d2r1", "d2r2", "d2r3", "d2r4", "d3r1", "d3r2", "d3r3", "d3r4", "d3r5", "d3r6"]
MULTI_IDS = ["d8_lp", "d8r1", "d8r2", "d8r3"]
REPEATABLE = {"p6a"}
# Not in the instruction's field list, but produced by the portal itself / present in the
# official sample - ignored.
KNOWN_EXTRA = {"uwagi", "ra11", "pf2"}
# Required in 2026 but PL_MONTHLY_XML.xsd ("friendly" format) has no element for them.
SURVEY_UNMAPPED = {"d7w5ar1", "d7w5ar2", "d7aw2", "d7aw3"}
CATEGORY_TYPES = {1, 2, 3, 4, 5, 7, 14}  # types for which p5 (category) makes sense

EMAIL_RE = re.compile(r"^\w+([-+.']\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$")
DIGITS_RE = re.compile(r"^[0-9]+$")
BARE_AMP_RE = re.compile(r"&(?!(?:[A-Za-z_][\w.-]*|#[0-9]+|#x[0-9A-Fa-f]+);)")
DECL_RE = re.compile(r"^\s*<\?xml[^>]*\?>")
ENC_RE = re.compile(r"""encoding\s*=\s*["']([^"']+)["']""")
XMLNS_RE = re.compile(r"""xmlns(?::([\w.-]+))?\s*=\s*["']([^"']*)["']""")


def to_int(v: Optional[str]) -> Optional[int]:
    if v is None:
        return None
    v = v.strip()
    return int(v) if DIGITS_RE.match(v) and len(v) <= 15 else None


def regon_ok(r: str) -> bool:
    def chk(digits: str, w: list[int]) -> bool:
        s = sum(int(digits[i]) * w[i] for i in range(len(w))) % 11
        return (0 if s == 10 else s) == int(digits[len(w)])

    if not re.fullmatch(r"[0-9]{9}|[0-9]{14}", r):
        return False
    if not chk(r, [8, 9, 2, 3, 4, 5, 6, 7]):
        return False
    return len(r) == 9 or chk(r, [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8])


def normalize_country(raw: Optional[str]) -> tuple[Optional[str], str]:
    """Returns (code, kind); kind: ok | padded | alpha | invalid | empty."""
    if raw is None or raw.strip() == "":
        return None, "empty"
    t = raw.strip()
    if DIGITS_RE.match(t) and len(t) <= 6:
        code = "%03d" % int(t)
        if code in ISO_NAME:
            return code, ("ok" if code == t else "padded")
        return None, "invalid"
    if t.upper() in ISO_ALPHA:
        return ISO_ALPHA[t.upper()], "alpha"
    return None, "invalid"


# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------
@dataclass
class Issue:
    severity: str  # ERROR | WARNING | INFO
    rule: str
    field: str
    message: str
    fixable: bool = False


@dataclass
class Field:
    id: str
    value: Optional[str]
    index: int = 0
    occ: int = 0  # n-th occurrence of the same id with the same index
    elem: Optional[ET.Element] = None
    where: str = ""
    parent: Optional[ET.Element] = None


@dataclass
class Row:
    index: int
    occ: int
    lp: Optional[str] = None
    country: Optional[str] = None
    acc: Optional[str] = None
    nights: Optional[str] = None
    has: set = dc_field(default_factory=set)


@dataclass
class Model:
    fmt: str  # base | survey
    root: ET.Element
    fields: list
    extra: dict


@dataclass
class Result:
    path: str
    issues: list = dc_field(default_factory=list)
    notes: list = dc_field(default_factory=list)
    text: Optional[str] = None  # (possibly repaired) XML text without declaration
    root: Optional[ET.Element] = None
    model: Optional[Model] = None
    month: Optional[int] = None
    year: Optional[int] = None
    repaired_amp: int = 0
    fatal: bool = False

    def add(self, sev, rule, fld, msg, fixable=False):
        self.issues.append(Issue(sev, rule, fld, msg, fixable))

    def count(self, sev):
        return sum(1 for i in self.issues if i.severity == sev)


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------
def parse_xml(text: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    parser.feed(text)
    return parser.close()


def load(path: str, res: Result) -> None:
    with open(path, "rb") as fh:
        raw = fh.read()

    declared = None
    if raw.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8-sig"
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        enc = "utf-16"
        res.add("WARNING", "KOD", "", "plik jest zakodowany w UTF-16; usługa sieciowa wymaga UTF-8", True)
    else:
        m = ENC_RE.search(raw[:300].decode("ascii", "replace"))
        declared = m.group(1) if m else None
        enc = declared or "utf-8"
    if declared and declared.lower().replace("_", "-") not in ("utf-8", "utf8"):
        res.add("WARNING", "KOD", "",
                f"zadeklarowane kodowanie to '{declared}'; usługa sieciowa wymaga XML zakodowanego w UTF-8", True)
    try:
        text = raw.decode(enc)
    except (LookupError, UnicodeDecodeError) as e:
        res.add("ERROR", "KOD", "", f"nie można odczytać pliku w kodowaniu '{enc}': {e}")
        if enc.lower().replace("_", "-") in ("utf-8", "utf8"):
            res.add("INFO", "KOD", "", "plik jest prawdopodobnie zapisany w windows-1250 / ISO-8859-2 "
                    "bez odpowiedniej deklaracji kodowania")
        res.fatal = True
        return
    text = text.lstrip("﻿")
    text = DECL_RE.sub("", text, count=1)  # declaration removed: we pass already-decoded text

    try:
        root = parse_xml(text)
    except ET.ParseError as e:
        lines = [text.count("\n", 0, m.start()) + 1 for m in BARE_AMP_RE.finditer(text)]
        repaired = None
        if lines:
            try:
                candidate = BARE_AMP_RE.sub("&amp;", text)
                root = parse_xml(candidate)
                repaired = candidate
            except ET.ParseError:
                pass
        if repaired is None:
            res.add("ERROR", "XML", "", f"plik nie jest poprawnym dokumentem XML: {e}")
            if lines:
                res.add("ERROR", "XML", "", "niezakodowany znak '&' w wierszu(-ach) %s - należy użyć &amp;" %
                        ", ".join(map(str, lines[:10])))
            res.fatal = True
            return
        res.add("ERROR", "XML", "",
                "plik nie jest poprawnym dokumentem XML: niezakodowany znak '&' w wierszu(-ach) %s (należy zapisać "
                "jako &amp;); pozostałe kontrole wykonano na naprawionym tekście" % ", ".join(map(str, lines[:10])),
                True)
        res.repaired_amp = len(lines)
        text = repaired

    for prefix, uri in XMLNS_RE.findall(text[:5000]):
        try:
            ET.register_namespace(prefix or "", uri)
        except ValueError:
            pass
    res.text = text
    res.root = root


# --------------------------------------------------------------------------------------
# Schema validation
# --------------------------------------------------------------------------------------
def xsd_validate_lxml(res: Result, xsd_path: str) -> bool:
    try:
        from lxml import etree as LET  # type: ignore
    except ImportError:
        return False
    xsd_doc = LET.parse(xsd_path)
    for n in xsd_doc.xpath("//xs:import | //xs:element[@ref='ds:Signature']", namespaces={"xs": NS_XS}):
        n.getparent().remove(n)  # xmldsig import would need network access; not used by KT-1
    schema = LET.XMLSchema(xsd_doc)
    doc = LET.fromstring(res.text.encode("utf-8"))
    if not schema.validate(doc):
        for err in schema.error_log:
            msg = re.sub(r"\{[^}]*\}", "", err.message)  # drop {namespace} noise
            res.add("ERROR", "XSD", "", f"wiersz {err.line}: {msg}")
    res.notes.append(f"schemat: pełna walidacja XSD ({os.path.basename(xsd_path)}, lxml)")
    return True


BOOL_VALUES = {"true", "false", "1", "0"}
INT_RE = re.compile(r"^[+-]?[0-9]+$")


def xsd_validate_builtin(res: Result) -> None:
    """Structural check equivalent to sprawozdanie.xsd (used when lxml is not installed)."""
    root = res.root
    res.notes.append("schemat: wbudowana kontrola struktury równoważna sprawozdanie.xsd "
                     "(pip install lxml - pełna walidacja XSD)")

    def bad(msg):
        res.add("ERROR", "XSD", "", msg)

    def check_attrs(el, name, allowed: dict, required: set):
        for a, v in el.attrib.items():
            if a.startswith("{%s}" % NS_XSI):
                continue
            if a not in allowed:
                bad(f"<{name}>: atrybut '{a}' jest niedozwolony")
            elif allowed[a] == "int" and not INT_RE.match(v.strip()):
                bad(f"<{name} id='{el.get('id', '')}'>: atrybut {a}='{v}' nie jest liczbą całkowitą")
            elif allowed[a] == "bool" and v.strip() not in BOOL_VALUES:
                bad(f"<{name} id='{el.get('id', '')}'>: atrybut {a}='{v}' nie jest wartością logiczną")
        for a in required:
            if a not in el.attrib:
                bad(f"<{name} id='{el.get('id', '')}'>: brak wymaganego atrybutu '{a}'")

    check_attrs(root, "Sprawozdanie",
                {"formularzSymbol": "str", "formularzWersja": "str", "numerSprawozdania": "int"},
                {"formularzSymbol", "formularzWersja"})
    kids = [c for c in root if isinstance(c.tag, str)]
    order = [q("Elementy"), q("Zalaczniki"), q("Strony"), "{%s}Signature" % NS_DS]
    pos = -1
    seen = set()
    for c in kids:
        if c.tag not in order:
            bad(f"nieoczekiwany element <{local(c.tag)}> w <Sprawozdanie>")
            continue
        p = order.index(c.tag)
        if p <= pos or c.tag in seen:
            bad(f"element <{local(c.tag)}> jest powtórzony lub w złej kolejności w <Sprawozdanie>")
        pos = max(pos, p)
        seen.add(c.tag)
    if q("Elementy") not in seen:
        bad("brak wymaganego elementu <Elementy>")
        return
    el = root.find(q("Elementy"))
    if (el.text or "").strip():
        bad("<Elementy> nie może zawierać tekstu")
    items = [c for c in el if isinstance(c.tag, str)]
    if not items:
        bad("<Elementy> musi zawierać co najmniej jeden element")
    for c in items:
        name = local(c.tag)
        if c.tag == q("Pole"):
            check_attrs(c, name, {"id": "str", "wartosc": "str", "indeks": "int",
                                  "automatyczne": "bool", "korekta": "bool"}, {"id"})
        elif c.tag == q("Sekcja"):
            check_attrs(c, name, {"id": "str", "widoczna": "bool", "indeks": "int"}, {"id"})
        elif c.tag == q("MultiSekcja"):
            check_attrs(c, name, {"id": "str", "widoczna": "bool", "indeks": "int", "iloscSekcji": "int"},
                        {"id", "iloscSekcji"})
        else:
            bad(f"nieoczekiwany element <{name}> w <Elementy> (dozwolone: Pole, Sekcja, MultiSekcja)")
            continue
        if len([x for x in c if isinstance(x.tag, str)]) or (c.text or "").strip():
            bad(f"<{name} id='{c.get('id', '')}'> musi być pusty (wartość podaje się w atrybucie 'wartosc')")
        if (c.tail or "").strip():
            bad(f"tekst po <{name} id='{c.get('id', '')}'> jest niedozwolony")


def local(tag) -> str:
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else str(tag)


# --------------------------------------------------------------------------------------
# Model builders
# --------------------------------------------------------------------------------------
def build_base(root: ET.Element, res: Result) -> Model:
    fields = []
    occ: dict = {}
    el = root.find(q("Elementy"))
    multi = None
    if el is not None:
        for c in el:
            if c.tag == q("MultiSekcja") and c.get("id") == "s_dz8_multi":
                multi = c
            if c.tag != q("Pole"):
                continue
            fid = c.get("id", "")
            idx_raw = c.get("indeks")
            idx = 0
            if idx_raw is not None:
                if INT_RE.match(idx_raw.strip()):
                    idx = int(idx_raw)
                else:
                    res.add("ERROR", "POLE", fid, f"indeks='{idx_raw}' nie jest liczbą całkowitą")
            key = (fid, idx)
            o = occ.get(key, 0)
            occ[key] = o + 1
            fields.append(Field(fid, c.get("wartosc"), idx, o, c, "", el))
    return Model("base", root, fields, {"elementy": el, "multi": multi})


def child(el: Optional[ET.Element], name: str) -> Optional[ET.Element]:
    if el is None:
        return None
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def children(el: Optional[ET.Element], name: str) -> list:
    return [] if el is None else [c for c in el if local(c.tag) == name]


def build_survey(root: ET.Element, res: Result) -> Model:
    fields: list = []

    def add(fid, parent, name, path, idx=0, occ=0):
        n = child(parent, name)
        if n is not None:
            fields.append(Field(fid, n.text or "", idx, occ, n, f"{path}/{name}", parent))

    hdr = child(root, "Header")
    rep = child(hdr, "Reporter")
    for fid, name in [("n_imie", "FirstName"), ("n_nazwisko", "LastName"), ("n_telefon", "PhoneNo"),
                      ("n_email_sprawozdawca", "ReporterEMail"), ("n_email_firma", "FirmEMail")]:
        add(fid, rep, name, "Header/Reporter")
    add("jsbad", hdr, "IdentyficationNumber", "Header")
    add("mc", hdr, "Month", "Header")
    add("rok", hdr, "Year", "Header")

    cont = child(root, "Contents")
    est = child(cont, "Establishment")
    E = "Contents/Establishment"
    add("p1", est, "Name", E)
    addr = child(est, "Address")
    add("sym", child(addr, "Locality"), "Symbol", E + "/Address/Locality")
    add("p2_adres", addr, "Street", E + "/Address")
    add("p2_poczta", addr, "Post", E + "/Address")
    op = child(est, "OpenPeriod")
    add("p6", op, "Period", E + "/OpenPeriod")
    months = children(op, "Month")
    for i, mth in enumerate(months):
        fields.append(Field("p6a", mth.text or "", 0, i, mth, f"{E}/OpenPeriod/Month[{i + 1}]", op))

    kind, kname = None, ""
    for kname in ("HotelAlike", "CampingFacilities", "OtherFacilities"):
        kind = child(est, kname)
        if kind is not None:
            break
    K = f"{E}/{kname}"
    add("p3", kind, "Type", K)
    add("p4", kind, "ProvidesHotelServices", K)
    add("p5", kind, "EstablishmentCategory", K)
    acc = child(kind, "Accomodation")
    bp = child(acc, "BedPlaces")
    add("d3r5", bp, "AccessibleAllYear", K + "/Accomodation/BedPlaces")
    add("d3r6", bp, "Seasonal", K + "/Accomodation/BedPlaces")
    a, s = to_int(child(bp, "AccessibleAllYear").text if child(bp, "AccessibleAllYear") is not None else None), \
        to_int(child(bp, "Seasonal").text if child(bp, "Seasonal") is not None else None)
    if a is not None and s is not None:
        fields.append(Field("d3r4", str(a + s), 0, 0, None, "wyliczone AccessibleAllYear+Seasonal"))
    rooms = child(acc, "Bedrooms")
    for fid, name in [("d3r1", "Total"), ("d3r2", "Plumbed"), ("d3r3", "WheelchairAccessible")]:
        add(fid, rooms, name, K + "/Accomodation/Bedrooms")
    util = child(kind, "Utilisation")
    U = K + "/Utilisation"
    add("d7w1", util, "ActivityDays", U)
    add("d7w2", util, "BedPlaces", U)
    add("d7w3", util, "Bedrooms", U)
    usage = child(util, "Usage")
    for base, name in [("d7w4", "AccommodatedTourists"), ("d7w5", "NightsSpent"), ("d7w6", "RentedBedrooms")]:
        grp = child(usage, name)
        add(base + "r1", grp, "Total", f"{U}/Usage/{name}")
        add(base + "r2", grp, "Foreign", f"{U}/Usage/{name}")
    ref = child(util, "BedPlacesForRefugees")
    for fid, name in [("d7aw1", "NominalNumberOfBedplacesForRefugees"),
                      ("d7aw2", "NumberOfRefugeesAccommodated"), ("d7aw3", "NumberOfOvernightStaysOfRefugees")]:
        add(fid, ref, name, U + "/BedPlacesForRefugees")
    cat = child(cont, "CateringUnits")
    for fid, name in [("d2r1", "Restaurants"), ("d2r2", "Bars"), ("d2r3", "Centeens"), ("d2r4", "DiningPoints")]:
        add(fid, cat, name, "Contents/CateringUnits")
    foreign = children(cont, "ForeignTourists")
    for i, ft in enumerate(foreign):
        P = f"Contents/ForeignTourists[{i + 1}]"
        add("d8r1", ft, "Country", P, i)
        add("d8r2", ft, "Accoumodated", P, i)
        add("d8r3", ft, "Nights", P, i)
    return Model("survey", root, fields, {
        "contents": cont, "catering": cat, "accomodation": acc, "kind": kind,
        "provides": child(kind, "ProvidesHotelServices"), "foreign": foreign, "open": op,
    })


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------
class Checker:
    def __init__(self, res: Result, args):
        self.res = res
        self.m: Model = res.model
        self.args = args
        self.by: dict = {}
        for f in self.m.fields:
            self.by.setdefault(f.id, []).append(f)

    # -- helpers -------------------------------------------------------------------------
    def first(self, fid) -> Optional[Field]:
        lst = self.by.get(fid)
        return lst[0] if lst else None

    def val(self, fid) -> Optional[str]:
        f = self.first(fid)
        return f.value.strip() if f is not None and f.value is not None else None

    def num(self, fid) -> Optional[int]:
        return to_int(self.val(fid))

    def has(self, fid) -> bool:
        return bool(self.val(fid))

    def label(self, f: Field) -> str:
        if self.m.fmt == "survey":
            return f"{f.id} ({f.where})"
        if f.id in MULTI_IDS or f.index:
            return f"{f.id}[indeks={f.index}]"
        return f.id

    def err(self, rule, fld, msg, fixable=False):
        self.res.add("ERROR", rule, fld, msg, fixable)

    def warn(self, rule, fld, msg, fixable=False):
        self.res.add("WARNING", rule, fld, msg, fixable)

    def info(self, rule, fld, msg, fixable=False):
        self.res.add("INFO", rule, fld, msg, fixable)

    def show(self, fid) -> str:
        v = self.val(fid)
        return "brak" if v is None else repr(v)

    def cmp(self, rule, a, op, b, factor=1):
        x, y = self.num(a), self.num(b)
        if x is None or y is None:
            return
        rhs = y * factor
        ok = {"le": x <= rhs, "ge": x >= rhs, "lt": x < rhs, "eq": x == rhs}[op]
        if not ok:
            sym = {"le": "<=", "ge": ">=", "lt": "<", "eq": "="}[op]
            right = f"{b} x {factor} ({rhs})" if factor != 1 else f"{b} ({y})"
            self.err(rule, a, f"{a} ({x}) musi być {sym} {right}")

    def implies(self, rule, a, b):
        x = self.num(a)
        if x is not None and x > 0:
            y = self.num(b)
            if y is None or y <= 0:
                self.err(rule, b, f"{a} = {x} > 0, więc {b} musi być > 0 (jest: {self.show(b)})")

    # -- run -------------------------------------------------------------------------------
    def run(self):
        self.period()
        if self.m.fmt == "base":
            self.header()
        self.fields()
        self.required()
        self.rules()
        self.foreign()

    def period(self):
        a = self.args
        month, msrc = None, ""
        if a.month:
            month, msrc = a.month, "--month"
        elif self.num("mc") in R(1, 12):
            month, msrc = self.num("mc"), "pole mc"
        year, ysrc = None, ""
        if a.year:
            year, ysrc = a.year, "--year"
        elif self.num("rok") and 2000 <= self.num("rok") <= 2100:
            year, ysrc = self.num("rok"), "pole rok"
        self.res.month, self.res.year = month, year
        if month:
            self.res.notes.append(f"okres  : miesiąc {month:02d}{'/' + str(year) if year else ''} "
                                  f"(z: {msrc}{', ' + ysrc if ysrc and ysrc != msrc else ''})")
        else:
            self.res.notes.append("okres  : miesiąc nieznany - podaj --month N, aby sprawdzić reguły zależne "
                                  "od miesiąca R1, R3, R7, R14")

    def header(self):
        r = self.m.root
        sym = r.get("formularzSymbol")
        if sym is not None and sym != "KT-1":
            self.err("NAGŁ", "formularzSymbol", f"musi mieć wartość 'KT-1' (jest '{sym}')")
        ver = r.get("formularzWersja")
        self.res.notes.append(f"formularz: {sym} wersja {ver} (sprawdź numer wersji publikowany przez GUS na bieżący "
                              "rok - instrukcja jest aktualizowana co roku)")
        nr = r.get("numerSprawozdania")
        if nr is not None and nr.strip() != "0":
            self.warn("NAGŁ", "numerSprawozdania", f"dla KT-1 powinien być 0 (jest '{nr}')")

    def fields(self):
        is_base = self.m.fmt == "base"
        for fid, lst in self.by.items():
            spec = SPEC.get(fid)
            if spec is None:
                if fid in KNOWN_EXTRA:
                    continue
                if re.match(r"^d[456]", fid):
                    self.warn("POLE", fid, "działy 4, 5 i 6 nie występują w sprawozdaniu KT-1 w 2026 r.")
                elif lst[0].elem is not None and lst[0].elem.get("automatyczne") == "true":
                    self.info("POLE", fid, "pole automatyczne spoza wykazu pól KT-1 w instrukcji (pominięte)")
                else:
                    self.warn("POLE", fid, "nieznany identyfikator pola - brak w wykazie pól KT-1 na 2026 r.")
                continue
            if fid not in MULTI_IDS and fid not in REPEATABLE and len(lst) > 1:
                self.err("POLE", fid, f"pole występuje {len(lst)} razy (dozwolone raz)")
            for f in lst:
                if is_base and f.index and fid not in MULTI_IDS:
                    self.warn("POLE", self.label(f), "atrybut indeks stosuje się tylko w multisekcji (dział 8)")
                self.value(f, spec)

    def value(self, f: Field, spec: Spec):
        raw = f.value
        if raw is None or raw.strip() == "":
            return
        v = raw.strip()
        lbl = self.label(f)
        if v != raw and spec.type != "str":
            self.info("POLE", lbl, f"wartość {raw!r} zawiera spacje na początku/końcu", True)
        t = spec.type
        if t == "str":
            if len(raw) > spec.length:
                self.err("POLE", lbl, f"tekst dłuższy niż {spec.length} znaków ({len(raw)})")
            if f.id == "p2_poczta" and not re.match(r"^\d{2}-\d{3}", v):
                self.warn("POLE", lbl, f"{v!r} powinno zaczynać się od kodu pocztowego NN-NNN")
        elif t in ("int", "p3"):
            if not DIGITS_RE.match(v):
                self.err("R2" if t == "p3" else "POLE", lbl, f"{v!r} nie jest nieujemną liczbą całkowitą")
                return
            if spec.length and len(v) > spec.length:
                self.err("POLE", lbl, f"{v!r} ma więcej niż {spec.length} cyfr(y)")
                return
            if spec.allowed and int(v) not in spec.allowed and f.id != "p6a":  # p6a is reported by R9
                rule = {"p3": "R2", "p6": "R8"}.get(f.id, "POLE")
                allowed = (f"{spec.allowed[0]}..{spec.allowed[-1]}" if len(spec.allowed) > 2
                           else " lub ".join(map(str, spec.allowed)))
                self.err(rule, lbl, f"wartość {v} niedozwolona (dozwolone: {allowed})")
                return
            if t == "p3" and self.m.fmt == "base" and len(v) == 1:
                self.warn("R2", lbl, f"rodzaj obiektu należy zapisać dwiema cyframi ('0{v}')", True)
        elif t == "email":
            if not EMAIL_RE.match(v):
                self.err("POLE", lbl, f"{v!r} nie jest poprawnym adresem e-mail")
        elif t == "phone":
            if not re.match(r"^\+?[0-9 ()\-/]{6,25}$", v):
                self.warn("POLE", lbl, f"{v!r} nie wygląda na numer telefonu")
        elif t == "regon":
            if len(v) > spec.length:
                self.err("POLE", lbl, f"dłuższy niż {spec.length} znaków")
            elif re.fullmatch(r"[0-9]{9}0{5}", v) and regon_ok(v[:9]):
                pass  # 9-digit REGON padded with zeros - this is how the portal itself fills jsbad
            elif len(v) == 14 and regon_ok(v[:9]):
                self.warn("POLE", lbl, f"{v!r}: błędna suma kontrolna 14-cyfrowego REGON (pierwsze 9 cyfr poprawne)")
            elif not regon_ok(v):
                self.err("POLE", lbl, f"{v!r} nie jest poprawnym numerem REGON (9 lub 14 cyfr z poprawną sumą "
                         "kontrolną)")
        elif t == "teryt":
            if not DIGITS_RE.match(v) or len(v) > spec.length:
                self.err("POLE", lbl, f"{v!r} nie jest identyfikatorem miejscowości TERYT (tylko cyfry)")
            elif len(v) != 7:
                self.warn("POLE", lbl, f"identyfikator miejscowości TERYT (SIMC) ma zwykle 7 cyfr ({v!r})")
        # country codes are checked in foreign()

    def required(self):
        for fid, spec in SPEC.items():
            if spec.required and not self.has(fid):
                if self.m.fmt == "survey" and fid in SURVEY_UNMAPPED:
                    self.warn("WYM", fid, f"pole wymagane w 2026 r. ({spec.desc}), ale PL_MONTHLY_XML.xsd nie ma dla "
                              "niego elementu - po transformacji go zabraknie")
                else:
                    self.err("WYM", fid, f"brak wymaganego pola lub pole puste ({spec.desc})")

    def rules(self):
        month, year = self.res.month, self.res.year
        p3 = self.num("p3")
        hotel = p3 is not None and 1 <= p3 <= 4

        # R1 - July-only fields
        present = [f for f in JULY_ONLY if f in self.by]
        if month is not None and month != 7 and present:
            self.err("R1", ", ".join(present), "pola dozwolone tylko w sprawozdaniu za lipiec", True)

        # R3
        if p3 is not None and (5 <= p3 <= 13 or 16 <= p3 <= 20):
            v = self.num("p4")
            if v is not None and v <= 0:
                self.err("R3", "p4", f"p3 = {p3:02d}, więc p4 musi być > 0")
            elif v is None and month == 7:
                self.err("R3", "p4", f"p3 = {p3:02d}: w sprawozdaniu za lipiec pole p4 jest wymagane")

        # R4-R6 categories
        p5 = self.num("p5")
        for rule, types, allowed, txt in (("R4", (1, 2, 3), (1, 2, 3, 4, 5, 9), "1-5 lub 9"),
                                          ("R5", (5, 7), (6, 7, 8, 9), "6-9"),
                                          ("R6", (14,), (2, 3, 4, 5, 9), "2-5 lub 9")):
            if p3 in types and (p5 is None or p5 not in allowed):
                hint = ""
                if self.m.fmt == "survey" and p5 is None and p3 in (5, 7, 14):
                    hint = " - uwaga: PL_MONTHLY_XML.xsd nie ma elementu EstablishmentCategory dla tego rodzaju obiektu"
                self.err(rule, "p5", f"p3 = {p3:02d}, więc kategoria p5 musi mieć wartość {txt} "
                         f"(jest: {self.show('p5')}){hint}")
        if p3 is not None and p3 not in CATEGORY_TYPES and self.has("p5"):
            self.warn("R4", "p5", f"kategorii nie podaje się dla rodzaju obiektu {p3:02d}")

        # R7
        if month == 7 and hotel:
            for fid in ("d3r1", "d3r2"):
                v = self.num(fid)
                if v is None or v <= 0:
                    self.err("R7", fid, f"sprawozdanie za lipiec, p3 = {p3:02d}: {fid} musi być > 0 "
                             f"(jest: {self.show(fid)})")

        # R8, R9 - open period
        p6 = self.num("p6")
        months = [f for f in self.by.get("p6a", [])]
        if p6 == 2:
            vals = [to_int(f.value) for f in months]
            good = {v for v in vals if v is not None and 1 <= v <= 12}
            if not months:
                self.err("R9", "p6a", "obiekt sezonowy (p6 = 2): wymagane są miesiące działania p6a")
            for f, v in zip(months, vals):
                if v is None or not 1 <= v <= 12:
                    self.err("R9", self.label(f), f"miesiąc {f.value!r} musi mieć wartość 1-12", True)
            if len(good) == 12:
                self.err("R9", "p6a", "obiekt sezonowy (p6 = 2) nie może działać przez wszystkie 12 miesięcy")
            if len([v for v in vals if v in good]) != len(good):
                self.warn("R9", "p6a", "ten sam miesiąc podano więcej niż raz", True)
        elif p6 == 1 and months:
            self.warn("R9", "p6a", "podano miesiące działania p6a dla obiektu całorocznego (p6 = 1)", True)

        # R10 - R13 (July: rooms and bed places)
        self.cmp("R10", "d3r1", "ge", "d3r2")
        self.cmp("R11", "d3r1", "ge", "d3r3")
        if self.has("d3r4") and (self.has("d3r5") or self.has("d3r6")):
            s = (self.num("d3r5") or 0) + (self.num("d3r6") or 0)
            if self.num("d3r4") is not None and self.num("d3r4") != s:
                self.err("R12", "d3r4", f"d3r4 ({self.num('d3r4')}) musi być równe d3r5 + d3r6 ({s})")
        if (self.num("d3r1") or 0) > 0 or hotel:
            self.cmp("R13", "d3r4", "lt", "d3r1", 10)

        # R14, R15 - days of activity
        d = self.num("d7w1")
        if d is not None:
            if not 1 <= d <= 31:
                self.err("R15", "d7w1", f"liczba dni działalności musi mieć wartość 1-31 (jest {d})")
            elif month:
                days = calendar.monthrange(year or 2024, month)[1]  # 2024 = leap year if year unknown
                if d > days:
                    self.err("R14", "d7w1", f"liczba dni działalności ({d}) przekracza liczbę dni w miesiącu "
                             f"{month:02d} ({days})")
                elif month == 2 and d == 29 and not year:
                    self.warn("R14", "d7w1", "29 dni w lutym jest poprawne tylko w roku przestępnym (rok nieznany)")

        # R16 - R19 - capacity
        if hotel:
            v = self.num("d7w3")
            if v is None or v <= 0:
                self.err("R16", "d7w3", f"p3 = {p3:02d}, więc nominalna liczba pokoi d7w3 musi być > 0 "
                         f"(jest: {self.show('d7w3')})")
        w2, w3 = self.num("d7w2"), self.num("d7w3")
        if w2 is not None and (w2 + (w3 or 0)) <= 0:
            self.err("R17", "d7w2", "d7w2 + d7w3 musi być > 0")
        if w2 is not None and w2 <= 0:
            self.err("R18", "d7w2", "nominalna liczba miejsc noclegowych d7w2 musi być > 0")
        if w3 is not None and (w3 > 0 or hotel):
            self.cmp("R19", "d7w2", "lt", "d7w3", 10)

        # R20 - R35 - utilisation
        self.cmp("R20", "d7w4r1", "le", "d7w2")
        self.cmp("R21", "d7w5r1", "le", "d7w2")
        self.cmp("R22", "d7w6r1", "le", "d7w3")
        self.cmp("R23", "d7w4r1", "ge", "d7w4r2")
        self.cmp("R24", "d7w5r1", "ge", "d7w5r2")
        self.cmp("R25", "d7w5ar1", "ge", "d7w5ar2")
        self.cmp("R26", "d7w5r1", "ge", "d7w5ar1")
        self.cmp("R27", "d7w5r2", "ge", "d7w5ar2")
        self.cmp("R28", "d7w6r1", "ge", "d7w6r2")
        self.cmp("R29", "d7w4r1", "le", "d7w5r1")
        self.cmp("R30", "d7w4r2", "le", "d7w5r2")
        a, b, c, e = (self.num(x) for x in ("d7w4r1", "d7w4r2", "d7w5r1", "d7w5r2"))
        if None not in (a, b, c, e) and a - b > c - e:
            self.err("R31", "d7w4r1", f"turyści krajowi d7w4r1-d7w4r2 ({a - b}) muszą być <= "
                     f"noclegom krajowym d7w5r1-d7w5r2 ({c - e})")
        self.implies("R32", "d7w4r1", "d7w5r1")
        self.implies("R33", "d7w4r2", "d7w5r2")
        if hotel:
            self.implies("R34", "d7w4r1", "d7w6r1")
            self.implies("R35", "d7w4r2", "d7w6r2")
        # refugees - not in the rule list, analogous to R29/R32
        x, y = self.num("d7aw2"), self.num("d7aw3")
        if x is not None and y is not None and x > y:
            self.warn("R29*", "d7aw2", f"uchodźcy ({x}) > noclegi udzielone uchodźcom d7aw3 ({y})")

    def rows(self) -> list:
        rows: dict = {}
        for f in self.m.fields:
            if f.id not in MULTI_IDS:
                continue
            r = rows.setdefault((f.index, f.occ), Row(f.index, f.occ))
            v = f.value.strip() if f.value is not None else ""
            r.has.add(f.id)
            if f.id == "d8_lp":
                r.lp = v
            elif f.id == "d8r1":
                r.country = v
            elif f.id == "d8r2":
                r.acc = v
            else:
                r.nights = v
        return [rows[k] for k in sorted(rows)]

    def foreign(self):
        rows = self.rows()
        data = [r for r in rows if r.has - {"d8_lp"}]
        n = len(data)
        lbl = lambda r: (f"wiersz indeks={r.index}" + (f" (wystąpienie {r.occ + 1})" if r.occ else "")  # noqa: E731
                         if self.m.fmt == "base" else f"ForeignTourists[{r.index + 1}]")

        dup_idx = sorted({r.index for r in rows if r.occ})
        if dup_idx:
            self.err("MS", "d8", "kilka pól działu 8 ma ten sam indeks (%s) - każdy wiersz multisekcji musi mieć "
                     "własny indeks 0..n-1" % ", ".join(map(str, dup_idx)), True)
        elif self.m.fmt == "base" and [r.index for r in data] != list(range(n)):
            self.warn("MS", "d8", "wartości indeks w multisekcji nie są kolejne 0..%d" % (n - 1), True)

        codes: dict = {}
        sum_acc = sum_n = 0
        for i, r in enumerate(data):
            L = lbl(r)
            for fid in ("d8r1", "d8r2", "d8r3"):
                if fid not in r.has:
                    self.err("MS", L, f"brak pola {fid} w tym wierszu", True)
            code, kind = normalize_country(r.country)
            if kind == "padded":
                self.info("R37", L, f"kod kraju {r.country!r} należy zapisać trzema cyframi ('{code}')", True)
            elif kind == "alpha":
                self.err("R37", L, f"kraj {r.country!r} musi być podany numerycznym kodem ISO 3166-1 ('{code}' = "
                         f"{country_name(code)})", True)
            elif kind == "invalid":
                self.err("R37", L, f"{r.country!r} nie jest numerycznym kodem kraju ISO 3166-1 (dla kraju "
                         "nieustalonego / bezpaństwowca użyj 999)", True)
            elif kind == "empty" and "d8r1" in r.has:
                self.err("R37", L, "pusty kod kraju", True)
            if code == POLAND:
                self.warn("R37", L, "616 = Polska - mieszkańcy Polski nie są turystami zagranicznymi")
            if code:
                codes.setdefault(code, []).append(r)
            acc, nights = to_int(r.acc), to_int(r.nights)
            for fid, raw, v in (("d8r2", r.acc, acc), ("d8r3", r.nights, nights)):
                if fid in r.has and v is None:
                    self.err("POLE", L, f"{fid} = {raw!r} nie jest nieujemną liczbą całkowitą")
                elif v is not None and len(str(v)) > 6:
                    self.err("POLE", L, f"{fid} = {v} ma więcej niż 6 cyfr")
            if acc is not None and nights is not None and acc > nights:
                self.err("R36", L, f"liczba turystów d8r2 ({acc}) musi być <= liczbie noclegów d8r3 ({nights})")
            if acc is not None and acc > 0 and (nights is None or nights <= 0):
                self.err("R39", L, f"liczba turystów d8r2 = {acc} > 0, więc liczba noclegów d8r3 musi być > 0")
            if code and (nights is None or nights <= 0) and not (acc and acc > 0):
                self.err("R40", L, f"podano kraj {code}, więc liczba noclegów d8r3 musi być > 0 "
                         "(pusty wiersz - można go usunąć)", True)
            if self.m.fmt == "base" and r.lp is not None and r.lp != str(i + 1):
                self.warn("MS", L, f"d8_lp = {r.lp!r}, oczekiwano {i + 1}", True)
            sum_acc += acc or 0
            sum_n += nights or 0

        for code, rs in codes.items():
            if len(rs) > 1:
                self.err("R38", "d8r1", f"kraj {code} ({country_name(code)}) występuje {len(rs)} razy "
                         f"({', '.join(lbl(r) for r in rs)}) - wpisy należy zsumować w jednym wierszu", True)

        if self.m.fmt == "base":
            ms = self.m.extra.get("multi")
            if ms is None and n:
                self.err("MS", "s_dz8_multi", f'brak elementu <MultiSekcja id="s_dz8_multi" iloscSekcji="{n}"/>', True)
            elif ms is not None and ms.get("iloscSekcji", "").strip() != str(n):
                self.err("MS", "s_dz8_multi", f"iloscSekcji = {ms.get('iloscSekcji')!r}, a sekcja ma "
                         f"{n} wiersz(y)", True)

        for tot, s, what in (("d8r2w0", sum_acc, "turystów"), ("d8r3w0", sum_n, "noclegów")):
            if self.has(tot) and self.num(tot) != s:
                self.err("R41", tot, f"suma automatyczna {tot} = {self.show(tot)}, a suma {what} w wierszach "
                         f"wynosi {s}", True)
        for fid, s, what in (("d7w4r2", sum_acc, "turystów zagranicznych (d8r2)"),
                             ("d7w5r2", sum_n, "noclegów turystów zagranicznych (d8r3)")):
            v = self.num(fid)
            if v is not None and v != s:
                self.err("R41", fid, f"{fid} = {v}, a suma {what} w dziale 8 wynosi {s}")


# --------------------------------------------------------------------------------------
# Fixing
# --------------------------------------------------------------------------------------
def remove_child(parent: ET.Element, el: ET.Element) -> None:
    kids = list(parent)
    i = kids.index(el)
    if i > 0:
        kids[i - 1].tail = el.tail
    parent.remove(el)


def replace_group(parent: ET.Element, old: list, new: list) -> None:
    kids = list(parent)
    first = min(old, key=kids.index)
    pos = kids.index(first)
    ws = first.tail
    for k, el in enumerate(new):
        el.tail = ws
        parent.insert(pos + k, el)
    for el in old:
        remove_child(parent, el)


def append_child(parent: ET.Element, el: ET.Element) -> None:
    kids = list(parent)
    if kids:
        between = kids[-2].tail if len(kids) > 1 else parent.text
        el.tail = kids[-1].tail
        kids[-1].tail = between
    parent.append(el)


class Fixer:
    def __init__(self, res: Result, args):
        self.res = res
        self.m: Model = res.model
        self.args = args
        self.log: list = []
        self.chk = Checker(res, args)

    def set_value(self, f: Field, v: str):
        if self.m.fmt == "base":
            f.elem.set("wartosc", v)
        else:
            f.elem.text = v
        f.value = v

    def remove_field(self, f: Field):
        if f.elem is not None and f.parent is not None and f.elem in list(f.parent):
            remove_child(f.parent, f.elem)

    def run(self) -> list:
        if self.res.repaired_amp:
            self.log.append(f"zakodowano {self.res.repaired_amp} znak(i) '&' jako &amp;")
        self.whitespace()
        self.p3()
        self.july()
        self.open_months()
        self.foreign()
        return self.log

    def whitespace(self):
        for f in self.m.fields:
            spec = SPEC.get(f.id)
            if f.elem is None or f.value is None or spec is None or spec.type == "str":
                continue
            if f.value.strip() != f.value:
                self.log.append(f"{f.id}: usunięto spacje z wartości {f.value!r}")
                self.set_value(f, f.value.strip())

    def p3(self):
        f = self.chk.first("p3")
        if self.m.fmt == "base" and f is not None and f.value and re.fullmatch(r"[0-9]", f.value.strip()):
            self.set_value(f, "0" + f.value.strip())
            self.log.append(f"p3: '{f.value[1:]}' -> '{f.value}'")

    def july(self):
        month = self.res.month
        if month is None or month == 7:
            return
        if self.m.fmt == "base":
            for f in self.m.fields:
                if f.id in JULY_ONLY:
                    self.remove_field(f)
                    self.log.append(f"{f.id}: usunięto (pole tylko dla lipca, miesiąc sprawozdania {month:02d})")
        else:
            cont, kind = self.m.extra["contents"], self.m.extra["kind"]
            for key, parent in (("catering", cont), ("accomodation", kind), ("provides", kind)):
                el = self.m.extra.get(key)
                if el is not None:
                    remove_child(parent, el)
                    self.log.append(f"<{local(el.tag)}>: usunięto (dane tylko dla lipca, miesiąc sprawozdania "
                                    f"{month:02d})")

    def open_months(self):
        p6 = self.chk.num("p6")
        seen = set()
        for f in self.chk.by.get("p6a", []):
            v = to_int(f.value)
            why = None
            if p6 == 1:
                why = "obiekt całoroczny (p6 = 1)"
            elif p6 == 2 and (v is None or not 1 <= v <= 12):
                why = "niepoprawny miesiąc"
            elif p6 == 2 and v in seen:
                why = "powtórzony miesiąc"
            seen.add(v)
            if why:
                self.remove_field(f)
                self.log.append(f"p6a {f.value!r}: usunięto ({why})")

    def foreign(self):
        rows = [r for r in self.chk.rows() if r.has - {"d8_lp"}]
        merged: dict = {}
        for r in rows:
            where = f"indeks={r.index}" if self.m.fmt == "base" else f"ForeignTourists[{r.index + 1}]"
            code, kind = normalize_country(r.country)
            if kind in ("invalid", "empty"):
                if self.args.invalid_country == "remove":
                    self.log.append(f"dział 8 {where}: usunięto wiersz z niepoprawnym krajem {r.country!r} "
                                    f"({r.acc or 0} turystów, {r.nights or 0} noclegów)")
                    continue
                code = UNKNOWN_COUNTRY
                self.log.append(f"dział 8 {where}: niepoprawny kraj {r.country!r} -> 999 (kraj nieustalony)")
            elif kind in ("padded", "alpha"):
                self.log.append(f"dział 8 {where}: kraj {r.country!r} -> '{code}' ({country_name(code)})")
            acc, nights = to_int(r.acc) or 0, to_int(r.nights) or 0
            if code in merged:
                m = merged[code]
                self.log.append(f"dział 8 {where}: powtórzony kraj {code} ({country_name(code)}) scalony: "
                                f"turyści {m[0]}+{acc}={m[0] + acc}, noclegi {m[1]}+{nights}={m[1] + nights}")
                m[0] += acc
                m[1] += nights
            else:
                merged[code] = [acc, nights]
        if not self.args.keep_zero_rows:
            for code in [c for c, (a, n) in merged.items() if a == 0 and n == 0]:
                del merged[code]
                self.log.append(f"dział 8: usunięto pusty wiersz kraju {code} (0 turystów, 0 noclegów)")
        new = [(c, a, n) for c, (a, n) in merged.items()]

        old_sig = [(r.index, r.lp or "", r.country, r.acc, r.nights) for r in rows]
        had_lp = "d8_lp" in self.chk.by
        new_sig = [(i, str(i + 1) if had_lp else "", c, str(a), str(n)) for i, (c, a, n) in enumerate(new)]
        if self.m.fmt == "survey":
            old_sig = [s[2:] for s in old_sig]
            new_sig = [s[2:] for s in new_sig]
        if old_sig != new_sig:
            if self.m.fmt == "base":
                self.write_base(new, had_lp)
            else:
                self.write_survey(new)
            self.log.append(f"dział 8: przebudowano sekcję turystów zagranicznych ({len(rows)} -> {len(new)} "
                            "wiersz(y))")
        if self.m.fmt == "base":
            self.base_totals(new)

    def write_base(self, new: list, had_lp: bool):
        old = [f for f in self.m.fields if f.id in MULTI_IDS]
        parent = old[0].parent
        lp_tpl = next((f.elem for f in old if f.id == "d8_lp"), None)
        elems = []
        for i, (code, acc, nights) in enumerate(new):
            vals = ([("d8_lp", str(i + 1))] if had_lp else []) + \
                   [("d8r1", code), ("d8r2", str(acc)), ("d8r3", str(nights))]
            for fid, v in vals:
                attrs = {}
                if fid == "d8_lp" and lp_tpl is not None and lp_tpl.get("automatyczne"):
                    attrs["automatyczne"] = lp_tpl.get("automatyczne")
                attrs["id"] = fid
                if i:
                    attrs["indeks"] = str(i)
                attrs["wartosc"] = v
                elems.append(ET.Element(q("Pole"), attrs))
        replace_group(parent, [f.elem for f in old if f.elem in list(parent)], elems)

    def write_survey(self, new: list):
        old = self.m.extra["foreign"]
        parent = self.m.extra["contents"]
        elems = []
        for code, acc, nights in new:
            e = copy.deepcopy(old[0])
            for name, v in (("Country", code), ("Accoumodated", str(acc)), ("Nights", str(nights))):
                c = child(e, name)
                if c is None:
                    c = ET.SubElement(e, name)
                c.text = v
            elems.append(e)
        replace_group(parent, old, elems)

    def base_totals(self, new: list):
        n = len(new)
        el = self.m.extra["elementy"]
        ms = self.m.extra.get("multi")
        if ms is None and n:
            append_child(el, ET.Element(q("MultiSekcja"), {"iloscSekcji": str(n), "id": "s_dz8_multi"}))
            self.log.append(f'dodano <MultiSekcja id="s_dz8_multi" iloscSekcji="{n}"/>')
        elif ms is not None and ms.get("iloscSekcji") != str(n):
            self.log.append(f"s_dz8_multi: iloscSekcji {ms.get('iloscSekcji')!r} -> '{n}'")
            ms.set("iloscSekcji", str(n))
        for fid, s in (("d8r2w0", sum(a for _, a, _ in new)), ("d8r3w0", sum(x for _, _, x in new))):
            f = self.chk.first(fid)
            if f is not None and f.elem is not None and (f.value or "").strip() != str(s):
                self.log.append(f"{fid}: {f.value!r} -> '{s}'")
                self.set_value(f, str(s))


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
def validate(path: str, args) -> Result:
    res = Result(path)
    load(path, res)
    if res.fatal:
        return res
    root = res.root
    if root.tag == q("Sprawozdanie"):
        fmt = "base"
        res.notes.insert(0, "format : podstawowy (Sprawozdanie / Pole)")
    elif root.tag == "{%s}Survey" % NS_KT1:
        fmt = "survey"
        res.notes.insert(0, "format : przyjazny KT-1 (Survey, PL_MONTHLY_XML.xsd) - przed wysłaniem wymaga "
                         "transformacji XSL")
    else:
        if local(root.tag) in ("Sprawozdanie", "Survey"):
            res.add("ERROR", "XML", "", f"element główny <{local(root.tag)}> ma złą przestrzeń nazw "
                    f"'{root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''}' (oczekiwano {NS_SPR} lub "
                    f"{NS_KT1})")
        else:
            res.add("ERROR", "XML", "", f"nieznany element główny <{local(root.tag)}> - oczekiwano <Sprawozdanie> "
                    "lub <Survey>")
        res.fatal = True
        return res

    if not args.no_schema:
        xsd = os.path.join(args.schema_dir, "sprawozdanie.xsd" if fmt == "base" else "PL_MONTHLY_XML.xsd")
        done = False
        try:
            done = os.path.exists(xsd) and xsd_validate_lxml(res, xsd)
        except Exception as e:  # broken schema etc.
            res.add("WARNING", "XSD", "", f"walidacja XSD przez lxml nie powiodła się: {e}")
        if not done:
            if fmt == "base":
                xsd_validate_builtin(res)
            else:
                res.notes.append("schemat: walidacja XSD formatu przyjaznego wymaga lxml (pip install lxml)")

    res.model = build_base(root, res) if fmt == "base" else build_survey(root, res)
    Checker(res, args).run()
    return res


USE_COLOR = False
COLORS = {"ERROR": "31", "WARNING": "33", "INFO": "90", "OK": "32", "HEAD": "36", "FIX": "35"}


def c(kind: str, s: str) -> str:
    return f"\033[{COLORS[kind]}m{s}\033[0m" if USE_COLOR else s


def summary_line(ne: int, nw: int, ni: int) -> str:
    return f"błędy: {ne}, ostrzeżenia: {nw}, informacje: {ni}"


def print_report(res: Result, title: str, show_info: bool, fix_mode: bool):
    print()
    print(c("HEAD", f"=== {title}: {res.path}"))
    for n in res.notes:
        print(f"    {n}")
    for sev in ("ERROR", "WARNING", "INFO"):
        if sev == "INFO" and not show_info:
            continue
        for i in res.issues:
            if i.severity != sev:
                continue
            tag = f"[{i.rule}] " if i.rule else ""
            fld = f"{i.field}: " if i.field else ""
            fx = "  (do poprawienia automatycznie)" if i.fixable and not fix_mode else ""
            print(c(sev, f"  {SEV_PL[sev]:<11} {tag}{fld}{i.message}{fx}"))
    ne, nw, ni = res.count("ERROR"), res.count("WARNING"), res.count("INFO")
    nf = sum(1 for i in res.issues if i.fixable)
    if res.fatal:
        print(c("ERROR", "  WYNIK: NIE MOŻNA ZWALIDOWAĆ"))
    elif ne:
        print(c("ERROR", f"  WYNIK: NIEPOPRAWNY - {summary_line(ne, nw, ni)}"))
    else:
        print(c("OK", f"  WYNIK: POPRAWNY - {summary_line(ne, nw, ni)}"))
    if nf and not fix_mode:
        print(f"  {nf} problem(ów) można poprawić automatycznie - uruchom ponownie z opcją --fix")


HTML_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2330;--muted:#667085;--line:#e4e7ec;
--err:#c4321f;--err-bg:#fdecea;--warn:#a15c00;--warn-bg:#fff4e0;--info:#5b6474;--info-bg:#eef0f3;
--ok:#18794e;--ok-bg:#e6f6ed;--fix:#6941c6;--fix-bg:#f1ecfd;--accent:#2559c9}
@media (prefers-color-scheme:dark){:root{--bg:#14161b;--card:#1d2027;--text:#e6e8ec;--muted:#9aa3b2;--line:#2e323b;
--err:#ff8a7a;--err-bg:#3a1d1a;--warn:#ffc061;--warn-bg:#36290f;--info:#aeb6c4;--info-bg:#262a32;
--ok:#5fd39b;--ok-bg:#15301f;--fix:#b9a2ff;--fix-bg:#2a2340;--accent:#7aa2ff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:0;word-break:break-all}
h3{font-size:14px;margin:20px 0 8px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.sub{color:var(--muted);margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:16px 0}
.head{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:12px;white-space:nowrap}
.b-ok{background:var(--ok-bg);color:var(--ok)}.b-err{background:var(--err-bg);color:var(--err)}
.notes{margin:10px 0 0;padding:0;list-style:none;color:var(--muted);font-size:13px}
.counts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chip{border:1px solid var(--line);background:transparent;color:var(--text);border-radius:999px;padding:3px 12px;
font:inherit;font-size:12px;cursor:pointer}.chip[aria-pressed=false]{opacity:.45}
.chip b{margin-right:4px}.c-ERROR b{color:var(--err)}.c-WARNING b{color:var(--warn)}.c-INFO b{color:var(--info)}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px}
.tbl td{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}
.tbl tr:last-child td{border-bottom:0}
.sev{font-weight:700;font-size:11px;padding:2px 7px;border-radius:4px;white-space:nowrap}
.s-ERROR{color:var(--err);background:var(--err-bg)}.s-WARNING{color:var(--warn);background:var(--warn-bg)}
.s-INFO{color:var(--info);background:var(--info-bg)}
code,.mono{font-family:Consolas,"Cascadia Mono",monospace;font-size:12.5px}
.fx{color:var(--fix);background:var(--fix-bg);font-size:11px;padding:1px 6px;border-radius:4px;white-space:nowrap}
.fixes{margin:0;padding-left:18px}.fixes li{margin:2px 0}
.empty{color:var(--ok);margin:8px 0}
a{color:var(--accent)}
.hidden{display:none}
@media (max-width:640px){.tbl .c-field{display:none}main{padding:16px 12px}}
"""

HTML_JS = """
document.querySelectorAll('.chip').forEach(function(b){b.addEventListener('click',function(){
var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on);
var card=b.closest('.card');card.querySelectorAll('tr.'+b.dataset.sev).forEach(function(r){r.classList.toggle('hidden',!on)})})});
"""


def build_html(records: list) -> str:
    import datetime
    import html
    from pathlib import Path

    e = html.escape

    def issues_table(res: Result, fix_mode: bool) -> str:
        order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
        items = sorted(res.issues, key=lambda i: order[i.severity])
        if not items:
            return '<p class="empty">Nie znaleziono problemów.</p>'
        rows = []
        for i in items:
            fx = ' <span class="fx">do poprawienia automatycznie</span>' if i.fixable and not fix_mode else ""
            rows.append(f'<tr class="{i.severity}"><td><span class="sev s-{i.severity}">{SEV_PL[i.severity]}</span>'
                        f'</td><td class="mono">{e(i.rule)}</td><td class="mono c-field">{e(i.field)}</td>'
                        f'<td>{e(i.message)}{fx}</td></tr>')
        return ('<table class="tbl"><thead><tr><th>Waga</th><th>Reguła</th><th class="c-field">Pole</th>'
                f'<th>Opis</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')

    def section(res: Result, title: str, fix_mode: bool) -> str:
        ne, nw, ni = res.count("ERROR"), res.count("WARNING"), res.count("INFO")
        if res.fatal:
            badge = '<span class="badge b-err">NIE MOŻNA ZWALIDOWAĆ</span>'
        elif ne:
            badge = '<span class="badge b-err">NIEPOPRAWNY</span>'
        else:
            badge = '<span class="badge b-ok">POPRAWNY</span>'
        uri = Path(os.path.abspath(res.path)).as_uri()
        notes = "".join(f"<li>{e(n)}</li>" for n in res.notes)
        chips = "".join(f'<button class="chip c-{s}" data-sev="{s}" aria-pressed="true"><b>{n}</b>{label}</button>'
                        for s, n, label in (("ERROR", ne, "błędy"), ("WARNING", nw, "ostrzeżenia"),
                                            ("INFO", ni, "informacje")))
        nf = sum(1 for i in res.issues if i.fixable)
        hint = (f'<p class="sub" style="margin:10px 0 0">Problemy do poprawienia automatycznie: {nf} - uruchom '
                f'ponownie z opcją <code>--fix</code>.</p>' if nf and not fix_mode else "")
        return (f'<div class="card"><div class="head"><div><h3 style="margin:0 0 4px">{e(title)}</h3>'
                f'<h2><a href="{e(uri)}">{e(res.path)}</a></h2></div>{badge}</div>'
                f'<ul class="notes">{notes}</ul><div class="counts">{chips}</div>{hint}'
                f'<h3>Wyniki kontroli</h3>{issues_table(res, fix_mode)}</div>')

    parts = []
    for r in records:
        parts.append(section(r["res"], "Walidacja", False))
        if r["fixed"]:
            fixes = "".join(f"<li>{e(x)}</li>" for x in r["fix_log"])
            out_uri = Path(os.path.abspath(r["out"])).as_uri()
            parts.append(f'<div class="card"><h3 style="margin-top:0">Poprawki automatyczne</h3>'
                         f'<p>Poprawiony plik: <a href="{e(out_uri)}">{e(r["out"])}</a></p>'
                         f'<ol class="fixes">{fixes}</ol></div>')
            parts.append(section(r["final"], "Walidacja po poprawkach", True))
            if r["final"].count("ERROR"):
                parts.append('<p class="sub">Pozostałe błędy wymagają ręcznej korekty - poprawnej wartości nie da się '
                             'ustalić na podstawie pliku.</p>')
    valid = sum(1 for r in records if not r["final"].fatal and not r["final"].count("ERROR"))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f'<!doctype html><html lang="pl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Raport walidacji KT-1</title>'
            f'<style>{HTML_CSS}</style></head><body><main><h1>Raport walidacji KT-1</h1>'
            f'<div class="sub">{now} &middot; poprawne pliki: {valid} z {len(records)} &middot; '
            f'kt1_validator {__version__}</div>{"".join(parts)}</main><script>{HTML_JS}</script></body></html>')


def write_xml(res: Result, out: str):
    tree = ET.ElementTree(res.root)
    with open(out, "wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(fh, encoding="utf-8", xml_declaration=False, short_empty_elements=True)


def main(argv=None) -> int:
    global USE_COLOR
    ap = argparse.ArgumentParser(
        prog="kt1_validator",
        description="Walidacja (i opcjonalna korekta) plików XML sprawozdania GUS KT-1 - instrukcja 2026.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="kod wyjścia: 0 = poprawny, 1 = błędy walidacji, 2 = nie można odczytać pliku\n"
               "przykłady:\n"
               "  python kt1_validator.py raport.xml\n"
               "  python kt1_validator.py raport.xml --month 3 --year 2026 --fix\n"
               "  python kt1_validator.py raporty\\*.xml --json wynik.json")
    ap.add_argument("files", nargs="+", help="plik(i) XML; można używać symboli wieloznacznych")
    ap.add_argument("-m", "--month", type=int, choices=range(1, 13), metavar="1-12",
                    help="miesiąc sprawozdawczy (domyślnie: pole 'mc', jeśli jest)")
    ap.add_argument("-y", "--year", type=int, help="rok sprawozdawczy (domyślnie: pole 'rok', jeśli jest)")
    ap.add_argument("--fix", action="store_true", help="zapisz poprawioną kopię i ją zwaliduj")
    ap.add_argument("-o", "--output", help="plik wynikowy dla --fix (domyślnie: <nazwa>.fixed.xml; tylko dla "
                    "jednego pliku)")
    ap.add_argument("--in-place", action="store_true", help="z --fix: nadpisz plik wejściowy (kopia .bak zostaje)")
    ap.add_argument("--invalid-country", choices=["unknown", "remove"], default="unknown",
                    help="--fix: niepoprawny kod kraju zamień na 999 (domyślnie) lub usuń wiersz")
    ap.add_argument("--keep-zero-rows", action="store_true",
                    help="--fix: zachowaj wiersze krajów z 0 turystów i 0 noclegów")
    ap.add_argument("--schema-dir", default=os.path.join(SCRIPT_DIR, "schemas"), help="katalog z plikami XSD")
    ap.add_argument("--no-schema", action="store_true", help="pomiń walidację XSD / struktury")
    ap.add_argument("-q", "--quiet", action="store_true", help="nie pokazuj komunikatów INFO")
    ap.add_argument("--json", metavar="PLIK", help="zapisz wyniki również w formacie JSON")
    ap.add_argument("--html", metavar="PLIK", help="ścieżka raportu HTML (domyślnie: <nazwa>.report.html obok "
                    "pliku wejściowego; kt1-report-<czas>.html w bieżącym katalogu dla wielu plików)")
    ap.add_argument("--no-html", action="store_true", help="nie twórz raportu HTML")
    ap.add_argument("--no-open", action="store_true", help="utwórz raport HTML, ale nie otwieraj przeglądarki")
    ap.add_argument("--no-color", action="store_true", help="wyłącz kolory w konsoli")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    USE_COLOR = not args.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ
    if USE_COLOR and os.name == "nt":
        os.system("")  # enables ANSI escape sequences in the Windows console

    import glob
    files = []
    for p in args.files:
        hits = sorted(glob.glob(p)) if any(ch in p for ch in "*?[") else [p]
        files.extend(hits or [p])
    if args.output and len(files) > 1:
        ap.error("--output można użyć tylko dla jednego pliku wejściowego")

    exit_code = 0
    summary = []
    records = []
    for path in files:
        if not os.path.isfile(path):
            print(c("ERROR", f"\n=== nie znaleziono pliku: {path}"))
            exit_code = 2
            continue
        res = validate(path, args)
        print_report(res, "WALIDACJA", not args.quiet, False)
        final = res
        fix_log = []
        out = None
        if args.fix and not res.fatal:
            fix_log = Fixer(res, args).run()
            if args.in_place:
                out = path
                import shutil
                shutil.copy2(path, path + ".bak")
            else:
                out = args.output or os.path.splitext(path)[0] + ".fixed.xml"
            print()
            reencode = any(i.rule == "KOD" for i in res.issues)
            if fix_log or reencode:
                if reencode:
                    fix_log.append("plik zapisano w kodowaniu UTF-8")
                write_xml(res, out)
                print(c("HEAD", f"=== POPRAWKI zapisane w: {out}"))
                for line in fix_log:
                    print(c("FIX", f"  POPRAWIONO {line}"))
                final = validate(out, args)
                print_report(final, "WALIDACJA PO POPRAWKACH", not args.quiet, True)
                if final.count("ERROR"):
                    print("  pozostałe błędy wymagają ręcznej korekty (poprawnej wartości nie da się ustalić)")
            else:
                out = None
                print(c("HEAD", "=== POPRAWKI: brak problemów do automatycznej poprawy"))
        records.append({"res": res, "final": final, "fix_log": fix_log, "out": out, "fixed": final is not res})
        if final.fatal:
            exit_code = max(exit_code, 2)
        elif final.count("ERROR"):
            exit_code = max(exit_code, 1)
        summary.append({
            "file": path, "valid": not final.fatal and final.count("ERROR") == 0,
            "fixed_file": out, "fixes": fix_log,
            "issues_before_fix": [i.__dict__ for i in res.issues],
            "issues": [i.__dict__ for i in final.issues],
        })

    if len(files) > 1:
        ok = sum(1 for s in summary if s["valid"])
        print(c("HEAD", f"\n=== PODSUMOWANIE: poprawne pliki: {ok} z {len(files)}"))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
    if records and not args.no_html:
        if args.html:
            report = args.html
        elif len(records) == 1:
            report = os.path.splitext(records[0]["res"].path)[0] + ".report.html"
        else:
            import datetime
            report = "kt1-report-%s.html" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(build_html(records))
        print(c("HEAD", f"\n=== Raport HTML: {os.path.abspath(report)}"))
        if not args.no_open:
            import webbrowser
            from pathlib import Path
            webbrowser.open(Path(os.path.abspath(report)).as_uri())
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
