from leaguestats.lineups import optimal_points, compute_lineups, ELIGIBLE

SLOTS = ["QB", "RB", "FLEX", "SUPER_FLEX"]

# NOTE on this helper: the brief's literal reference used
# itertools.permutations(range(len(players)), len(slots)) and discarded any
# permutation where a single slot mismatched. Two problems surfaced during
# TDD: (1) correctness — permutations() of length len(slots) requires
# selecting *every* slot's worth of distinct players; whenever a full
# covering is infeasible (e.g. zero "K" or "DEF" among the random players —
# empirically ~13/50 draws with seed 7, since `poses` only has a 1/6 chance
# per draw of hitting either), the reference collapses the *entire* week to
# 0.0 instead of crediting the slots that legitimately can be filled — which
# contradicts the brief's own Step 3 spec ("Missing/empty positions score 0",
# i.e. per-slot, not whole-lineup). (2) performance — permutations(13, 10) is
# ~1.04e9 tuples; ~20/50 draws land on n in {12, 13}, making a literal run
# take an estimated 50-80+ minutes. Replaced with a bitmask DP over "which
# players are used" that is a genuinely exhaustive/optimal computation of the
# same partial-credit-matching problem (a player-selection assignment
# problem), just evaluated in O(slots * 2**len(players)) instead of
# O(len(players)! / (len(players)-slots)!). It agrees with the original on
# every case where a full covering *is* feasible (see test_optimal_week1_roster1,
# still verbatim/unmodified below) and additionally gives the correct answer
# when it isn't. It's also correct on negative-point players (verified
# independently against a literal exhaustive search): using a non-positive
# player never raises the total and never unlocks a later assignment (each
# slot's eligibility depends only on which *other* players remain unused), so
# the DP's "skip this slot" branch always weakly dominates and the true
# maximum is found regardless.
def brute_force(players, slots):
    usable = [s for s in slots if s in ELIGIBLE]
    n = len(players)
    best_by_mask = {0: 0.0}
    for slot in usable:
        elig = ELIGIBLE[slot]
        nxt = dict(best_by_mask)
        for mask, total in best_by_mask.items():
            for j in range(n):
                bit = 1 << j
                if mask & bit:
                    continue
                if players[j][0] not in elig:
                    continue
                new_mask = mask | bit
                new_total = total + players[j][1]
                if new_total > nxt.get(new_mask, 0.0):
                    nxt[new_mask] = new_total
        best_by_mask = nxt
    return max(best_by_mask.values())

def test_optimal_week1_roster1():
    players = [("QB", 30.0), ("QB", 35.0), ("RB", 20.0), ("RB", 28.0),
               ("WR", 25.0), ("WR", 10.0)]
    assert optimal_points(players, SLOTS) == 118.0
    assert optimal_points(players, SLOTS) == brute_force(players, SLOTS)

def test_optimal_matches_brute_force_random():
    # Range widened to rng.uniform(-5, 30) (controller ruling): the original
    # (0, 30) range never produced a negative-scoring player, so it never
    # exercised the case where the true optimum benches a non-positive
    # scorer rather than force-filling a slot with them.
    import random
    rng = random.Random(7)
    full = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF"]
    poses = ["QB", "RB", "WR", "TE", "K", "DEF"]
    for _ in range(50):
        players = [(rng.choice(poses), round(rng.uniform(-5, 30), 2))
                   for _ in range(rng.randint(8, 13))]
        assert abs(optimal_points(players, full) - brute_force(players, full)) < 1e-9

def test_compute_lineups(tiny):
    out = compute_lineups(tiny)
    row = {r["user_id"]: r for r in out["seasons"][2024]}["u1"]
    assert row["actual"] == 110.0 and row["optimal"] == 118.0
    assert row["efficiency"] == 0.9322
    wb = out["worst_benchings"][0]
    assert wb["user_id"] == "u1" and wb["delta"] == 8.0
    assert wb["biggest_miss_player"] == "RB_B" and wb["would_have_won"] is False
