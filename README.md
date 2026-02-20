# NZscan - WiFi Scanner

<p align="center">
  <a href="https://github.com/NeleBiH/NZscan/releases">
    <img src="https://img.shields.io/github/v/release/NeleBiH/NZscan?color=00d4ff&style=flat" alt="Release"/>
  </a>
  <a href="https://github.com/NeleBiH/NZscan/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/NeleBiH/NZscan?color=7c3aed" alt="License"/>
  </a>
</p>

<p align="center">
  <a href="#english">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="#bosanski">🇧🇦 Bosanski / Hrvatski / Srpski</a>
</p>

---

## Screenshots

<p align="center">
  <img src="Screenshot/11.png" alt="Main window" width="700"/>
</p>

<p align="center">
  <img src="Screenshot/12.png" alt="Network Details" width="500"/>
</p>

---

<a name="english"></a>

## 🇬🇧 English

### Description

NZscan is an advanced WiFi scanner for Linux. It detects and monitors available WiFi networks in real time with a modern UI and support for multiple colour themes.

### Features

**WiFi Scanning**
- Lists all visible WiFi networks
- Per-network info: SSID, BSSID, signal strength (% and dBm), channel, frequency, band, security
- Real-time signal strength graph
- Auto-refresh with configurable interval
- Column sorting
- Search filter and band filter (2.4 / 5 GHz)

**User Interface**
- 4 colour themes: **Dark** (default), **Light**, **Nord**, **Dracula**
- System tray support — minimise instead of closing
- Network Details dialog with signal history graph

### Installation

**Requirements:** Python 3.10+, Linux, NetworkManager (`nmcli`)

**Automatic install (recommended)**
```bash
git clone https://github.com/NeleBiH/NZscan.git
cd NZscan
chmod +x setup.sh
./setup.sh
```
The script auto-detects your distro (apt / dnf / pacman / zypper / xbps) and installs all required packages.

**Manual install**
```bash
pip install -r requirements.txt
python main.py
```

### Usage

| Control | Description |
|---|---|
| 🔄 **Scan** | Trigger a manual scan |
| **Auto** | Toggle automatic refresh |
| **Settings** | Preferences (theme, interval, tray…) |
| **About** | App info and GitHub link |

- Double-click a row → Network Details with signal graph
- X button → minimises to system tray
- Right-click tray icon → context menu

### Configuration

Settings are stored in `config.json`:

| Key | Description |
|---|---|
| `theme` | UI theme (`Dark` / `Light` / `Nord` / `Dracula`) |
| `scan_interval` | Scan interval in seconds |
| `start_minimized` | Start minimised to tray |
| `show_signal_bars` | Show signal bars in table |
| `close_to_tray` | X button minimises instead of closing |
| `show_tray_notifications` | System tray notifications |

### Technologies

- **PySide6** — Qt framework for Python
- **NetworkManager (nmcli)** — WiFi scanning backend

### License

MIT License — see [LICENSE](LICENSE) for details.

### Contributing

Pull requests are welcome. For major changes please open an issue first.

---

<a name="bosanski"></a>

## 🇧🇦 Bosanski / Hrvatski / Srpski

### Opis

NZscan je napredni WiFi skener za Linux. Aplikacija omogućuje detekciju i praćenje dostupnih WiFi mreža u realnom vremenu sa modernim UI sučeljem i podrškom za više tema.

### Značajke

**WiFi Skeniranje**
- Prikaz svih dostupnih WiFi mreža
- Informacije o svakoj mreži: SSID, BSSID, signal (% i dBm), kanal, frekvencija, pojas, sigurnost
- Graf praćenja snage signala u realnom vremenu
- Auto-refresh s podesivim intervalom
- Sortiranje po koloni
- Filter po imenu i frekventnom pojasu (2.4 / 5 GHz)

**Korisničko Sučelje**
- 4 teme: **Dark** (zadano), **Light**, **Nord**, **Dracula**
- System tray podrška — minimiziranje umjesto zatvaranja
- Network Details dijalog s grafom signala

### Instalacija

**Preduvjeti:** Python 3.10+, Linux, NetworkManager (`nmcli`)

**Automatska instalacija (preporučeno)**
```bash
git clone https://github.com/NeleBiH/NZscan.git
cd NZscan
chmod +x setup.sh
./setup.sh
```
Skripta automatski detektira distro (apt / dnf / pacman / zypper / xbps) i instalira sve potrebne pakete.

**Ručna instalacija**
```bash
pip install -r requirements.txt
python main.py
```

### Korištenje

| Kontrola | Opis |
|---|---|
| 🔄 **Scan** | Ručno pokretanje skeniranja |
| **Auto** | Uključi / isključi automatsko osvježavanje |
| **Settings** | Postavke (tema, interval, tray…) |
| **About** | Informacije o aplikaciji |

- Dvoklik na red → Network Details s grafom signala
- X gumb → minimizira u system tray
- Desni klik na tray ikonu → izbornik

### Konfiguracija

Postavke se čuvaju u `config.json`:

| Ključ | Opis |
|---|---|
| `theme` | Tema sučelja (`Dark` / `Light` / `Nord` / `Dracula`) |
| `scan_interval` | Interval skeniranja u sekundama |
| `start_minimized` | Pokreni minimiziran u tray |
| `show_signal_bars` | Prikaži signal bars u tablici |
| `close_to_tray` | X gumb minimizira umjesto zatvaranja |
| `show_tray_notifications` | Tray notifikacije |
