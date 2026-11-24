"""The Port Authority's tax-result pictures (23 Nov 2026): two wide 16:9 pictures of each tax lady, made for the
full-width result screen at her desk (web/customs.js revealHtml) and shown nowhere else.

    tax_good   she is delighted: the tax is paid, or she has bought your cargo
    tax_bad    she is furious: she has caught a lie

Each is filed under Personas > (her name) with that role, tagged "tax-result", in a pair: one NSFW (her own nude
look from persona_prompts_v2) and one clean (her own clean look), like every other picture pair. Her identity comes
from her Cast & Voices prompt, her wide setting and light from persona_prompts_v2, and the moment from SCENES below.

This module is the one source of those prompts. It is used by:
    tools/queue_tax_result_pictures.py   (Queue_TaxLady_Result_Pictures.bat: the first batch)
    media.admin_view                     (hands the prompts to Admin > Media Library, so the Recipe
                                          "Tax lady result pictures" paints the same pictures again)
"""
import persona_prompts_v2 as pp

ROLES = ("tax_good", "tax_bad")
ASPECT = "16:9"
TAG = "tax-result"

# The moment. An expression and a few props only, so it sits with any of her costumes; no costume words here.
SCENES = {
    "tax_good": "the moment she stamps the captain's papers and is delighted with him, a broad warm triumphant smile, "
                "eyes bright and fixed on the viewer, a freshly stamped clearance paper held up in one hand, a brass seal "
                "and a neat stack of silver dollars gleaming beside her, warm golden light",
    "tax_bad": "the moment she catches the captain in a lie and is furious, eyes blazing and fixed on the viewer, jaw set, "
               "lips pressed thin, one arm thrust out pointing straight at the viewer, the false manifest crushed in her "
               "other fist, a pried-open crate of contraband spilling across the floor beside her, hard low lamplight "
               "and deep red shadow",
}
# Where she sits in the wide frame: the result text is laid over the bottom of the picture in white.
FRAME = ("wide cinematic widescreen film still, her face and figure in the upper two-thirds of the frame, "
         "the bottom of the picture falling into soft dark shadow")

RECIPE = {"id": "taxlady_results", "name": "Tax lady result pictures: 1 clean + 1 NSFW each", "kind": "persona",
          "subjects": [], "roles": list(ROLES), "by": "role", "mode": "pairs", "clean": 1, "nsfw": 1, "count": 1,
          "mood": "", "pose": False, "tag": TAG}


def who():
    """The women who sit at a Port Authority desk: the ten port officers and the Registrar (Mrs. Marlowe)."""
    return [k for k in pp.LOOKS if (k.startswith("officer_") or k == "taxlady") and k in pp.MASTER
            and all(t in pp.LOOKS[k] for t in ("nude", "clean", "light"))]


def _tail(tier):
    return pp.MASTER_TAIL[tier].replace("epic cinematic wallpaper master shot", FRAME)


def build(key, result, tier="clean", saved=None):
    """One full prompt. result is tax_good or tax_bad; tier is a persona_prompts_v2 look (nude, topless, clean...).
    saved is her Cast & Voices portrait prompt, so an edited face carries over."""
    if result not in SCENES:
        raise ValueError("result must be tax_good or tax_bad")
    if tier not in pp.ALL_TIERS:
        raise ValueError("tier must be one of " + ", ".join(pp.ALL_TIERS))
    look = pp.LOOKS[key]
    ident = pp.identity_from_prompt(key, saved) if saved else None
    parts = ["An " + pp._who(look, tier, ident), look[tier], pp.MASTER[key], SCENES[result], look["light"]]
    return ", ".join(parts) + _tail(tier)


def all_prompts(characters=None, nsfw_tier="nude"):
    """{persona: {role: {"nsfw": prompt, "clean": prompt, "aspect": "16:9"}}} for Admin > Media Library."""
    chars = characters or {}
    out = {}
    for key in who():
        saved = (chars.get(key) or {}).get("portrait_prompt") or None
        out[key] = {r: {"nsfw": build(key, r, nsfw_tier, saved), "clean": build(key, r, "clean", saved),
                        "aspect": ASPECT} for r in ROLES}
    return out


def recipe():
    """The saved Recipe that tops these pictures up (subjects filled in)."""
    return dict(RECIPE, subjects=who())
