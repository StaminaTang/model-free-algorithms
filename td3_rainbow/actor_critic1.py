import numpy as np
import tensorflow as tf
import tensorflow.contrib as tc

from basic_model.model import Module
import utility.tf_utils as tf_utils

class Base(Module):
    def __init__(self, 
                 name, 
                 args, 
                 graph,
                 state,
                 reuse=False, 
                 is_target=False, 
                 scope_prefix='',):
        self.state = state
        self._variable_scope = (scope_prefix + '/' 
                                if scope_prefix != '' and not scope_prefix.endswith('/') 
                                else scope_prefix) + name
        
        super().__init__(name, args, graph, reuse=reuse)


class Actor(Base):
    """ Interface """
    def __init__(self, 
                 name, 
                 args, 
                 graph,
                 state,
                 action_dim,
                 reuse=False, 
                 is_target=False, 
                 scope_prefix=''):
        self.action_dim = action_dim
        self._noisy_sigma = args['noisy_sigma']

        super().__init__(name, 
                         args, 
                         graph, 
                         state, 
                         reuse=reuse, 
                         is_target=is_target, 
                         scope_prefix=scope_prefix)

    """ Implementation """
    def _build_graph(self, **kwargs):
        self.action = self._network(self.state, self.action_dim)
        
    def _network(self, state, action_dim):
        with tf.variable_scope('net', reuse=self._reuse):
            x = self._dense(state, 512)
            x = self._dense_resnet_norm_activation(x, 512)
            x = self._noisy_norm_activation(x, 256, sigma=self._noisy_sigma)
            x = self._noisy(x, action_dim, sigma=self._noisy_sigma)
            x = tf.tanh(x, name='action')

        return x


class Critic(Base):
    """ Interface """
    def __init__(self,
                 name,
                 args,
                 graph,
                 state,
                 action,
                 actor_action,
                 action_dim,
                 reuse=False, 
                 is_target=False, 
                 scope_prefix=''):
        self.action = action
        self.actor_action = actor_action
        self.action_dim = action_dim

        super().__init__(name, 
                         args,
                         graph, 
                         state, 
                         reuse=reuse, 
                         is_target=is_target, 
                         scope_prefix=scope_prefix)

    """ Implementation """
    def _build_graph(self, **kwargs):
        self.Q, self.Q_with_actor = self._build_net('net')

    def _build_net(self, name):
        with tf.variable_scope(name, reuse=self._reuse):
            Q = self._network(self.state, self.action, self.action_dim, self._reuse)
            Q_with_actor = self._network(self.state, self.actor_action, self.action_dim, True)

        return Q, Q_with_actor

    def _network(self, state, action, action_dim, reuse):
        self._reset_counter('dense_resnet')
        
        with tf.variable_scope('net', reuse=reuse):
            x = self._dense(state, 512-action_dim, kernel_initializer=tf_utils.kaiming_initializer())
            x = tf.concat([x, action], 1)
            x = self._dense_resnet_norm_activation(x, 512)
            x = self._dense_norm_activation(x, 256)
            x = self._dense(x, 1, name='Q')

        return x
        
class DoubleCritic(Critic):
    """ Interface """
    def __init__(self, 
                 name, 
                 args, 
                 graph, 
                 state,
                 action,
                 actor_action, 
                 action_dim,
                 reuse=False, 
                 is_target=False, 
                 scope_prefix=''):
        super().__init__(name, 
                         args, 
                         graph, 
                         state, 
                         action,
                         actor_action,
                         action_dim,
                         reuse=reuse,
                         is_target=is_target, 
                         scope_prefix=scope_prefix)

    """ Implementation """
    def _build_graph(self, **kwargs):
        self.Q1, self.Q1_with_actor = self._build_net(name='Q1')
        self.Q2, self.Q2_with_actor = self._build_net(name='Q2')
        self.Q_with_actor = tf.minimum(self.Q1_with_actor, self.Q2_with_actor, 'Q_with_actor')