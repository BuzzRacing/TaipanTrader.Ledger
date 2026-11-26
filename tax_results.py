"""Wide, fully dressed portraits for Port Authority results."""
import persona_prompts_v2 as pp

ROLES = ("tax_good", "tax_bad")
SCENES = {
    "tax_good": "the officer holds up freshly stamped clearance papers with a triumphant smile, "
                "a brass seal and a neat stack of silver dollars on the desk",
    "tax_bad": "the officer points firmly at a false manifest, jaw set, "
               "an opened crate of contraband beside the desk, hard low lamplight",
}
FRAME = "face and figure in the upper two-thirds of the frame, soft dark shadows below for captions"


def all_prompts(characters=None):
    chars = characters or {}
    return {
        cid: {role: {"clean": pp.build_master(cid, mood=f"{scene}, {FRAME}",
                                             saved=chars.get(cid, {}).get("portrait_prompt")),
                     "aspect": "16:9"}
              for role, scene in SCENES.items()}
        for cid in pp.MASTER if cid.startswith("officer_") or cid == "taxlady"
    }
