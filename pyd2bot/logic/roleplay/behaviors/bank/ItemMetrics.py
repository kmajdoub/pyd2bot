from dataclasses import dataclass
from typing import List


@dataclass
class ItemMetrics:
    gid: int
    weight: int
    value: float
    stack_uids: List[int]
    stack_quantities: List[int]
    batch_size: int
    
    @property
    def total_quantity(self) -> int:
        return sum(self.stack_quantities)
        
    @property
    def value_density(self) -> float:
        """Calculate value per weight unit for a complete batch"""
        if self.weight == 0:
            return float('inf')
        batch_value = self.value * self.batch_size
        batch_weight = self.weight * self.batch_size
        return batch_value / batch_weight
        
    def __lt__(self, other):
        return self.value_density > other.value_density