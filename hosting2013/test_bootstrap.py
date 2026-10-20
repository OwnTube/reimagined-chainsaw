"""Guard the independence of the server-only replication challenge."""
import unittest
import os
import socket
from windows_join_probe import script_source, udp_binding


class BootstrapTests(unittest.TestCase):
    def test_client_must_receive_challenge_over_network_not_source(self):
        secret = '0123456789abcdef'*3
        client = script_source('client','RCCJOIN_test_client',53640,secret)
        host = script_source('host','RCCJOIN_test_host',53640,secret)
        self.assertNotIn(secret,client)
        self.assertIn('local token = "'+secret+'"',host)
        self.assertIn('"|REPLICATED_TOKEN|"',client)
        self.assertIn('"|REPLICATED_MOVEMENT|"',client)
        self.assertIn('local port = 53640',client)
        self.assertIn('network:PlayerConnect(0, "localhost", port, 0, 30)',client)
        self.assertNotIn('__RCC_',client+host)

    @unittest.skipUnless(os.name=='nt','Windows UDP owner table required')
    def test_udp_owner_query_checks_both_pid_and_network_byte_order_port(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1',0))
            port = probe.getsockname()[1]
            self.assertTrue(udp_binding(os.getpid(),port))
            self.assertFalse(udp_binding(0,port))
            self.assertFalse(udp_binding(os.getpid(),0))


if __name__ == '__main__':unittest.main()
