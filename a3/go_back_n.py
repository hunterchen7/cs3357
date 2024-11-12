import time
from threading import Thread

class GBN_sender:
    def __init__(self, input_file, window_size, packet_len, nth_packet, send_queue, ack_queue, timeout_interval, logger):
        self.input_file = input_file
        self.window_size = window_size
        self.packet_len = packet_len
        self.nth_packet = nth_packet
        self.send_queue = send_queue
        self.ack_queue = ack_queue
        self.timeout_interval = timeout_interval
        self.logger = logger
        
        # initialize sender state variables
        self.base = 0
        self.packets = self.prepare_packets()
        self.acks_list = [False] * len(self.packets)
        self.packet_timers = [0] * len(self.packets)
        self.dropped_list = []

    def prepare_packets(self):
        # read data from input_file and convert to binary representation
        with open(self.input_file, 'r') as file:
            data = file.read()
        
        # convert data to binary, each char to 8-bit binary
        binary_data = ''.join(format(ord(char), '08b') for char in data)
        
        # create packets with data bits and sequence numbers
        packets = []
        seq_num = 0
        seq_num_bits = 16  # sequence number is 16 bits
        
        for i in range(0, len(binary_data), self.packet_len - seq_num_bits):
            data_bits = binary_data[i:i + (self.packet_len - seq_num_bits)]
            padded_data_bits = data_bits.ljust(self.packet_len - seq_num_bits, '0')  # pad if needed
            
            # construct packet with 16-bit sequence number at the end
            packet = padded_data_bits + format(seq_num, f'0{seq_num_bits}b')
            packets.append(packet)
            seq_num += 1

        return packets

    def send_packets(self):
        # send all packets in the current window
        for i in range(self.base, min(self.base + self.window_size, len(self.packets))):
            if not self.acks_list[i]:  # only send unacknowledged packets
                if (i + 1) % self.nth_packet == 0 and i not in self.dropped_list:
                    self.dropped_list.append(i)
                    self.logger.info(f"packet {i} dropped")
                else:
                    self.send_queue.put(self.packets[i])
                    self.logger.info(f"sending packet {i}")
                    self.packet_timers[i] = time.time()

    def send_next_packet(self):
        # increment base and send the last packet within the window if available
        self.base += 1
        if self.base + self.window_size - 1 < len(self.packets):
            i = self.base + self.window_size - 1
            if not self.acks_list[i]:
                if (i + 1) % self.nth_packet == 0 and i not in self.dropped_list:
                    self.dropped_list.append(i)
                    self.logger.info(f"packet {i} dropped")
                else:
                    self.send_queue.put(self.packets[i])
                    self.logger.info(f"sending packet {i}")
                    self.packet_timers[i] = time.time()

    def check_timers(self):
        # check for any packet in the window that has timed out
        current_time = time.time()
        for i in range(self.base, min(self.base + self.window_size, len(self.packets))):
            if not self.acks_list[i] and (current_time - self.packet_timers[i] > self.timeout_interval):
                self.logger.info(f"packet {i} timed out")
                return True  # indicating a timeout occurred
        return False

    def receive_acks(self):
        # continuously listen for acks from receiver
        while self.base < len(self.packets):
            if not self.ack_queue.empty():
                ack = self.ack_queue.get()
                if not self.acks_list[ack]:
                    self.acks_list[ack] = True
                    self.logger.info(f"ack {ack} received")
                    self.send_next_packet()
                else:
                    self.logger.info(f"ack {ack} received, ignoring")

    def run(self):
        # start packet transmission
        self.send_packets()
        
        # start separate thread for ack handling
        ack_thread = Thread(target=self.receive_acks)
        ack_thread.start()

        # monitor timeouts and resend packets if necessary
        while self.base < len(self.packets):
            if self.check_timers():
                # resend all packets in the current window on timeout
                self.send_packets()

        # signal end of transmission
        self.send_queue.put(None)


class GBN_receiver:
    def __init__(self, output_file, send_queue, ack_queue, logger):
        self.output_file = output_file
        self.send_queue = send_queue
        self.ack_queue = ack_queue
        self.logger = logger
        
        # initialize receiver state variables
        self.packet_list = []
        self.expected_seq_num = 0

    def process_packet(self, packet):
        # extract sequence number and data from the packet
        seq_num_bits = 16
        data_bits = packet[:-seq_num_bits]
        seq_num = int(packet[-seq_num_bits:], 2)

        # check if the received packet is the expected one
        if seq_num == self.expected_seq_num:
            # packet is in order; add data and send acknowledgment
            self.packet_list.append(data_bits)
            self.ack_queue.put(seq_num)
            self.logger.info(f"packet {seq_num} received")
            
            # update expected sequence number
            self.expected_seq_num += 1
            return True
        else:
            # packet out of order; re-send last acknowledgment
            self.ack_queue.put(self.expected_seq_num - 1)
            self.logger.info(f"packet {seq_num} received out of order")
            return False

    def write_to_file(self):
        # convert binary data to text and write to output file
        with open(self.output_file, 'w') as file:
            for data_bits in self.packet_list:
                # each 8-bit segment represents a character in ascii
                for i in range(0, len(data_bits), 8):
                    char_bits = data_bits[i:i + 8]
                    if len(char_bits) == 8:  # avoid incomplete byte at the end
                        char = chr(int(char_bits, 2))
                        if char != '\x00':  # ignore null characters
                            file.write(char)

    def run(self):
        # continuously listen for packets until end of transmission (None received)
        while True:
            packet = self.send_queue.get()
            if packet is None:
                # end of transmission signal
                break
            self.process_packet(packet)
        
        # write all received data to the output file after receiving all packets
        self.write_to_file()
