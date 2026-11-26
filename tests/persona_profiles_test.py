"""Cast profiles stay distinct, family-friendly and visually consistent."""

import re

import cast


PROFILE_FIELDS = (
    "name", "title", "delivery", "catchphrase", "bio", "quirk", "vice", "secret",
)
FAMILY_TONE_LEAKS = (
    "bawdy",
    "bad habits in the cabins",
    "purring figures",
    "smouldering gaze",
    "riding crop",
)


def test_every_persona_has_a_complete_profile():
    assert len(cast.CHARACTERS) >= 44
    for cid, persona in cast.CHARACTERS.items():
        missing = [field for field in PROFILE_FIELDS if not str(persona.get(field) or "").strip()]
        assert not missing, f"{cid} is missing {', '.join(missing)}"
        assert set(persona["stats"]) == set(cast.STAT_KEYS), cid


def test_personas_have_distinct_names_hooks_deliveries_and_stat_shapes():
    for field in ("name", "catchphrase", "delivery"):
        values = [persona[field].casefold() for persona in cast.CHARACTERS.values()]
        assert len(values) == len(set(values)), f"duplicate persona {field}"

    shapes = [tuple(persona["stats"][key] for key in cast.STAT_KEYS)
              for persona in cast.CHARACTERS.values()]
    assert len(shapes) == len(set(shapes)), "two personas have the same four-stat silhouette"


def test_portrait_age_matches_profile_age():
    for cid, persona in cast.CHARACTERS.items():
        match = re.search(r"\(age (\d+)\)", persona["portrait_prompt"])
        assert match, f"{cid} portrait has no age"
        assert int(match.group(1)) == persona["age"], cid


def test_family_profiles_do_not_reintroduce_adult_fork_tone():
    for cid, persona in cast.CHARACTERS.items():
        text = " ".join(str(persona.get(field) or "")
                        for field in PROFILE_FIELDS + ("portrait_prompt",)).casefold()
        leaks = [phrase for phrase in FAMILY_TONE_LEAKS if phrase in text]
        assert not leaks, f"{cid} contains adult-fork wording: {', '.join(leaks)}"


def test_male_personas_do_not_describe_themselves_with_female_pronouns():
    for cid in cast.MEN:
        persona = cast.CHARACTERS[cid]
        text = f"{persona['quirk']} {persona['secret']}"
        assert not re.search(r"\b(?:she|her|hers|woman|women)\b", text, re.IGNORECASE), cid
