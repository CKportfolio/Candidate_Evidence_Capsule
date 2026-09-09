# Candidate_Evidence_Capsule — generator strony wiedzy o kandydacie

[![CI](https://github.com/CKportfolio/Candidate_Evidence_Capsule/actions/workflows/ci.yml/badge.svg)](https://github.com/CKportfolio/Candidate_Evidence_Capsule/actions/workflows/ci.yml)

`story_mapper.py` buduje publiczną, maszynowo czytelną stronę wiedzy o kandydacie na podstawie kilku rodzajów materiałów źródłowych: narracji zawodowej, CV, dokumentacji projektów i dodatkowych historii projektowych.

Projekt wyrósł z prostego ograniczenia konwencjonalnych dokumentów rekrutacyjnych. Krótkie CV może przedstawić daty, role i technologie, ale ma niewiele miejsca na rozumowanie stojące za projektami: skąd wziął się problem, jak został rozłożony na części, co zmieniło się podczas implementacji oraz dlaczego dane rozwiązanie zostało uproszczone albo zatrzymane.

Generator zachowuje ten bogatszy kontekst w jednym uporządkowanym źródle, które można opublikować jako podstronę portfolio. Strona pozostaje czytelna dla człowieka, a jej stabilne identyfikatory, etykiety pochodzenia, indeks wyszukiwania i podsumowanie JSON ułatwiają nawigację oprogramowaniu oraz systemom AI.

## Zasady projektowe

### Wiedza, nie scenariusz rozmowy

Wygenerowana strona nie zawiera szablonów pytań rekrutera, dyrektyw dla modeli, narzuconej procedury oceny ani konkluzji dotyczącej zatrudnienia. Opisuje kandydata i mapuje dostarczone źródła, nie mówiąc czytelnikowi, jaką opinię ma sobie wyrobić.

### Jawne pochodzenie informacji

Każdy atom tekstu otrzymuje etykietę wskazującą jego pochodzenie:

- `STORY-CLAIM` — narracja kandydata albo dodatkowa historia;
- `CV-DECLARED` — informacja wyodrębniona z CV;
- `REPO-DOCUMENTED` — informacja zawarta w dokumentacji repozytorium stworzonej przez kandydata;
- `DERIVED-SIGNAL` — relacja albo uporządkowanie utworzone w wyniku analizy semantycznej/statystycznej;
- `INFERENCE` — interpretacja zbudowana na podstawie kilku punktów danych;
- `UNKNOWN` — dostarczone materiały nie pozwalają rozstrzygnąć danej kwestii.

Etykiety zachowują rozróżnienie między tym, co mówi źródło, a tym, co mogłoby zostać ustalone w niezależnym audycie kodu lub działania programu.

### Stabilne identyfikatory źródeł

Znane historie i repozytoria korzystają ze stałych przestrzeni nazw. Dodanie nowego pliku nie zmienia po cichu identyfikatorów źródeł, do których odwołuje się ręcznie opracowany indeks. Nieznane źródła otrzymują deterministyczne przestrzenie nazw wyprowadzone z ich nazw.

### Precyzja przed automatycznym zgadywaniem

Evidence Index wykorzystuje ręcznie sprawdzone identyfikatory atomów powiązane ze źródłami. Jeśli wskazany atom zniknie, generator pomija dany wpis zamiast po cichu zastępować go semantycznie podobnym fragmentem.

### Analiza semantyczna bez oceny semantycznej

Generator używa modelu `intfloat/multilingual-e5-small` do tworzenia znormalizowanych embeddingów. Służą one do:

- zrównoważonej reprezentacji narracji ze źródeł;
- wskazywania centralnych fragmentów historii;
- eksploracyjnego grupowania semantycznego;
- badania relacji między tematami narracji a dokumentacją projektów;
- diagnostyki wrażliwości typu leave-one-story-out.

Wyniki porządkują znaczenie wewnątrz dostarczonego korpusu. Nie są prawdopodobieństwami prawdy, ocenami kandydata ani poziomami kompetencji.

## Układ danych wejściowych

```text
story_mapper/
├── story_mapper.py
├── requirements.txt
├── input/
│   ├── LM_LONG.txt
│   ├── candidate_cv.pdf
│   ├── extra/
│   │   ├── historia pierwszych automatyzacji.txt
│   │   ├── ml bot history.txt
│   │   ├── program do wprowadzania zlecen.txt
│   │   ├── plyciarz history.txt
│   │   └── historia candidate capsule.txt
│   └── repo/
│       ├── BOT_EU/README.md
│       ├── Demand-Radar/README.md
│       ├── MAG-AS/README.md
│       ├── PiTcA/README.md
│       ├── StreszCzarka---Krypto-AI-news-serwis/README.md
│       ├── Zonda-Kalkulator-PITolenia-/README.md
│       ├── market-data-intelligence-lab/README.md
│       ├── web-3Dviever-glb/README.md
│       ├── wynajem_motorowek/README.md
│       └── Candidate_Evidence_Capsule/README.md
├── tests/
│   └── test_story_mapper.py
└── .github/
    └── workflows/ci.yml
```

`LM_LONG.txt` jest wymagany. Pliki PDF w głównym katalogu `input/` są traktowane jako źródła CV. Pliki Markdown i tekstowe w `input/extra` stają się źródłami narracyjnymi. Pliki Markdown i tekstowe w każdym katalogu `input/repo/<projekt>/` stają się źródłami dokumentacji projektu; README projektu jest wczytywany jako pierwszy.

Historia założycielska ma stabilną nazwę pliku:

```text
input/extra/historia candidate capsule.txt
```

Jej pełny tekst pojawia się w otwierającej sekcji wygenerowanej strony, a także jest rozbijany na atomy w Evidence Registry.

## Wymagania

- Python 3.10 lub nowszy;
- `numpy`;
- `pypdf`;
- `sentence-transformers`;
- `scikit-learn`.

Przykładowa konfiguracja środowiska:

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy pypdf sentence-transformers scikit-learn
```

Model embeddingowy jest pobierany przy pierwszym użyciu, dlatego pierwsze budowanie może potrwać dłużej niż kolejne.

## Budowanie

Uruchom generator z katalogu projektu:

```bash
python story_mapper.py
```

Wygenerowane artefakty trafiają do `output/`:

```text
output/
├── CEZARY_KRYCH.semantic.md
├── CEZARY_KRYCH.semantic.json
└── CEZARY_KRYCH.raw_sources.md
```

- `CEZARY_KRYCH.semantic.md` jest kompletnym źródłem publicznej strony wiedzy;
- `CEZARY_KRYCH.semantic.json` zawiera maszynowo czytelne podsumowanie;
- `CEZARY_KRYCH.raw_sources.md` jest materiałem pomocniczym budowania i zawiera nieprzetworzone dane narracyjne.

Źródło Markdown można zamienić w statyczną stronę portfolio za pomocą osobnego renderera `story_mapper_site.py`:

```bash
python story_mapper_site.py \
  --input output/CEZARY_KRYCH.semantic.md \
  --output candidate/index.html \
  --base-url https://example.com/candidate/
```

Publiczna domena nie jest celowo wpisana na stałe do generatora. Renderer jest utrzymywany osobno i nie jest częścią tego repozytorium.

## Testy i CI

Zestaw testów korzysta ze standardowego modułu `unittest` Pythona i nie pobiera modelu embeddingowego. W teście integracyjnym używany jest deterministyczny lokalny zamiennik, dzięki czemu cała ścieżka budowania jest sprawdzana bez zależności od zewnętrznej usługi modelowej.

Te same kontrole można uruchomić lokalnie:

```bash
python -m py_compile story_mapper.py
python -m unittest discover -s tests -v
```

GitHub Actions uruchamia te kontrole automatycznie przy każdym pushu do `main` oraz dla każdego pull requestu. Workflow instaluje również zadeklarowane zależności i uruchamia `pip check`.

## Struktura wygenerowanej strony

Wynik zawiera:

1. pochodzenie i ewolucję projektu;
2. słownik pochodzenia informacji i definicje warstw prawdy;
3. powiązany ze źródłami Evidence Index;
4. zwięzły Claim Graph;
5. karty projektów z bezpośrednimi linkami do repozytoriów GitHub;
6. relacje semantyczne i grupowania eksploracyjne;
7. kanoniczny Evidence Registry;
8. opis metodologii i maszynowo czytelne podsumowanie JSON.

Linki projektów prowadzą bezpośrednio do publicznych repozytoriów w [organizacji GitHub `CKportfolio`](https://github.com/orgs/CKportfolio/repositories).

## Czego projekt nie robi

Generator nie uruchamia kodu projektów, nie mierzy ich działania w czasie wykonywania, nie ustala niezależnie autorstwa i nie przeprowadza audytu bezpieczeństwa. README repozytoriów pozostają dokumentacją stworzoną przez kandydata. Wynik jest uporządkowanym źródłem portfolio, a nie niezależnym certyfikatem.

Pipeline semantyczny nie rozstrzyga również, czy kandydat powinien zostać zatrudniony, ani nie przypisuje mu poziomu inżynierskiego. Te oceny pozostają poza generatorem.

## Prywatność i publikacja

Wszystko umieszczone w `input/` może zostać odtworzone albo przedstawione w wygenerowanym wyniku. Przed zbudowaniem publicznej strony należy więc usunąć prywatne dane kontaktowe, dane uwierzytelniające, klucze API i poufne informacje klientów.

Sam generator może być publiczny, podczas gdy prywatne warianty źródeł pozostają poza repozytorium. Do demonstracji lepiej nadaje się czysty korpus przykładowy albo zestaw zredagowanych danych wejściowych.

## Ewolucja projektu

Wcześniejsze wersje eksperymentowały z dużymi promptami, zestawami pytań rekrutera, statycznymi kopiami repozytoriów i szczegółowymi procedurami awaryjnymi dla modeli, które nie potrafiły otwierać linków osadzonych w załącznikach. Testy przeprowadzone na kilku dostawcach AI pokazały, że dokładanie kolejnych instrukcji zwiększało złożoność bez niezawodnego wpływu na politykę dostępu do narzędzi.

Obecny projekt rozwiązuje ten problem na poziomie dostarczenia materiału. Baza wiedzy jest publikowana jako zwykła podstrona portfolio dostępna pod jednym bezpośrednim adresem, a kod projektów pozostaje w zwykłych, publicznych repozytoriach GitHub. Rezultat jest mniejszy, niezależny od dostawcy i celowo nie jest promptem.

## Status

To eksperymentalny projekt portfolio i architektury informacji, rozwijany przez kolejne implementacje, testy red-team, próby z różnymi dostawcami i upraszczanie. Jego głównym tematem nie jest automatyczne ocenianie kandydatów, lecz wierne uporządkowanie złożonej historii zawodowej. Oraz zmiany benchmarku do ktorego przyrównuje rekruter ze stażu i doświadczenia w IT, na umiejętnośc skutecznego szukania problemów poszczególnych ludzi do ich zautomatyzowania.
