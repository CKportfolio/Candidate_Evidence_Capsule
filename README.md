Candidate Evidence Capsule

AI-czytelna warstwa portfolio, która pozwala modelowi językowemu analizować kandydaturę na podstawie uporządkowanych historii, opisów projektów, ograniczeń i odsyłaczy do kodu.

To repozytorium nie zawiera generatora story_mapper.py. Jego głównym artefaktem jest prompt, który przenosi aktualną kapsułę z pliku Markdown do istniejącej strony HTML, nie przebudowując jej warstwy przeznaczonej dla człowieka.

W skrócie

Candidate Evidence Capsule jest czymś pomiędzy rozszerzonym CV, indeksem dowodów i maszynowo czytelną dokumentacją portfolio. Rekruter może wkleić adres opublikowanej strony do chata AI z dostępem do internetu i zapytać na przykład:

które projekty najlepiej pokazują sposób myślenia kandydata;

co wynika z kodu i dokumentacji, a co pozostaje deklaracją autora;

jakie problemy kandydat rozwiązywał i dlaczego wybierał określone rozwiązania;

jakie są ograniczenia, niedokończone elementy i obszary wymagające dalszej weryfikacji.

Kapsuła nie wydaje werdyktu rekrutacyjnego. Dostarcza modelowi lepiej uporządkowany materiał do samodzielnej analizy.

Skąd wziął się ten pomysł

Autor zetknął się z prostym problemem: klasyczne CV nie dawało mu wystarczającego pola, aby pokazać sposób rozpoznawania problemów, dochodzenia do rozwiązań i budowania narzędzi z pomocą AI. Skoro takiego pola nie było, stworzył je sam — opracował własny format autoprezentacji przeznaczony jednocześnie dla człowieka i modelu językowego.

Nie był to format odtworzony z przeczytanego opisu ani gotowego poradnika. Powstał jako autorska koncepcja rozwijana z AI asystującym w analizie, redakcji i implementacji.

Technicznym punktem wyjścia były doświadczenia zdobyte podczas projektowania systemu filtracji treści dla znajdującej się w portfolio StreszCzarki. Mechanizm ten ostatecznie nie wszedł do finalnej wersji programu, ale pozostała po nim wiedza o wektoryzacji tekstu, embeddingach i semantycznym porządkowaniu treści. Ta wiedza została później wykorzystana przy budowie źródłowej kapsuły kandydata.

Czym kapsuła jest — a czym nie jest

Kapsuła jest statyczną warstwą wiedzy osadzoną w stronie portfolio. Zawiera wybrane informacje, które pomagają modelowi odnaleźć i połączyć:

tło zawodowe autora;

historię powstawania projektów;

problem, rozwiązanie, użyty stack i status każdego projektu;

znane ograniczenia i świadome punkty zatrzymania;

bezpośrednie linki do repozytoriów;

identyfikatory commitów lub inne dane pozwalające wskazać analizowany stan repozytorium, jeżeli są dostępne.

Kapsuła nie jest:

chatbotem ani osobnym modelem AI;

automatycznym systemem oceny kandydatów;

niezależnym audytem kodu, bezpieczeństwa lub autorstwa;

dowodem, że prototyp jest systemem produkcyjnym;

gwarancją, że każdy chat potrafi otworzyć wskazany adres — model musi mieć dostęp do internetu lub otrzymać plik HTML bezpośrednio.

Określenie „gadające CV” jest skrótem myślowym: odpowiada model językowy, natomiast kapsuła dostarcza mu materiał.

Obecny pipeline

Proces ma dwa wyraźnie rozdzielone etapy:

historie + CV + dokumentacja projektów
                    │
                    ▼
          story_mapper.py
       (poza tym repozytorium)
                    │
                    ▼
      CEZARY_KRYCH.semantic.md
                    │
                    ├──────────────┐
                    │              │
                    ▼              ▼
PROMPT_CAPSULE_REPLACEMENT.md   aktualny index.html
                    │              │
                    └──────┬───────┘
                           ▼
                   chat / model AI
                           │
                           ▼
             index.html z nową kapsułą
                           │
                           ▼
                       publikacja

Etap 1: zbudowanie źródła semantycznego

story_mapper.py jest uruchamiany w osobnym projekcie roboczym:

python story_mapper.py

Wynikiem potrzebnym w następnym etapie jest:

CEZARY_KRYCH.semantic.md

Plik zawiera rozbudowany materiał źródłowy: atomy informacji wyprowadzone z historii kandydata, CV i dokumentacji repozytoriów oraz relacje pomagające odnaleźć właściwy kontekst.

Sam generator, jego zależności, dane wejściowe i testy nie należą do tego repozytorium.

Etap 2: osadzenie kapsuły w istniejącej stronie

Do chata obsługującego załączniki przekazywane są trzy elementy:

treść PROMPT_CAPSULE_REPLACEMENT.md;

nowy CEZARY_KRYCH.semantic.md;

aktualny index.html opublikowanej strony.

Model wykorzystuje plik semantyczny jako aktualne źródło treści, dopasowuje z niego kapsułę do istniejącego dokumentu i zwraca kompletny, zaktualizowany index.html.

Kontrakt podmiany

Prompt pełni rolę specyfikacji transformacji, a nie generatora całej witryny od zera. Jego zadaniem jest:

odnalezienie kontenera kapsuły w obecnym HTML;

zachowanie wyglądu, CSS, skryptów, nawigacji i ludzkiej części portfolio;

zbudowanie użytecznej, skróconej reprezentacji aktualnego pliku semantycznego;

zachowanie informacji nadal potwierdzonych przez nowe źródło;

dodanie nowych, użytecznych atomów, których nie było w poprzedniej kapsule;

usunięcie lub zastąpienie treści starej kapsuły, jeżeli stała się nieaktualna albo nie ma już oparcia w nowym materiale;

zachowanie bezpośrednich linków do źródeł i uczciwych opisów ograniczeń;

zwrócenie jednego gotowego pliku index.html.

Nie jest to operacja „dopisz nowy Markdown do strony”. Model wykonuje selekcję i redakcję: z szerokiej bazy wiedzy tworzy krótszą warstwę odpowiednią do odczytu z publicznej strony.

Rozdzielenie odpowiedzialności

Element

Odpowiedzialność

story_mapper.py

Buduje pełne źródło semantyczne z materiałów wejściowych.

CEZARY_KRYCH.semantic.md

Jest aktualnym źródłem treści i kontekstu.

PROMPT_CAPSULE_REPLACEMENT.md

Określa zasady wyboru treści oraz bezpiecznej podmiany kapsuły.

index.html

Jest szablonem i właścicielem wyglądu, układu oraz ludzkiej warstwy portfolio.

Model AI

Działa jako semantyczny redaktor i renderer między Markdownem a istniejącym HTML-em.

Człowiek

Sprawdza diff, prawdziwość treści i końcowy wygląd przed publikacją.

Taki podział celowo oddziela bazę wiedzy od prezentacji. Zmiana treści kapsuły nie wymaga projektowania strony od początku, a zmiana wyglądu strony nie wymaga przebudowy źródłowej analizy semantycznej.

Jak użyć repozytorium

Wygeneruj aktualny CEZARY_KRYCH.semantic.md w projekcie zawierającym story_mapper.py.

Pobierz aktualny index.html z wdrożonej strony lub lokalnego źródła.

Otwórz chat, który przyjmuje duże pliki tekstowe i potrafi zwrócić kompletny HTML.

Wklej treść PROMPT_CAPSULE_REPLACEMENT.md.

Dołącz CEZARY_KRYCH.semantic.md i index.html.

Zapisz zwrócony plik jako nowy index.html.

Przejrzyj zmiany i dopiero potem opublikuj stronę.

Kontrola przed publikacją

Ponieważ ostatni etap wykonuje model generatywny, wynik wymaga kontroli człowieka. Należy sprawdzić:

czy zmieniła się wyłącznie kapsuła i elementy bezpośrednio potrzebne do jej obsługi;

czy sekcja portfolio dla człowieka, CSS i JavaScript pozostały nienaruszone;

czy wszystkie linki i kotwice działają;

czy nazwy projektów, adresy repozytoriów i identyfikatory commitów są poprawne;

czy żaden tekst nie został przypadkowo urwany lub przypisany do niewłaściwego pola;

czy stare, niepotwierdzone informacje nie zostały zachowane;

czy opisy prototypów i ograniczeń nie sugerują większej dojrzałości niż pokazują źródła;

czy do publicznej strony nie trafiły dane prywatne, klucze, tokeny ani informacje klientów.

Do porównania plików można użyć:

git diff --no-index index.previous.html index.html

Dlaczego w procesie pozostaje AI

Klasyczny renderer może deterministycznie zamienić Markdown na HTML, ale nie rozstrzyga dobrze, które nowe informacje są przydatne w publicznej kapsule, jak skrócić je bez zgubienia sensu ani jak dopasować je do istniejącej narracji strony.

W tym projekcie AI pełni rolę warstwy adaptacyjnej. Zaletą jest możliwość aktualizacji kapsuły bez utrzymywania rozbudowanego renderera. Kosztem jest mniejsza powtarzalność: dwa uruchomienia mogą dać nieco inny tekst, dlatego prompt ustanawia granice, a człowiek zatwierdza wynik.

Model zaufania

Kapsuła porządkuje informacje dostarczone przez autora. Bezpośrednie linki do repozytoriów i wskazanie konkretnego commita ułatwiają niezależne sprawdzenie części twierdzeń, ale sama obecność informacji w kapsule nie czyni jej zewnętrznie potwierdzonym faktem.

W interpretacji należy rozróżniać:

deklarację autora;

opis w dokumentacji projektu;

artefakt widoczny w repozytorium;

zachowanie potwierdzone przez uruchomienie programu;

ocenę lub wniosek osoby analizującej materiał.

Przykład

Portfolio z osadzoną Candidate Evidence Capsule

Na przykładowej stronie kapsuła jest zwykłą treścią HTML dostępną bez uruchamiania aplikacji. Model z dostępem do internetu może odczytać ją z tego samego dokumentu co warstwę portfolio przeznaczoną dla człowieka.

Ograniczenia obecnego podejścia

Transformacja wykonywana przez model nie jest w pełni deterministyczna.

Proces zawiera ręczny krok przenoszenia plików do chata i odbierania wyniku.

Bardzo duży plik semantyczny może przekroczyć limit kontekstu wybranego narzędzia.

Dostęp modelu do opublikowanej strony zależy od możliwości i polityki konkretnego dostawcy.

Liczba plików, testów lub workflow w repozytorium jest tylko sygnałem strukturalnym; nie zastępuje przeglądu kodu ani uruchomienia testów.

Publiczna kapsuła jest selekcją pełnej bazy wiedzy, a nie jej kopią jeden do jednego.

Status

Projekt eksperymentalny, rozwijany w praktyce podczas budowania portfolio i testowania sposobów przekazywania złożonego kontekstu kandydatury modelom językowym. Jego celem nie jest automatyczne udowodnienie poziomu inżynierskiego, lecz stworzenie lepszego pola do rozmowy o sposobie myślenia, wykonanych projektach i granicach dostępnych dowodów.
