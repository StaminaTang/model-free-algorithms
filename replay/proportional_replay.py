import numpy as np
import ray

from replay.utils import reset_buffer, add_buffer, copy_buffer
from replay.ds.sum_tree import SumTree
from replay.prioritized_replay import PrioritizedReplay


class ProportionalPrioritizedReplay(PrioritizedReplay):
    """ Interface """
    def __init__(self, args, state_dim, action_dim):
        super().__init__(args, state_dim, action_dim)
        reset_buffer(self.memory, self.capacity, state_dim, action_dim, False)     # exp_id    -->     exp
        self.data_structure = SumTree(self.capacity)                               # prio_id   -->     priority, exp_id

    """ Implementation """
    def _sample(self):
        assert self.good_to_learn, 'There are not sufficient transitions in buffer to learn \
                                -- buffer length: {}\t minimum size: {}'.format(len(self), self.min_size)
        total_priorities = self.data_structure.total_priorities
        
        segment = total_priorities / self.batch_size

        priorities, exp_ids = list(zip(*[self.data_structure.find(np.random.uniform(i * segment, (i+1) * segment), i, (i+1) * segment, total_priorities, self.data_structure.total_priorities)
                                        for i in range(self.batch_size)]))

        priorities = np.squeeze(priorities)
        probabilities = priorities / total_priorities

        self._update_beta()
        # compute importance sampling ratios
        N = len(self)
        IS_ratios = self._compute_IS_ratios(N, probabilities)
        
        return IS_ratios, exp_ids, self._get_samples(exp_ids)

    def _get_samples(self, exp_ids):
        exp_ids = list(exp_ids) # convert tuple to list

        return (
            self.memory['state'][exp_ids],
            self.memory['action'][exp_ids],
            self.memory['reward'][exp_ids],
            self.memory['next_state'][exp_ids],
            self.memory['done'][exp_ids],
            self.memory['steps'][exp_ids],
        )
