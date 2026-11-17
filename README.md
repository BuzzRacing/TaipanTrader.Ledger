# SeaTrader

A turn-based trading game for 1 to 8 players, set in the Far East of the 1860s and inspired by the classic Taipan. One PC runs the game; everyone plays in a web browser on their own device, and a harbor board can run on a big screen.

## Play

1. Double-click **Launch_SeaTrader.bat**. It starts the game server (a minimised window) and opens the player screen full screen. Alt+F4 closes the full-screen window.
2. Other players open the address shown on the join screen (for example `http://192.168.1.20:8765`) on a phone, tablet or laptop on the same network. The first time, Windows may ask whether to allow Python through the firewall; choose Allow on private networks.
3. For a second monitor or TV, double-click **Launch_HarborBoard.bat**.
4. The first player to join is the host, who picks the game length and starts the game.
5. To change anything about the game, double-click **Launch_Admin.bat** (see Admin below).

| File | What it does |
|---|---|
| `Launch_SeaTrader.bat` | Starts the server if needed and opens the player screen |
| `Launch_HarborBoard.bat` | Opens the big-screen harbor board |
| `Stop_SeaTrader.bat` | Saves and stops the server |
| `New_Game.bat` | Archives the current game and starts a fresh one |
| `Launch_Admin.bat` | Opens the Admin command center |

Needs Python 3.8 or newer. Nothing else to install: the server uses only the standard library.

The game saves after every turn to `saves/current.json` and resumes from it on the next launch. Players rejoin automatically on the device they joined with, or by entering the same name on another device.

## Admin

**Launch_Admin.bat** opens the command center at `http://localhost:8765/admin`. Nothing changes until you press **Save & apply**; then every open player screen and harbor board updates at once, mid-game included.

| Page | What you control |
|---|---|
| Live Game | The game in progress with nothing hidden: every house's silver, debt, fleet and cargo; every price in every port; weather and bans. Start, end the turn, finish, start a new game, restore an earlier one, post news, correct a player's money or position. |
| Brand | Game title, tagline, currency symbol, and the names of the moneylender, pirate lord, bank and winner's title. |
| Look & Style | Every colour, the four fonts (game title, name headers, general text, special text), the web fonts to download, text size, corner roundness, the eight house colours and your own CSS, with a live preview. |
| Graphics | Logo, tab icon, backgrounds, a painted chart to replace the drawn coastlines, and a picture for each cargo, port and ship. |
| Art Bible | The Historical private-release visual canon: 1860 China Seas art direction, palette, typography, adult nudity and kink rules, cultural and historical guardrails, exact asset specifications, AI Farm prompt builder, reusable recipes and an approval checklist. |
| Cast & Voices | The characters who read the game aloud: profile cards with portrait, Inworld voice, story and stats; auditions; who reads which line; the Inworld key. See Voices below. |
| Language & Text | Every line of wording. Reword English or add whole languages. |
| Ratings & Difficulty | Content rating (Historical private adult or Family-friendly sharing), difficulty levels, and the ranks players earn. Family-friendly also locks the Art Bible prompt studio to dressed, non-erotic direction; it does not replace artwork already uploaded under Graphics. |
| Game Setup, Economy, Cargo, Ports, Ships, Weather & Seas, Pirates & Customs | Every rule and number in the game, and the tables of cargoes, ports, ships and seas. |
| Backup & Access | Named presets, automatic backups of each save, export and import, reset, and the admin password. |

The Admin page needs no password on the computer running the game. Other devices cannot open it until you set a password under Backup & Access (or with `python server.py --admin-password WORD`); they then sign in at `http://<address>:8765/admin`.

Settings live in the `config` folder, uploaded images in `web/uploads`, games in `saves`, records in `journal`, spoken lines in `cache/voice`. Delete `config` to return to the defaults.

## Captain's Report

Everything that happens is written down, so any game can be reviewed afterwards and any problem traced. Open **Admin > Captain's Report**.

- **Live console.** The game in progress as it happens. Click a line for its full details.
- **Review a game.** Any recorded game, month by month, with filters by kind of event, player and text, and a "Problems only" switch.
- **Server log.** Start-ups, shutdowns, errors with full detail, sign-ins, voice requests and font downloads.
- **Records kept.** Every journal on disk, with Keep and Delete.

What is recorded for each game:

- Every player action, with the numbers behind it (a trade lists quantity, price each, dealer margin and the market price before and after), and every refused action with the reason.
- Every roll of the dice with its odds, for example "caught in a storm: chance 12%, rolled 71.6% - no", and every battle round by round.
- A snapshot at the start of every month: each house's silver, bank, debt, cargo, fleet, standing and net worth, and every price in every port.
- Every admin action with the value it replaced, and every Save & apply with each setting that changed.
- Players joining, connecting, dropping out and coming back, with the device and address.

Records are organised by game, with months inside. A game's journal is kept until you delete it; once there are more than 50, the oldest are removed, except the game in progress and any marked Keep. The server log is one file per day and is kept for 30 days. Both limits are under **Game Setup > Records**. Passwords, the Inworld key and seat tokens are never written.

**Replay check.** Each snapshot also holds the dice seed for the month, so a month can be played again exactly from the journal. "Replay check" on a month (or `python replay.py` in a terminal) does this and compares the result with what was recorded. After a change to the rules, a difference shows what the change would have done to that month.

The files are plain text in the `journal` folder: `journal/games/<game>/events.jsonl` (one event per line) and `journal/server/server-<date>.log`.

## Tally Book (player statistics)

Every player has a Tally Book: their numbers as charts, heat maps and records. Open it with **Tally** at the foot of the tab rail (also in the Ledger tab, the lobby and the end-of-game screen), or go to `http://<server>:8765/stats`. It opens in its own window, so the deck never loses its place, and like the deck it never scrolls: only the panel area scrolls on a small screen.

- **This voyage / Career.** One game month by month, or every recorded game you sat in (matched by player name). Pick an earlier game from the Game list, or tap one in Career.
- **Fortune & Trade.** Net worth with each new rank starred and shipwrecks marked; silver, bank and debt; profit by cargo; where the silver went (cargo, guns, repairs, ships, protection, interest, booty, losses); best and worst sales.
- **Routes & Ports.** Every voyage traced on the sea chart (thicker for routes sailed more, marks for storms, battles, seizures and wrecks) with **Replay** to sail the whole run again; profit by port; a port-by-month heat map of profit or standing.
- **Markets.** A price map of every cargo in every port against the average; one cargo's price in every port over time with your buys and sales on it; the **trade score**: each trade scored 0 to 100 by where its price sat among every price of that cargo you saw (100 is the cheapest buy or the dearest sale), plus what you paid the dealers and what your big orders cost by moving the market.
- **Perils & Rivals.** The race between every house, a bar race you can play, storms, battles, gunnery, booty, seizures, robberies and wrecks with what each cost, the battle log, and head to head.
- **Fair play.** While a game is running you see your own numbers, only the prices you actually saw, and rivals' net worth (already public on the standings). When the game ends every book opens: every price in every port and every rival's full breakdown. Without a seat in the game in progress, a name shows only that player's past games.
- **Nothing new is recorded.** It is all worked out from the Captain's Report journal (`stats.py`), so every game recorded since records began has stats. Every chart has a hover read-out and a table view.

## Voices

The game's lines are read aloud by a cast of ten characters through [Inworld](https://inworld.ai) text-to-speech: the first mate reads the captain's log, the bosun calls the battles and storms, Elder Brother Wu answers about loans, the comprador about trades, the crier reads the news on the harbor board, and so on.

- **The key.** The server uses the Base64 API key from the Inworld dashboard. If the `INWORLD_API_KEY` environment variable is set on this computer (as it is for GrumpyRobot and Sector Says What), nothing more is needed. Otherwise paste the key under Admin > Cast & Voices; it is saved in `config/voice_key.json`, which is never uploaded to GitHub. Player screens never see the key.
- **Cost.** A line is sent to Inworld only the first time a screen plays it, then kept in `cache/voice/` for good and replayed from there for free; nothing is pruned. `cache/voice/index.jsonl` lists what every clip says and who says it. Lines with amounts in them ("Bought 60 Rice for $951.") are spoken as a short version without the numbers ("Bought Rice."), so they sound the same every time and are paid for once; the screen still shows the full line. The spoken versions are in `cast.py` (`SAY`) and can be edited per line under Cast & Voices > Who reads what. Changing a voice or speed simply makes fresh lines; "Clear saved clips" on the Cast & Voices page moves them to `cache/voice_cleared/` rather than deleting them.
- **Each character** has a portrait, an Inworld voice (any system voice, or your own cloned and designed voices), speaking speed, a delivery note (followed by the full TTS-2 model only), and a made-up profile: story, catchphrase, quirk, weakness, secret and four stats. Each card also has a portrait prompt for your image generator, written to the Art Bible.
- **Who reads what.** Every line of the captain's log, news, confirmations and rule messages can be given to any character or kept silent.
- **On each device** a speaker button mutes the voices on that screen only. The full-screen launchers let the board and the host's screen play sound without a tap; other phones and tablets start speaking after the first tap.

## Moving to a Raspberry Pi

The server is plain Python with nothing to install, so the same folder runs on a Pi unchanged.

1. Copy the whole `SeaTrader` folder to the Pi, for example to `~/SeaTrader`. To carry on a game in progress, include the `saves` folder; leave it out to start fresh. Include `journal` to keep the records of earlier games. Your Admin settings (`config`) images (`web/uploads`) and fonts (`web/fonts`) come along with the folder.
2. On the Pi, run `bash pi/install.sh` from that folder. This installs a service that starts the game at boot and restarts it if it stops. It prints the Pi's address when it finishes.
3. On the Windows PC, create `server_address.txt` next to the launchers containing that address on one line, for example `192.168.1.50:8765`. The launchers then open the Pi's game instead of starting a local server. Delete the file to go back to running on the PC.

Players' devices join at the Pi's address. Anyone already in the game types the same name on the join screen to pick up their firm where they left it.

| On the Pi | Command |
|---|---|
| Run once in a terminal, no service | `./run.sh` |
| Follow the log | `journalctl -u seatrader -f` |
| Stop / start | `sudo systemctl stop seatrader` / `start` |
| Remove the service | `bash pi/uninstall.sh` |

With the game on a Pi, open the Admin page from any device at `http://<the Pi's address>:8765/admin` after setting a password on the Pi with `python3 server.py --admin-password WORD`. The host can also manage a game from the player screen: the Ledger tab has **End the month now** and **Host: start a new game**. `Stop_SeaTrader.bat` and `New_Game.bat` only act on a server running on the PC.

### Known limits

- Seats are claimed by name with no password: anyone can take over the firm of a player who is not connected. That suits a living-room game and makes switching devices easy, but it is not secure.
- The game is meant for a home network. Do not expose the port to the internet.

## How a turn works

One turn is one month. Everyone does their port business at the same time: trade, bank, repair, buy ships. Then each player picks a destination, or stays. When every connected player has given orders, the month passes: voyages resolve, interest accrues, markets move and the weather changes. The host can end a turn early; anyone who has not given orders, or has dropped off, stays at anchor.

## Rules in brief

- **Ports and cargo.** Nine ports and eight cargoes. Each port makes some things cheaply and pays well for others.
- **Shared market.** Buying pushes a price up and selling pushes it down, for everyone. You see live prices only where you are; your price book remembers what you last saw elsewhere.
- **Standing.** Trading in a port raises your standing there, which narrows the dealers' margin and lowers repair costs. Being caught with opium wrecks it.
- **Weather.** Each sea has a monthly forecast, right about four times in five. Typhoon season in the north runs June to October. Storms damage ships and can blow you off course.
- **Fleet.** Up to five ships that sail together and share one hold. Lose a ship and you lose whatever the rest cannot carry.
- **Pirates.** Give standing orders to fight or run before you sail. Guns win fights and booty; fast ships run better.
- **Li Yuen.** Pay his agent in Hong Kong and his fleets leave you alone, and sometimes drive off other pirates.
- **Money.** The bank in Hong Kong pays 0.5% a month and is safe from thieves. Elder Brother Wu lends at 6% a month, compounding.
- **Opium.** The most profitable cargo and the riskiest. Ports ban it from time to time: prices jump there, and so do seizures.
- **Gold.** Legal bullion: high value, steady prices, cheap in Nagasaki and dear in Calcutta. But when a port declares a ban it sometimes covers gold too (50% by default, *Cargo → Sometimes contraband* in Admin). While it does, gold sells for more there and customs will seize it. The market and price board flag gold as banned in those ports.
- **Winning.** When the game length runs out, the house with the highest net worth is Taipan.

## Project layout

| Path | Contents |
|---|---|
| `engine.py` | All game rules. No networking or file access, so it is easy to test. It holds no numbers of its own: everything comes from the settings. |
| `config.py` | Every setting and its default, the description the Admin page is drawn from, and the checks applied before anything is saved. Add a setting here and it appears in Admin. |
| `strings.py` | Every line of wording, in English. |
| `cast.py` | The default cast: profile cards, voices and who reads which line. |
| `voice.py` | Inworld voices: works out who reads a line, makes the audio on request, keeps it in `cache/voice/`. |
| `server.py` | Web server, live updates to every screen, saves, and the admin interface. |
| `journal.py` | The records: writes the game journal and the server log, reads them back for the Captain's Report, and prunes old ones. |
| `stats.py` | The Tally Book's numbers: works out a player's voyage and career from the journal, with the fair-play rules. Never writes anything. |
| `replay.py` | Plays a recorded month again from the journal and checks it comes out the same. `python replay.py --list` shows the recorded games. |
| `journal/` | Created on first run: one folder per game under `games/`, one server log per day under `server/`. Not uploaded to GitHub. |
| `web/` | Player screen (`index.html`, `player.js`), Tally Book (`stats.html`, `stats.js`, `stats.css`), harbor board (`board.html`, `board.js`), admin (`admin.html`, `admin.js`), chart and styles. |
| `fonts.py` | Downloads the Google Fonts named under Look & Style into `web/fonts/` once, in the background, so every screen gets them from the game with no internet. Run `python fonts.py` to fetch them by hand. |
| `web/fonts/` | The downloaded fonts. Copy it with the folder so a Pi without internet has them. |
| `config/` | Created on first save: `settings.json`, `lang/`, `presets/`, `backups/`. |
| `pi/`, `run.sh` | Raspberry Pi / Linux service installer and runner. |
| `tests/sim_test.py` | Plays 40 full games with bots and checks the rules never break. Run `python tests/sim_test.py`. |
| `tests/config_test.py` | Checks the settings, the wording, and that a game survives its ports, cargoes and ships being changed mid-game. |
| `tests/journal_test.py` | Plays recorded bot games through a restart, admin corrections and a settings change, then replays every month from the journal and checks each comes out exactly as recorded. |
| `tests/stats_test.py` | Plays recorded bot games and checks the Tally Book: the books balance, fair play holds while a game runs, everything opens when it ends, and the career adds up. |
| `tests/voice_test.py` | Checks the cast and the voice layer against a pretend Inworld, so it runs offline. |
