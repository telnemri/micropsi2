__author__ = 'rvuine'

from micropsi_core.nodenet.netapi import NetAPI

class TheanoNetAPI(NetAPI):
    """
    Theano / numpy extension of the NetAPI, giving native modules access to bulk operations and efficient
    data structures for machine learning purposes.
    """

    def __init__(self, nodenet):
        super(TheanoNetAPI, self).__init__(nodenet)
        self.__nodenet = nodenet

    @property
    def floatX(self):
        return self.__nodenet.numpyfloatX

    def announce_nodes(self, nodespace_uid, numer_of_nodes, average_element_per_node):
        self.__nodenet.announce_nodes(nodespace_uid, numer_of_nodes, average_element_per_node)

    def get_selectors(self, group):
        """
        Returns The indices for the elements for the given group, as an ndarray of ints.
        These indices are valid in a, w, and theta.
        """
        return self.__nodenet.nodegroups[group]

    def get_a(self):
        """
        Returns the theano shared variable with the activation vector
        """
        return self.__nodenet.a

    def get_w(self):
        """
        Returns the theano shared variable with the link weights
        Caution: Changing non-zero values to zero or zero-values to non-zero will lead to inconsistencies.
        """
        return self.__nodenet.w

    def get_theta(self):
        """
        Returns the theano shared variable with the "theta" parameter values
        """
        return self.__nodenet.g_theta

    def decay_por_links(self, nodespace_uid):
        """ Decays all por-links in the given nodespace """
        #    por_cols = T.lvector("por_cols")
        #    por_rows = T.lvector("por_rows")
        #    new_w = T.set_subtensor(nodenet.w[por_rows, por_cols], nodenet.w[por_rows, por_cols] - 0.0001)
        #    self.decay = theano.function([por_cols, por_rows], None, updates={nodenet.w: new_w}, accept_inplace=True)
        import numpy as np
        from .theano_definitions import node_from_id, PIPE, POR
        porretdecay = self.__nodenet.get_modulator('por_ret_decay')
        ns = self.get_nodespace(nodespace_uid)
        partition = ns._partition
        if partition.has_pipes and porretdecay != 0:
            ns_id = node_from_id(nodespace_uid)
            node_ids = np.where(partition.allocated_node_parents == ns_id)[0]
            pipe_ids = np.where(partition.allocated_nodes == PIPE)[0]
            ns_pipes = np.intersect1d(node_ids, pipe_ids, assume_unique=True)
            por_cols = partition.allocated_node_offsets[ns_pipes] + POR
            w = partition.w.get_value(borrow=True)
            por_rows = np.nonzero(w[:, por_cols] > 0.)[0]
            cols, rows = np.meshgrid(por_cols, por_rows)
            w_update = w[rows, cols]
            w_update *= (1 - porretdecay)
            w[rows, cols] = w_update
            partition.w.set_value(w, borrow=True)
