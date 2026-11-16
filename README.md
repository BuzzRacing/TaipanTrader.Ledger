# SeaTrader

A turn-based trading game for 1 to 8 players, set in the Far East of the 1860s and inspired by the classic Taipan. One PC runs the game; everyone plays in a web browser on their own device, and a harbor board can run on a big screen.

## Play

1. Double-click **Launch_SeaTrader.bat**. It starts the game server (a minimised window) and opens the player screen full screen. Alt+F4 closes the full-screen window.
2. Other players open the address shown on the join screen (for example `http://192.168.1.20:8765`) on a phone, tablet or laptop on the same network. The first time, Windows may ask whether to allow Python through the firewall; choose Allow on private networks.
3. For a second monitor or TV, double-click **Launch_HarborBoard.bat**.
4. The first player to join is the host, who picks the game length and starts the game.

| File | What it does |
|---|---|
| `Launch_SeaTrader.bat` | Starts the server if needed and opens the player screen |
| `Launch_HarborBoard.bat` | Opens the big-screen harbor board |
| `Stop_SeaTrader.bat` | Saves and stops the server |
| `New_Game.bat` | Archives the current game and starts a fresh one |

Needs Python 3.8 or newer. Nothing else to install: the server uses only the standard library.

The game saves after every turn to `saves/current.json` and resumes from it on the next launch. Players rejoin automatically on the device they joined with, or by entering the same name on another device.

## Moving to a Raspberry Pi

The server is plain Python with nothing to install, so the same folder runs on a Pi unchanged.

1. Copy the whole `SeaTrader` folder to the Pi, for example to `~/SeaTrader`. To carry on a game in progress, include the `saves` folder; leave it out to start fresh.
2. On the Pi, run `bash pi/install.sh` from that folder. This installs a service that starts the game at boot and restarts it if it stops. It prints the Pi's address when it finishes.
3. On the Windows PC, create `server_address.txt` next to the launchers containing that address on one line, for example `192.168.1.50:8765`. The launchers then open the Pi's game instead of starting a local server. Delete the file to go back to running on the PC.

Players' devices join at the Pi's address. Anyone already in the game types the same name on the join screen to pick up their firm where they left it.

| On the Pi | Command |
|---|---|
| Run once in a terminal, no service | `./run.sh` |
| Follow the log | `journalctl -u seatrader -f` |
| Stop / start | `sudo systemctl stop seatrader` / `start` |
| Remove the service | `bash pi/uninstall.sh` |

With the game on a Pi, the host manages it from the player screen: the Ledger tab has **End the month now** and **Host: start a new game**. `Stop_SeaTrader.bat` and `New_Game.bat` only act on a server running on the PC.

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
- **Winning.** When the game length runs out, the house with the highest net worth is Taipan.

## Project layout

| Path | Contents |
|---|---|
| `engine.py` | All game rules. No networking or file access, so it is easy to test and tune. The tables at the top (goods, ports, ships, rates) are the balance knobs. |
| `server.py` | Web server, live updates to every screen, saves. |
| `web/` | Player screen (`index.html`, `player.js`), harbor board (`board.html`, `board.js`), chart and styles. |
| `pi/`, `run.sh` | Raspberry Pi / Linux service installer and runner. |
| `tests/sim_test.py` | Plays 40 full games with bots and checks the rules never break. Run `python tests/sim_test.py`. |
