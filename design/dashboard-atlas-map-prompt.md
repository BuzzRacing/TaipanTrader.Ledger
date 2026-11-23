# Command Center sea chart — image brief

**Project:** Crimson Ledger / SeaTrader
**Prepared:** 22 November 2026
**Used by:** Captain's Atlas and Monsoon Observatory (Command Center tabs)
**Decision:** a new painted map in the mockup's style (Question B, 22 Nov 2026)

## What the picture is for

One background chart that both tabs share. The page draws everything that
carries meaning on top of it: the ten port markers and names, share and
warehouse badges, commission routes, and the weather for each sea. So the
picture must be **quiet, dark and unlabelled**. Any lettering, port dot, route
line or storm painted into it would contradict the live data.

## Geography it must cover

The game's chart runs from longitude 85°E to 135°E and latitude 10°S to 35°N,
drawn flat (equal degrees), which is a **10:9 shape, slightly wider than tall**.

Left to right and top to bottom it has to show, in their true places:

- the Bay of Bengal and the mouth of the Ganges (Calcutta) on the far left;
- the Malay Peninsula, the Gulf of Siam (Bangkok) and Singapore at its tip;
- Sumatra, Java (Batavia) and Borneo along the bottom;
- Indochina's coast (Saigon) and the South China Sea in the middle;
- the China coast from Hong Kong up past Foochow to Shanghai;
- the Philippines (Manila), Formosa, and the foot of Japan (Nagasaki) on the
  right;
- open water for the four seas: Yellow Sea & Japan, South China Sea,
  Straits & Java Sea, Bay of Bengal.

## Generation prompt

Use case: historical-map. Asset type: full-bleed background sea chart for the
Crimson Ledger Command Center, an 1860 China Seas merchant trading game. One
antique hand-painted nautical chart of East and Southeast Asia seen straight
from above, flat equirectangular projection, north at the top, covering
longitude 85 to 135 east and latitude 10 south to 35 north, with geographically
accurate coastlines: the Bay of Bengal and Ganges delta at the far left, the
Malay Peninsula and Gulf of Siam, Sumatra, Java and Borneo along the bottom,
Indochina and the South China Sea in the centre, the China coast running north
to the Yangtze, Hainan, Formosa, the Philippine islands, and southern Japan at
the upper right. Land in dark aged parchment and tarnished brass-brown with
soft engraved hill shading; sea in deep ink-teal lacquer with fine engraved
wave lines and faint depth shading, slightly lighter along the coasts.
Oxblood-lacquer and antique-brass mood, low contrast, dark overall so bright
markers and text can sit on top. Painterly, tactile, even lighting, no
vignette darker than the sea itself. Completely unlabelled: no place names, no
lettering, no numbers, no compass rose, no cartouche, no title, no border, no
ships, no sea monsters, no route lines, no port dots, no clouds, no storms, no
people, no watermark, no modern detail. 10:9 landscape composition filling the
whole frame edge to edge.

## Delivery

- Shape: 10:9 landscape. Aim for at least 2000 x 1800; WebP.
- One clean (family-safe) picture is enough; there are no people in it.
- Suggested file: `web/assets/branding/crimson-ledger-sea-chart-v01.webp`.

## Known risk: painted coastlines drift

Image generators rarely place coastlines exactly. Port markers are drawn from
each port's real longitude and latitude, so on a drifting map Singapore can
land in the sea or Shanghai inland. Two safeguards are planned:

1. **Per-port nudge table.** After the picture is chosen, each port gets a small
   x/y correction for that picture, stored beside the image setting, so markers
   sit on the painted coast.
2. **Pick for accuracy first.** When judging candidates, check these six points
   before looks: Calcutta at the head of the Bay of Bengal, Singapore at the tip
   of the peninsula, Batavia on Java's north-west coast, Hong Kong on the south
   China coast, Shanghai at the Yangtze mouth, Nagasaki on Kyushu's west side.

If no candidate is close enough, the fallback is to use the painted picture for
the sea texture only and draw accurate coastlines in code over it.
