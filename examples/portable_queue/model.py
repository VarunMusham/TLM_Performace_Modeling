"""Synthetic parallel service lanes; illustrative, not a production IP model."""
def schedule(workload, lanes, service_tick):
    free = [0]*lanes
    observations = []
    for operation in workload:
        offered = int(operation["offer_tick"])
        lane = min(range(lanes), key=lambda index: (free[index], index))
        accepted = max(offered, free[lane])
        completed = accepted + service_tick*int(operation.get("work", 1))
        free[lane] = completed
        txid, size = operation["id"], int(operation["payload_bytes"])
        observations.extend([(offered, "offer", txid, size), (accepted, "accept", txid, size),
                             (completed, "complete", txid, size)])
    # Stable sorting retains each transaction's offer/accept/complete ordering.
    return sorted(observations, key=lambda observation: observation[0])
