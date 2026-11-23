# Captain's Command Center — feed schemas

**Project:** Crimson Ledger / SeaTrader
**Written:** 22 November 2026 (Phase 2)
**Endpoint:** `GET /api/dashboard`
**Built by:** `dashboard_feed.py` (history, context) and `dashboard_suites.py` (everything below "Suites")

Every section is built while the server holds the game, in one pass. The private suites are cut from a copy of
the game taken once at the start of that pass.

## Visibility

| Level | When | What goes out |
|---|---|---|
| public | rivals at the table, game in play | history, `context` without `captain`, `weather` |
| open, several houses | the game has ended | the above plus prices, deals, lane profit |
| open, one house | a solo game past the lobby | everything, including the six private suites |

A private suite is never sent empty or masked. With rivals at the table its key is absent, and the page shows
the Sealed stamp because the key is missing.

## context (public; `captain` solo only)

| Field | Meaning | Source |
|---|---|---|
| `date`, `turn`, `phase` | this month | game state |
| `months_total`, `months_left` | length of the game and what is left | `years * 12`, `turn` |
| `seas` | forecast level 0–3 for each sea | `s.weather` |
| `worst_sea` | `{region, level}` | from `seas` |
| `forecast_accuracy` | how often a forecast holds | `rules.weather` |
| `houses` | number of houses | game state |
| `captain.port`, `dest`, `at_sea` | where the fleet is and is bound | player |
| `captain.worth`, `worth_change` | net worth; change since the last month closed | `Game.worth`, journal |
| `captain.rank` | commissioned rank | `commissioned_rank` |
| `captain.fleet` | `{ships, crippled, hull}`; hull is the average share of full hull | player ships |

## Suites

### weather (public)

| Field | Meaning |
|---|---|
| `seas[region].level` | this month's forecast, 0 Calm to 3 Typhoon |
| `seas[region].harbours` | the ports on that sea |
| `forecast_accuracy` | chance the sea comes as forecast |
| `storm_chance[level]` | the rules' base storm chance at each level, difficulty applied |

`history` (public), from the journal:

| Field | Meaning |
|---|---|
| `storms[]` | every storm that landed, newest first, the newest 24: `turn`, `date`, `pid`, `band`, `typhoon`, `ships` hit, `damage` in hull points, `worst` hull left, `offcourse` (port blown to, or null) |
| `storms[].cargo`, `guns` | units overboard and guns lost; sent at the open level only |
| `totals` | `voyages`, `storms`, `typhoons`, `offcourse`, `wrecks` for the whole game |
| `seas[region]` | `months` forecast and `held`, the months the sea came exactly as forecast |

### routes (private)

One row for every port other than the one the fleet is in.

| Field | Meaning | Rule |
|---|---|---|
| `dest`, `distance` | where and how far | `engine.distance` |
| `risk` | distance factor | `distance / risk_div`, kept within `risk_min`–`risk_max` |
| `level` | forecast used | the worse of the two seas |
| `storm` | chance of a storm on the forecast | `storm_chance[level] * min(risk, 1.4) * difficulty` |
| `pirates` | chance of a pirate attack | `chance * risk * difficulty * allure * flag_deter` |
| `lord` | chance the pirate queen finds the fleet | 0 while protected; else `chance * risk * difficulty * flag_deter * lord_pull` |
| `banned` | cargoes banned at the destination | `Game.banned` |

`inputs` carries what went into them: `allure`, `flag_deter`, `lord_pull`, `protect` (months), `protect_save`,
`offcourse`, `hull`, `cargo_cost` (what the cargo aboard cost), `forecast_accuracy`.

These are odds on the forecast. If the sea comes different, the storm chance is the one for the sea that came.
After a storm lands, cargo is lost and the fleet is found less often, so the pirate odds then fall. No field
says a route is safe. `tests/dashboard_suites_test.py` sails real voyages and checks these against the game's
recorded dice.

### atlas (private)

`ports[port]`:

| Field | Meaning | Source |
|---|---|---|
| `here`, `home` | where the fleet is; the house's home port | player |
| `services` | bank, lender, warehouse, shipyard this house can use there | `port_has` |
| `rep`, `band` | standing 0–100 and its band 0 Hostile to 4 Favoured | `p.rep`, `band_here` |
| `effects` | what that band does: audit, margin, yard, match, tax_cut, avoid | `band_effects` |
| `tax.base`, `tax.mine` | the port's rate and the rate this house pays | `tax_rate`, `tax_rate_for` |
| `tax.home_free`, `tax.share_cut` | why the two differ | `home_free`, `share_cut` |
| `shares` | `{mine, total, left, patron, patron_me}` | share book, `patron_of` |
| `warehouse` | `{goods, cap, used, rent, empty, home}` or null | `_store_view`, `warehouse_rents` |
| `commissions` | ids of active commissions that end here | `contracts_view` |
| `crackdown`, `banned` | a ban is on; which cargoes | game state |

Top level: `shares` `{earned, placed, free, cap, value}`, `tax_holiday` (months), `standing_on`.

### trade (private)

| Field | Meaning |
|---|---|
| `port`, `cargo`, `capacity`, `used` | the hold where the fleet is |
| `basis` | average paid per unit for each cargo held |
| `stored` | units ashore by cargo, all warehouses together (never counted as cargo aboard) |
| `rot` | perishables aboard and their age |
| `spread`, `purse` | the dealers' margin and purse in this port |
| `known`, `tips`, `hot_tips` | prices remembered, the Registrar's prices, live hot tips |
| `lot` | a private lot on offer, if any |
| `opportunities` | up to 8 rows `{good, buy, buy_price, sell, sell_price, gap, pct}` |

An opportunity is the widest gap between two ports' posted prices for one cargo, legal at both ends. It leaves
out the dealers' margin, tax, the price moving as the cargo sells, and the voyage. It is never called a profit.
Prices for every port are in the existing `ports` block.

### fleet (private)

`ships` and `laid_up` are the Player screen's own rows (type, name, hull, guns, cannons, hold, value, repair,
wage, crippled). Also `capacity`, `used`, `guns`, `cannons`, `hull`, `classes`, `ledger` (the Fleet tab's cost
ledger), `protect`, `protect_cost`, `wrecks`, and the newest 12 `fights`.

### treasury (private)

| Field | Meaning | Source |
|---|---|---|
| `worth` | net worth | `Game.worth` |
| `parts` | cash, bank, debt (negative), fleet, laid_up, shares, estate, cargo; they sum to `worth` | the terms of `Game.worth` |
| `books` | last statement, this month, year, game (money only, no log lines) | `books_view` |
| `bank.slices` | `{to, rate, amount, interest}` per slice; `rate` includes the great house's bonus | `bank_tiers`, `house_bank_bonus` |
| `bank.interest` | this month's interest on today's deposit | `bank_interest` |
| `debt` | debt, rate, next interest, loan room, the collectors' clock, bankruptcy clock, cap | engine debt helpers |
| `estate` | the great house as the Player screen has it | `estate_view` |
| `costs.wages`, `classes`, `laid` | the month's wage bill and what each class costs | `upkeep`, `fleet_ledger` |
| `costs.rents`, `rent` | rent by warehouse and in all | `warehouse_rents` |
| `costs.yearly`, `december_in` | December's bills and months until them | `yearly_upkeep` |
| `costs.protect` | months of protection left and what renewing costs | player |
| `next_month` | `{costs, bank_interest, loan_interest, net}` | the fields above |

`next_month` holds only what the rules already fix. Trade, weather, fights and events are not in it. The test
suite closes a month at anchor and checks the bank paid, and the books charged, what this block named.

### career (private)

`rank`, `rank_id`, `next_rank` (with the worth it needs), `qualified_rank`, `worth`, `fame`, `home`, `captain`,
`shares` `{earned, placed, free, cap, by_port, patron_of}`, `commissions` (active and on offer, as the Player
screen has them), `legends`, `promotions` (count).

## Size and cost

On the fixtures with default rules: lobby 4.1 KB, early 21.7 KB, middle 35.6 KB, late (month 200) 67.3 KB,
rivals 10.1 KB. Budget 100 KB. A late-game build takes about 4 ms.
