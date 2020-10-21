import mir_eval
import numpy as np
import scipy.io as sio
import pandas as pd
import glob
import os
from pesq import pesq

'''Set of functions to extract quality metrics (SDR, SIR, SAR) for DANet performance assessment'''


class metrics_sequences:
    """Container to store the individual metrics (e.g. SDR, SIR or SAR) of a sequence or
    several utterances in stacked format"""
    def __init__(self, individuals):

        'individuals shall have a dimension for stacking'
        if len(individuals.shape) < 3:
            individuals = np.expand_dims(individuals, axis=0)

        self.individuals = individuals
        self.mean = np.mean(individuals, axis=0)
        self.std_deviation = np.std(individuals, axis=0)

def quality_eval_one_audio(estimated_sources, reference_sources, start_ind=float('inf'), end_ind=float('inf'), print_SDR=True):
    """
    Compute SDR, SIR and SAR of input

    INPUTS:
        estimated_sources(n_sources, num_samples): estimated sources
        reference_sources(n_sources, num_samples): reference sources
        start_ind, end_ind: int, index of first and last sample of one utterance
        print_SDR(bool): true, if metric information shall be shown

    Possibly three cases:
        - take 1 minute sequence and compute quality measures
        - use several concatenated sequences and compute quality measures once, n < 0,
                  -n gives number of sequences that are concatenated
        - use only one utterance and compute quality measures for it, use parameters start_ind, end_ind and m

    OUTPUT:
        save_measures: array with SDR, SIR, SAR, PESQ values
    """
    if estimated_sources.shape[0] != reference_sources.shape[0]:
        raise ValueError('quality_eval.py: Same number of estimated and reference signals required.')

    'align number of samples for each source'
    if start_ind < float('inf'):
        for i in range(estimated_sources.shape[0]):
            estimated_sources[i] = estimated_sources[i][start_ind:end_ind]
            reference_sources[i] = reference_sources[i][start_ind:end_ind]

    'get input quality measures'
    mixture_input = np.sum(reference_sources, axis=0, keepdims=True)
    mixture_input = np.tile(mixture_input, reps=(reference_sources.shape[0], 1))
    (sdr, sir, sar, perm) = mir_eval.separation.bss_eval_sources(reference_sources, mixture_input)
    pesq_var = np.array([pesq(8000, reference_sources[0], mixture_input[0], mode='nb')]) # 8000 kHz sampling freq, narrowband mode
    for i in range(1, reference_sources.shape[0]):
        pesq_var = np.concatenate([pesq_var, np.array([pesq(8000, reference_sources[i], mixture_input[i], mode='nb')])])

    metrics_input = np.array([sdr, sir, sar, pesq_var]).T  # (nr_sources, 4) SDR,SIR,SAR, PESQ
    if print_SDR:
        print('SDR_input_speech: ' + str(sdr[0]))
        print('PESQ_input_speech: ' + str(pesq_var[0]))

    'compute output quality measures'
    (sdr, sir, sar, perm) = mir_eval.separation.bss_eval_sources(reference_sources, estimated_sources)
    pesq_var = np.array([pesq(8000, reference_sources[0], estimated_sources[0], mode='nb')])  # 8000 kHz sampling freq, narrowband mode
    for i in range(1, reference_sources.shape[0]):
        pesq_var = np.concatenate([pesq_var, np.array([pesq(8000, reference_sources[i], estimated_sources[i], mode='nb')])])
    metrics_output = np.array([sdr, sir, sar, pesq_var]).T  # (nr_sources, 4) SDR,SIR,SAR, PESQ in same ordering as nr_sources inputs
    if print_SDR:
        print('SDR_output_speech: ' + str(sdr[0]))
        print('PESQ_output_speech: ' + str(pesq_var[0]))

    return metrics_input, metrics_output

# Settings
Fs= 16000
pesq_window = 30    #calculate pesq score per 30 seconds
SNR_situ_array = ["-21","-26","-31","-36","-41","-46"]
dB_exchange_dict = {"-21":"-5dB","-26":"0dB","-31":"5dB","-36":"10dB","-41":"15dB","-46":"20dB"}
database_dir='./generated_files/'
noi_type_str_vec = {1:'PED', 2:'CAF', 3:'STR'}
noise_type_num = 3

for SNR in SNR_situ_array:
    for k in range(1,noise_type_num+1):
        mixture_dir = database_dir + SNR + '/y_test_data_snr_' + SNR + '_' + str(k) + '.mat'
        reference_dir = database_dir + SNR + '/s_' + str(k) + '.mat'
        s_hat_baseline_dir= database_dir + SNR + '/s_hat_test_data_snr_' + SNR + '_model_6snrs_baseline_' + str(k) + '.mat'
        s_hat_pw_dir = database_dir + SNR + '/s_hat_test_data_snr_' + SNR + '_model_6snrs_weight_filter_AMR_direct_freqz_' + str(k) + '.mat'

        # Load data
        mixture_tmp = sio.loadmat(os.path.normcase(mixture_dir))
        mixture = mixture_tmp['y_vec_temp']
        reference_tmp = sio.loadmat(os.path.normcase(reference_dir))
        reference = reference_tmp['s_vec_temp']
        s_hat_baseline_tmp = sio.loadmat(os.path.normcase(s_hat_baseline_dir))
        s_hat_baseline = s_hat_baseline_tmp['s_hat_temp']
        s_hat_pw_tmp = sio.loadmat(os.path.normcase(s_hat_pw_dir))
        s_hat_pw = s_hat_pw_tmp['s_hat_temp']

        # Calculate measurements
        data_length = len(reference[0])
        for i in range(data_length//(pesq_window*Fs)):       # calculate pesq per 30 seconds
            _, mixture_score = quality_eval_one_audio(mixture[:, i * pesq_window * Fs:(i + 1) * pesq_window * Fs],
                                                 reference[:, i * pesq_window * Fs:(i + 1) * pesq_window * Fs])
            _, baseline_score = quality_eval_one_audio(s_hat_baseline[:, i * pesq_window * Fs:(i + 1) * pesq_window * Fs],
                                                      reference[:, i * pesq_window * Fs:(i + 1) * pesq_window * Fs])
            _, pw_score = quality_eval_one_audio(s_hat_pw[:, i * pesq_window * Fs:(i + 1) * pesq_window * Fs],
                                                 reference[:, i * pesq_window * Fs:(i + 1) * pesq_window * Fs])
            mixture_score = list(mixture_score.reshape(-1))
            baseline_score = list(baseline_score.reshape(-1))
            pw_score = list(pw_score.reshape(-1))

            # Store as csv files
            mixture_score.append(' ')
            baseline_score.append(' ')
            pw_score.append(' ')
            dataframe = pd.DataFrame({'':['SDR','SIR','SAR','PESQ',' '], 'mixture':mixture_score,'baseline':baseline_score,'percep_loss':pw_score})
            dataframe.to_csv('./measurements/' + dB_exchange_dict[SNR] + '/' + noi_type_str_vec[k] + '_noise_case_measurement.csv', index=False, mode = 'a+', sep=',')

