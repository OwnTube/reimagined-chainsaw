"""Guard the independence of the server-only replication challenge."""
import unittest
from windows_join_probe import script_source


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


if __name__ == '__main__':unittest.main()
