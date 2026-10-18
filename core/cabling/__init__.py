"""
core/cabling — DMX cabling planner (3.6.0)
==========================================

Plans the DMX cabling of a show with the kit you own: which splitter output
feeds which fixtures, in what order, which cable goes where, which adapters
and terminators are needed and what is missing.  The show is only read,
never changed.

* :mod:`core.cabling.kit` — devices as ports, presets, the base inventory
  (your kit, in settings) and tonight's copy.
* :mod:`core.cabling.rig` — what the show says: fixtures with their place on
  the stage, patch, DMX connector, the universes and their outputs, and the
  match of each fixture against the inventory (mine, borrowed, venue).
* :mod:`core.cabling.chain` — the connector walk along a chain: adapters,
  terminators and the C checks that follow from the ports.
* :mod:`core.cabling.plan` — ``<show>.cabling.json`` next to the show.

Standard library only.
"""
