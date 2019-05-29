import numpy as np
from scipy.signal import upfirdn
import subprocess

import params
import read_write
import preambles
import plot_helper
import fourier_helper
import helper
import mappings


def retrieve_message_as_bytes():
    if params.logs:
        print("Retrieving the message from the appropriate file...")

    message_file = open(params.input_message_file_path)
    message = message_file.readline()
    message_bytes = helper.string2bits(message)
    new_bytes = [b[1:] for b in message_bytes]
    new_message_bytes_grouped = ''.join(new_bytes)

    if params.logs:
        print("Sent message:\n{}".format(message))
        print("Length: {} characters".format(len(message)))
        print("Corresponding bytes:\n{}".format(message_bytes))
        print("New bytes:\n{}".format(new_bytes))
        print("--------------------------------------------------------")
    return new_message_bytes_grouped


def message_bytes_to_int(new_bits):
    if params.MOD == 1 or params.MOD == 2:
        # New structure with bits_per_symbol bits by row
        new_bits = [new_bits[i:i + params.BITS_PER_SYMBOL] for i in range(0, len(new_bits), params.BITS_PER_SYMBOL)]

        # Convert this new bits sequence to an integer sequence
        ints = [[int(b, 2) for b in new_bits]]

        if params.logs:
            print("Cropped and re-structured bits:\n{}".format(new_bits))
            print("Equivalent integers (indices for our mapping):\n{}".format(ints))
            print("--------------------------------------------------------")
    elif params.MOD == 3:
        # Choose the number of bit streams (depends on the number of frequency ranges)
        n_bit_streams = len(params.FREQ_RANGES)

        # Choose the length of our bit streams
        len_bit_streams = int(np.ceil(len(new_bits) / (n_bit_streams - 1)))

        # Make it even
        while len_bit_streams % params.BITS_PER_SYMBOL != 0:
            len_bit_streams += 1

        # Construct the bit streams array with zeros
        bit_streams = np.zeros((n_bit_streams, len_bit_streams), dtype=int)

        # Fill the bit streams arrays
        for i in range(len(new_bits)):
            bit_streams[i % (n_bit_streams - 1)][int(np.floor(i / (n_bit_streams - 1)))] = new_bits[i]

        # Construct the parity check bit stream and insert it in the bit streams array
        pc_bit_stream = np.sum(bit_streams[:n_bit_streams - 1], axis=0)
        for i in range(len_bit_streams):
            pc_bit_stream[i] = 0 if pc_bit_stream[i] % 2 == 0 else 1
        bit_streams[n_bit_streams - 1] = pc_bit_stream

        if params.logs:
            print("Bit streams: {}".format(np.shape(bit_streams)))
            for i in range(len(bit_streams)):
                print("{}".format(bit_streams[i]))
            print("--------------------------------------------------------")

        # Group them by groups of BITS_PER_SYMBOL bits
        ints = np.zeros((n_bit_streams, int(len_bit_streams / params.BITS_PER_SYMBOL)), dtype=str)
        for i in range(n_bit_streams):
            for j in range(int(len_bit_streams / params.BITS_PER_SYMBOL)):
                index = j*params.BITS_PER_SYMBOL
                grouped_bits = ''.join(map(str, bit_streams[i][index:index + params.BITS_PER_SYMBOL]))
                mapping_index = int(grouped_bits, base=2)
                ints[i][j] = mapping_index

        if params.logs:
            print("Ints bits stream {}:\n{}".format(ints.shape, ints))
            print("--------------------------------------------------------")
    else:
        raise ValueError("This modulation type does not exist yet... He he he")

    corresponding_symbols = np.zeros(np.shape(ints), dtype=complex)
    mapping = mappings.choose_mapping()
    for i in range(len(ints)):
        corresponding_symbols[i] = [mapping[int(j)] for j in ints[i]]

    if params.logs:
        print("Mapping the integers to the symbols in the mapping...")
        print("Symbols/n-tuples to be sent:\n{}".format(corresponding_symbols))
        print("Shape of the symbols: {}".format(np.shape(corresponding_symbols)))
        print("--------------------------------------------------------")
    if params.plots:
        plot_helper.plot_complex_symbols(corresponding_symbols, "{} data symbols to send"
                                         .format(np.shape(corresponding_symbols)), "blue")
    return corresponding_symbols


def generate_preamble_to_transmit(len_data_symbols):
    if params.logs:
        print("Generating the preamble...")

    preambles.generate_preamble_symbols(len_data_symbols)
    preamble_symbols = read_write.read_preamble_symbols()

    if params.plots:
        plot_helper.plot_complex_symbols(preamble_symbols, "Preamble symbols")
    if params.logs:
        print("Preamble symbols:\n{}".format(preamble_symbols))
        print("--------------------------------------------------------")
    return preamble_symbols


def concatenate_symbols(preamble_symbols, data_symbols):
    if params.logs:
        print("Concatenating everything together (preamble-data-flipped preamble)...")

    if params.MOD == 1 or params.MOD == 2:
        p_data_p_symbols = np.concatenate((preamble_symbols, data_symbols[0], preamble_symbols[::-1]))
        if params.logs:
            print("Total symbols: {}".format(p_data_p_symbols))
            print("Number of total symbols: {}".format(np.shape(p_data_p_symbols)))
    elif params.MOD == 3:
        p_data_p_symbols = []
        for i in range(len(data_symbols)):
            p_data_p_symbols.append(np.concatenate((preamble_symbols, data_symbols[i], preamble_symbols[::-1])))
        if params.logs:
            for i in range(len(p_data_p_symbols)):
                print("Total symbols {}: {}".format(i, p_data_p_symbols))
                print("Number of total symbols {}: {}".format(i, np.shape(p_data_p_symbols)))
                if params.plots:
                    plot_helper.plot_complex_symbols(p_data_p_symbols[i], "Symbols {}".format(i))
    else:
        raise ValueError("This mapping type does not exist yet... He he he")
    return p_data_p_symbols


def shape_symbols(h, p_data_p_symbols, USF):
    if params.logs:
        print("Pulse shaping the symbols...")

    if params.MOD == 1 or params.MOD == 2:
        p_data_p_samples = upfirdn(h, p_data_p_symbols, USF)
        if params.logs:
            print("Samples: {}".format(p_data_p_samples))
            print("Up-sampling factor: {}".format(params.USF))
            print("Number of samples: {}".format(len(p_data_p_samples)))
        if params.plots:
            plot_helper.samples_fft_plots(p_data_p_samples, "Samples after the pulse shaping", shift=True)
    elif params.MOD == 3:
        p_data_p_samples = []
        for i in range(len(p_data_p_symbols)):
            p_data_p_samples.append(upfirdn(h, p_data_p_symbols[i], USF))
        if params.plots:
            for i in range(len(p_data_p_samples)):
                plot_helper.samples_fft_plots(p_data_p_samples[i], "Samples {} after the pulse shaping".format(i),
                                              shift=True)
    else:
        raise ValueError("This mapping type does not exist yet... He he he")

    if params.logs:
        print("--------------------------------------------------------")
    return p_data_p_samples


def shape_preamble_samples(h, preamble_symbols, USF):
    if params.logs:
        print("Shaping the preamble...")

    preamble_samples = upfirdn(h, preamble_symbols, USF)
    read_write.write_preamble_samples(preamble_samples)

    if params.logs:
        print("Number of samples for the preamble: {}".format(len(preamble_samples)))
    if params.plots:
        plot_helper.samples_fft_plots(preamble_samples, "Preamble samples", shift=True)
    if params.logs:
        print("--------------------------------------------------------")
    return None


def modulate_samples(p_data_p_samples):
    if params.logs:
        print("Choosing the modulation frequencies and modulating the samples...")
    if params.MOD == 1 or params.MOD == 3:
        modulating_frequencies = params.np.mean(params.FREQ_RANGES, axis=1)
    elif params.MOD == 2:
        modulating_frequencies = [params.FREQ_RANGES[0][1], params.FREQ_RANGES[2][1]]
    else:
        raise ValueError("This mapping type does not exist yet... He he he")

    if np.any(np.iscomplex(p_data_p_samples)):
        if params.MOD == 1 or params.MOD == 2:
            p_data_p_modulated_samples = fourier_helper.modulate_complex_samples(p_data_p_samples,
                                                                                 modulating_frequencies)
            if params.logs:
                print("Min and max sample after modulation: ({}, {})".format(min(p_data_p_samples),
                                                                             max(p_data_p_samples)))
            if params.plots:
                plot_helper.samples_fft_plots(p_data_p_samples, "Samples to send", time=True, complex=True, shift=True)
        elif params.MOD == 3:
            modulated_samples = []
            for i in range(len(p_data_p_samples)):
                modulated_samples.append(fourier_helper.modulate_complex_samples(p_data_p_samples[i],
                                                                                 [modulating_frequencies[i]]))
            p_data_p_modulated_samples = np.sum(modulated_samples, axis=0).flatten()
        else:
            raise ValueError("This mapping type does not exist yet... He he he")
    else:
        raise ValueError("TODO: handle real samples (e.g SSB)")
    if params.logs:
        print("--------------------------------------------------------")
    return p_data_p_modulated_samples


def scale_samples(p_data_p_modulated_samples):
    if params.logs:
        print("Scaling the samples to the server constraints...")
    samples_to_send = p_data_p_modulated_samples / (np.max(np.abs(p_data_p_modulated_samples))) * params.\
        ABS_SAMPLE_RANGE

    if params.logs:
        print("Number of samples: {}".format(len(samples_to_send)))
        print("Minimum sample after scaling: {}".format(min(samples_to_send)))
        print("Maximum sample after scaling: {}".format(max(samples_to_send)))
        print("--------------------------------------------------------")
    return samples_to_send


def send_samples():
    """
    Launch the client.py file with the correct arguments according to the parameters in the param file
    :return: None
    """
    subprocess.call(["python3 client.py" +
                     " --input_file=" + params.input_sample_file_path +
                     " --output_file=" + params.output_sample_file_path +
                     " --srv_hostname=" + params.server_hostname +
                     " --srv_port=" + str(params.server_port)],
                    shell=True)
    if params.logs:
        print("Samples sent!")
        print("--------------------------------------------------------")
    return None
