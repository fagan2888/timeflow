import numpy as np
from keras import backend as K
from keras.layers import (Input, Dense, TimeDistributed, Activation, LSTM, GRU,
                          Dropout, merge, Reshape, Flatten, RepeatVector,
                          Recurrent, AtrousConv1D, Conv1D,
                          MaxPooling1D, SimpleRNN, BatchNormalization)
from keras.models import Model, Sequential

import sample_data
import keras_util as ku


# input: (t, m, e), (t, m), or (m)
def encoder(model_input, layer, size, num_layers, drop_frac=0.0, batch_norm=False,
            output_size=None, filter_length=None, **parsed_args):
    if output_size is None:
        output_size = size

    encode = model_input
    for i in range(num_layers):
        kwargs = {}
        if issubclass(layer, Recurrent):
            kwargs['return_sequences'] = (i < num_layers - 1)
        if issubclass(layer, Conv1D):
            kwargs['activation'] = 'relu'  # TODO pass in
            kwargs['filter_length'] = filter_length
            kwargs['border_mode'] = 'same'
        if issubclass(layer, AtrousConv1D):
            kwargs['atrous_rate'] = 2 ** i
            
        encode = layer(size if i < (num_layers - 1) else output_size, **kwargs)(encode)
        if drop_frac > 0.0:
            encode = Dropout(drop_frac)(encode)
        if batch_norm:
            encode = BatchNormalization()(encode)

    if len(encode.get_shape()) > 2:
        encode = Flatten()(encode)
    return encode


# aux input: (t) or (t, e) or None
# output: just m (output_len==1)
def decoder(encode, layer, n_step, size, num_layers, drop_frac=0.0, aux_input=None,
            batch_norm=False, filter_length=None, **parsed_args):
    decode = RepeatVector(n_step)(encode)
    if aux_input is not None:
        decode = merge([aux_input, decode], mode='concat')

    for i in range(num_layers):
        kwargs = {}
        if issubclass(layer, Recurrent):
            kwargs['return_sequences'] = True
        if issubclass(layer, Conv1D):
            kwargs['activation'] = 'relu'  # TODO pass in
            kwargs['filter_length'] = filter_length
            kwargs['border_mode'] = 'same'
        if issubclass(layer, AtrousConv1D):
            kwargs['atrous_rate'] = 2 ** i
            
        decode = layer(size, **kwargs)(decode)
        if drop_frac > 0.0:
            decode = Dropout(drop_frac)(decode)
        if batch_norm:
            decode = BatchNormalization()(decode)

    decode = TimeDistributed(Dense(1, activation='linear'))(decode)
    return decode


def main(args=None):
    if not args:
        args = ku.parse_model_args()

    np.random.seed(0)
    train = np.arange(args.N_train); test = np.arange(args.N_test) + args.N_train
    X, Y, X_raw = sample_data.periodic(args.N_train + args.N_test, args.n_min, args.n_max,
                                       t_max=2*np.pi, even=args.even, A_shape=5.,
                                       noise_sigma=args.sigma, w_min=0.1, w_max=1.)

    if args.even:
        X = X[:, :, 1:2]
    else:
        X[:, :, 0] = np.c_[np.diff(X[:, :, 0]), np.zeros(X.shape[0])]

    model_type_dict = {'gru': GRU, 'lstm': LSTM, 'vanilla': SimpleRNN,
                       'conv': Conv1D, 'atrous': AtrousConv1D}
    K.set_session(ku.limited_memory_session(args.gpu_frac, args.gpu_id))

    main_input = Input(shape=(X.shape[1], X.shape[-1]), name='main_input')
    if args.even:
        model_input = main_input
        aux_input = None
    else:
        aux_input = Input(shape=(X.shape[1], X.shape[-1] - 1), name='aux_input')
        model_input = [main_input, aux_input]

    encode = encoder(main_input, layer=model_type_dict[args.model_type], **vars(args))
    decode = decoder(encode, layer=model_type_dict[args.model_type], n_step=X.shape[1],
                     aux_input=aux_input, **vars(args))
    model = Model(model_input, decode)

    run = ku.get_run_id(**vars(args))
 
    if args.even:
        history = ku.train_and_log(X[train], X[train], run, model, **vars(args))
    else:
        sample_weight = (X[train, :, -1] != -1)
        history = ku.train_and_log({'main_input': X[train], 'aux_input': X[train, :, 0:1]},
                                   X_raw[train, :, 1:2], run, model,
                                   sample_weight=sample_weight, **vars(args))
    return X, Y, model, args


if __name__ == '__main__':
    X, Y, model, args = main()
