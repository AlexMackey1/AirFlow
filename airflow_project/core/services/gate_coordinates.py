"""
Author: Alexander Mackey, Student ID: C22739165
Description: GPS coordinate definitions for Dublin Airport terminal pathways and gate positions.

Coordinates were captured manually using Google Maps interior floor plan view and
verified visually against the debug heatmap endpoint (/api/debug/pathways/).

Each pathway is an ordered list of (lat, lon) tuples tracing the walking route
a passenger takes from check-in through security to their departure gate.

Points are ordered landside → airside (entrance to gate direction).

Structure:
    T1_SPINE         — ordered list of (lat, lon): T1 check-in → security → duty free concourse
    T1_PIER_1        — Pier 1 (gates 102–114), branches from duty free end
    T1_PIER_2        — Pier 2 (gates 202–216), branches from duty free end
    T1_PIER_3        — Pier 3 (gates 301–307A), branches from duty free at Pier 3 junction
    T2_SPINE         — T2 check-in → security → duty free concourse → pier entrance
    T2_PIER_4        — Pier 4 (gates 401–426)
    T2_CONNECTOR     — Connector walkway from T2 duty free to T1 security (gates 33x, 3xx)

    T1_PATHWAYS      — dict: pier name → ordered (lat, lon) list
    T2_PATHWAYS      — dict: pathway name → ordered (lat, lon) list
    T1_GATES         — dict: gate str → (lat, lon)
    T2_GATES         — dict: gate str → (lat, lon)
    GATE_TO_PATHWAY  — dict: gate str → (terminal, pathway_key)
    TERMINAL_FALLBACK — dict: terminal str → fallback pathway key

Gate routing rules:
    T1:
        1xx  → pier_1
        2xx  → pier_2
        3xx  → pier_3
        6, 8, 9, 10, 11, 13 → pier_1 (Ryanair remote apron stands, routed to Pier 1)
        unrecognised / no gate → T1 spine fallback

    T2:
        4xx            → t2_pier_4
        332–337        → t2_connector (stop at gate coord, do not continue to T1)
        335A–F         → mapped to Gate 335/334 coordinate
        3xx            → t2_connector then through to T1 Pier 3
        USPC / 29x / 22-x / 7-x → excluded (dropped)
        unrecognised   → T2 spine fallback

Caveats:
    - Gate 13 and single-digit gates are AviationStack placeholder values for Ryanair
      remote apron stands; they are physically Pier 1 operations.
    - Gates 335A–F are a remote bus-gate building; mapped to Gate 335/334 coordinate.
    - Gates 301–307A in T2 data are physically T1 Pier 3 gates; passengers walk the
      full T2→T1 connector before rejoining T1 security and Pier 3.
    - T2 is treated as a single flat level (multi-floor building, heatmap is 2D top-down).
    - T2_DutyFree_Right is excluded — it is not on the path to any departure gates.
"""

# ---------------------------------------------------------------------------
# T1 PATHWAYS
# ---------------------------------------------------------------------------

T1_SPINE = [
    # Landside: check-in hall
    (53.42763777648964,  -6.244210108381046),   # T1 check-in entrance (kerbside)
    (53.42727588708599,  -6.244109249448979),   # T1 check-in middle (desk area)
    # Security
    (53.42693499905454,  -6.243493344612003),   # Security entrance / queue
    (53.42665951223897,  -6.243675910848759),   # Security middle
    (53.42649139376667,  -6.243891670946742),   # Security exit (airside start)
    # Duty free concourse — runs from security exit toward pier junctions
    (53.42681067702182,  -6.244401433824323),   # Duty free entrance
    (53.42697567242094,  -6.244655549458656),   # Junction with Pier 3 corridor
    (53.42718518326812,  -6.244981336994643),   # Duty free point 2
    (53.42769305095892,  -6.245763539604911),   # Duty free point 3
    (53.42781217953728,  -6.245763539604911),   # Duty free point 4
    (53.42799609668685,  -6.245682863999980),   # Duty free point 5
    (53.42833048947520,  -6.245686371635148),   # Duty free end — junction Pier 1 & Pier 2
]

# Pier 1: gates 102–114 + Ryanair remote apron stands (6, 8, 9, 10, 11, 13)
# Branches north from duty free end junction.
T1_PIER_1 = [
    (53.42833048947520,  -6.245686371635148),   # Junction (shared with spine end)
    (53.42835032913965,  -6.245586721387276),   # Corridor start
    (53.42849397202116,  -6.245257141345526),
    (53.42863579616211,  -6.244973336309575),
    (53.42883034902157,  -6.244625446265505),
    (53.42901035507976,  -6.244359951231872),
    (53.42912854046099,  -6.244265349553221),   # Bend
    (53.42926308957195,  -6.244234832882690),
    (53.42934309155133,  -6.244240936211186),
    (53.42953764117353,  -6.244363002893316),
    (53.42966673435660,  -6.244518637913031),
    (53.42990673755648,  -6.244958077966633),
    (53.43010310279131,  -6.245287658008382),
    (53.43037037623659,  -6.245724046396996),
    (53.43041401256797,  -6.246157383127268),
    (53.43042855799842,  -6.246483911501965),
    (53.43045764884444,  -6.246908093222365),   # Gate 102
    (53.43047401243656,  -6.247359739946246),   # Gate 103
    (53.43048673967054,  -6.247637441648091),   # Gate 104
    (53.43050310325145,  -6.248006693361533),   # Gate 105
    (53.43055401213633,  -6.248427823499052),   # Gate 106
    (53.43054673944319,  -6.248812333547760),   # Gate 107
    (53.43057401203897,  -6.249236515324001),   # Gate 108/109
    (53.43061806260121,  -6.249850251765244),   # Gate 110
    (53.43065931903495,  -6.250377290487969),   # Gate 111–113
    (53.43064785891848,  -6.250588875376654),   # Pier 1 end
]

# Pier 2: gates 202–224
# Branches south from duty free end junction.
T1_PIER_2 = [
    (53.42833048947520,  -6.245686371635148),   # Junction (shared with spine end)
    (53.42866905949138,  -6.246209009248339),   # Pier 2 start
    (53.42853579200518,  -6.246850111593248),   # Pier 2 middle 1
    (53.42827759837746,  -6.247402463329885),   # Pier 2 middle 2
    (53.42802849458826,  -6.247951763399469),   # Pier 2 end
]

# Pier 3: gates 301–307A
# Branches south from the duty free concourse at the Pier 3 junction.
# Long straight corridor → circular rotunda with gates around it.
T1_PIER_3 = [
    (53.42697567242094,  -6.244655549458656),   # Junction with duty free (Pier 3 branch)
    (53.42685722396749,  -6.244764563231589),   # Corridor start
    (53.42662987843054,  -6.245293600659058),   # Corridor middle
    (53.42636050105249,  -6.245617435690418),   # Corridor end
    (53.42621912500071,  -6.245934858164436),   # Rotunda centre
    (53.42649423470871,  -6.245870732415651),   # Gate 301
    (53.42634330668656,  -6.246342056669215),   # Gate 302/303
    (53.42602092728718,  -6.246258920331201),   # Gate 304/305
    (53.42598051903387,  -6.245737040033055),   # Gate 306/307
]

T1_PATHWAYS = {
    'spine':  T1_SPINE,
    'pier_1': T1_PIER_1,
    'pier_2': T1_PIER_2,
    'pier_3': T1_PIER_3,
}

# ---------------------------------------------------------------------------
# T2 PATHWAYS
# ---------------------------------------------------------------------------

# T2 Spine: check-in hall → security → duty free concourse → pier entrance branch point.
# T2 check-in has Left/Center/Right points to spread the heatmap realistically
# across the wide check-in hall (desks on both sides).
# T2_DutyFree_Right is intentionally excluded — not on the path to any departure gates.
T2_SPINE = [
    # Check-in hall (fans across three columns)
    (53.42663657480154,  -6.240832767734519),   # Check-in Left
    (53.42648044112443,  -6.239750698211091),   # Check-in Entrance (centre kerbside)
    (53.42633163218588,  -6.239921618173584),   # Check-in Centre
    (53.42611646108333,  -6.238986553967259),   # Check-in Right
    # Security
    (53.42596683814652,  -6.240170330917978),   # Security entrance / queue
    (53.42574923819294,  -6.240382252747229),   # Security
    (53.42564194081540,  -6.240454280748964),   # Security exit
    # Duty free concourse
    (53.42560617495928,  -6.240472287762861),   # Duty free entrance
    (53.42547741764152,  -6.240598336766221),   # Duty free middle
    (53.42556683248651,  -6.241174560789141),   # Duty free Left (branch to connector & Pier 4)
    # Pier entrance branch point — passengers split here to Pier 4 vs connector
    (53.42533738287880,  -6.240791812179080),   # Pier entrance
]

# T2 Pier 4: gates 401–426
# Branches south from the duty free Left / Pier entrance area.
T2_PIER_4 = [
    (53.42556683248651,  -6.241174560789141),   # Duty free Left (branch start from spine)
    (53.42505490756576,  -6.241176383712536),   # Pier 4 point 1
    (53.42492142026545,  -6.241050264983961),   # Gate 407
    (53.42473148693487,  -6.241714966766465),   # Gate 408/409/410
    (53.42423348696615,  -6.242566251525537),   # Gate 401/402 & 411–414
    (53.42368154147225,  -6.243523418242377),   # Gate 403/404 & 415–418
    (53.42315284255948,  -6.244363120392126),   # Gate 405/406 & 419–422
    (53.42269966681712,  -6.245139448831933),   # Gate 423–426
]

# T2 Connector + 33x gates.
# Passengers walking to 33x gates STOP at the relevant gate coordinate.
# Passengers walking to T1 3xx gates CONTINUE past Gate 332 through the
# connector and rejoin T1 at the security/duty free junction.
#
# Full path: T2 spine → Duty free Left → Gate 336/337 → Gate 335/334 →
#            Gate 332 → Connector Start → Connector End → Rejoin T1 Security
T2_CONNECTOR = [
    (53.42556683248651,  -6.241174560789141),   # T2 Duty free Left (branch start)
    (53.42551155043918,  -6.241356178210372),   # Gate 336/337
    (53.42582480447297,  -6.242461248281906),   # Gate 335/334
    (53.42594626970174,  -6.242986961228559),   # Gate 332
    (53.42602618085356,  -6.243142529347701),   # Connector start (inter-terminal walkway)
    (53.42621477056408,  -6.243421479078219),   # Connector end
    (53.42636500244790,  -6.243700428808322),   # Rejoin T1 security / duty free approach
]

# Full path for T1 3xx gates via T2 connector:
# T2_CONNECTOR + T1_PIER_3 (after the rejoin point)
# The interpolator builds this compound path at runtime.

T2_PATHWAYS = {
    'spine':        T2_SPINE,
    'pier_4':       T2_PIER_4,
    't2_connector': T2_CONNECTOR,
}

# ---------------------------------------------------------------------------
# GATE COORDINATE LOOKUPS
# ---------------------------------------------------------------------------

T1_GATES = {
    # Pier 1
    '102': (53.43045764884444, -6.246908093222365),
    '103': (53.43047401243656, -6.247359739946246),
    '104': (53.43048673967054, -6.247637441648091),
    '105': (53.43050310325145, -6.248006693361533),
    '106': (53.43055401213633, -6.248427823499052),
    '107': (53.43054673944319, -6.248812333547760),
    '108': (53.43057401203897, -6.249236515324001),
    '109': (53.43057401203897, -6.249236515324001),   # shares with 108
    '110': (53.43061806260121, -6.249850251765244),
    '111': (53.43065931903495, -6.250377290487969),
    '112': (53.43065931903495, -6.250377290487969),
    '113': (53.43065931903495, -6.250377290487969),
    '114': (53.43064785891848, -6.250588875376654),
    # Pier 2
    '202': (53.42866905949138, -6.246209009248339),
    '203': (53.42853579200518, -6.246850111593248),
    '204': (53.42827759837746, -6.247402463329885),
    '205': (53.42802849458826, -6.247951763399469),
    '206': (53.42802849458826, -6.247951763399469),
    # Pier 3 rotunda
    '301': (53.42649423470871, -6.245870732415651),
    '302': (53.42634330668656, -6.246342056669215),
    '303': (53.42634330668656, -6.246342056669215),
    '304': (53.42602092728718, -6.246258920331201),
    '305': (53.42602092728718, -6.246258920331201),
    '306': (53.42598051903387, -6.245737040033055),
    '307': (53.42598051903387, -6.245737040033055),
    '307A': (53.42598051903387, -6.245737040033055),  # suffix variant
}

T2_GATES = {
    # Pier 4
    '401': (53.42423348696615, -6.242566251525537),
    '402': (53.42423348696615, -6.242566251525537),
    '403': (53.42368154147225, -6.243523418242377),
    '404': (53.42368154147225, -6.243523418242377),
    '405': (53.42315284255948, -6.244363120392126),
    '406': (53.42315284255948, -6.244363120392126),
    '407': (53.42492142026545, -6.241050264983961),
    '408': (53.42473148693487, -6.241714966766465),
    '409': (53.42473148693487, -6.241714966766465),
    '410': (53.42473148693487, -6.241714966766465),
    '411': (53.42423348696615, -6.242566251525537),
    '412': (53.42423348696615, -6.242566251525537),
    '413': (53.42423348696615, -6.242566251525537),
    '414': (53.42423348696615, -6.242566251525537),
    '415': (53.42368154147225, -6.243523418242377),
    '416': (53.42368154147225, -6.243523418242377),
    '417': (53.42368154147225, -6.243523418242377),
    '418': (53.42368154147225, -6.243523418242377),
    '419': (53.42315284255948, -6.244363120392126),
    '420': (53.42315284255948, -6.244363120392126),
    '421': (53.42315284255948, -6.244363120392126),
    '422': (53.42315284255948, -6.244363120392126),
    '423': (53.42269966681712, -6.245139448831933),
    '424': (53.42269966681712, -6.245139448831933),
    '425': (53.42269966681712, -6.245139448831933),
    '426': (53.42269966681712, -6.245139448831933),
    # Connector / 33x gates
    '332': (53.42594626970174, -6.242986961228559),
    '334': (53.42582480447297, -6.242461248281906),
    '335': (53.42582480447297, -6.242461248281906),
    '336': (53.42551155043918, -6.241356178210372),
    '337': (53.42551155043918, -6.241356178210372),
    # 335A–F: remote bus-gate building, mapped to nearest gate coord
    '335A': (53.42582480447297, -6.242461248281906),
    '335B': (53.42582480447297, -6.242461248281906),
    '335C': (53.42582480447297, -6.242461248281906),
    '335D': (53.42582480447297, -6.242461248281906),
    '335E': (53.42582480447297, -6.242461248281906),
    '335F': (53.42582480447297, -6.242461248281906),
}

# ---------------------------------------------------------------------------
# GATE → PATHWAY ROUTING
# ---------------------------------------------------------------------------

# Maps gate number (str) → (terminal, pathway_key)
# terminal: 'T1' | 'T2'
# pathway_key: key in T1_PATHWAYS or T2_PATHWAYS
GATE_TO_PATHWAY: dict[str, tuple[str, str]] = {
    # T1 Pier 1 — numbered gates
    '102': ('T1', 'pier_1'), '103': ('T1', 'pier_1'), '104': ('T1', 'pier_1'),
    '105': ('T1', 'pier_1'), '106': ('T1', 'pier_1'), '107': ('T1', 'pier_1'),
    '108': ('T1', 'pier_1'), '109': ('T1', 'pier_1'), '110': ('T1', 'pier_1'),
    '111': ('T1', 'pier_1'), '112': ('T1', 'pier_1'), '113': ('T1', 'pier_1'),
    '114': ('T1', 'pier_1'),
    # T1 Pier 1 — Ryanair remote apron stand placeholders
    '6':  ('T1', 'pier_1'), '8':  ('T1', 'pier_1'), '9':  ('T1', 'pier_1'),
    '10': ('T1', 'pier_1'), '11': ('T1', 'pier_1'), '13': ('T1', 'pier_1'),
    # T1 Pier 2
    '202': ('T1', 'pier_2'), '203': ('T1', 'pier_2'), '204': ('T1', 'pier_2'),
    '205': ('T1', 'pier_2'), '206': ('T1', 'pier_2'),
    # T1 Pier 2 extended range (AviationStack may return these)
    '207': ('T1', 'pier_2'), '208': ('T1', 'pier_2'), '209': ('T1', 'pier_2'),
    '210': ('T1', 'pier_2'), '211': ('T1', 'pier_2'), '212': ('T1', 'pier_2'),
    '213': ('T1', 'pier_2'), '214': ('T1', 'pier_2'), '215': ('T1', 'pier_2'),
    '216': ('T1', 'pier_2'), '217': ('T1', 'pier_2'), '218': ('T1', 'pier_2'),
    '219': ('T1', 'pier_2'), '220': ('T1', 'pier_2'), '221': ('T1', 'pier_2'),
    '222': ('T1', 'pier_2'), '223': ('T1', 'pier_2'), '224': ('T1', 'pier_2'),
    # T1 Pier 3
    '301': ('T1', 'pier_3'), '302': ('T1', 'pier_3'), '303': ('T1', 'pier_3'),
    '304': ('T1', 'pier_3'), '305': ('T1', 'pier_3'), '306': ('T1', 'pier_3'),
    '307': ('T1', 'pier_3'), '307A': ('T1', 'pier_3'),
    # T2 Pier 4
    '401': ('T2', 'pier_4'), '402': ('T2', 'pier_4'), '403': ('T2', 'pier_4'),
    '404': ('T2', 'pier_4'), '405': ('T2', 'pier_4'), '406': ('T2', 'pier_4'),
    '407': ('T2', 'pier_4'), '408': ('T2', 'pier_4'), '409': ('T2', 'pier_4'),
    '410': ('T2', 'pier_4'), '411': ('T2', 'pier_4'), '412': ('T2', 'pier_4'),
    '413': ('T2', 'pier_4'), '414': ('T2', 'pier_4'), '415': ('T2', 'pier_4'),
    '416': ('T2', 'pier_4'), '417': ('T2', 'pier_4'), '418': ('T2', 'pier_4'),
    '419': ('T2', 'pier_4'), '420': ('T2', 'pier_4'), '421': ('T2', 'pier_4'),
    '422': ('T2', 'pier_4'), '423': ('T2', 'pier_4'), '424': ('T2', 'pier_4'),
    '425': ('T2', 'pier_4'), '426': ('T2', 'pier_4'),
    # T2 Connector — 33x gates (stop at gate; don't continue to T1)
    '332': ('T2', 't2_connector_stop'), '334': ('T2', 't2_connector_stop'),
    '335': ('T2', 't2_connector_stop'), '336': ('T2', 't2_connector_stop'),
    '337': ('T2', 't2_connector_stop'),
    # 335A–F: remote bus gates — treat same as 335 (connector stop)
    '335A': ('T2', 't2_connector_stop'), '335B': ('T2', 't2_connector_stop'),
    '335C': ('T2', 't2_connector_stop'), '335D': ('T2', 't2_connector_stop'),
    '335E': ('T2', 't2_connector_stop'), '335F': ('T2', 't2_connector_stop'),
    # T2 → T1 Pier 3 (full connector + T1 pier 3 walk)
    # AviationStack returns these under terminal T2 for some codeshares
    # The pathway_interpolator handles the compound path at runtime.
}

# Fallback when gate is absent / unrecognised
TERMINAL_FALLBACK = {
    'T1': ('T1', 'spine'),
    '1':  ('T1', 'spine'),
    'T2': ('T2', 'spine'),
    '2':  ('T2', 'spine'),
}

# Gates that should be dropped entirely (no meaningful pathway)
EXCLUDED_GATES = {'USPC'}

# Pattern prefixes that indicate unresolvable remote stand identifiers
# e.g. '29-5', '22-2', '28A-', '7-15'
import re
_UNRESOLVABLE_PATTERN = re.compile(r'^\d{2}-\d+$|^\d{2}[A-Z]-$')


def is_excluded_gate(gate: str) -> bool:
    """Return True if the gate value should be dropped with no fallback."""
    if gate in EXCLUDED_GATES:
        return True
    if _UNRESOLVABLE_PATTERN.match(gate):
        return True
    return False