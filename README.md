# Walidator XML KT-1

Sprawdza pliki XML z miesięcznym sprawozdaniem **KT-1** (turystyczne obiekty noclegowe, GUS) zgodnie
z `Instrukcja_dla_dostawcow_oprogramowania_2026.docx` i dołączonymi do niej plikami XSD. Wypisuje wszystkie
znalezione problemy, tworzy raport HTML i może zapisać poprawioną kopię pliku.

## Wymagania

- Python 3.8 lub nowszy. Skrypt korzysta tylko z biblioteki standardowej.
- Opcjonalnie: `pip install lxml` włącza pełną walidację XSD (`schemas/*.xsd`). Bez lxml pliki w formacie
  podstawowym przechodzą wbudowaną kontrolę struktury, równoważną `sprawozdanie.xsd`.

## Uruchamianie

Windows (cmd / PowerShell), z tego katalogu:

```bat
kt1-validate.cmd raport.xml
```

```bat
kt1-validate.cmd raport.xml --month 3 --year 2026 --fix
```

Bezpośrednio przez Pythona (dowolny system):

```bash
python kt1_validator.py raport.xml --month 3 --fix
```

Linux / macOS / Git Bash:

```bash
./kt1-validate.sh raport.xml --fix
```

Kilka plików naraz (symbole wieloznaczne działają także w Windows):

```bat
kt1-validate.cmd C:\raporty\*.xml -q --json wynik.json
```

### Opcje

| Opcja | Znaczenie |
|---|---|
| `-m N`, `--month N` | Miesiąc sprawozdawczy 1-12. Domyślnie: pole `mc`, jeśli występuje. Potrzebny do reguł R1, R3, R7, R14 (pola tylko dla lipca, liczba dni w miesiącu). |
| `-y N`, `--year N` | Rok sprawozdawczy. Domyślnie: pole `rok`. Używany dla lutego w latach przestępnych. |
| `--fix` | Wprowadza poprawki automatyczne, zapisuje `<nazwa>.fixed.xml` i ponownie waliduje wynik. |
| `-o PLIK` | Plik wynikowy dla `--fix` (tylko dla jednego pliku wejściowego). |
| `--in-place` | Z `--fix`: nadpisuje plik wejściowy i zostawia kopię `.bak`. |
| `--invalid-country unknown\|remove` | Z `--fix`: niepoprawny kod kraju zamieniany jest na `999` (domyślnie, sumy pozostają zgodne) albo wiersz jest usuwany. |
| `--keep-zero-rows` | Z `--fix`: zachowuje wiersze krajów z 0 turystów i 0 noclegów. |
| `-q` | Ukrywa komunikaty INFO. |
| `--html PLIK` | Ścieżka raportu HTML. Domyślnie: `<nazwa>.report.html` obok pliku wejściowego albo `kt1-report-<data-godzina>.html` w bieżącym katalogu, gdy sprawdzanych jest kilka plików. |
| `--no-open` | Tworzy raport HTML, ale nie otwiera go w przeglądarce. |
| `--no-html` | Nie tworzy raportu HTML (tylko wynik w konsoli). |
| `--json PLIK` | Dodatkowo zapisuje wyniki w formacie JSON (do integracji). |
| `--no-schema` | Pomija walidację XSD / kontrolę struktury. |
| `--no-color` | Wyłącza kolory w konsoli. |

Cały wynik (konsola, raport HTML, `--help`) jest po polsku. Waga problemu jest oznaczana jako
BŁĄD / OSTRZEŻENIE / INFO. Wynik `--json` zachowuje klucze `ERROR` / `WARNING` / `INFO`, żeby nie psuć integracji.

Każde uruchomienie tworzy też **raport HTML** i otwiera go w domyślnej przeglądarce. Raport pokazuje status
każdego pliku, wyniki kontroli z filtrowaniem według wagi, listę poprawek automatycznych z odnośnikiem do
poprawionego pliku oraz wynik walidacji po poprawkach. Przy uruchomieniach automatycznych (harmonogram,
przetwarzanie wsadowe) użyj `--no-open` lub `--no-html`.

Kod wyjścia: `0` plik poprawny (ostrzeżenia dopuszczalne), `1` błędy walidacji, `2` brak pliku lub nie da się
go odczytać. Z `--fix` kod wyjścia dotyczy poprawionego pliku.

## Obsługiwane formaty

- **Format podstawowy**: `<Sprawozdanie xmlns="http://ps.stat.gov.pl/ps/schema/sprawozdanie">` z elementami
  `<Pole id="…" wartosc="…"/>`. Ten format wysyła się do portalu.
- **Format przyjazny**: `<Survey xmlns="http://ps.stat.gov.pl/ps/schema/sprawozdanie/kt1">`
  (`PL_MONTHLY_XML.xsd`). Jest sprawdzany przez przypisanie jego elementów do tych samych pól KT-1.

## Co jest sprawdzane

| Znacznik | Kontrole |
|---|---|
| `[XML]` | Poprawność składni XML, np. niezakodowany znak `&` w nazwie (`Home & Travel`). |
| `[KOD]` | Kodowanie. Usługa sieciowa wymaga UTF-8. |
| `[XSD]` | Schemat / struktura (`sprawozdanie.xsd`). |
| `[NAGŁ]` | `formularzSymbol="KT-1"`, `numerSprawozdania="0"`, wyświetla `formularzWersja`. |
| `[POLE]` | Nieznane lub powtórzone pola, liczby całkowite i maksymalna liczba cyfr, długość tekstu, wartości dozwolone (p3 01-20, p5 1-9, p6 1/2, …), wyrażenie regularne e-mail z instrukcji, suma kontrolna REGON, symbol TERYT, kod pocztowy. |
| `[WYM]` | Pola wymagane (liczba wystąpień `1..1` w instrukcji). |
| `[R1]`…`[R41]` | 41 reguł z rozdziału *Walidacje*, numerowanych tak jak w instrukcji. |
| `[MS]` | Multisekcja turystów zagranicznych: `indeks` 0..n-1, `MultiSekcja s_dz8_multi iloscSekcji`, `d8_lp`, każdy wiersz ma d8r1/d8r2/d8r3. |

Kody krajów (R37) są sprawdzane z pełną listą numerycznych kodów ISO 3166-1 (249 kodów, polskie nazwy
krajów) oraz kodem `999` (kraj nieustalony / bezpaństwowiec). Kod `616` (Polska) daje ostrzeżenie, bo
mieszkańcy Polski nie są turystami zagranicznymi.

## Poprawki automatyczne (`--fix`)

- Zamiana niezakodowanego `&` na `&amp;`, zapis pliku w UTF-8.
- Kody krajów: usunięcie spacji, uzupełnienie zerami (`40` → `040`), zamiana kodów literowych ISO
  (`DE`/`DEU` → `276`).
- Niepoprawny kod kraju → `999` albo usunięcie wiersza z `--invalid-country remove`.
- **Scalanie powtórzonych krajów**: turyści i noclegi są sumowane (R38).
- Usunięcie wierszy z 0 turystów i 0 noclegów.
- Przenumerowanie multisekcji (`indeks`, `d8_lp`), poprawienie lub dodanie `MultiSekcja iloscSekcji`,
  przeliczenie `d8r2w0` / `d8r3w0`.
- Usunięcie pól tylko dla lipca (p4, d2*, d3*) ze sprawozdań za inne miesiące (miesiąc musi być znany).
- `p6a`: usunięcie dla obiektów całorocznych, usunięcie powtórzonych lub niepoprawnych miesięcy.
- `p3` uzupełnione zerem do 2 cyfr, usunięcie spacji z wartości liczbowych.

Niezgodności rachunkowe (np. R10-R35 albo R41 *d7w4r2 ≠ suma d8r2*) są tylko raportowane, bo poprawnej
wartości nie da się ustalić na podstawie pliku.

## Uwagi do interpretacji

- R13 (`d3r4 < d3r1 × 10`) i R19 (`d7w2 < d7w3 × 10`) są stosowane, gdy liczba pokoi jest > 0 lub obiekt
  jest typu hotelowego (p3 01-04). W przeciwnym razie obiekty bez pokoi (kempingi) zawsze nie przechodziłyby
  tych reguł.
- Pola `uwagi`, `ra11`, `pf2` oraz pola z `automatyczne="true"` dodawane przez sam portal (np. `RA_F`,
  `d8r2wr`) nie występują w wykazie pól instrukcji. Są pomijane lub pokazywane jako INFO.
- 14-cyfrowe `jsbad` złożone z poprawnego 9-cyfrowego REGON i `00000` jest akceptowane, bo tak wypełnia je
  sam portal.
- `PL_MONTHLY_XML.xsd` (format przyjazny) jest starszy niż wykaz pól na 2026 r. Nie ma elementów dla
  d7w5ar1/2 (platformy rezerwacyjne), d7aw* (uchodźcy) ani kategorii kempingów i pozostałych obiektów,
  a `PL_MONTHLY_XML.XSL` zawiera dla nich niepoprawne wzorce. Skrypt zgłasza to jako ostrzeżenia.
  Zalecany jest format podstawowy.

## Pliki

- `kt1_validator.py`: walidator.
- `kt1-validate.cmd`, `kt1-validate.sh`: skrypty uruchamiające.
- `schemas/`: `sprawozdanie.xsd` i `PL_MONTHLY_XML.xsd`, wyodrębnione z instrukcji.
- `samples/Sprawozdanie_KT1_testowe.xml`: oficjalny przykład z instrukcji (poprawny).
- `samples/Sprawozdanie_KT1_bledne.xml`: przykład z błędami (niezakodowany `&`, powtórzony kraj 826, kod
  `40`, brak MultiSekcja). Poprawka: `kt1-validate.cmd samples\Sprawozdanie_KT1_bledne.xml --fix`.
