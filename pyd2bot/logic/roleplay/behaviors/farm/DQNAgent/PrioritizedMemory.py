import random
from collections import namedtuple
from typing import TYPE_CHECKING

import numpy as np

from pyd2bot.logic.roleplay.behaviors.farm.DQNAgent.SumTree import SumTree

if TYPE_CHECKING:
    from pyd2bot.logic.roleplay.behaviors.farm.DQNAgent.DQNAgent import \
        DQNAgent

Transition = namedtuple('Transition', ('state', 'action', 'reward', 'next_state'))

class PrioritizedMemory:

    def __init__(self, capacity, agent:'DQNAgent', beta=0.4, beta_increment=0.001):
        self.agent = agent
        self.capacity = capacity
        self.beta = beta
        self.beta_increment = beta_increment
        self.tree = SumTree(capacity)
        self.transitions = []

    def add(self, state, action, reward, next_state):
        transition = Transition(state, action, reward, next_state)
        self.transitions.append(transition)
        priority = self._get_priority(reward)
        self.tree.add(priority, transition)

        if len(self.transitions) > self.capacity:
            self.transitions.pop(0)

    def sample(self, batch_size):
        batch = []
        segment = self.tree.total() / batch_size
        priorities = []

        self.beta = np.min([1., self.beta + self.beta_increment])

        for i in range(batch_size):
            a = segment * i
            b = segment * (i + 1)
            s = random.uniform(a, b)
            idx, priority, transition = self.tree.get(s)
            batch.append(transition)
            priorities.append(priority)

        sampling_probabilities = np.array(priorities) / self.tree.total()
        is_weight = np.power(self.tree.capacity * sampling_probabilities, -self.beta)
        is_weight /= is_weight.max()

        return batch, is_weight

    def update_priorities(self, td_errors):
        for td_error, transition in zip(td_errors, self.transitions):
            priority = self._get_priority(td_error)
            self.tree.update(priority, transition)

    def _get_priority(self, td_error):
        return (np.abs(td_error) + self.agent.epsilon) ** self.agent.learning_rate

    def __len__(self):
        return len(self.transitions)