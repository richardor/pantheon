import os, sys, subprocess, time
from subprocess import Popen, PIPE
from interruptingcow import timeout
from generate_html import generate_html
import unittest

# print test usage
def test_usage():
    print "Test Usage:"
    print "python test.py scheme"

# parse congestion control option, return friendly name and script to run
def parse_cc_option(cc_option):
    # add more congestion control options here
    if cc_option == 'default_tcp':
        return 'Default TCP', 'default_tcp.py'

    if cc_option == 'ledbat':
        return 'LEDBAT', 'ledbat.py'

    if cc_option == 'quic':
        return 'QUIC', 'quic.py'

    if cc_option == 'pcc':
        return 'PCC', 'pcc.py'

    if cc_option == 'verus':
        return 'Verus', 'verus.py'

    print "Congestion control option is not valid."
    return None, None

class TestCongestionControl(unittest.TestCase):
    # run parameterized test cases
    def __init__(self, test_name, cc_option):
        cc_friendly_name, src_name = parse_cc_option(cc_option)

        self.assertTrue(cc_friendly_name is not None)
        self.assertTrue(src_name is not None)

        super(TestCongestionControl, self).__init__(test_name)
        self.cc_friendly_name = cc_friendly_name
        self.src_name = src_name
        self.DEVNULL = open(os.devnull, 'wb')

    def __del__(self):
        self.DEVNULL.close()

        if self.src_name == 'verus.py':
            # move the files generated by Verus to /tmp
            print os.getcwd()
            try:
                client_out = os.path.join(os.getcwd(), 'client_*.out')
                verus_tmp = os.path.join(os.getcwd(), 'verus_tmp')
                clean_cmd = 'mv %s %s && rm -rf /tmp/verus_tmp && mv %s /tmp' \
                              % (client_out, verus_tmp, verus_tmp)
                print clean_cmd
                subprocess.call(clean_cmd, shell=True)
            except:
                pass

    # Pattern 1: run receiver, run sender, no necessary input to sender
    def run_pattern1(self):
        # run receiver
        recv_cmd = ['python', self.src_file, 'receiver'] 
        recv_proc = Popen(recv_cmd, stdout=self.DEVNULL, stderr=PIPE)

        # find port that receiver prints
        port_info = recv_proc.stderr.readline()
        port = port_info.rstrip().rsplit(' ', 1)[1]

        # run sender
        send_cmd = "'python %s sender %s %s'" % (self.src_file, self.ip, port)
        mahimahi_cmd = 'mm-link %s %s --once --uplink-log=%s -- sh -c %s' % \
                        (self.uplink_trace, self.downlink_trace,
                         self.link_log, send_cmd) 

        send_proc = Popen(mahimahi_cmd, shell=True, 
                    stdout=self.DEVNULL, stderr=self.DEVNULL)

        # simply wait for 10 seconds
        try:
            with timeout(3, exception=RuntimeError):
                send_proc.communicate()
        except:
            pass
        else:
            print 'Warning: quit earlier!'

        send_proc.terminate()
        recv_proc.terminate()

    # Pattern 2: run receiver, run sender, require input to sender from stdin
    def run_pattern2(self):
        # run receiver
        recv_cmd = ['python', self.src_file, 'receiver'] 
        recv_proc = Popen(recv_cmd, stdout=self.DEVNULL, stderr=PIPE)

        # find port that receiver prints
        port_info = recv_proc.stderr.readline()
        port = port_info.rstrip().rsplit(' ', 1)[1]

        # run sender
        send_cmd = "'python %s sender %s %s'" % (self.src_file, self.ip, port)
        mahimahi_cmd = 'mm-link %s %s --once --uplink-log=%s -- sh -c %s' % \
                        (self.uplink_trace, self.downlink_trace,
                         self.link_log, send_cmd) 

        # writing random data to sender for 10 seconds
        send_proc = Popen(mahimahi_cmd, shell=True, 
                    stdin=PIPE, stdout=self.DEVNULL, stderr=self.DEVNULL)
        try:
            with timeout(10, exception=RuntimeError):
                while True:
                    send_proc.stdin.write(os.urandom(1024 * 128))
        except:
            pass
        else:
            print 'Warning: quit earlier!'

        send_proc.stdin.close()
        send_proc.terminate()
        recv_proc.terminate()

    # QUIC Pattern: run sender, run receiver, generate a HTML as input to sender
    def run_quic(self):
        # generate html of size that can be transferred longer than 10 seconds 
        generate_html(300000)

        # run sender
        send_cmd = 'python %s sender' % self.src_file
        send_proc = Popen(send_cmd, shell=True, stdout=self.DEVNULL, stderr=PIPE)

        # find port that sender prints
        port_info = send_proc.stderr.readline()
        port = port_info.rstrip().rsplit(' ', 1)[1]

        # run receiver (notice direction: switch uplink and downlink trace)
        recv_cmd = "'python %s receiver %s %s'" % (self.src_file, self.ip, port)
        mahimahi_cmd = 'mm-link %s %s --once --downlink-log=%s -- sh -c %s' % \
                        (self.downlink_trace, self.uplink_trace,
                         self.link_log, recv_cmd) 

        recv_proc = Popen(mahimahi_cmd, shell=True, 
                          stdout=self.DEVNULL, stderr=self.DEVNULL)

        try:
            with timeout(10, exception=RuntimeError):
                send_proc.communicate()
        except:
            pass
        else:
            print 'Warning: quit earlier!'

        send_proc.terminate()
        recv_proc.terminate()

    # congestion control test
    def test_congestion_control(self):
        src_name = self.src_name
        cc_prefix = src_name[:-3]
        test_dir = os.path.abspath(os.path.dirname(__file__))
        src_dir = os.path.abspath(os.path.join(test_dir, '../src')) 
        self.src_file = os.path.join(src_dir, src_name) 

        # run setup, ignore any output
        setup_cmd = ['python', self.src_file, 'setup'] 
        setup_proc = Popen(setup_cmd, stdout=self.DEVNULL, stderr=self.DEVNULL)
        setup_proc.communicate()
        
        # prepare mahimahi
        traces_dir = '/usr/share/mahimahi/traces/'
        self.uplink_trace = traces_dir + 'Verizon-LTE-short.up'
        self.downlink_trace = traces_dir + 'Verizon-LTE-short.down'
        self.link_log = os.path.join(test_dir, '%s_link.log' % cc_prefix) 
        self.ip = '$MAHIMAHI_BASE'

        print 'Running %s...' % self.cc_friendly_name 
        # add more congestion control mechanisms tests here
        if (src_name == 'default_tcp.py' or 
            src_name == 'pcc.py' or 
            src_name == 'verus.py'):
            self.run_pattern1()

        if src_name == 'ledbat.py':
            self.run_pattern2()

        if src_name == 'quic.py':
            self.run_quic()

        # generate throughput graph
        throughput_graph_file = open(os.path.join(test_dir, 
                                '%s_throughput.html' % cc_prefix), 'wb')
        subprocess.call(['mm-throughput-graph', '500', self.link_log],
                        stdout=throughput_graph_file)
        throughput_graph_file.close()

def main():
    if len(sys.argv) != 2:
        test_usage()
        return
    cc_option = sys.argv[1].lower()

    # create test suite to run
    suite = unittest.TestSuite()
    suite.addTest(TestCongestionControl("test_congestion_control", cc_option))
    unittest.TextTestRunner().run(suite)

if __name__ == '__main__':
   main() 
