from typing import List, Set, Tuple
from pydofus2.com.ankamagames.dofus.internalDatacenter.items.ItemWrapper import ItemWrapper

BATCH_SIZES = [1, 10, 100]

def find_items_to_retrieve(
    server_id: int,
    type_ids: Set[int],
    bank_items: List[ItemWrapper],
    max_pods: int,
    max_slots: int,
    scorer
) -> Tuple[List[Tuple[int, int, int]], bool]:  # Returns (selections, has_remainder)
    candidates = []
    for item in bank_items:
        if item.typeId not in type_ids:
            continue
            
        for batch_size in BATCH_SIZES:
            if batch_size > item.quantity:
                continue
                
            score = scorer.score(server_id, item.objectGID, batch_size)
            candidates.append({
                'uid': item.objectUID,
                'batch_size': batch_size,
                'available_qty': item.quantity,
                'weight_per_unit': item.weight,
                'score_per_batch': score
            })

    candidates.sort(key=lambda x: x['score_per_batch'], reverse=True)

    selected = []
    remaining_pods = max_pods
    remaining_slots = max_slots
    has_remainder = False

    for candidate in candidates:
        if remaining_slots <= 0 or remaining_pods <= 0:
            has_remainder = True
            break

        available_batches = candidate['available_qty'] // candidate['batch_size']
        max_by_weight = (remaining_pods // candidate['weight_per_unit']) // candidate['batch_size'] if candidate['weight_per_unit'] > 0 else available_batches
        max_by_slots = remaining_slots
        
        possible_batches = min(available_batches, max_by_weight, max_by_slots)
        
        if possible_batches > 0:
            quantity = possible_batches * candidate['batch_size']
            
            # If we can't take all available batches, we have remainder
            if possible_batches < available_batches:
                has_remainder = True

            selected.append((
                candidate['uid'],
                quantity,
                candidate['batch_size']
            ))
            
            remaining_pods -= quantity * candidate['weight_per_unit']
            remaining_slots -= possible_batches

    return selected, has_remainder