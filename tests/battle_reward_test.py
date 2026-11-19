"""Victory estimates use the actual encounter cargo without changing any combat rolls."""
import copy
import json

from battle_test import setup, new_game, sail, _win
from engine import Game, R


def test_reward_matches_victory_and_survives_reload():
    setup(battle__parley=False, pirates__gun_hit=1.0, pirates__hit=0.0)
    for seed in range(1, 21):
        game = new_game(seed=seed, names=("Ann",), guns=20, cargo={})
        player = game.s["players"]["p1"]
        player["ships"] = [game._new_ship("barque", guns=12)]
        sail(game, present=["p1"])
        state, dice = copy.deepcopy(game.s), game.rng.getstate()
        reward = game.battle_view(player)["reward"]
        assert game.battle_view(player)["reward"] == reward
        assert game.s == state and game.rng.getstate() == dice
        loaded = Game(state=json.loads(json.dumps(game.s)), seed=999)
        assert loaded.battle_view(loaded.s["players"]["p1"])["reward"] == reward
        _win(game, ["p1"])
        result = player["fights"][-1]
        assert result["prize_tier"] == reward["tier"]
        assert result["prize_worth"] == reward["cargo_worth"]
        assert result["prize_left"] == reward["cargo_left"]
        assert reward["silver_min"] <= result["booty"] <= reward["silver_max"]


def test_reward_full_hold_and_no_prize():
    setup(battle__parley=False)
    game = new_game(names=("Ann",), cargo={})
    player = game.s["players"]["p1"]
    player["cargo"] = {"rice": game.capacity(player)}
    sail(game, present=["p1"])
    reward = game.battle_view(player)["reward"]
    assert reward["cargo_worth"] == 0 and reward["cargo_left"] > 0
    assert reward["silver_max"] > 0
    R["battle"]["prize"] = False
    R["pirates"]["booty_min"] = R["pirates"]["booty_max"] = 0
    reward = game.battle_view(player)["reward"]
    assert reward == {"silver_min": 0, "silver_max": 0, "cargo_worth": 0,
                      "tier": "none", "cargo_left": 0}


def test_matched_reward_uses_original_fleet_value():
    setup(battle__parley=False)
    game = new_game(names=("Ann",), cargo={})
    player = game.s["players"]["p1"]
    sail(game, present=["p1"])
    battle = player["battle"]
    battle.update(worth_n=12.5, match={"match": 1.2})
    before = game.battle_view(player)["reward"]
    battle["hp"].pop()
    after = game.battle_view(player)["reward"]
    assert before == after, "Sinking a junk must not reduce the victory prize"
    assert before["silver_min"] == int(12.5 * R["pirates"]["booty_min"] * R["battle"]["match_booty"])


if __name__ == "__main__":
    test_reward_matches_victory_and_survives_reload()
    test_reward_full_hold_and_no_prize()
    test_matched_reward_uses_original_fleet_value()
    print("OK: battle reward estimates, reload, dice, capacity and empty prizes")
