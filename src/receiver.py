import numpy as np

import params
import enc_dec_helper
import plot_helper
import synchronization
import fourier_helper
import pulses
import mappings


def decoder(y, mapping):
    """
    :param y: the observation vector, i.e the received symbols
    :param mapping: the chosen mapping for the communication
    :return: integers between 0 and M-1, i.e integers corresponding to the bits sent
    """

    # Make sure y and mapping have less or equal than 2 dimensions
    if len(y.shape) > 2 or len(mapping.shape) > 2:
        raise AttributeError("One of the vectors y and mapping has more than 2 dimensions!")

    # If y is a column vector, make it a row vector
    n_elems_axis_0_y = np.size(y, 0)
    if n_elems_axis_0_y != 1:
        y = y.reshape(1, n_elems_axis_0_y)
    else:
        y = y.reshape(1, np.size(y, 1))

    # If mapping is a row vector, make it a column vector
    if np.size(mapping, 0) == 1:
        mapping = mapping.reshape(np.size(mapping, 1), 1)
    else:
        mapping = mapping.reshape(np.size(mapping, 0), 1)

    if params.verbose:
        print("y: {}\n{}".format(np.shape(y), y))
        print("mapping: {} \n{}".format(np.shape(mapping), mapping))

    # Number of symbols in the mapping
    M = np.size(mapping, 0)
    # Number of symbols received
    S = np.size(y, 1)

    distances = np.transpose(abs(np.tile(y, (M, 1)) - np.tile(mapping, (1, S))))
    ints = np.argmin(distances, 1)
    if params.verbose:
        print("Equivalent integers:\n{}".format(ints))
    return ints


def ints_to_message(ints):
    """
    :param ints: integers between 0 and M-1, i.e integers corresponding to the bits sent
    :return: the corresponding guessed message as a string
    """

    # Convert the ints to BITS_PER_SYMBOL bits
    bits = ["{0:0{bits_per_symbol}b}".format(i, bits_per_symbol=params.BITS_PER_SYMBOL) for i in ints]
    if params.verbose:
        print("Groups of BITS_PER_SYMBOL bits representing each integer:\n{}".format(bits))

    # Make a new string with it
    bits = ''.join(bits)
    if params.verbose:
        print("Bits grouped all together:\n{}".format(bits))

    # Slice the string into substrings of 7 characters
    bits = [bits[i:i+7] for i in range(0, len(bits), 7)]
    if params.verbose:
        print("Groups of 7 bits:\n{}".format(bits))

    # Add a zero at the beginning of each substring (cf transmitter)
    new_bits = []
    for sub_string in bits:
        new_bits.append('0' + sub_string)
    if params.verbose:
        print("Groups of 8 bits (0 added at the beginning, cf. transmitter):\n{}".format(new_bits))

    # Convert from array of bytes to string
    message = ''.join(enc_dec_helper.bits2string(new_bits))
    print("Message received:\n{}".format(message))

    return message


def received_from_server():
    # Read the received samples from the server
    output_sample_file = open(params.output_sample_file_path, "r")
    received_samples = [float(line) for line in output_sample_file.readlines()]
    output_sample_file.close()

    # Plot the received samples
    plot_helper.plot_complex_function(received_samples, "Received samples in time domain")
    plot_helper.fft_plot(received_samples, "Received samples in frequency domain", shift=True)

    # Read the preamble samples saved previously
    preamble_samples_file = open(params.preamble_sample_file_path, "r")
    preamble_samples = [complex(line) for line in preamble_samples_file.readlines()]
    preamble_samples_file.close()

    plot_helper.plot_complex_function(preamble_samples, "Preamble samples in time domain")

    # Find the frequency range that has been removed
    range_indices, removed_freq_range = fourier_helper.find_removed_freq_range_2(received_samples)
    print("Removed frequency range: {}".format(removed_freq_range))

    # Choose a frequency among the 3 available frequency ranges
    if removed_freq_range == 0:
        fc = np.mean(params.FREQ_RANGES[1])
    else:
        fc = np.mean(params.FREQ_RANGES[0])

    # Demodulate the samples with the appropriate frequency fc
    demodulated_samples = fourier_helper.demodulate(received_samples, fc)
    plot_helper.plot_complex_function(demodulated_samples, "Demodulated samples in Time domain")
    plot_helper.fft_plot(demodulated_samples, "Demodulated samples in Time domain", shift=True)

    # Match filter
    _, h = pulses.root_raised_cosine()
    h_matched = np.conjugate(h[::-1])
    y = np.convolve(demodulated_samples, h_matched)
    plot_helper.plot_complex_function(y, "y in Time domain")
    plot_helper.fft_plot(y, "y in Frequency domain", shift=True)

    # Find the delay
    delay = synchronization.maximum_likelihood_sync(demodulated_samples, synchronization_sequence=preamble_samples)
    print("The delay is of {} samples".format(delay))

    # Crop the samples (remove the ramp-up and ramp-down)
    # TODO find the length of the ending garbage
    garbage = []
    data_samples = y[delay + len(preamble_samples) - int(len(h)/2) - 1:len(y) - int(len(h)/2) - len(garbage)]
    plot_helper.plot_complex_function(data_samples, "y after puting the right sampling time")

    # Down-sample
    symbols_received = data_samples[::params.USF]
    print("Symbols received:\n{}", format(symbols_received))
    plot_helper.plot_complex_symbols(symbols_received, "Data symbols received")

    # Decode the symbols
    ints = decoder(symbols_received, mappings.mapping)
    ints_to_message(ints)


# Intended for testing (to run the program, run main.py)
if __name__ == "__main__":

    received_from_server()

    # TODO Demodulate (cos and sin to go to baseband)
    # TODO      Modulation type 1: choose 1 of the 3 available frequency ranges, and shift it to 0
    # TODO      Modulation type 2: choose the available frequency range among the 2 sent, and shift it to 0
    # TODO Lowpass (Discard other frequency ranges and noise)
    # TODO      Modulation type 1: low-pass between -1000Hz and 1000Hz
    # TODO      Modulation type 2: low_pass between -2000Hz and 2000Hz
    # TODO After all that, we can do the synchronization between received_samples_baseband and preamble_samples
    # TODO When the delay is found, we can start sampling (depends on SPAN and T I guess)
    # TODO Then, we give this complex array to the decoder

    # observation_test = np.array([1+2j, -1-0.5j, -1+0.5j, 1+0.1j, 1-2j, 1+2j, -1-0.5j])
    # plot_helper.plot_complex_symbols(observation_test, "observation", "blue")
    # ints = decoder(observation_test, helper.mapping)
    # ints_to_message(ints)
