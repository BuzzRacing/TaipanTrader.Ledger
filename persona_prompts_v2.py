"""Taipan Trader persona prompts: one dressed, family-friendly look per persona.

Forked from Crimson Ledger's persona prompts. Taipan Trader is family-friendly only, so every persona has a single
look ("clean"). The old tier names (sultry, boudoir, topless, nude) are kept only so older callers still work, and
every one of them gives the clean look.

Usage (dry run, prints every prompt with its word count):
    python persona_prompts_v2.py
    python persona_prompts_v2.py --who bookkeeper,officer_batavia
    python persona_prompts_v2.py --master            (wide 16:9 wallpaper master shots)
In code:
    import persona_prompts_v2 as pp
    pp.build("bookkeeper", "clean", mood="smile")    # a full prompt string
    pp.motion("bookkeeper")                          # the Wan 2.2 movement line
"""
import argparse
import sys

ADULT = "adult"

# The tail starts with ", romanticized" on purpose: callers split prompts on it.
_TAIL = (", romanticized 1860 China Seas photograph, elegant fully dressed styling, natural skin, "
         "confident direct gaze, hands in frame, 3:4 portrait")
_MASTER_TAIL = (", romanticized 1860 China Seas photograph, epic cinematic wallpaper master shot, elegant fully dressed "
                "styling, low heroic camera angle, rich depth and atmosphere, confident direct gaze, 16:9")
ALL_TIERS = ("sultry", "boudoir", "topless", "nude", "clean")
TIERS = ALL_TIERS
TAIL = {t: _TAIL for t in ALL_TIERS}
MASTER_TAIL = {t: _MASTER_TAIL for t in ALL_TIERS}

# Short expression lines (a mood is an expression, never a costume).
SPICE_MOODS = {
    "teasing": "a teasing sidelong look, as if about to share a joke",
    "caught_looking": "eyebrows raised in mock surprise, as if caught mid-thought",
    "after_hours": "relaxed and smiling, a cup of tea in hand, the office closed for the night",
    "dare": "chin lifted, one eyebrow raised, a dare written all over the smile",
    "wink": "a slow wink and a half-smile",
    "triumph": "head thrown back in a delighted laugh, flushed with winning",
    "pout": "a mock frown, arms crossed, pretending to be cross with you",
    "purr": "chin on one hand, smiling over a secret to be shared for a price",
}

# who:    identity and setting, the one thing that must not change between pictures.
# clean:  the costume.
# light:  the persona's own light and photographic mood.
# motion: what moves in a Wan 2.2 loop (movement only; the look comes from the picture).
LOOKS = {'narrator': {'who': '{adult} Parsi woman (age 41), the pirate first mate on a schooner quarterdeck in Hong Kong '
                     'harbour at dusk, black logbook under one arm, brass chronometer in her hand',
              'clean': 'lacquer-black frock coat buttoned over an ivory high-collared blouse, oxblood sash, black '
                       'Parsi topi',
              'light': 'low gold dusk light, warm soft focus, fine film grain',
              'motion': 'coat tails and loose strands of hair stirring in the sea breeze, chronometer chain '
                        'swinging, a slow knowing blink'},
 'bosun': {'who': '{adult} Irish man (age 38), broad-shouldered pirate bosun and master gunner beside a smoking '
                  'brass cannon, red beard and wild red hair, powder smudges on his face and forearms, coil of slow '
                  'match in one hand, fierce laughing grin',
           'clean': 'tobacco-leather waistcoat buttoned over a linen shirt, oxblood sash, sleeves rolled, leather '
                    'gun belt',
           'light': 'hard orange gun-flash from one side, smoke haze, high contrast',
           'motion': 'smoke curling off the cannon, hair whipping in the wind, the slow match glowing and swinging'},
 'lender': {'who': '{adult} Cantonese woman (age 63), the silver-haired Silver Queen of Hong Kong behind a rosewood '
                   'desk in a lamplit counting house, abacus, silver dollars and ledgers before her, a faint knowing '
                   'smile',
            'clean': 'dark Qing-era silk jacket with a high mandarin collar and imperial-jade fastenings',
            'light': 'warm lamplight with a soft glow, rich amber shadows, velvet depth',
            'motion': 'lamp flame flickering, a slow slide of one abacus bead, her fan opening and closing'},
 'pirate': {'who': '{adult} Cantonese woman (age 48), the Pirate Queen of the South China Sea on the stern deck of a '
                   'great war junk at night, elaborate pinned hair, a single white peony on the rail, cold and '
                   'utterly calm',
            'clean': 'dark quilted silk robe closed over sculpted leather armour, high collar, oxblood sash',
            'light': 'lantern light from below, deep blue night, a rim of silver moon',
            'motion': 'lantern flames swaying, robe silk lifting in the night wind, the peony petals trembling'},
 'agent': {'who': "{adult} Macanese-Chinese woman (age 37), the pirate queen's dangerously glamorous agent seated in "
                  'a lacquered tea house on the Hong Kong waterfront, small ivory coin balance before her, red silk '
                  'protection token between two fingers, commanding pose and knowing half-smile',
           'clean': 'fitted oxblood Qing-era silk jacket with sheer sleeves over a high-necked under-blouse, gold '
                    'hairpins',
           'light': 'red paper-lantern glow, warm smoky haze, soft shadows',
           'motion': 'steam curling from the teacup, the red token swinging between her fingers, lantern light '
                     'shimmering on silk'},
 'banker': {'who': "{adult} Scottish man (age 52), tall, lean chief cashier behind a brass teller's grille in a Hong "
                   'Kong bank, steel spectacles, neat auburn side-whiskers going grey, leather gloves, silver '
                   'dollars and a ledger before him, cool appraising gaze',
            'clean': 'severe lacquer-black frock coat over a burgundy silk waistcoat, high white collar and black '
                     'cravat',
            'light': "cool green banker's-lamp light against warm brass, crisp and glossy",
            'motion': 'slow fingertip tapping on the counter, a stack of silver dollars being counted, brass grille '
                      'glinting'},
 'comprador': {'who': '{adult} Cantonese man (age 45), stout, prosperous comprador in a busy godown of tea chests '
                      'and silk bales, round shrewd face, thin moustache, long queue, abacus under one arm and '
                      'writing brush in hand, confident appraising look',
               'clean': 'storm-blue Qing-era silk changshan with jade buttons, black silk skullcap, jade ring',
               'light': 'sticky golden tropical light through shutters, glossy skin, soft focus',
               'motion': 'abacus beads clicking, dust motes drifting in the shutter light, a slow fan of his hand '
                         'against the heat'},
 'shipwright': {'who': '{adult} Cantonese man (age 56), muscular master shipwright beside a half-built junk hull, '
                       'adze on one shoulder, sawdust on sun-browned forearms, grey-streaked hair tied back, '
                       'weathered hands on teak, proud gruff smile',
                'clean': 'linen shirt buttoned with sleeves rolled, a leather work apron over it, cloth wrapped at '
                         'the wrists',
                'light': 'late sun through the unfinished ribs of the hull, warm shafts, gentle haze',
                'motion': 'sawdust drifting through the light, the adze tapped lightly against his palm, a slow '
                          'proud grin'},
 'customs': {'who': '{adult} English man (age 39), tall and powerfully built, close-cropped fair hair and a clipped '
                    'moustache, fierce customs inspector on a crowded Shanghai wharf, pith helmet under one arm, '
                    'manifest clipboard and boarding pistol, crates opened behind him, stern glare',
             'clean': 'storm-blue uniform coat with brass buttons fastened to the collar, white cross-belt',
             'light': 'hard morning wharf light, crisp shadows, glossy highlights',
             'motion': 'flags snapping in the wind behind him, a slow tap of the clipboard against his palm'},
 'crier': {'who': '{adult} English man (age 29), wiry, grinning news crier on the Hong Kong waterfront, holding a '
                  'fresh broadsheet and brass handbell, ink on his fingers, tousled auburn hair under a battered '
                  'cocked hat, one boot on a bollard, mid-call',
           'clean': 'short tobacco-leather jacket over a striped shirt and neckerchief, oxblood trousers tucked into '
                    'boots',
           'light': 'bright cheeky harbour sunshine, sparkle on the water, high-key and playful',
           'motion': 'handbell ringing and swinging, broadsheet fluttering, coat tails flapping in the harbour '
                     'breeze'},
 'bookmaker': {'who': '{adult} Macanese woman (age 34), the bookmaker of the Golden Fan, leaning over a lacquered '
                      'fan-tan table with one ringed hand on a gold-and-jade abacus, a chalked odds board behind '
                      'her, glossy black hair pinned with a gold fan comb, amused gaze straight into the camera',
               'clean': 'black silk cheongsam-cut gown with oxblood and gold embroidery and a high mandarin collar, '
                        'jade drop earrings',
               'light': 'green baize glow with warm lantern smoke, casino chiaroscuro, glossy highlights',
               'motion': 'lantern smoke drifting, a coin spinning on the table, the golden fan flicking open'},
 'mayor': {'who': '{adult} Black Swahili woman from Zanzibar (age 47), tall, full-figured and commanding, deep brown '
                  'skin, hair wrapped high in an oxblood silk headwrap with heavy gold hoops, the Mayor of a treaty '
                  'port behind a teak harbour-office desk, ledger and iron strongbox before her, gold chain of '
                  'office, harbour lanterns through the window, cool appraising smile',
           'clean': 'fitted pirate frock coat buttoned over a high-necked blouse, the gold chain of office across '
                    'her chest',
           'light': 'warm harbour dusk through the window, gold rim light, regal and unhurried',
           'motion': 'the chain of office swinging, lantern light flickering through the window, a slow turn of one '
                     'link between her fingers'},
 'taxlady': {'who': '{adult} English woman (age 36), Mrs. Evelyn Marlowe, the widowed Registrar of the Port of Hong '
                    'Kong at a harbour-office desk on a foggy wharf, dark hair pinned up with spectacles pushed up '
                    'into it, open ledger and a jade-topped pencil, conspiratorial half-smile',
             'clean': 'black coat buttoned over an oxblood high-collared blouse, a ribbon at her throat',
             'light': 'soft fog-diffused window light, pearly and intimate, gentle shadows',
             'motion': 'spectacles pushed up into her hair, a pencil tapped against her lip, fog drifting past the '
                       'window'},
 'bookkeeper': {'who': "{adult} French-Indian woman (age 38), Mademoiselle Celeste Vautrin, the House's private "
                       'bookkeeper seated upright at a rosewood desk in a lamplit counting room above the Hong Kong '
                       'wharf, a great crimson-bound ledger open before her, quill in her ink-stained fingers, '
                       'gold wire spectacles low on her nose, a wry appraising gaze over the rims',
                'clean': 'black silk blouse buttoned to the collar under an oxblood waistcoat, gold wire spectacles',
                'light': 'candle glow, warm brass and silver highlights, deep red shadows, intimate',
                'motion': 'candle flame flickering, the quill drawn slowly across her lower lip, a page turning'},
 'officer_singapore': {'who': '{adult} English man (age 44), portly and genial with thinning sandy hair, the languid '
                              'Port Authority officer of Singapore lounging in a rattan chair on a shaded colonial '
                              'wharf-office veranda, a glass of lime cordial in one hand and a customs stamp '
                              'dangling forgotten from the other, ceiling fan and palms, heavy-lidded amused gaze',
                       'clean': 'rumpled white linen suit with a loosened cravat and a straw boater',
                       'light': 'hot dappled veranda light through palms, hazy and honeyed',
                       'motion': 'ceiling fan turning, palm shadows moving across his skin, ice shifting in the '
                                 'glass'},
 'officer_manila': {'who': '{adult} Spanish-Filipina woman (age 38), the charming Port Authority officer of Manila '
                           'in a carved narra-wood customs office, fan of Manila embroidery in one hand, ivory '
                           'customs seal in the other, bales of silk behind her, inviting smile and hungry eyes',
                    'clean': 'black lace mantilla gown with a high neckline and a crimson silk sash',
                    'light': 'warm candlelight on carved wood, golden and soft, lace shadows across her skin',
                    'motion': 'fan fluttering, candle flames bending, lace mantilla stirring in a draught'},
 'officer_saigon': {'who': '{adult} French woman (age 33), the mercurial colonial Port Authority officer of Saigon '
                           'reclining on a chaise in a shuttered customs house, a glass of absinthe and a gold coin '
                           'on the table beside an open ledger, a teasing sidelong smile',
                    'clean': 'violet silk day dress with a high neckline and a tricolour sash',
                    'light': 'slatted tropical light striping her skin, warm and humid, soft shutter shadows',
                    'motion': 'the gold coin flipping and catching the light, shutter light sliding across her skin, '
                              'absinthe swirling in the glass'},
 'officer_nagasaki': {'who': '{adult} Japanese man (age 35), slender and composed, hair in a neat topknot, the '
                             'ledger-keeper of the Dejima customs house in Nagasaki at a low lacquered desk with '
                             'brush, abacus and open ledger, calm unblinking gaze',
                      'clean': 'deep indigo silk kimono and hakama, neatly worn',
                      'light': 'soft paper-lantern glow, pale and quiet, delicate shadows',
                      'motion': 'paper lantern light flickering, a slow brushstroke, silk stirring as he breathes'},
 'officer_foochow': {'who': '{adult} Chinese woman (age 40), the Port Authority officer of Foochow serving tea in a '
                            'customs house hung with tea-chest labels, jade pins in her black hair, a steaming clay '
                            'teapot tilted in her hand, a slow knowing smile',
                     'clean': 'jade-green silk qipao buttoned to the collar',
                     'light': 'soft river light through lattice, pearly green, dreamy and warm',
                     'motion': 'steam rising from the teapot, tea pouring in a slow stream, lattice shadows moving'},
 'officer_shanghai': {'who': '{adult} Ningbo Chinese man (age 37), imposing and broad, shaven forehead and long '
                             'queue, the collector of the Bund behind a carved desk, clerks waiting, the Shanghai '
                             'riverfront behind him, commanding amused gaze',
                      'clean': 'fitted oxblood brocade magua jacket over a black silk robe, mandarin hat with a '
                               'coral button',
                      'light': 'crisp Bund morning light, bright and glossy, crisp rim light on his hair',
                      'motion': 'baton tapping, brocade shifting in the river wind, a slow lift of one eyebrow'},
 'officer_bangkok': {'who': '{adult} Siamese man (age 42), dignified court official with close-cropped greying hair, '
                            "keeper of the King's river tolls at Bangkok in a teak pavilion over the Chao Phraya, "
                            'jasmine garland in hand, gracious steady gaze',
                     'clean': 'gold-threaded silk raj pattern jacket buttoned high over a silk chong kraben',
                     'light': 'warm river-reflected light on gold leaf, glowing and serene',
                     'motion': 'jasmine petals drifting, river light rippling across the gold, silk stirring in the '
                               'breeze'},
 'officer_batavia': {'who': '{adult} Dutch woman (age 39), the strict Port Authority officer of Batavia in a '
                            'whitewashed VOC customs hall, a long brass ruler resting across an open ledger, spectacles '
                            'low on her nose, pale blonde hair pinned tight, a stern stare with a flicker of dry '
                            'amusement',
                     'clean': 'severe black lace-collared gown buttoned to the throat, long black gloves',
                     'light': 'cool whitewashed hall light with a warm hard accent, crisp and glossy',
                     'motion': 'the crop tapping once per column, dust drifting in the hall light, a slow lowering '
                               'of her spectacles'},
 'officer_calcutta': {'who': '{adult} English man (age 46), sleek and silver-haired with a waxed moustache, the '
                             'collector of the port of Calcutta at a vast mahogany desk in a hall of pillars, '
                             'punkahs swaying, strongboxes behind him, sweet poisonous smile',
                      'clean': 'midnight-purple frock coat over a silk waistcoat, ruby tie pin, white gloves',
                      'light': 'swaying punkah shadows, deep plum and gold, luxurious and slow',
                      'motion': 'punkah fan swaying overhead, peacock feathers stirring, rubies catching the light'},
 'officer_hongkong': {'who': '{adult} Portuguese woman (age 33), the Port Authority officer of Hong Kong on a '
                             'crowded Victoria Harbour wharf, a gold crucifix and a dagger at her hip, leaning over '
                             'a customs desk with a manifest upside down before her, a slow dangerous smile',
                      'clean': 'wine-red silk jacket buttoned over a black lace blouse',
                      'light': 'bright harbour glare with warm reflected water-light, glossy and bold',
                      'motion': 'the crucifix swinging, lorchas bobbing behind her, a slow lean across the desk'},
 'warden_hongkong': {'who': '{adult} English man (age 52), tall, broad-shouldered and grizzled with iron-grey '
                            'mutton-chop whiskers, the governor of Victoria Gaol in Hong Kong in 1860, standing at '
                            'an open iron cell door with one hand on the bars and a great ring of brass keys at his '
                            'belt, lamplight on whitewashed stone, a dry, knowing half-smile',
                     'clean': "dark blue gaoler's frock coat buttoned to the collar, wide leather belt",
                     'light': 'lamplight on whitewashed stone, cold grey-gold, striped with shadows of bars',
                     'motion': 'the key ring swinging from his finger, lamp flame wavering, his knowing smile slowly '
                               'widening'},
 'warden_singapore': {'who': '{adult} English woman (age 36), Miss Rosalind Pell, slim with sun-browned skin and '
                             "chestnut curls pinned up loosely, the keeper of the Pearl's Hill lock-up in Singapore "
                             'leaning against barred teak doors, a pith helmet tipped back, a ring of keys twirled '
                             'on one finger, a bright teasing smile, playful and in charge',
                      'clean': "crisp white linen officer's tunic buttoned to the collar, pith helmet, key ring at "
                               'her belt',
                      'light': 'slatted tropical sunlight striping skin and teak, bright and warm',
                      'motion': 'the keys twirling, the helmet tipping further back with a wink, slatted light '
                                'drifting'},
 'warden_manila': {'who': '{adult} Spanish man (age 48), lean and severe with a trimmed black beard, the alcaide of '
                          'the Bilibid prison in Manila in 1860, a rosary in one hand and a ring of keys in the '
                          'other, stone archway and iron grille behind him, cold pious gaze',
                   'clean': 'black military frock coat buttoned to the throat with a crimson sash',
                   'light': 'candlelight gold on old stone, warm and heavy',
                   'motion': 'candle flames bending, the rosary swaying, a slow lift of his chin'},
 'warden_saigon': {'who': '{adult} Corsican-French woman (age 41), Madame Odile Marchetti, lean with olive skin and '
                          'cropped black hair, the gardienne of the Maison Centrale in Saigon seated on a stool '
                          'before a cell, a hand of playing cards fanned against the bars, a thin smile on her lips, '
                          'an amused, bored, dangerous look',
                   'clean': 'military coat buttoned to the collar over a white blouse, pistol belt, cards in one '
                            'hand',
                   'light': 'shuttered tropical bars of light across her skin, cigarette smoke curling',
                   'motion': 'smoke curling from the cigarette, cards flicking between her fingers, a bored slow '
                             'blink'},
 'warden_nagasaki': {'who': '{adult} Japanese woman (age 44), Kuroda Hisa, slender and composed, black hair in a '
                            "tight samurai-wife's knot, the warden of the Sakuramachi gaol kneeling upright on a "
                            'tatami platform before a wooden lattice cell, a brush and an open register before her, '
                            'a ring of iron keys beside her knee, a perfectly calm unreadable stare',
                     'clean': 'dark indigo kimono neatly worn and tied with the obi, keys at her knee',
                     'light': 'paper lantern glow on pale skin, soft amber, deep still shadows',
                     'motion': 'the brush moving once across the register, lantern light breathing, a slow blink'},
 'warden_foochow': {'who': '{adult} Fujianese man (age 50), wiry and patient with a long grey queue and a thin '
                           'beard, the keeper of the Min River yamen cells in Foochow in 1860, seated by a wooden '
                           'cell door with a teapot and a single cup, lantern light, soft knowing smile',
                    'clean': "plain dark blue yamen official's robe, black cap",
                    'light': 'smoky lantern light, warm and soft, river mist at the bars',
                    'motion': 'steam curling from the tea, the lantern swaying, a slow knowing smile'},
 'warden_shanghai': {'who': '{adult} Chinese woman (age 39), Madam Tang Xiu-ying, tall and athletic with a sharp jaw '
                            'and strong legs, black hair in a long braid over one shoulder, the gaoler of the Mixed '
                            'Court cells in Shanghai striding down a stone corridor of iron-barred cells, a bamboo '
                            'rod resting on her shoulder, a cold commanding stare',
                     'clean': 'black riding jacket buttoned to the collar, gloves and boots, leather key strap '
                              'across her chest',
                     'light': 'cold blue gaslight on stone, hard and clean',
                     'motion': 'the braid swinging as she strides, the rod tapping the bars, gaslight flickering'},
 'warden_bangkok': {'who': '{adult} Thai court lady (age 46), Khun Ying Prapai, graceful and full-figured with short '
                           "court-style hair, the keeper of the King's prison at a teak-barred cell in a gilded "
                           'courtyard, a lotus bud in one hand and a ring of keys in the other, a gracious immovable '
                           'smile',
                    'clean': 'gold-threaded silk sabai draped neatly over a fitted silk blouse, gold armlets',
                    'light': 'warm river light on gold and teak, soft haze',
                    'motion': 'the lotus bud turning in her fingers, the gold chain glinting, a slow gracious smile'},
 'warden_batavia': {'who': '{adult} Dutch man (age 45), stout and red-cheeked with a clipped fair beard, the gaoler '
                           'of the Batavia Stadhuis cells in 1860, reading from a long printed list of rules beneath '
                           'whitewashed vaults, keys at his belt, dry wicked smile',
                    'clean': 'black coat with a starched white collar, buttoned waistcoat',
                    'light': 'lantern light in a vaulted brick cellar, warm orange against cold shadow',
                    'motion': 'the lantern swaying, the list of rules fluttering, one eyebrow lifting'},
 'warden_calcutta': {'who': '{adult} English man (age 49), plump and kindly-faced with white side-whiskers and '
                            'spectacles, the superintendent of the Presidency Jail in Calcutta in 1860, holding a '
                            'folded blanket and a ring of keys by a barred door, punkah and lamplight, warm '
                            'unsettling smile',
                     'clean': 'white linen coat buttoned high over a waistcoat, black cravat',
                     'light': 'punkah-stirred air, warm lamplight on skin and iron, honey gold',
                     'motion': 'the punkah swaying, the keys jingling, a fatherly tilt of his head'},
 'teller_temple': {'who': '{adult} Chinese woman (age 47), Mother Chen Sui-lan, graceful and full-figured with a '
                          'calm beautiful face, long black hair pinned up with red lacquer pins, the keeper of the '
                          'lantern at a sea goddess temple on the Fujian coast kneeling beside a great glowing red '
                          'paper lantern, incense smoke curling around her, gilded carvings of waves and dragons '
                          'behind, an open scroll across her lap, a serene knowing smile as if she has already read '
                          'the ending',
                   'clean': 'crimson and gold silk temple robe worn closed with a high collar',
                   'light': 'red lantern glow and incense haze on gold, warm and devotional',
                   'motion': 'incense smoke curling, the lantern flame breathing, the scroll lifting in a draught'},
 'teller_tavern': {'who': '{adult} Spanish-Filipina woman (age 34), Josefina "La Golondrina" Reyes, vivid with warm '
                          'brown skin, a mass of dark curls and gold hoop earrings, a tavern singer on a small stage '
                          'in a smoky waterfront tavern, seated on the edge of a table with a guitar across her knee '
                          'and a glass of rum raised, head thrown back in a wicked laugh',
                   'clean': 'scarlet off-shoulder blouse with a modest neckline and a tiered skirt',
                   'light': "warm lantern light, smoky amber haze, sailors' silhouettes behind",
                   'motion': 'fingers strumming, hair swinging as she laughs, smoke drifting through lantern light'},
 'teller_drowned': {'who': '{adult} Cornish woman (age 29), Morwenna Teague, the Drowned Bride, pale and beautiful '
                           'with sea-green eyes and long dark wet hair strung with tiny shells and a strand of '
                           "pearls, risen from the sea on the moonlit deck of a trading junk, a ship's bell frozen "
                           'mid-swing beside her, a soft sad smile',
                    'clean': 'ivory wedding gown with a high lace collar and long sleeves, sea water dripping from '
                             'the hem',
                    'light': 'a faint blue-green glow, moonlight, fog and still black water',
                    'motion': 'water dripping from her hair, the bell trembling, fog rolling over the deck'},
 'legend_otohime': {'who': '{adult} Japanese woman (age 30), Princess Otohime, tall and exquisite with ink-black '
                           'hair falling to her hips and pinned with coral and gold, the daughter of the Dragon King '
                           'in an undersea palace of coral and lacquer, a small black lacquer box tied with a red '
                           'cord in both hands, a great sea turtle at her side, an amused regal dangerous smile',
                    'clean': 'high-collared sea-blue and silver court robe trailing in the water, ropes of pearls',
                    'light': 'shafts of green light falling through the water, pearl shimmer, deep teal',
                    'motion': 'hair and robe drifting in the current, the sea turtle gliding past, shafts of light '
                              'rippling'},
 'gamemaster': {'who': '{adult} Armenian woman (age 44), Madame Anahit Sarkissian, the regal ringmistress-croupier '
                       'presiding at a gilded gaming table in a Calcutta merchant-palace hall, jewelled brass bell '
                       'and ivory gavel before her, dark hair swept up beneath a small gold diadem, a ruby collar '
                       "necklace, a queen's knowing smile",
                'clean': "crimson velvet ringmaster's tailcoat with gold braid and ermine lapels buttoned over a "
                         'high-collared white silk blouse with a lace jabot, gold waistcoat chain, white opera '
                         'gloves',
                'light': 'chandelier and footlight glow on rosewood and gold leaf, amber and crimson velvet shadows, '
                         'opulent and regal',
                'motion': "raising the jewelled bell and ringing it once with a sovereign's flourish, the ivory "
                          'gavel spinning between her gloved fingers, gold dice rolling across green baize, '
                          'chandelier light flickering'},
 'thieves': {'who': '{adult} Tamil woman (age 31), Kamala "Magpie" Pillai, the pickpocket queen of a crowded '
                    'Singapore quay market at night, long dark braid wound with jasmine, a small brass nose-stud, '
                    "one hand lifting a fat purse from a captain's coat while the other holds a peacock feather and "
                    'a china teacup, a mischievous grin as if you have already noticed and do not mind',
             'clean': 'teal silk jacket buttoned over an ivory high-collared blouse, a wide gold-threaded sash, '
                      'jasmine in her braid, bangles on one wrist',
             'light': 'lantern-lit night market, warm amber lamps against a cool teal haze, playful sparkle on silk '
                      'and brass',
             'motion': 'peacock feather twirling between her fingers, purses swinging from her sash, her hand '
                       'sliding slyly into a coat pocket, lantern light flickering'}}

MASTER = {'narrator': 'alone at the helm of the schooner as a typhoon front glows crimson behind her, brass instruments '
             'gleaming, the lights of Hong Kong spread far below',
 'bosun': 'alone in a smoke-filled gun deck framed by a blazing broadside, rows of brass cannon firing, sparks and '
          'embers drifting past him',
 'lender': 'enthroned behind a vast rosewood desk in a grand lamplit counting house, mountains of silver dollars and '
           'towering ledger shelves rising into shadow behind her',
 'pirate': 'alone on the stern of her flagship at the head of a night fleet of black-sailed war junks, lanterns '
           'stretching to the horizon, a storm breaking behind her',
 'agent': 'alone in a grand lantern-hung tea house above the Praya at night, red silk banners cascading, the harbour '
          'glittering through open screens',
 'banker': 'alone at the heart of the great vault hall, walls of iron safes and brass grilles receding into shadow, '
           'shafts of gaslight falling on him',
 'comprador': 'alone in a cathedral of silk bales and tea chests in a vast godown, shafts of golden light pouring '
              'through high shutters',
 'shipwright': 'alone before a towering half-built junk on the slip at sunset, ribs of timber soaring above him, '
               'sparks and sawdust glowing in the light',
 'customs': 'alone on the Bund wharf steps at dawn above a harbour full of ships, flags snapping, a mountain of '
            'seized crates at his feet',
 'crier': 'high in the rigging above the Hong Kong waterfront at golden hour, broadsheets fluttering down around him '
          'like confetti',
 'bookmaker': 'alone at the head of a grand fan-tan hall, green baize tables stretching away, chandeliers and '
              'lantern smoke, a towering odds board blazing behind her',
 'mayor': 'alone at the great window of the harbour office at dusk, the whole port and its fleet glittering below, '
          'the chain of office catching the light',
 'taxlady': 'alone on the harbour-office steps in rolling fog, a great ledger open in her arms, ship lanterns '
            'glowing like stars through the mist',
 'bookkeeper': 'alone in her lamplit counting room above the wharf, walls of crimson ledgers rising into shadow, a '
               'window full of moonlit harbour behind her',
 'officer_singapore': 'alone on a vast colonial veranda at sunset, palms and the Singapore roads blazing orange '
                      'beyond the balustrade',
 'officer_manila': 'alone in a grand narra-wood customs hall under hanging lanterns, mountains of silk bales and '
                   'porcelain lit gold around her',
 'officer_saigon': 'alone on a chaise in a vast shuttered customs hall, bars of tropical light slicing across the '
                   'floor, ceiling fans turning slowly overhead',
 'officer_nagasaki': 'alone on a tatami platform in a lantern-lit hall above Dejima bay, paper screens glowing, mist '
                     'drifting over the water beyond',
 'officer_foochow': 'alone in a tea-house hall hung with tea-chest banners, river mist and green hills glowing '
                    'through carved lattice behind her',
 'officer_shanghai': 'alone on the Bund customs house steps at dawn, the whole skyline of ships and godowns '
                     'stretched behind him, brocade banners snapping',
 'officer_bangkok': 'alone in a gilded river pavilion at golden hour, temple spires and royal barges glowing on the '
                    'river behind him',
 'officer_batavia': 'alone at the head of a whitewashed VOC hall of columns and ledgers, long shafts of cold light '
                    'and a wall of iron strongboxes behind her',
 'officer_calcutta': 'alone at a vast mahogany desk in a Strand Road hall of pillars, punkahs swaying, a wall of '
                     'open strongboxes and rubies glittering behind him',
 'officer_hongkong': 'alone on a crowded Victoria Harbour quay at golden hour, lorchas and junks packed behind her, '
                     'the Peak glowing in the haze',
 'warden_hongkong': 'alone in the long whitewashed corridor of Victoria Gaol, tiers of iron cell doors receding into '
                    'lamplit shadow, the great key ring raised in one hand',
 'warden_singapore': "alone before the great barred teak doors of the Pearl's Hill lock-up at noon, hard stripes of "
                     'tropical sun cutting through the slats, a ring of keys spinning in one hand',
 'warden_manila': 'alone in the vaulted candlelit corridor of the Bilibid, stone arches and iron grilles receding '
                  'into gold shadow, his black coat stirring in a draught',
 'warden_saigon': 'alone in the shuttered central hall of the Saigon Maison Centrale, bars of tropical light slicing '
                  'across tiers of cells, smoke drifting, a stool and a fanned hand of cards',
 'warden_nagasaki': 'alone on the tatami platform of the Sakuramachi gaol, a long wooden lattice of cells receding '
                    'behind her, paper lanterns glowing, rain on the roof',
 'warden_foochow': 'alone in a lantern-lit yamen corridor of wooden cells above the Min River, river mist drifting '
                   'through the lattice, a cup of tea steaming in his hands',
 'warden_shanghai': 'alone at the centre of a vast stone corridor of iron-barred cells under cold gaslight, '
                    'perspective lines racing to a far door, the bamboo rod on her shoulder',
 'warden_bangkok': 'alone in a gilded palace courtyard of teak-barred cells, temple spires and golden light beyond '
                   'the gate, lotus petals drifting on a still pool',
 'warden_batavia': 'alone in a vast vaulted brick cellar beneath the Stadhuis, rows of iron grilles and arches '
                   'receding into lantern-lit gloom',
 'warden_calcutta': 'alone in a pillared Presidency Jail gallery, punkahs swaying overhead, tiers of barred doors '
                    'lit honey gold, a folded blanket over his arm',
 'teller_temple': 'alone in the great hall of a sea goddess temple, towering red lanterns and gilded wave carvings, '
                  'incense smoke rising in shafts of gold',
 'teller_tavern': "alone on a tiny stage in a smoky waterfront tavern, lanterns and sailors' silhouettes in the "
                  'haze, the harbour glittering beyond the door',
 'teller_drowned': 'alone on the moonlit deck of a ghostly trading junk, fog and still black water to the horizon, '
                   'the frozen bell beside her, a faint blue-green glow rising from the sea',
 'legend_otohime': "alone in the great hall of the Dragon King's palace beneath the waves, coral pillars and lacquer "
                   'gates, shafts of green light, a great sea turtle gliding past',
 'gamemaster': 'alone at the head of a vast gilded gaming palace at night, a long rosewood table stretching away '
               'under crystal chandeliers, gold dice glowing before her, crimson velvet drapes and marble columns',
 'thieves': 'alone in a lantern-lit Singapore quay market at dusk, stalls and hanging lamps and sampans receding '
            'behind her, a peacock feather in her hand and purses swinging from her sash, the crowd a blur of silk '
            'and steam'}

for _l in LOOKS.values():
    for _t in ALL_TIERS:
        _l[_t] = _l["clean"]


def _who(look, tier=None, identity=None):
    """The identity line. identity is the one edited in Cast & Voices (see identity_from_prompt)."""
    return identity or look["who"].format(adult=ADULT)


def identity_from_prompt(key, saved):
    """The identity written in a Cast & Voices portrait prompt: everything between the leading "An " and the
    costume. Returns None (the code's own identity is used) when the prompt has been rewritten beyond recognition."""
    text = str(saved or "").strip()
    if key not in LOOKS or not text.startswith("An "):
        return None
    cut = text.find(", " + LOOKS[key]["clean"])
    if cut < 0:
        return None
    ident = text[3:cut].strip()
    if len(ident) < 40 or "(age " not in ident:
        return None
    return ident


def build(key, tier="clean", mood=None, saved=None):
    """A full prompt for one persona. tier is accepted for older callers; every tier is the dressed look."""
    if tier not in ALL_TIERS:
        raise ValueError("tier must be one of " + ", ".join(ALL_TIERS))
    look = LOOKS[key]
    ident = identity_from_prompt(key, saved) if saved else None
    parts = ["An " + _who(look, tier, ident), look["clean"], look["light"]]
    if mood:
        parts.append(SPICE_MOODS.get(mood, mood))
    return ", ".join(parts) + _TAIL


def motion(key):
    """The Wan 2.2 movement line for the picture (movement only; the look comes from the picture)."""
    return LOOKS[key]["motion"]


def build_master(key, tier="clean", mood=None, saved=None):
    """A wide 16:9 wallpaper master shot of one persona: the look plus the persona's own epic scene."""
    if tier not in ALL_TIERS:
        raise ValueError("tier must be one of " + ", ".join(ALL_TIERS))
    look = LOOKS[key]
    ident = identity_from_prompt(key, saved) if saved else None
    parts = ["An " + _who(look, tier, ident), look["clean"], MASTER[key], look["light"]]
    if mood:
        parts.append(SPICE_MOODS.get(mood, mood))
    return ", ".join(parts) + _MASTER_TAIL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default="")
    ap.add_argument("--mood", default="")
    ap.add_argument("--master", action="store_true", help="wide 16:9 wallpaper master shots instead of portraits")
    a = ap.parse_args()
    keys = [k for k in (a.who.split(",") if a.who else LOOKS) if k]
    for k in keys:
        p = (build_master if a.master else build)(k, "clean", a.mood or None)
        print("== {} [{} words]\n{}\n   motion: {}\n".format(k, len(p.split()), p, motion(k)))
    print("{} prompts".format(len(keys)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
