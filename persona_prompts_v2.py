"""Crimson Ledger persona prompts, v2 (proposal, 21 Nov 2026). NOT wired in yet: cast.py is untouched.

Why this exists (full audit: project doc "SeaTrader Persona Prompt Audit"):
  * The shared style tail was 67 words on every persona, about 53% of every prompt, identical for all 23.
    That tail, not the faces, is why everyone converges on the same lacquer-black / oxblood / brass picture.
  * The renderer is Qwen-Image 2.1 at CFG 1.0, where the negative prompt does nothing, and the tail's "no text",
    "no explicit sex act or coercion", "no nudity" clauses sit in the POSITIVE prompt, which can plant the very
    idea they forbid. This module states only what we want.
  * Each persona gets her own light, her own costume ladder (sultry -> boudoir -> topless) and her own
    motion line, so stills and the Wan 2.2 loops come from the same source.

Every prompt keeps the adult anchor "{adult} ... (age N)". Costume-level kink only (leather, laces, gloves,
crops, cords, chokers), always with her in command. Nothing below asks for sex acts, genitals or coercion.

Usage (dry run, prints every prompt with its word count):
    python persona_prompts_v2.py
    python persona_prompts_v2.py --tier topless --who bookkeeper,officer_batavia
    python persona_prompts_v2.py --master --tier boudoir            (wide 16:9 wallpaper master shots)
In code:
    import persona_prompts_v2 as pp
    pp.build("bookkeeper", "boudoir", mood="ledger_sly")      # a full prompt string
    pp.motion("bookkeeper")                                   # the Wan 2.2 movement line
"""
import argparse
import sys

ADULT = "unmistakably adult"

# The tail starts with ", romanticized" on purpose: tools/queue_persona_pairs.py split() looks for it.
TAIL = {
    "sultry": ", romanticized 1860 China Seas glamour photograph, sultry editorial styling, natural skin with a soft "
              "sheen, confident direct gaze, hands in frame, 3:4 portrait",
    "boudoir": ", romanticized 1860 China Seas glamour photograph, intimate boudoir styling with clever cover, "
               "natural skin with a soft sheen, confident direct gaze, hands in frame, 3:4 portrait",
    "topless": ", romanticized 1860 China Seas glamour photograph, bold magazine-centerfold styling, tasteful and "
               "playful, natural skin with a soft sheen, confident direct gaze, hands in frame, 3:4 portrait",
}
TIERS = tuple(TAIL)

# Short mood lines for the queue tool (add to MOODS there). Each is an expression, not a costume.
SPICE_MOODS = {
    "teasing": "a teasing sidelong look, one finger hooked in her own collar as if deciding whether to say yes",
    "caught_looking": "lips parted in mock surprise, as if she has just caught the viewer looking and is not sorry",
    "after_hours": "unguarded and glowing, hair down, a glass in her hand, the office closed for the night",
    "dare": "chin lifted, one eyebrow raised, a dare written all over her smile",
    "wink": "a slow wink and a half-smile, leaning in as though you are the only person in the room",
    "triumph": "head thrown back in a delighted laugh, flushed with winning",
    "pout": "a mock pout, arms crossed under her bust, pretending to be cross with you",
    "purr": "heavy-lidded and satisfied, chin on her hand, purring over a secret she will share for a price",
}

# who:      identity and setting, the one thing that must not change between pictures.
# sultry / boudoir / topless: her costume ladder. Boudoir keeps clever cover (props, hair, hands, fabric).
# light:    her own light and photographic mood, so no two women look lit by the same lamp.
# motion:   what moves in a Wan 2.2 loop (movement only; the look comes from the picture).
LOOKS = {
    "narrator": dict(
        who="{adult} Parsi woman (age 41), the pirate first mate on a schooner quarterdeck in Hong Kong harbour at dusk, black logbook under one arm, brass chronometer in her hand",
        sultry="lacquer-black frock coat open over an ivory angrakha-cut corset, oxblood sash",
        boudoir="frock coat slipping off both shoulders, corset laced loose, ivory stockings above her boots, logbook held across her chest",
        topless="bare-breasted under the open frock coat, oxblood sash low on her hips, logbook and chronometer her only cover",
        light="low gold dusk light, warm soft focus, fine film grain",
        motion="coat tails and loose strands of hair stirring in the sea breeze, chronometer chain swinging, a slow knowing blink"),
    "bosun": dict(
        who="{adult} Irish woman (age 34), voluptuous pirate bosun and master gunner beside a smoking brass cannon, red hair whipping loose, powder smudges on her skin, coil of slow match in one hand, fierce laughing grin",
        sultry="tobacco-leather waistcoat over a deeply unlaced linen shirt, oxblood sash, leather gun belt",
        boudoir="waistcoat hanging open, shirt knotted under her bust, leather straps crossed over her hips, a stray lock of red hair across her chest",
        topless="bare-breasted in an open leather waistcoat, powder-streaked, gun belt slung low on her hips, grinning like she dares you to say something",
        light="hard orange gun-flash from one side, smoke haze, high contrast",
        motion="smoke curling off the cannon, hair whipping in the wind, the slow match glowing and swinging"),
    "lender": dict(
        who="{adult} Cantonese woman (age 63), the silver-haired Silver Queen of Hong Kong behind a rosewood desk in a lamplit counting house, abacus, silver dollars and ledgers before her, a faint seductive smile",
        sultry="dark Qing-era silk jacket with a plunging crossed neckline and imperial-jade fastenings, silk garters glimpsed at an ankle",
        boudoir="silk jacket slipped off one shoulder, a sheer chemise beneath, jade-handled fan lowered just so, bare shoulders glowing",
        topless="jacket open and fallen from both shoulders, bare-breasted and unhurried, a string of silver dollars draped across her lap, the ledger angled to keep a little mystery",
        light="warm lamplight with a soft glow, rich amber shadows, velvet depth",
        motion="lamp flame flickering, a slow slide of one abacus bead, her fan opening and closing"),
    "pirate": dict(
        who="{adult} Cantonese woman (age 48), the Pirate Queen of the South China Sea on the stern deck of a great war junk at night, elaborate pinned hair, a single white peony on the rail, coldly sensual and utterly calm",
        sultry="dark quilted silk robe falling open over sculpted leather armour and a daring bare decolletage, oxblood sash",
        boudoir="robe sliding off her shoulders over a leather harness-cut bodice, red silk cord wound around her gloved fingers, peony held to her lips",
        topless="robe fallen to her hips, bare-breasted in the lantern light with a crossed leather baldric and nothing else, peony between two fingers",
        light="lantern light from below, deep blue night, a rim of silver moon",
        motion="lantern flames swaying, robe silk lifting in the night wind, the peony petals trembling"),
    "agent": dict(
        who="{adult} Macanese-Chinese woman (age 37), the pirate queen's dangerously glamorous agent seated in a lacquered tea house on the Hong Kong waterfront, small ivory coin balance before her, red silk protection token between two fingers, commanding pose and knowing half-smile",
        sultry="fitted oxblood Qing-era silk jacket with sheer sleeves and a deep neckline, gold hairpins",
        boudoir="sheer sleeves and open jacket over a lace-edged chemise, jacket slipping from one shoulder, red silk cord looped around her wrist",
        topless="bare-breasted behind a sheer oxblood jacket worn open, the red token held to her lips, an ivory balance catching the light",
        light="red paper-lantern glow, warm smoky haze, soft shadows",
        motion="steam curling from the teacup, the red token swinging between her fingers, lantern light shimmering on silk"),
    "banker": dict(
        who="{adult} Scottish woman (age 52), statuesque chief cashier behind a brass teller's grille in a Hong Kong bank, steel spectacles, pinned auburn hair, silver dollars and a ledger, cool appraising gaze charged with erotic authority",
        sultry="severe lacquer-black frock coat over a burgundy silk corset, leather gloves, velvet choker",
        boudoir="frock coat draped off her shoulders, burgundy corset laced loose, long leather gloves, spectacles low on her nose",
        topless="bare-breasted behind the grille in nothing but leather gloves, a velvet choker and her spectacles, the ledger resting open on the counter",
        light="cool green banker's-lamp light against warm brass, crisp and glossy",
        motion="slow fingertip tapping on the counter, a stack of silver dollars being counted, brass grille glinting"),
    "comprador": dict(
        who="{adult} Cantonese woman (age 45), heavy-set, full-figured and voluptuous comprador in a busy godown of tea chests and silk bales, abacus under one arm, writing brush in hand, confident appraising look",
        sultry="storm-blue Qing-era jacket with jade fastenings, neckline loosened in the humid heat",
        boudoir="jacket open and off her shoulders, a silk camisole clinging in the heat, jade bangle, a silk scarf dangling between her breasts",
        topless="bare-breasted and glowing in the heat, jacket open, trousers low on her hips, the abacus held to one side like a dare",
        light="sticky golden tropical light through shutters, glossy skin, soft focus",
        motion="abacus beads clicking, dust motes drifting in the shutter light, a slow fan of her hand against the heat"),
    "shipwright": dict(
        who="{adult} Cantonese woman (age 56), muscular master shipwright beside a half-built junk hull, adze on one shoulder, silver-streaked hair tied back, weathered hands on teak, proud gruff smile",
        sultry="linen shirt open low and sleeves rolled, fitted leather waist cincher",
        boudoir="shirt knotted under her bust, leather cincher over bare midriff, sawdust glittering on sun-warmed skin",
        topless="bare-breasted in a leather work apron cinched low, sawdust on her skin, one forearm braced on the hull",
        light="late sun through the unfinished ribs of the hull, warm shafts, gentle haze",
        motion="sawdust drifting through the light, the adze tapped lightly against her palm, a slow proud grin"),
    "customs": dict(
        who="{adult} English woman (age 39), tall and powerfully muscular, strawberry-blonde hair in a tight braid, fierce customs inspector on a crowded Shanghai wharf, pith helmet under one arm, manifest clipboard, brass manacles at her belt, stern sensual glare",
        sultry="storm-blue uniform coat with brass buttons over a black silk corset and a daring neckline",
        boudoir="uniform coat unbuttoned and open, black silk corset laced tight, white gloves, a single braid over one bare shoulder",
        topless="uniform coat open over bare skin, brass buttons gleaming, manacles and a riding belt at her hips, clipboard held low like a shield she has no intention of using",
        light="hard morning wharf light, crisp shadows, glossy highlights",
        motion="braid swaying, flags snapping in the wind behind her, a slow tap of the clipboard against her thigh"),
    "crier": dict(
        who="{adult} English woman (age 29), the dazzling Gazette crier on the Hong Kong waterfront, fresh broadsheet and brass handbell in her hands, auburn hair escaping a small cocked hat, one boot on a bollard, mid-call with a wicked grin",
        sultry="short tobacco-leather jacket over an ivory corset and a dramatically split oxblood skirt",
        boudoir="jacket slipping off her shoulders, corset half-laced, split skirt falling away over a garter, broadsheet held across her chest",
        topless="bare-breasted in a cropped open jacket, split skirt and garter, the broadsheet and handbell the only cover and neither is very good at it",
        light="bright cheeky harbour sunshine, sparkle on the water, high-key and playful",
        motion="handbell ringing and swinging, broadsheet fluttering, skirt lifting in the harbour breeze"),
    "bookmaker": dict(
        who="{adult} Macanese woman (age 34), the bookmaker of the Golden Fan, leaning over a lacquered fan-tan table with one ringed hand on a gold-and-jade abacus, a chalked odds board behind her, glossy black hair pinned with a gold fan comb, amused gaze straight into the camera",
        sultry="black silk cheongsam-cut gown with oxblood and gold embroidery and a daring high slit, jade drop earrings",
        boudoir="gown unhooked and slipping from her shoulders, a garter and silk stocking showing through the slit, a golden fan held to her lips",
        topless="bare-breasted over the fan-tan table, gown pooled at her hips, towers of silver dollars and the golden fan placed with a gambler's sense of timing",
        light="green baize glow with warm lantern smoke, casino chiaroscuro, glossy highlights",
        motion="lantern smoke drifting, a coin spinning on the table, the golden fan flicking open"),
    "mayor": dict(
        who="{adult} woman (age 47), the Mayor of a treaty port behind a teak harbour-office desk, ledger and iron strongbox before her, gold chain of office, harbour lanterns through the window, cool appraising smile",
        sultry="fitted pirate frock coat over a corset, the chain of office resting low on her bust",
        boudoir="frock coat shrugged off one shoulder, corset laced loose, the heavy gold chain of office as her only jewellery, leaning across the desk",
        topless="bare-breasted behind the desk in only the gold chain of office, the strongbox lid half open beside her, utterly in charge",
        light="warm harbour dusk through the window, gold rim light, regal and unhurried",
        motion="the chain of office swinging, lantern light flickering through the window, a slow turn of one link between her fingers"),
    "taxlady": dict(
        who="{adult} English woman (age 36), Mrs. Evelyn Marlowe, the widowed Registrar of the Port of Hong Kong at a harbour-office desk on a foggy wharf, dark hair pinned up with spectacles pushed up into it, open ledger and a jade-topped pencil, conspiratorial half-smile",
        sultry="black coat over an oxblood corset, a ribbon at her throat",
        boudoir="coat slipping off her shoulders, oxblood corset laced loose, sheer black stockings, pencil held between her teeth",
        topless="bare-breasted under an open black coat, the ledger held up in one hand to share a secret and cover very little",
        light="soft fog-diffused window light, pearly and intimate, gentle shadows",
        motion="spectacles pushed up into her hair, a pencil tapped against her lip, fog drifting past the window"),
    "bookkeeper": dict(
        who="{adult} French-Indian woman (age 38), Mademoiselle Celeste Vautrin, the House's private bookkeeper reclining in a leather chair in a lamplit counting room above the Hong Kong wharf, a great crimson-bound ledger open across her lap, quill in her ink-stained fingers, gold wire spectacles low on her nose, a smouldering gaze over the rims",
        sultry="black silk blouse open to the waist over an oxblood lace corset, sheer black stockings",
        boudoir="blouse slipping off one shoulder, oxblood lace corset unlaced, garter belt and sheer stockings, one knee drawn up with the ledger placed just so",
        topless="bare-breasted in the leather chair, blouse fallen open, garter belt and black stockings, the crimson ledger and quill the only props that matter",
        light="candle glow, warm brass and silver highlights, deep red shadows, intimate",
        motion="candle flame flickering, the quill drawn slowly across her lower lip, a page turning"),
    "officer_singapore": dict(
        who="{adult} English woman (age 44), soft, plump and voluptuous with honey-blonde curls coming loose, the languid Port Authority officer of Singapore lounging in a rattan chair on a shaded colonial wharf-office veranda, a glass of gin sweating in one hand and a customs stamp dangling forgotten from the other",
        sultry="loosened white muslin gown slipping from one shoulder over a lace corset",
        boudoir="muslin gown half off, lace corset unlaced, bare shoulders and a bare leg stretched across the rattan, fan resting on her bosom",
        topless="bare-breasted and unbothered in the rattan chair, muslin gown pooled at her hips, gin glass raised in a lazy toast",
        light="hot dappled veranda light through palms, hazy and honeyed",
        motion="ceiling fan turning, palm shadows moving across her skin, ice shifting in the glass"),
    "officer_manila": dict(
        who="{adult} Spanish-Filipina woman (age 38), the charming Port Authority officer of Manila in a carved narra-wood customs office, fan of Manila embroidery in one hand, ivory customs seal in the other, bales of silk behind her, inviting smile and hungry eyes",
        sultry="off-shoulder black lace mantilla gown with a deep neckline and a crimson silk sash",
        boudoir="lace mantilla gown slipped to her elbows, crimson sash low on her hips, the embroidered fan held across her chest",
        topless="bare-breasted under a sheer black lace mantilla draped over her shoulders, crimson sash at her hips, the fan lowered an inch",
        light="warm candlelight on carved wood, golden and soft, lace shadows across her skin",
        motion="fan fluttering, candle flames bending, lace mantilla stirring in a draught"),
    "officer_saigon": dict(
        who="{adult} French woman (age 33), the mercurial colonial Port Authority officer of Saigon reclining on a chaise in a shuttered customs house, a glass of absinthe and a gold coin on the table beside an open ledger, a teasing sidelong smile",
        sultry="half-laced violet silk corset and a loosened tricolour sash",
        boudoir="violet corset unlaced, tricolour sash loose across her hips, bare legs crossed on the chaise, the gold coin balanced on her thumb",
        topless="bare-breasted on the chaise in nothing but the tricolour sash and thigh-high stockings, the gold coin flipped in the air",
        light="slatted tropical light striping her skin, warm and humid, soft shutter shadows",
        motion="the gold coin flipping and catching the light, shutter light sliding across her skin, absinthe swirling in the glass"),
    "officer_nagasaki": dict(
        who="{adult} Japanese woman (age 35), the precise Port Authority officer of Nagasaki kneeling at a low lacquer desk in the Dejima customs house, brush and inkstone, an abacus and a Dutch ledger before her, a calm piercing stare",
        sultry="deep indigo silk kimono worn loose off both shoulders, obi half undone",
        boudoir="kimono slipped to her elbows, obi undone and trailing, the brush held to her lips, bare back to the lantern",
        topless="bare-breasted and perfectly composed, indigo kimono pooled around her hips, brush poised above the ledger",
        light="soft paper-lantern glow, pale and quiet, delicate shadows",
        motion="paper lantern light flickering, a slow brushstroke, silk stirring as she breathes"),
    "officer_foochow": dict(
        who="{adult} Chinese woman (age 40), the Port Authority officer of Foochow serving tea in a customs house hung with tea-chest labels, jade pins in her black hair, a steaming clay teapot tilted in her hand, a slow knowing smile",
        sultry="jade-green silk qipao with a thigh-high slit, unbuttoned at the collar",
        boudoir="qipao unbuttoned to the waist and slipping off one shoulder, bare thigh through the slit, a porcelain teacup held to her lips",
        topless="bare-breasted in an open jade qipao, jade pins in her hair, steam from the teapot curling over her shoulder",
        light="soft river light through lattice, pearly green, dreamy and warm",
        motion="steam rising from the teapot, tea pouring in a slow stream, lattice shadows moving"),
    "officer_shanghai": dict(
        who="{adult} Chinese woman (age 37), the commanding Port Authority officer of Shanghai standing on the Bund customs house steps, gold-embroidered riding gloves and a customs baton, clerks and cargo behind her, imperious half-smile",
        sultry="fitted oxblood brocade jacket open over a black silk corset, high collar undone",
        boudoir="brocade jacket open and off her shoulders, black corset unlaced, the baton tapped against a gloved palm",
        topless="bare-breasted in an open brocade jacket and riding gloves, baton resting across her shoulders like she owns the staircase",
        light="crisp Bund morning light, bright and glossy, crisp rim light on her hair",
        motion="baton tapping, brocade shifting in the river wind, a slow lift of one eyebrow"),
    "officer_bangkok": dict(
        who="{adult} Thai court lady (age 42), the gracious Port Authority officer of Bangkok seated in a gilded river pavilion, jasmine garland and gold court jewellery, a palm-leaf tally and a royal seal beside her, river barges behind, serene smile with steel in her eyes",
        sultry="gold-threaded silk sabai draped over one bare shoulder and wrapped low",
        boudoir="sabai slipped down to her waist with the end gathered across her bosom, gold armlets and anklets, a jasmine garland trailing between her fingers",
        topless="bare-breasted in nothing but gold jewellery, a low-slung sabai and the jasmine garland draped around her neck",
        light="warm river-reflected light on gold leaf, glowing and serene",
        motion="jasmine petals drifting, river light rippling across the gold, silk stirring in the breeze"),
    "officer_batavia": dict(
        who="{adult} Dutch woman (age 39), the strict Port Authority officer of Batavia in a whitewashed VOC customs hall, a riding crop resting across an open ledger, spectacles low on her nose, pale blonde hair pinned tight, a stern stare with a hint of wicked enjoyment",
        sultry="severe black lace-collared gown with a laced leather corset over it and long black gloves",
        boudoir="gown unbuttoned and open, laced leather corset tight over bare skin, long black gloves, crop tapped against her palm",
        topless="bare-breasted in black gloves and a lace collar, the riding crop laid across the ledger, spectacles low, thoroughly in charge",
        light="cool whitewashed hall light with a warm hard accent, crisp and glossy",
        motion="the crop tapping once per column, dust drifting in the hall light, a slow lowering of her spectacles"),
    "officer_calcutta": dict(
        who="{adult} English woman (age 46), heavyset and statuesque with an imposing bosom and platinum-blonde hair piled high, the ruthless Port Authority officer of Calcutta at a mahogany desk in the Strand Road customs house, a strongbox lid half open beside her, a peacock-feather fan, a sweet venomous smile",
        sultry="plunging midnight-purple silk evening gown, ruby choker, long gloves",
        boudoir="evening gown pulled down off her shoulders, ruby choker, long gloves, the peacock fan held coyly across her chest",
        topless="bare-breasted in a ruby choker and long gloves, purple silk pooled at her waist, the peacock fan opened beside her",
        light="swaying punkah shadows, deep plum and gold, luxurious and slow",
        motion="punkah fan swaying overhead, peacock feathers stirring, rubies catching the light"),
    "officer_hongkong": dict(
        who="{adult} Portuguese woman (age 33), the Port Authority officer of Hong Kong on a crowded Victoria Harbour wharf, a gold crucifix and a dagger at her hip, leaning over a customs desk with a manifest upside down before her, a slow dangerous smile",
        sultry="wine-red silk jacket open over a black lace corset",
        boudoir="wine-red jacket slipping off her shoulders, black lace corset half unlaced, the dagger belt riding low on her hips",
        topless="bare-breasted in an open wine-red jacket, gold crucifix between her breasts, dagger at her hip, the manifest read upside down with a smile",
        light="bright harbour glare with warm reflected water-light, glossy and bold",
        motion="the crucifix swinging, lorchas bobbing behind her, a slow lean across the desk"),
}


# ---- Sultry v2 (21 Nov 2026, after review: v1 was "too covered" and "stiff"). Pose-first glamour: each woman gets a
# specific body pose using her own prop, and a costume that is actively coming undone (still dressed, not topless).
SULTRY = {
    "narrator": ("leaning back against the ship's rail with one hip cocked, chin tilted down and eyes up at the viewer, pulling a glove off with her teeth",
                 "frock coat open to the sternum over a loosened ivory corset, bare collarbones, oxblood sash slung low on her hips, one stocking-clad leg bent against the rail"),
    "bosun": ("straddling the cannon barrel and leaning toward the viewer with a wicked laugh, dragging the slow match slowly along her thigh",
              "waistcoat unbuttoned to the waist over a wet linen shirt knotted under her bust, bare midriff, belt riding low, bare thighs above tall boots"),
    "lender": ("reclining sideways across the rosewood desk on one elbow, legs crossed, slowly lowering a fan to reveal a smile",
               "silk jacket open to the waist over a sheer chemise, bare shoulders, silk garters and stocking tops showing where the hem rides up"),
    "pirate": ("sitting sideways on the stern rail with one boot up, head tilted, the white peony trailing across her lips, eyes half-lidded",
               "quilted robe sliding off both shoulders over a leather bodice laced to the navel, bare thighs between the robe and thigh-high boots"),
    "agent": ("perched on the edge of the tea table leaning forward with her elbows on her knees, dangling the red token above her parted lips",
              "oxblood jacket open to the waist over a lace-edged chemise, a high thigh slit showing a garter, bare shoulders"),
    "banker": ("leaning across the counter on both palms, chin down, eyes over her spectacles, pulling one leather glove off finger by finger",
               "frock coat open over a burgundy corset laced low, bare shoulders, velvet choker, a hitched skirt showing stocking tops and garters"),
    "comprador": ("sprawled back against the silk bales with one leg stretched out, fanning herself lazily, sweat on her throat",
                  "jacket open to the navel over a damp silk camisole clinging in the heat, trousers riding low on her hips, jade bangles"),
    "shipwright": ("sitting on a timber beam with her back arched, wiping sweat from her throat with a rag, a lazy proud grin",
                   "linen shirt open to the waist and soaked through, leather apron slung low, bare strong thighs under a short work skirt"),
    "customs": ("sitting on the edge of her desk with one boot propped on a crate, chin raised, tapping the baton against her palm",
                "uniform coat open to the waist over a black silk corset, shirt untucked, brass manacles swinging from her belt, a bare thigh above thigh-high boots"),
    "crier": ("kicking one leg up from the bollard and laughing mid-shout, the bell held high, the broadsheet fluttering against her hip",
              "jacket open over a half-laced ivory corset, split skirt showing stocking tops and a garter, bare shoulders"),
    "bookmaker": ("leaning across the fan-tan table toward the viewer with her chin on a ringed hand, the high slit falling open over a bare thigh",
                  "cheongsam gown unhooked at the collar and slit to the hip, a stocking and garter showing, shoulders bare"),
    "mayor": ("sitting on the front of the teak desk with her legs crossed, drawing the chain of office slowly through her fingers",
              "frock coat open over an unlaced corset, bare shoulders, stockings, the gold chain resting between her breasts"),
    "taxlady": ("perched on the desk edge with one shoe dangling, a pencil between her teeth, spectacles pushed up into her hair, about to share a secret",
                "coat slipping off one shoulder over a half-unlaced oxblood corset, ribbon at her throat, sheer stockings and garters showing"),
    "bookkeeper": ("stretched out in the leather chair with one leg over the arm, drawing the quill slowly across her lower lip, heavy-lidded",
                   "silk blouse open to the navel and slipping off one shoulder over an unlaced lace corset, garter belt and sheer stockings"),
    "officer_singapore": ("sprawled in the rattan chair with her gown riding up one leg, fanning herself with a declaration, heavy-lidded and amused",
                          "muslin gown slipped off both shoulders, lace corset half-laced, bare legs and a stocking top showing"),
    "officer_manila": ("leaning on the customs desk toward the viewer with her head tilted, slowly lowering the fan to reveal a hungry smile",
                       "lace mantilla gown pulled low off both shoulders, a deep plunge to the crimson sash, a bare leg through the slit"),
    "officer_saigon": ("stretched along the chaise on one hip, flipping the gold coin, eyes sliding sidelong to the viewer",
                       "violet corset laced half open, tricolour sash loose, bare legs crossed at the ankle, a silk stocking and garter"),
    "officer_nagasaki": ("kneeling and looking back over her bare shoulder at the viewer, the brush held to her lower lip",
                         "indigo kimono dragged off both shoulders to the elbows, obi undone and trailing, her nape and bare back to the lantern"),
    "officer_foochow": ("leaning forward to pour tea, the gown parting over one bare thigh, a slow knowing smile",
                        "qipao unbuttoned to the waist with a thigh-high slit, jade pins in her hair, bare shoulders"),
    "officer_shanghai": ("standing one step above the viewer with her hip cocked, tapping the baton against her glove, looking down with a smirk",
                         "brocade jacket open to the navel over a black corset, gold riding gloves, high boots with a bare thigh above them"),
    "officer_bangkok": ("reclining on silk cushions on one elbow, drawing the jasmine garland slowly through her fingers",
                        "sabai slipped to the waist and draped to cover very little, gold armlets, a gold belly chain, bare shoulders"),
    "officer_batavia": ("sitting on the ledger desk with her boots up on the chair, tapping the crop against a gloved palm, spectacles low, a smirk",
                        "black lace gown unbuttoned to the waist over a laced leather corset, long gloves, stocking tops showing"),
    "officer_calcutta": ("reclining in her chair, drawing the peacock fan slowly down her throat, a sweet venomous smile",
                         "midnight-purple gown dragged down off both shoulders in a deep plunge, ruby choker, long gloves"),
    "officer_hongkong": ("leaning across the desk toward the viewer on her forearms, the dagger belt riding low, a slow dangerous smile",
                         "wine-red jacket open over a half-unlaced black lace corset, bare shoulders, the gold crucifix between her breasts"),
}
for _k, (_pose, _outfit) in SULTRY.items():
    LOOKS[_k]["sultry_v1"] = LOOKS[_k]["sultry"]
    LOOKS[_k]["pose"], LOOKS[_k]["sultry"] = _pose, _outfit
TAIL["sultry"] = (", romanticized 1860 China Seas glamour photograph, sultry pin-up styling, caught mid-movement, "
                  "shallow depth of field, glossy highlights on bare skin, 3:4 portrait")

def _who(look, tier):
    """Her identity line. In the clean tier a body-emphasis phrase is softened so a modest costume stays modest."""
    who = look["who"].format(adult=ADULT)
    return who.replace(" with an imposing bosom", " with an imposing presence") if tier == "clean" else who


def build(key, tier="boudoir", mood=None):
    """A full prompt for one persona. mood is a key of SPICE_MOODS or your own words for her expression."""
    if tier not in ALL_TIERS:
        raise ValueError("tier must be one of " + ", ".join(ALL_TIERS))
    look = LOOKS[key]
    if tier == "sultry":      # pose-first: genre, her, her pose, her costume coming undone, then light
        parts = ["Vintage glamour photograph of an " + _who(look, tier), look["pose"], look["sultry"], look["light"]]
    else:
        parts = ["An " + _who(look, tier), look[tier], look["light"]]
    if mood:
        parts.append(SPICE_MOODS.get(mood, mood))
    return ", ".join(parts) + TAIL[tier]


def motion(key):
    """The Wan 2.2 movement line for her picture (movement only; the look comes from the picture)."""
    return LOOKS[key]["motion"]

# ---- Master shots (21 Nov 2026): wide 16:9 wallpaper, the woman dominating a dramatic scene of her own world.
# She is always alone in frame (no other figures), so the picture reads as hers and loops well in Wan 2.2.
MASTER_TAIL = {
    "sultry": ", romanticized 1860 China Seas glamour photograph, epic cinematic wallpaper master shot, sultry pin-up styling, caught mid-movement, "
              "low heroic camera angle, rich depth and atmosphere, natural skin with a soft sheen, confident direct gaze, 16:9",
    "boudoir": ", romanticized 1860 China Seas glamour photograph, epic cinematic wallpaper master shot, intimate boudoir styling with clever cover, "
               "low heroic camera angle, rich depth and atmosphere, natural skin with a soft sheen, confident direct gaze, 16:9",
    "topless": ", romanticized 1860 China Seas glamour photograph, epic cinematic wallpaper master shot, bold magazine-centerfold styling, tasteful and playful, "
               "low heroic camera angle, rich depth and atmosphere, natural skin with a soft sheen, confident direct gaze, 16:9",
}
MASTER = {
    "narrator": "alone at the helm of the schooner as a typhoon front glows crimson behind her, brass instruments gleaming, the lights of Hong Kong spread far below",
    "bosun": "alone in a smoke-filled gun deck framed by a blazing broadside, rows of brass cannon firing, sparks and embers drifting past her",
    "lender": "enthroned behind a vast rosewood desk in a grand lamplit counting house, mountains of silver dollars and towering ledger shelves rising into shadow behind her",
    "pirate": "alone on the stern of her flagship at the head of a night fleet of black-sailed war junks, lanterns stretching to the horizon, a storm breaking behind her",
    "agent": "alone in a grand lantern-hung tea house above the Praya at night, red silk banners cascading, the harbour glittering through open screens",
    "banker": "alone at the heart of the great vault hall, walls of iron safes and brass grilles receding into shadow, shafts of gaslight falling on her",
    "comprador": "alone in a cathedral of silk bales and tea chests in a vast godown, shafts of golden light pouring through high shutters",
    "shipwright": "alone before a towering half-built junk on the slip at sunset, ribs of timber soaring above her, sparks and sawdust glowing in the light",
    "customs": "alone on the Bund wharf steps at dawn above a harbour full of ships, flags snapping, a mountain of seized crates at her feet",
    "crier": "high in the rigging above the Hong Kong waterfront at golden hour, broadsheets fluttering down around her like confetti",
    "bookmaker": "alone at the head of a grand fan-tan hall, green baize tables stretching away, chandeliers and lantern smoke, a towering odds board blazing behind her",
    "mayor": "alone at the great window of the harbour office at dusk, the whole port and its fleet glittering below, the chain of office catching the light",
    "taxlady": "alone on the harbour-office steps in rolling fog, a great ledger open in her arms, ship lanterns glowing like stars through the mist",
    "bookkeeper": "alone in her lamplit counting room above the wharf, walls of crimson ledgers rising into shadow, a window full of moonlit harbour behind her",
    "officer_singapore": "alone on a vast colonial veranda at sunset, palms and the Singapore roads blazing orange beyond the balustrade",
    "officer_manila": "alone in a grand narra-wood customs hall under hanging lanterns, mountains of silk bales and porcelain lit gold around her",
    "officer_saigon": "alone on a chaise in a vast shuttered customs hall, bars of tropical light slicing across the floor, ceiling fans turning slowly overhead",
    "officer_nagasaki": "alone on a tatami platform in a lantern-lit hall above Dejima bay, paper screens glowing, mist drifting over the water beyond",
    "officer_foochow": "alone in a tea-house hall hung with tea-chest banners, river mist and green hills glowing through carved lattice behind her",
    "officer_shanghai": "alone on the Bund customs house steps at dawn, the whole skyline of ships and godowns stretched behind her, brocade banners snapping",
    "officer_bangkok": "alone in a gilded river pavilion at golden hour, temple spires and royal barges glowing on the river behind her",
    "officer_batavia": "alone at the head of a whitewashed VOC hall of columns and ledgers, long shafts of cold light and a wall of iron strongboxes behind her",
    "officer_calcutta": "alone at a vast mahogany desk in a Strand Road hall of pillars, punkahs swaying, a wall of open strongboxes and rubies glittering behind her",
    "officer_hongkong": "alone on a crowded Victoria Harbour quay at golden hour, lorchas and junks packed behind her, the Peak glowing in the haze",
}


# ---- Clean pair (decision 5, 21 Nov 2026): a hand-written dressed look per woman, same face and setting.
# Family-friendly screens use these (filed NOT NSFW, tag "<mood>, clean"). No regex swapping, so nothing can leak.
CLEAN = {
    "narrator": "lacquer-black frock coat buttoned over an ivory high-collared blouse, oxblood sash, black Parsi topi",
    "bosun": "tobacco-leather waistcoat buttoned over a laced linen shirt with a high collar, oxblood sash, sleeves rolled",
    "lender": "dark Qing-era silk jacket with a high mandarin collar and imperial-jade fastenings",
    "pirate": "dark quilted silk robe closed over sculpted leather armour, high collar, oxblood sash",
    "agent": "fitted oxblood Qing-era silk jacket with sheer sleeves over a high-necked under-blouse, gold hairpins",
    "banker": "severe lacquer-black frock coat over a high-necked burgundy silk blouse, leather gloves",
    "comprador": "storm-blue Qing-era jacket with jade fastenings buttoned to the collar, trousers",
    "shipwright": "linen shirt buttoned to the collar with sleeves rolled, a leather work apron over it",
    "customs": "storm-blue uniform coat with brass buttons fastened to the collar",
    "crier": "short tobacco-leather jacket buttoned over a high-collared ivory blouse and an oxblood skirt",
    "bookmaker": "black silk cheongsam-cut gown with oxblood and gold embroidery and a high mandarin collar, jade drop earrings",
    "mayor": "fitted pirate frock coat buttoned over a high-necked blouse, the gold chain of office across her chest",
    "taxlady": "black coat buttoned over an oxblood high-collared blouse, a ribbon at her throat",
    "bookkeeper": "black silk blouse buttoned to the collar under an oxblood waistcoat, gold wire spectacles",
    "officer_singapore": "white muslin gown with a modest neckline and a lace collar",
    "officer_manila": "black lace mantilla gown with a high neckline and a crimson silk sash",
    "officer_saigon": "violet silk day dress with a high neckline and a tricolour sash",
    "officer_nagasaki": "deep indigo silk kimono neatly worn and tied with the obi",
    "officer_foochow": "jade-green silk qipao buttoned to the collar",
    "officer_shanghai": "fitted oxblood brocade jacket buttoned over a black silk blouse, high collar, gold-embroidered riding gloves",
    "officer_bangkok": "gold-threaded silk sabai draped neatly over a fitted silk blouse",
    "officer_batavia": "severe black lace-collared gown buttoned to the throat, long black gloves",
    "officer_calcutta": "midnight-purple silk day gown with a modest neckline, ruby choker, long gloves",
    "officer_hongkong": "wine-red silk jacket buttoned over a black lace blouse",
}
for _k, _v in CLEAN.items():
    LOOKS[_k]["clean"] = _v
TAIL["clean"] = (", romanticized 1860 China Seas photograph, elegant fully dressed styling, high necklines, natural skin, "
                 "confident direct gaze, hands in frame, 3:4 portrait")
MASTER_TAIL["clean"] = (", romanticized 1860 China Seas photograph, epic cinematic wallpaper master shot, elegant fully dressed styling, "
                        "low heroic camera angle, rich depth and atmosphere, confident direct gaze, 16:9")

# ---- Nude tier (21 Nov 2026): fully bare glamour, the NSFW step above topless ("bottomless too").
# Magazine-centerfold composition: posed, turned, seated or draped so the picture stays glamour, never anatomical.
# Same women, same settings, same epic light. One hand-written look each; nothing is derived by regex.
NUDE = {
    "narrator": "bare and unashamed at the rail, the open frock coat fallen behind her, oxblood sash trailing from one hand, turned three-quarters away with the chronometer held low",
    "bosun": "nothing on but the gun belt and powder-streaked skin, leaning back against a cannon with one knee raised, grinning like she dares you to say something",
    "lender": "nude on the rosewood desk, hip turned to the lamp, silver dollars poured across her lap and the ledger angled to keep a little mystery",
    "pirate": "nude in the lantern light with a crossed leather baldric and nothing else, seen from behind over one shoulder, peony between two fingers",
    "agent": "bare beneath a sheer oxblood jacket slipped off her shoulders, reclining on the tea-house cushions, the red token held to her lips, knees angled to the side",
    "banker": "nothing but leather gloves, a velvet choker and her spectacles, seated sideways on the counter with the ledger open across her lap",
    "comprador": "bare and glowing in the heat, stretched on a stack of silk bales with one leg bent, the abacus held to one side like a dare",
    "shipwright": "nude but for a leather tool belt, sawdust on her skin, one forearm braced on the hull and her back to the lens, glancing over her shoulder",
    "customs": "nothing but the uniform cap and boots, perched on a stack of seized crates with the clipboard held low like a shield she has no intention of using",
    "crier": "bare on the printing-house stool in only a garter and one stocking, the broadsheet and handbell the only cover and neither is very good at it",
    "bookmaker": "nude across the fan-tan table, one knee drawn up, silver dollars stacked in towers around her and the golden fan placed with a gambler's sense of timing",
    "mayor": "nothing but the gold chain of office, sitting on the edge of the desk with the strongbox lid half open beside her, utterly in charge",
    "taxlady": "bare beneath nothing but a long black coat held closed in one fist, the ledger raised in the other hand to share a secret and cover very little",
    "bookkeeper": "nothing but black stockings, a garter belt and her spectacles, lying back in the leather chair with one leg draped over the arm, the crimson ledger and quill the only props that matter",
    "officer_singapore": "bare in the rattan chair, one leg crossed over the other, muslin gown abandoned on the floor, gin glass raised in a lazy toast",
    "officer_manila": "nude under a sheer black lace mantilla draped from her shoulders, crimson sash at her hip, the fan lowered an inch, seen in three-quarter profile",
    "officer_saigon": "nothing but the tricolour sash and thigh-high stockings, stretched along the chaise on her side, the gold coin flipped in the air",
    "officer_nagasaki": "bare and perfectly composed, kneeling on the tatami, indigo kimono slid from her shoulders to pool behind her, brush poised above the ledger",
    "officer_foochow": "nude behind rising tea steam, jade pins in her hair, the open qipao draped across one thigh, one hand on the teapot",
    "officer_shanghai": "nothing but riding gloves and tall boots, baton across her shoulders, leaning on the staircase newel with her back arched, owning the whole staircase",
    "officer_bangkok": "nothing but gold jewellery, armlets and the jasmine garland, reclining on silk cushions with the sabai drawn loosely across her hips",
    "officer_batavia": "nothing but black gloves and a lace collar, seated on the ledger desk with her knees crossed, the riding crop laid across the ledger, spectacles low, thoroughly in charge",
    "officer_calcutta": "nothing but a ruby choker and long gloves, lounging in her chair with purple silk trailing over her hips, the peacock fan opened beside her",
    "officer_hongkong": "bare but for a gold crucifix and a dagger belt, leaning on the desk with her weight on one hip, the manifest read upside down with a smile",
}
for _k, _v in NUDE.items():
    LOOKS[_k]["nude"] = _v
TAIL["nude"] = (", romanticized 1860 China Seas glamour photograph, bold vintage-centerfold nude styling, tasteful and playful, "
                "artful composition, natural skin with a soft sheen, confident direct gaze, 3:4 portrait")
MASTER_TAIL["nude"] = (", romanticized 1860 China Seas glamour photograph, epic cinematic wallpaper master shot, bold vintage-centerfold nude styling, "
                       "tasteful and playful, artful composition, low heroic camera angle, rich depth and atmosphere, natural skin with a soft sheen, confident direct gaze, 16:9")
# ---- The wardens, storytellers and Otohime (21 Nov 2026): the 14 characters from jail_cast.py and legend_cast.py,
# in the same v2 shape (identity, costume ladder, her own light, motion, master scene). Their old prompts were
# one fixed "completely nude" look; now each has the full ladder and a clean pair, with her in command.
_MORE = {
    "warden_hongkong": dict(
        who="{adult} English woman (age 52), Mrs. Agatha Crane, tall, broad-shouldered and handsome with a full mature figure, iron-grey hair in a severe bun, the matron of Victoria Gaol in Hong Kong at an open iron cell door, a great ring of brass keys at her belt, a dry knowing half-smile, fully in command",
        pose="leaning one shoulder on the cell door, twirling the ring of keys on one finger",
        sultry="grey matron's dress unbuttoned to the waist over a laced black corset, starched white collar, black stockings",
        boudoir="dress slipped off both shoulders, corset laced loose, the key belt slung low on her hips, keys held across her chest",
        topless="bare-breasted in a starched white collar and a wide leather belt slung low with its great ring of brass keys, one hand on the bars",
        nude="nothing but the starched white collar, black stockings and the wide key belt, leaning on the open cell door with one hand on the bars and the key ring held low",
        clean="grey matron's dress buttoned to the collar, starched white collar, wide black belt with a ring of brass keys",
        light="lamplight on whitewashed stone, cold grey-gold, striped with shadows of bars",
        motion="the key ring swinging from her finger, lamp flame wavering, her knowing smile slowly widening",
        master="alone in the long whitewashed corridor of Victoria Gaol, tiers of iron cell doors receding into lamplit shadow, the great key ring raised in one hand"),
    "warden_singapore": dict(
        who="{adult} English woman (age 36), Miss Rosalind Pell, slim and curvy with sun-browned skin and chestnut curls pinned up loosely, the keeper of the Pearl's Hill lock-up in Singapore leaning against barred teak doors, a pith helmet tipped back, a ring of keys twirled on one finger, a bright teasing smile, playful and in charge",
        pose="leaning back against the teak doors with one boot up, twirling the key ring",
        sultry="white linen officer's tunic unbuttoned to the waist over a loose camisole, pith helmet tipped back",
        boudoir="tunic slipping off her shoulders, camisole unlaced, bare thighs above riding boots, the helmet held low",
        topless="bare-breasted in the open white linen tunic and a tipped-back pith helmet, the key ring twirled on one finger",
        nude="nothing but the pith helmet and tall boots, the tunic dropped at her feet, leaning back against the barred teak doors with the key ring dangling from one finger",
        clean="crisp white linen officer's tunic buttoned to the collar, pith helmet, key ring at her belt",
        light="slatted tropical sunlight striping skin and teak, bright and warm",
        motion="the keys twirling, the helmet tipping further back with a wink, slatted light drifting",
        master="alone before the great barred teak doors of the Pearl's Hill lock-up at noon, hard stripes of tropical sun cutting through the slats, a ring of keys spinning in one hand"),
    "warden_manila": dict(
        who="{adult} Spanish-Filipina mestiza woman (age 48), Dona Remedios Salcedo, full-figured and statuesque with wide hips, black hair under a sheer black lace mantilla, the alcaide of the Bilibid prison in a candlelit stone archway, a rosary wound around one wrist and a ring of iron keys in her hand, a serene merciless gaze",
        pose="framed in the candlelit archway with one hip cocked, the rosary slipping through her fingers",
        sultry="black lace gown dragged off her shoulders under the mantilla, crimson sash knotted at her waist",
        boudoir="gown pooled to her waist under the mantilla, crimson sash low on her hips, the keys held across her bosom",
        topless="bare-breasted under the sheer black lace mantilla, crimson sash at her hips, rosary and keys in her hands",
        nude="nothing but the sheer lace mantilla, a crimson sash and the rosary, turned three-quarters in the stone archway with the ring of keys held low",
        clean="black lace mantilla gown with a high neckline, crimson sash, rosary at her wrist, a ring of iron keys",
        light="candlelight gold on old stone, warm and heavy",
        motion="candle flames bending, the rosary swaying, a slow lift of her chin",
        master="alone in the vaulted candlelit corridor of the Bilibid, stone arches and iron grilles receding into gold shadow, the mantilla stirring in a draught"),
    "warden_saigon": dict(
        who="{adult} Corsican-French woman (age 41), Madame Odile Marchetti, lean and curvy with olive skin and cropped black hair, the gardienne of the Maison Centrale in Saigon seated on a stool before a cell, a hand of playing cards fanned against the bars, a thin cigarette between her lips, an amused, bored, dangerous look",
        pose="straddling the stool backwards with her chin on the chair back, cards fanned",
        sultry="military coat open over a black camisole, pistol belt riding low",
        boudoir="coat sliding off her shoulders, camisole hiked up, pistol belt low on her hips, the cards held to her chest",
        topless="bare-breasted in an open military coat sliding off her shoulders, pistol belt buckled low",
        nude="nothing but the pistol belt and tall boots, seated astride the stool facing the chair back, the coat tossed over the bars, cards fanned in one hand",
        clean="military coat buttoned to the collar over a white blouse, pistol belt, cards in one hand",
        light="shuttered tropical bars of light across her skin, cigarette smoke curling",
        motion="smoke curling from the cigarette, cards flicking between her fingers, a bored slow blink",
        master="alone in the shuttered central hall of the Saigon Maison Centrale, bars of tropical light slicing across tiers of cells, smoke drifting, a stool and a fanned hand of cards"),
    "warden_nagasaki": dict(
        who="{adult} Japanese woman (age 44), Kuroda Hisa, slender and composed, black hair in a tight samurai-wife's knot, the warden of the Sakuramachi gaol kneeling upright on a tatami platform before a wooden lattice cell, a brush and an open register before her, a ring of iron keys beside her knee, a perfectly calm unreadable stare",
        pose="kneeling upright, one hand lifting the brush, the kimono slipping at one shoulder",
        sultry="dark indigo kimono worn loose and low at the collar, obi loosened",
        boudoir="kimono slid off both shoulders and gathered at her arms, obi loose, the register held before her",
        topless="bare-breasted and perfectly composed, the indigo kimono pooled around her hips",
        nude="nothing but the loosened obi trailing across her lap, kneeling upright on the tatami with the brush poised above the register, the indigo kimono pooled behind her",
        clean="dark indigo kimono neatly worn and tied with the obi, keys at her knee",
        light="paper lantern glow on pale skin, soft amber, deep still shadows",
        motion="the brush moving once across the register, lantern light breathing, a slow blink",
        master="alone on the tatami platform of the Sakuramachi gaol, a long wooden lattice of cells receding behind her, paper lanterns glowing, rain on the roof"),
    "warden_foochow": dict(
        who="{adult} Chinese woman (age 50), Madam Chen Yue-hua, plump, soft and handsome with a round belly, silver-streaked hair pinned up with jade, the keeper of the yamen cells on the Min River at Foochow before a wooden-barred cell, a lantern and a cup of tea in her hands, a ring of keys on a red cord at her waist, a patient knowing smile",
        pose="leaning on the cell bars with the tea cup raised, the jacket slipping from one shoulder",
        sultry="dark green silk jacket worn open, loose silk trousers, keys on a red cord",
        boudoir="jacket hanging off both shoulders over a silk bandeau, keys on the red cord at her hip, the tea held to her lips",
        topless="bare-breasted in the open dark green silk jacket, keys on the red cord at her waist, lantern and tea in her hands",
        nude="nothing but jade hairpins and the red cord of keys at her hip, the green silk jacket draped over one arm, seated on a low stool before the cell with the tea cup raised",
        clean="dark green silk jacket buttoned to the collar, keys on a red cord",
        light="smoky lantern light, warm and soft, river mist at the bars",
        motion="steam curling from the tea, the lantern swaying, a slow knowing smile",
        master="alone in a lantern-lit yamen corridor of wooden cells above the Min River, river mist drifting through the lattice, a cup of tea steaming in her hands"),
    "warden_shanghai": dict(
        who="{adult} Chinese woman (age 39), Madam Tang Xiu-ying, tall and athletic with a sharp jaw and strong legs, black hair in a long braid over one shoulder, the gaoler of the Mixed Court cells in Shanghai striding down a stone corridor of iron-barred cells, a bamboo rod resting on her shoulder, a cold commanding stare",
        pose="striding toward the viewer with the bamboo rod on her shoulder, the coat flaring",
        sultry="black riding jacket open over a fitted corset, riding gloves and boots, keys on a leather strap",
        boudoir="jacket off her shoulders, corset laced loose, gloves and tall boots, the leather key strap across her torso",
        topless="bare-breasted in black riding gloves and boots, a leather strap of keys slung diagonally across her body, the bamboo rod on her shoulder",
        nude="nothing but riding gloves, tall black boots and the leather key strap, striding down the corridor seen three-quarters from behind with the bamboo rod on her shoulder",
        clean="black riding jacket buttoned to the collar, gloves and boots, leather key strap across her chest",
        light="cold blue gaslight on stone, hard and clean",
        motion="the braid swinging as she strides, the rod tapping the bars, gaslight flickering",
        master="alone at the centre of a vast stone corridor of iron-barred cells under cold gaslight, perspective lines racing to a far door, the bamboo rod on her shoulder"),
    "warden_bangkok": dict(
        who="{adult} Thai court lady (age 46), Khun Ying Prapai, graceful and full-figured with short court-style hair, the keeper of the King's prison at a teak-barred cell in a gilded courtyard, a lotus bud in one hand and a ring of keys in the other, a gracious immovable smile",
        pose="standing in the gilded courtyard with one hip out, the lotus bud at her lips",
        sultry="gold-threaded silk sabai draped low over a fitted bandeau, heavy gold armlets",
        boudoir="sabai slipped to her hips over a gold bandeau, armlets and anklets, the keys held across her chest",
        topless="bare-breasted in a low-slung gold-threaded sabai, heavy gold armlets, anklets and a gold belly chain",
        nude="nothing but gold armlets, anklets and a belly chain, the sabai drawn loosely across her hips, turned in profile with the lotus bud and keys",
        clean="gold-threaded silk sabai draped neatly over a fitted silk blouse, gold armlets",
        light="warm river light on gold and teak, soft haze",
        motion="the lotus bud turning in her fingers, the gold chain glinting, a slow gracious smile",
        master="alone in a gilded palace courtyard of teak-barred cells, temple spires and golden light beyond the gate, lotus petals drifting on a still pool"),
    "warden_batavia": dict(
        who="{adult} Dutch woman (age 45), Mevrouw Hendrika Visser, tall and robust with broad hips, pale blonde hair pinned tight under a white cap, the keeper of the cells beneath the Stadhuis of Batavia in a vaulted brick cellar before an iron grille, a lantern held high and a printed list of rules in her other hand, a stern wickedly amused look",
        pose="leaning on the iron grille with the list of rules raised, one eyebrow cocked",
        sultry="grey wool dress unbuttoned to the waist, starched white collar, white cap, black stockings",
        boudoir="dress dropped off both shoulders, starched collar and white cap kept on, black stockings, the rule list held across her chest",
        topless="bare-breasted in the white cap, starched collar and black stockings, a heavy key ring on a belt at her hips, the lantern held high",
        nude="nothing but the white cap, starched collar and black stockings, the key belt slung low, the lantern held high and the printed rules covering very little",
        clean="grey wool dress buttoned to the throat, starched white collar and cap, key ring at her belt",
        light="lantern light in a vaulted brick cellar, warm orange against cold shadow",
        motion="the lantern swaying, the list of rules fluttering, one eyebrow lifting",
        master="alone in a vast vaulted brick cellar beneath the Stadhuis, rows of iron grilles and arches receding into lantern-lit gloom"),
    "warden_calcutta": dict(
        who="{adult} English woman (age 49), Mrs. Lavinia Hartley, heavyset and comfortable with a soft belly and rosy cheeks, auburn hair going grey in soft curls, the superintendent of the Presidency Jail in Calcutta at a barred cell door, a folded blanket over one arm and a great ring of keys in her hand, a sweet motherly quietly terrifying smile",
        pose="leaning in the doorway with the blanket over her arm, the keys swinging",
        sultry="plum silk gown with a plunging neckline, a cameo brooch on a velvet ribbon",
        boudoir="plum silk gown fallen off both shoulders, the cameo on its velvet ribbon, the folded blanket held across her chest",
        topless="bare-breasted in a plum silk gown pooled at her waist, a cameo brooch on a velvet ribbon at her throat, keys in hand",
        nude="nothing but the cameo brooch on its velvet ribbon, standing at the barred door with the folded blanket held low and the great ring of keys in her other hand, the plum gown at her feet",
        clean="plum silk day gown with a modest neckline, cameo brooch on a velvet ribbon, a great ring of keys",
        light="punkah-stirred air, warm lamplight on skin and iron, honey gold",
        motion="the punkah swaying, the keys jingling, a motherly tilt of her head",
        master="alone in a pillared Presidency Jail gallery, punkahs swaying overhead, tiers of barred doors lit honey gold, a folded blanket over her arm"),
    "teller_temple": dict(
        who="{adult} Chinese woman (age 47), Mother Chen Sui-lan, graceful and full-figured with a calm beautiful face, long black hair pinned up with red lacquer pins, the keeper of the lantern at a sea goddess temple on the Fujian coast kneeling beside a great glowing red paper lantern, incense smoke curling around her, gilded carvings of waves and dragons behind, an open scroll across her lap, a serene knowing smile as if she has already read the ending",
        pose="kneeling with the scroll unrolled, one hand lifting the lantern light across her face",
        sultry="crimson and gold silk temple robe loosened and falling off her shoulders",
        boudoir="robe slipped off both shoulders and gathered at her waist, the scroll held across her chest",
        topless="bare-breasted in a crimson and gold temple robe pooled at her waist, incense smoke and the unrolled scroll",
        nude="nothing but red lacquer hairpins, kneeling in the glow of the great paper lantern with the robe spread behind her and the scroll held low",
        clean="crimson and gold silk temple robe worn closed with a high collar",
        light="red lantern glow and incense haze on gold, warm and devotional",
        motion="incense smoke curling, the lantern flame breathing, the scroll lifting in a draught",
        master="alone in the great hall of a sea goddess temple, towering red lanterns and gilded wave carvings, incense smoke rising in shafts of gold"),
    "teller_tavern": dict(
        who="{adult} Spanish-Filipina woman (age 34), Josefina \"La Golondrina\" Reyes, curvy and vivid with warm brown skin, a mass of dark curls and gold hoop earrings, a tavern singer on a small stage in a smoky waterfront tavern, seated on the edge of a table with a guitar across her knee and a glass of rum raised, head thrown back in a wicked laugh",
        pose="perched on the table edge with the guitar on her knee, one bare foot swinging",
        sultry="plunging scarlet off-shoulder blouse and a tiered skirt hiked above her knee",
        boudoir="blouse off both shoulders and unlaced, tiered skirt hiked high, the guitar held across her chest",
        topless="bare-breasted with the scarlet blouse around her waist, the guitar across her knee, rum glass raised",
        nude="nothing but gold hoops and a red ribbon at her throat, seated on the table edge turned three-quarters with the guitar across her lap and the rum raised, the tiered skirt abandoned beside her",
        clean="scarlet off-shoulder blouse with a modest neckline and a tiered skirt",
        light="warm lantern light, smoky amber haze, sailors' silhouettes behind",
        motion="fingers strumming, hair swinging as she laughs, smoke drifting through lantern light",
        master="alone on a tiny stage in a smoky waterfront tavern, lanterns and sailors' silhouettes in the haze, the harbour glittering beyond the door"),
    "teller_drowned": dict(
        who="{adult} Cornish woman (age 29), Morwenna Teague, the Drowned Bride, pale and beautiful with sea-green eyes and long dark wet hair strung with tiny shells and a strand of pearls, risen from the sea on the moonlit deck of a trading junk, a ship's bell frozen mid-swing beside her, a soft teasing smile meant for one person only",
        pose="standing at the rail with water streaming from the hem, one hand on the frozen bell",
        sultry="a soaked ivory off-shoulder wedding gown clinging to her",
        boudoir="wet ivory gown slipping off her shoulders, the soaked lace clinging and sheer, pearls across her collarbones",
        topless="bare-breasted in a soaked ivory gown slid down to her waist, pearls wound across her collarbones, water streaming over her skin",
        nude="nothing but strands of pearls and wet hair, the sodden gown pooled at her feet, turned half away at the rail with one hand on the frozen bell, water streaming down her back",
        clean="ivory wedding gown with a high lace collar and long sleeves, sea water dripping from the hem",
        light="a faint blue-green glow, moonlight, fog and still black water",
        motion="water dripping from her hair, the bell trembling, fog rolling over the deck",
        master="alone on the moonlit deck of a ghostly trading junk, fog and still black water to the horizon, the frozen bell beside her, a faint blue-green glow rising from the sea"),
    "legend_otohime": dict(
        who="{adult} Japanese woman (age 30), Princess Otohime, tall and exquisite with ink-black hair falling to her hips and pinned with coral and gold, the daughter of the Dragon King in an undersea palace of coral and lacquer, a small black lacquer box tied with a red cord in both hands, a great sea turtle at her side, an amused regal dangerous smile",
        pose="floating upright in the green water, the lacquer box offered in both hands, the robe drifting",
        sultry="a plunging sea-blue and silver court robe trailing in the water like a tail, ropes of pearls",
        boudoir="court robe drifting off her shoulders, ropes of pearls across her bare collarbones, the lacquer box held across her chest",
        topless="bare-breasted in ropes of pearls, the sea-blue court robe drifting around her hips like a tail",
        nude="nothing but ropes of pearls and coral hairpins, her long black hair drifting across her body, the court robe trailing behind like a silver tail, the lacquer box held low in both hands",
        clean="high-collared sea-blue and silver court robe trailing in the water, ropes of pearls",
        light="shafts of green light falling through the water, pearl shimmer, deep teal",
        motion="hair and robe drifting in the current, the sea turtle gliding past, shafts of light rippling",
        master="alone in the great hall of the Dragon King's palace beneath the waves, coral pillars and lacquer gates, shafts of green light, a great sea turtle gliding past"),
}
for _k, _d in _MORE.items():
    _m = _d.pop("master")
    LOOKS[_k] = dict(_d, sultry_v1=_d["sultry"])
    MASTER[_k] = _m
LOOKS["mayor"]["who"] = ("{adult} Black Swahili woman from Zanzibar (age 47), tall, full-figured and commanding, deep brown skin, "
                         "hair wrapped high in an oxblood silk headwrap with heavy gold hoops, the Mayor of a treaty port behind a teak "
                         "harbour-office desk, ledger and iron strongbox before her, gold chain of office, harbour lanterns through the window, "
                         "cool appraising smile")

ALL_TIERS = ("sultry", "boudoir", "topless", "nude", "clean")

def build_master(key, tier="boudoir", mood=None):
    """A wide 16:9 wallpaper master shot of one persona: her look + her own epic scene. Same ladder as build()."""
    if tier not in ALL_TIERS:
        raise ValueError("tier must be one of " + ", ".join(ALL_TIERS))
    look = LOOKS[key]
    if tier == "sultry":
        parts = ["An " + _who(look, tier), look["pose"], look["sultry"], MASTER[key], look["light"]]
    else:
        parts = ["An " + _who(look, tier), look[tier], MASTER[key], look["light"]]
    if mood:
        parts.append(SPICE_MOODS.get(mood, mood))
    return ", ".join(parts) + MASTER_TAIL[tier]


# ---- The Game Master (21 Nov 2026): Madame Anahit Sarkissian, Mistress of the Table. Added in every tier.
# Regal pass (21 Nov 2026): grand, rich, elite ringmistress-royalty. Crimson velvet, gold braid, jewels, a lit hall of grandees.
LOOKS["gamemaster"] = dict(
    who="{adult} Armenian woman (age 44), Madame Anahit Sarkissian, the regal ringmistress-croupier presiding at a gilded gaming table in a Calcutta merchant-palace hall, jewelled brass bell and ivory gavel before her, dark hair swept up beneath a small gold diadem, a ruby collar necklace, a queen's knowing smile",
    sultry="crimson velvet ringmaster's tailcoat with gold braid and ermine lapels open to the waist over a gold-embroidered black corset, white opera gloves, bare collarbones",
    boudoir="crimson velvet tailcoat slipping off both shoulders, black corset laced loose, opera gloves, stockings above gold-capped boots, the ivory gavel held across her chest like a sceptre",
    topless="bare-breasted in an open crimson velvet tailcoat with gold braid and ermine trim, opera gloves, the jewelled bell held up to cover very little, utterly in command",
    light="chandelier and footlight glow on rosewood and gold leaf, amber and crimson velvet shadows, opulent and regal",
    motion="raising the jewelled bell and ringing it once with a sovereign's flourish, the ivory gavel spinning between her gloved fingers, gold dice rolling across green baize, chandelier light flickering")
LOOKS["gamemaster"]["pose"] = "standing tall at the head of the table, one gloved hand on the gavel, the other raising the bell beside her ear, chin lifted, a queen calling the court to order"
LOOKS["gamemaster"]["sultry_v1"] = LOOKS["gamemaster"]["sultry"]
LOOKS["gamemaster"]["clean"] = "crimson velvet ringmaster's tailcoat with gold braid and ermine lapels buttoned over a high-collared white silk blouse with a lace jabot, gold waistcoat chain, white opera gloves"
LOOKS["gamemaster"]["nude"] = "nothing but white opera gloves, the ruby collar necklace and the gold diadem, seated enthroned on the edge of the gilded table with the jewelled bell raised in one hand and the ivory gavel across her knees like a sceptre, a sovereign's dare in her smile"
MASTER["gamemaster"] = "alone at the head of a vast gilded gaming palace at night, a long rosewood table stretching away under crystal chandeliers, gold dice glowing before her, crimson velvet drapes and marble columns"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=ALL_TIERS, default="boudoir")
    ap.add_argument("--who", default="")
    ap.add_argument("--mood", default="")
    ap.add_argument("--master", action="store_true", help="wide 16:9 wallpaper master shots instead of portraits")
    a = ap.parse_args()
    keys = [k for k in (a.who.split(",") if a.who else LOOKS) if k]
    bad = 0
    for k in keys:
        p = (build_master if a.master else build)(k, a.tier, a.mood or None)
        ok = ADULT in p and "(age " in p
        bad += not ok
        print("== {} [{} words{}]\n{}\n   motion: {}\n".format(k, len(p.split()), "" if ok else ", MISSING ADULT ANCHOR", p, motion(k)))
    print("{} prompts, tier {}, {} missing the adult anchor".format(len(keys), a.tier, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
