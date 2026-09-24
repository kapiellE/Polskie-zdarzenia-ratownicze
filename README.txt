SERWER MULTIPLAYER 112
======================
W folderze sa 3 pliki: server.py, index.html, logo.png. Wszystkie wrzuc RAZEM do jednego folderu na hostingu.

1. Wgraj server.py, index.html i logo.png na hosting (ten sam folder).
2. Ustaw komende startowa:   python3 server.py
   (serwer sam bierze port ze zmiennej PORT lub SERVER_PORT; domyslnie 8080)
3. Otworz adres hostingu w przegladarce - to jest aplikacja. Ten sam adres daj innym.
4. Jako PIERWSZY zarejestruj nick kapiello z haslem XBGTfemboy. Inne haslo dla tego nicku jest odrzucane.

Nic nie trzeba instalowac (tylko Python 3.8+). Dane (konta, czat, wpisy) zapisuja sie w pliku data.json obok server.py - nie kasuj go.
Komendy admina na czacie: /ban nick   i   /unban nick
Przytrzymaj wiadomosc (0,7 s) jako kapiello = usuniecie.

Jesli strona ma zostac na GitHubie: w index.html zmien linie  const API="";  na  const API="https://TWOJ-SERWER";
