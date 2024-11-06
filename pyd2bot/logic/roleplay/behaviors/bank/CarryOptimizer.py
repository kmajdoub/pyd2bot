from dataclasses import dataclass
from typing import Dict, List, Tuple
from prettytable import PrettyTable

from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


@dataclass
class ItemInfo:
    gid: int
    weight: int
    market_value: float
    stack_uids: List[int]
    stack_quantities: List[int]
    batch_size: int

    @property
    def value_density(self) -> float:
        batch_weight = self.weight * self.batch_size
        if batch_weight == 0:
            return float('inf')
        return (self.market_value * self.batch_size) / batch_weight

    @property
    def total_quantity(self) -> int:
        return sum(self.stack_quantities)

    @property
    def total_batches(self) -> int:
        return self.total_quantity // self.batch_size


def optimize_carry(items: Dict[int, ItemInfo], available_pods: int) -> Tuple[List[int], List[int]]:
    """
    Optimized algorithm that:
    1. Sorts by value density
    2. Combines multiple batches from same stack
    3. Maximizes pod usage
    """
    logger = Logger()
    retrieve_uids = []
    retrieve_quantities = []
    remaining_pods = available_pods

    # Create initial analysis table
    analysis_table = PrettyTable()
    analysis_table.field_names = ["GID", "Value/Pod", "Weight", "Batch Size", "Total Qty", "Total Batches", "Market Value"]
    
    for gid, item in items.items():
        analysis_table.add_row([
            gid,
            f"{item.value_density:.2f}",
            item.weight,
            item.batch_size,
            item.total_quantity,
            item.total_batches,
            item.market_value
        ])
    
    logger.info(f"\nInitial Item Analysis:\n{analysis_table}")

    # Sort by value density
    sorted_items = sorted(
        [(item.value_density, gid, item) for gid, item in items.items()],
        reverse=True
    )

    # Create retrieval plan table
    retrieval_table = PrettyTable()
    retrieval_table.field_names = ["GID", "Stack UID", "Available", "Batches", "To Retrieve", "Pods Used"]

    # Process items by value density
    for _, gid, item in sorted_items:
        # Calculate maximum batches possible with remaining pods
        max_batches_by_pods = remaining_pods // (item.weight * item.batch_size)
        total_available_batches = item.total_batches
        
        batches_to_take = min(max_batches_by_pods, total_available_batches)
        if batches_to_take == 0:
            logger.info(f"Skipping GID {gid} - Not enough pods remaining ({remaining_pods}) or no complete batches available")
            continue

        # Distribute batches across stacks
        remaining_batches = batches_to_take
        for uid, qty in zip(item.stack_uids, item.stack_quantities):
            if remaining_batches == 0:
                break
                
            stack_batches = qty // item.batch_size
            batches_from_stack = min(remaining_batches, stack_batches)
            
            if batches_from_stack > 0:
                total_qty = batches_from_stack * item.batch_size
                pods_used = total_qty * item.weight
                
                retrieval_table.add_row([
                    gid,
                    uid,
                    qty,
                    batches_from_stack,
                    total_qty,
                    pods_used
                ])

                retrieve_uids.append(uid)
                retrieve_quantities.append(total_qty)
                remaining_pods -= pods_used
                remaining_batches -= batches_from_stack

    logger.info(f"\nRetrieval Plan:\n{retrieval_table}")
    logger.info(f"Remaining pods: {remaining_pods}")

    return retrieve_uids, retrieve_quantities