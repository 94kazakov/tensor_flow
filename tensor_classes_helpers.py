import tensorflow as tf
import data_help as DH
import numpy as np

"""
NOTES:
1) when tensor([a,b,c])*tensor([b,c]) = tensor([a,b,c])
        tensor([a,b])*tensor([b]) = tensor([a,b])
        OR
        tensor([a,1])*tensor([b]) = tensor([a,b]) - equivalent
        OR
        tensor([b])*tensor([a,1]) = tensor([a,b])
2) dynamics shape vs static:
        tf.shape(my_tensor)[0] - dynamics (as graph computes) ex: batch_size=current_batch_size
        my_tensor.get_shape() - static (graph's 'locked in' value) ex: batch_size=?
3) output = tf.py_func(func_of_interest)
    the output of py_func needs to be returned in order for func_of_interest to ever be "executed"
4) tf.Print() - not sure how to use. It seems like it still needs to be evaluated with the session.
5) how to get shape of dynamic dimension? - can't.
6) start: tensorboard --logdir=run1:logs/run1/ --port 6006
7) To make variable not learnable, have to specify either:
    tf.Variable(my_weights, trainable=False)
    OR
    optimizer = tf.train.AdagradOptimzer(0.01)
    first_train_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                         "scope/prefix/for/first/vars")
    first_train_op = optimizer.minimize(cost, var_list=first_train_vars)
    second_train_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                          "scope/prefix/for/second/vars")
    second_train_op = optimizer.minimize(cost, var_list=second_train_vars)
8) When our variable names/dimensions are not exactly like they were in the saved model, it won't work.

Issues:

Tasks:
 - how to access variable by name?  (ex: I want to retrieve a named variable)
 - use scopes: https://github.com/llSourcell/tensorflow_demo/blob/master/board.py

*Lab number: 1b11
"""

def get_tensor_by_name(name):
    print tf.all_variables()
    return [v for v in tf.global_variables() if v.name == name][0]

def input_placeholder(max_length_seq=100, 
                        frame_size=3, name=None):
    
    x = tf.placeholder("float", 
                        [None, max_length_seq, 
                        frame_size], name=name) #None - for dynamic batch sizing
    return x

def output_placeholder(max_length_seq=100, 
                        number_of_classes=50, name=None):
    
    y = tf.placeholder("float", 
                        [None, max_length_seq,  
                        number_of_classes], name=name)
    return y

def weights_init(n_input, n_output, name=None, small=False, idendity=False, forced_zero=False):
    init_matrix = None
    if small:
        init_matrix = tf.random_normal([n_input, n_output], stddev=0.01)
    else:
        init_matrix = tf.random_normal([n_input, n_output])

    if idendity:
        init_matrix = tf.diag(tf.ones([n_input]))
    elif forced_zero:
        init_matrix = tf.diag(tf.zeros([n_input]))

    trainable = True
    if idendity or forced_zero:
        trainable = False
    learnable_print = lambda bool: "Learned" if bool else "Not Learned"
    print name, learnable_print(trainable)

    W = tf.Variable(init_matrix, name=name, trainable=trainable)
    return W

def bias_init(n_output, name=None, small=False, forced_zero=False):
    if small: #bias is negative so that initially, bias is pulling tthe sigmoid towards 0, not 1/2.
        b = tf.random_normal([n_output], mean=-4.0, stddev = 0.01)
    else:
        b = tf.random_normal([n_output])

    if forced_zero:
        b = tf.stop_gradient(tf.zeros([n_output]))

    trainable = True
    if  forced_zero:
        trainable = False
    learnable_print = lambda bool: "Learned" if bool else "Not Learned"
    print name, learnable_print(trainable)

    b = tf.Variable(b, trainable=trainable, name=name)
    return b

def softmax_init(shape):
    # softmax initialization of size shape casted to tf.float32
    return tf.cast(tf.nn.softmax(tf.Variable(tf.random_normal(shape))), tf.float32)

def cut_up_x(x_set, ops):
    # x_set: [batch_size, max_length, frame_size]
    x_set = tf.transpose(x_set, [1,0,2])
    x_set = tf.cast(x_set, tf.float32)
    # x_set: [max_length, batch_size, frpoame_size]
    # splits accross 2nd axis, into 3 splits of x_set tensor (very backwards argument arrangement)
    x, xt, yt = tf.split(x_set, 3, 2)

    # at this point x,xt,yt : [max_length, batch_size, 1] => collapse
    x = tf.reduce_sum(x, reduction_indices=2)
    #xt = tf.reduce_sum(xt, reduction_indices=2)
    #yt = tf.reduce_sum(yt, reduction_indices=2)

    # one hot embedding of x (previous state)
    x = tf.cast(x, tf.int32) # needs integers for one hot embedding to work
    # depth=n_classes, by default 1 for active, 0 inactive, appended as last dimension
    x_vectorized = tf.one_hot(x - 1, ops['n_classes'], name='x_vectorized')
    # x_vectorized: [max_length, batch_size, n_classes]
    return x_vectorized, xt, yt

def errors_and_losses(sess, P_x, P_y, P_len, P_mask, P_batch_size, T_accuracy,  T_cost, dataset_names, datasets, ops):
    # passes all needed tensor placeholders to fill with passed datasets
    # computers errors and losses for train/test/validation sets
    # Depending on what T_accuracy, T_cost are, different nets can be called
    accuracy_entry = []
    losses_entry = []
    for i in range(len(dataset_names)):
        dataset = datasets[i]
        dataset_name = dataset_names[i]
        batch_indeces_arr = DH.get_minibatches_ids(len(dataset), ops['batch_size'], shuffle=True)

        acc_avg = 0.0
        loss_avg = 0.0
        for batch_ids in batch_indeces_arr:
            x_set, batch_y, batch_maxlen, batch_size, mask = DH.pick_batch(
                                            dataset = dataset,
                                            batch_indeces = batch_ids, 
                                            max_length = ops['max_length']) 
            accuracy_batch, cost_batch = sess.run([T_accuracy, T_cost],
                                                    feed_dict={
                                                        P_x: x_set,
                                                        P_y: DH.embed_one_hot(batch_y, 0.0, ops['n_classes'], ops['max_length']),
                                                        P_len: batch_maxlen,
                                                        P_mask: mask,
                                                        P_batch_size: batch_size})
            acc_avg += accuracy_batch
            loss_avg += cost_batch
        accuracy_entry.append(acc_avg/len(batch_indeces_arr))
        losses_entry.append(cost_batch/len(batch_indeces_arr))
    return accuracy_entry, losses_entry
    
def LSTM_params_init(ops):
    W = {'out': weights_init(n_input=ops['n_hidden'],
                                 n_output=ops['n_classes'],
                                 name='W_out')}
    b = {'out': bias_init(
        ops['n_classes'],
        name='b_out')}

    params = {
        'W': W,
        'b': b
    }
    return params


def RNN(x_set, T_seq_length, ops, params):
    W = params['W']
    b = params['b']


    # lstm cell
    #lstm_cell = rnn_cell.BasicLSTMCell(n_hidden, forget_bias=1.0)
    lstm_cell = tf.contrib.rnn.BasicLSTMCell(ops['n_hidden'], forget_bias=1.0)
    # get lstm_cell's output
    # dynamic_rnn return by default: 
    #   outputs: [max_time, batch_size, cell.output_size]
    x, xt, yt = cut_up_x(x_set, ops)

    x = tf.concat([x, xt, yt], 2) #[max_time, batch_size, n_hid + 2]
    outputs, states = tf.nn.dynamic_rnn(
                                lstm_cell, 
                                x, 
                                dtype=tf.float32,
                                sequence_length=T_seq_length,
                                time_major=True)
    
    # linear activation, using rnn innter loop last output
    # project into class space: x-[max_time, hidden_units], T_W-[hidden_units, n_classes]
    output_projection = lambda x: tf.nn.softmax(tf.matmul(x, W['out']) + b['out'])

    return tf.map_fn(output_projection, outputs)


def HPM_params_init(ops):
    # W_in: range of each element is from 0 to 1, since each weight is a "probability" for each hidden unit.
    # W_recurrent:
    #ALERNATE
    # W = {'in': weights_init(n_input=ops['n_classes'],
    #                         n_output=ops['n_hidden'],
    #                         name='W_in',
    #                         idendity=True),
    #      'recurrent': weights_init(n_input=ops['n_hidden'],
    #                                n_output=ops['n_hidden'],
    #                                name='W_recurrent',
    #                                small=True,
    #                                forced_zero=True),
    #      'out':  weights_init(n_input=ops['n_hidden'],
    #                                n_output=ops['n_classes'],
    #                                name='W_out',
    #                                idendity=True)
    #      }
    #
    # b = {
    #      'recurrent': bias_init(n_output=ops['n_hidden'],
    #                      name='b_recurrent',
    #                      small=True,
    #                      forced_zero=True),
    #      'out': bias_init(n_output=ops['n_classes'],
    #                      name='b_out',
    #                      small=False,
    #                      forced_zero=True)
    #     }

    #OR
    W = {'in': weights_init(n_input=ops['n_classes'],
                            n_output=ops['n_hidden'],
                            name='W_in'),
         'recurrent': weights_init(n_input=ops['n_hidden'],
                                   n_output=ops['n_hidden'],
                                   name='W_recurrent',
                                   small=True),
         'out': weights_init(n_input=ops['n_hidden'],
                             n_output=ops['n_classes'],
                             name='W_out')
         }

    b = {
        'recurrent': bias_init(n_output=ops['n_hidden'],
                               name='b_recurrent',
                               small=True),
        'out': bias_init(n_output=ops['n_classes'],
                         name='b_out')
    }

    # ALTERNATE
    timescales = 2.0 ** np.arange(-7,7)#0,12)#(-7,7) vs (0, 1)
    #timescales = 2.0 ** np.array([1,2,3,4,5,6,7,8,9,10,11])
    n_timescales = len(timescales)
    gamma = 1.0 / timescales
    c = tf.fill([n_timescales], 1.0 / n_timescales)

    if ops['unique_mus_alphas']:
        mu = tf.Variable(-tf.log(
                            tf.fill([ops['n_hidden'], n_timescales], 1e-3)),
                         name='mu', trainable=True, dtype=tf.float32)
        alpha = tf.Variable(
                    tf.random_uniform([ops['n_hidden'], n_timescales], minval=0.5, maxval=0.5001, dtype=tf.float32),
                    name='alpha')
    else:
        # TODO: Understand why and how it works. so by putting  a log there, we are skewing the gradient?
        mu = tf.Variable(-tf.log(
                            tf.fill([n_timescales], 1e-3)),
                         name='mu', trainable=True, dtype=tf.float32)
        # alpha is just initialized to a const value
        alpha = tf.Variable(
                    tf.random_uniform([n_timescales], minval=0.5, maxval=0.5001, dtype=tf.float32),
                    name='alpha')


    params = {
        'W': W,
        'b': b,
        'timescales': timescales,
        'n_timescales': n_timescales,
        'mu': mu,
        'gamma': gamma,
        'alpha': alpha,
        'c': c
    }
    return params



# HPM logic:
# Learn weights of the hawkes' processes.
# Have multiple timescales for each process that are ready to "kick-in".
# For a certain event type in whichever time-scale works best => reinitialize c_
# every new sequence. 
def HPM(x_set, ops, params, batch_size):
    # init h, alphas, timescales, mu etc
    # convert x from [batch_size, max_length, frame_size] to
    #               [max_length, batch_size, frame_size]
    # and step over each time_step with _step function
    batch_size = tf.cast(batch_size, tf.int32)  # cast placeholder into integer

    W = params['W']
    b = params['b']
    n_timescales = params['n_timescales']

    gamma = params['gamma']
    # Scale important params by gamma
    alpha_init = params['alpha']
    mu_init = params['mu']
    # exp(--log(x) = x
    mu = tf.exp(-mu_init)
    alpha = tf.nn.softplus(alpha_init) * gamma

    c_init = params['c']


    def _C(likelyhood, prior_of_event):
        # timescale posterior
        # formula 3 - reweight the ensemble
        # likelihood, prior, posterior have dimensions:
        #       [batch_size, n_hid, n_timescales]
        minimum = 1e-30
        # likelyhood = c_
        timescale_posterior = prior_of_event * likelyhood + minimum
        timescale_posterior = timescale_posterior / tf.reduce_sum(timescale_posterior,
                                                                  reduction_indices=[2],
                                                                  keep_dims=True)

        return timescale_posterior

    def _Z(h_prev, delta_t):
        # Probability of no event occuring at h_prev intensity till delta_t (integral over intensity)
        # delta_t: batch_size x n_timescales
        # h_prev: batch_size x n_hid x n_timescales
        # time passes
        # formula 1

        h_prev -= mu
        delta_t = tf.expand_dims(delta_t, 2)  # [batch_size, 1] -> [batch_size, 1, 1]

        _gamma = gamma #local copy since we can't modify global copy
        if ops['unique_mus_alphas']:
            _gamma = tf.zeros([ops['n_hidden'], n_timescales], tf.float32) + gamma #[n_timescale]->[n_hid, n_timescale}

        h_times_gamma_factor = h_prev * (1.0 - tf.exp(-_gamma * delta_t)) / gamma
        result = tf.exp(-(h_times_gamma_factor + mu*delta_t), name='Z')
        return result

    def _H(h_prev, delta_t):
        # decay current intensity
        # TODO: adopt into _Z, to avoid recomputing
        h_prev -= mu
        h_prev_tr = tf.transpose(h_prev, [1,0,2]) #[bath_size, n_hid, n_timescales] -> [n_hid, batch_size, n_timescales}
        # gamma * delta_t: [batch_size, n_timescales]
        result = tf.exp(-gamma * delta_t) * h_prev_tr
        return tf.transpose(result, [1,0,2], name='H') + mu

    def _y_hat(z, c):
        # Marginalize timescale
        # (batch_size, n_hidden, n_timescales)
        # output: (batch_size, n_hidden)
        # c - timescale probability
        # z - quantity
        return tf.reduce_sum(z * c, reduction_indices = [2], name='yhat')

    def _step(accumulated_vars, input_vars):
        h_, c_, _, _, _ = accumulated_vars
        x, xt, yt = input_vars
        # : mask: (batch_size, n_classes
        # : x - vectorized x: (batch_size, n_classes)
        # : xt, yt: (batch_size, 1)
        # : h_, c_ - from previous iteration: (batch_size, n_hidden, n_timescales)

        # 1) event
        # current z, h
        h = _H(h_, xt)
        z = _Z(h_, xt) #(batch_size, n_hidden, n_timescales)
        # input part:


        # recurrent part: since y_hat is for t+1, we wait until here to calculate it rather
        #                   rather than in previous iteration

        y_hat = _y_hat(z, c_) # :(batch_size, n_hidden)
        # ALTERNATE
        event = tf.sigmoid(
                        tf.matmul(x, W['in']) +  #:[batch_size, n_classes]*[n_classes, n_hid]
                        tf.matmul(y_hat, W['recurrent']) + b['recurrent'])  #:(batch_size, n_hid)*(n_hid, n_hid)
        #OR TODO: make a flag for this running config
        #event = tf.matmul(x, W['in'])
        # 2) update c
        event = tf.expand_dims(event, 2) # [batch_size, n_hid] -> [batch_size, n_hid, 1]
        # to support multiplication by [batch_size, n_hid, n_timescales]
        # TODO: check Mike's code on c's update. Supposedely, just a tad bit more efficient
        c = event * _C(z*h, c_) + (1.0 - event) * _C(z, c_) # h^0 = 1
        # c = _C(z, c_)
        # c = event * _C(h, c) + (1.0 - event) * c

        # 3) update intensity
        # - here alpha can either be a vector [n_timescales] or a matrix [n_hid, n_timescales]
        h += alpha * event

        # 4) apply mask & predict next event
        z_hat = _Z(h, yt)

        y_predict = _y_hat(1 - z_hat, c)

        return [h, c, y_predict, event, z_hat]



    x, xt, yt = cut_up_x(x_set, ops)
    print x

    # collect all the variables of interest
    T_summary_weights = tf.zeros([1],name='None_tensor')
    if ops['collect_histograms']:
        tf.summary.histogram('W_in', W['in'], ['W'])
        tf.summary.histogram('W_rec', W['recurrent'], ['W'])
        tf.summary.histogram('W_out', W['out'], ['W'])
        tf.summary.histogram('b_rec', b['recurrent'], ['b'])
        tf.summary.histogram('b_out', b['out'], ['b'])
        tf.summary.histogram('c_init', c_init, ['init'])
        tf.summary.histogram('mu_init', mu, ['init'])
        tf.summary.histogram('alpha_init', params['alpha'], ['init'])
        T_summary_weights = tf.summary.merge([
                                tf.summary.merge_all('W'),
                                tf.summary.merge_all('b'),
                                tf.summary.merge_all('init')
                                ], name='T_summary_weights')


    rval = tf.scan(_step,
                    elems=[x, xt, yt],
                    initializer=[
                        tf.zeros([batch_size, ops['n_hidden'], n_timescales], tf.float32) + mu, #h
                        tf.zeros([batch_size, ops['n_hidden'], n_timescales], tf.float32) + c_init, #c
                        tf.zeros([batch_size, ops['n_hidden']], tf.float32), # yhat
                        tf.zeros([batch_size, ops['n_hidden'], 1]), #debugging placeholder
                        tf.zeros([batch_size, ops['n_hidden'], n_timescales])

                    ]
                   , name='hpm/scan')

    hidden_prediction = tf.transpose(rval[2], [1, 0, 2]) # -> [batch_size, n_steps, n_classes]
    output_projection = lambda x: tf.clip_by_value(tf.nn.softmax(tf.matmul(x, W['out']) + b['out']), 1e-8, 1.0)

    return tf.map_fn(output_projection, hidden_prediction), T_summary_weights, [rval[0], rval[1], rval[2], rval[3], rval[4]]
