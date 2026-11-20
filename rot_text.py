"""Wording for perishable cargo that rots (rot.py, 20 Nov 2026). Merged into strings.EN / strings.FAMILY at
import, so every line can be edited in Admin > Language & Text like any other. The Captain's log line is
written in the house voice (house_voice.HOUSE_STYLE: sexy, funny, innuendo, never explicit) with a clean
version in FAMILY."""

EN = {
    # ---- Captain's log --------------------------------------------------------------------------
    "l.rot": "You left it hanging too long, Captain. {goods} went soft and sour in the hold. Cargo, like some people, will not wait forever.",
    # ---- the books and the Tally Book -----------------------------------------------------------
    "port.pl.rot": "Rotted in the hold",
    "st.line.rot": "Rotted in the hold",
    # ---- the market row on the player screen ----------------------------------------------------
    "rot.age": "{n} mo aboard",
    "rot.warn": "{n} mo aboard: rots at month end",
    "rot.tip": "{good} is perishable. This lot has been aboard {n} months on average. It is safe for {grace} months; after that a share of it rots every month. Selling it, or leaving it ashore in a warehouse, stops the clock.",
    "rot.tip_warn": "{good} is perishable and has been aboard {n} months on average. The month-end will rot a share of it (it is safe for {grace} months). Sell it, or land it in a warehouse.",
}

FAMILY = {
    "l.rot": "{goods} sat in the hold too long and went bad, Captain. Cargo does not keep forever.",
}
