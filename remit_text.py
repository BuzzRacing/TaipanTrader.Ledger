"""Wording for repaying the home moneylender from another port (engine._remit, web/player.js, 23 Nov 2026).

An away moneylender's office (Admin > Ports > Moneylender) only takes repayments. The silver goes home with a
merchant: he keeps a fee, may be robbed on the road or may help himself to a little, and only what arrives lowers
the debt. The Port screen keeps a report of what was sent and what really got home.
{sent} {fee} {lost} {arrived} {owed} are amounts; {port} is where the house is, {home} its home port.
"""

EN = {
    # --- the receipts (Confirmations) ------------------------------------------------------------------
    "m.remit.safe": "Sent {sent} home from {port}. The merchant kept {fee} and {arrived} reached {home}. Debt left: {owed}.",
    "m.remit.skimmed": "Sent {sent} home from {port}. The merchant kept {fee}, then helped himself to {lost} more. {arrived} reached {home}. Debt left: {owed}.",
    "m.remit.robbed": "Sent {sent} home from {port}. The merchant kept {fee}, then was robbed on the road and lost {lost}. Only {arrived} reached {home}. Debt left: {owed}.",
    # --- rule messages ---------------------------------------------------------------------------------
    "e.lender_repay_only": "The moneylender's office in {port} only takes repayments. She lends in {home}.",
    # --- the Port screen: the moneylender's card and the report ----------------------------------------
    "port.remit.office": "Her office in {port}: repayments only",
    "port.remit.terms": "A merchant carries it home. He keeps {fee} of what you send; each trip there is a {rob} chance he is robbed and a {skim} chance he helps himself. Only what arrives lowers the debt.",
    "port.remit.title": "Sent home",
    "port.remit.sent": "Sent", "port.remit.fees": "Merchants' fees", "port.remit.lost": "Lost on the road",
    "port.remit.arrived": "Reached {home}", "port.remit.trips": "Sendings",
    "port.remit.robbed": "Robbed", "port.remit.skimmed": "Skimmed",
    "port.remit.how.safe": "Got home", "port.remit.how.skimmed": "Skimmed", "port.remit.how.robbed": "Robbed",
    "port.remit.row": "{port}: sent {sent}, {arrived} arrived",
    "port.remit.none": "Nothing sent home yet.",
    "port.remit.fee_stat": "Merchant's fee",
    "port.remit.trips_note": "{n} sendings", "port.remit.trips_note_1": "1 sending",
    # --- the account book ------------------------------------------------------------------------------
    "port.pl.remit_fee": "Merchants' fees on repayments", "port.pl.remit_lost": "Lost on the road home",
}

FAMILY = {}
