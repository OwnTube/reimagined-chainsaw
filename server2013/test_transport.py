"""Wire-level tests with real sockets; native Player validation is separate."""
import socket
import struct
import unittest
from transport import ResearchHost, address, encapsulate, acknowledge, acknowledgements
from transport_trace import MAGIC, frames


class TransportTests(unittest.TestCase):
    def test_owned_socket_handshake_ping_ack_and_application_limit(self):
        host=ResearchHost(0)
        client=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        client.bind(('127.0.0.1',0));client.settimeout(1)
        peer=client.getsockname()
        self.addCleanup(client.close);self.addCleanup(host.socket.close)
        request=b'\x05'+MAGIC+b'\x05'+bytes(1446)
        host.receive(request,peer)
        reply=client.recv(1500)
        self.assertEqual(reply[:17],b'\x06'+MAGIC)
        self.assertEqual(len(reply),28)
        host.receive(b'\x07'+MAGIC+address(('127.0.0.1',host.port))+struct.pack('>H',1492)+bytes(8),peer)
        self.assertEqual(len(client.recv(1500)),35)
        request=b'\x09'+bytes(8)+(123).to_bytes(8,'big')+b'\x00'+b'private-connection-test-9382'
        host.receive(encapsulate(request,0,0),peer)
        self.assertEqual(client.recv(1500),acknowledge(0))
        accepted=client.recv(1500)
        self.assertEqual(frames(accepted)[0]['payload'][0],16)
        self.assertEqual(len(frames(accepted)[0]['payload']),96)
        host.receive(acknowledge(0),peer)
        self.assertFalse(host.pending)
        host.receive(encapsulate(b'\x13'+bytes(93),1,1,0),peer)
        self.assertEqual(client.recv(1500),acknowledge(1))
        self.assertTrue(host.connected)
        host.receive(encapsulate(b'\x00'+(456).to_bytes(8,'big'),2),peer)
        client.recv(1500)
        pong=frames(client.recv(1500))[0]['payload']
        self.assertEqual(pong[:9],b'\x03'+(456).to_bytes(8,'big'))
        host.receive(encapsulate(b'\x8a'+b'not a world',3,2,1),peer)
        client.recv(1500)
        self.assertEqual(host.application_messages[0]['id'],138)
        self.assertFalse(host.report()['game_join_validated'])
        self.assertNotIn('private-connection-test-9382',str(host.report()))

    def test_corrupt_frames_and_ack_ranges_fail_closed(self):
        for packet in (b'\x84',b'\x84\x00\x00\x00\x60\x00\x50',b'\xc0\xff\xff'):
            with self.assertRaises(ValueError):
                acknowledgements(packet) if packet[0]==192 else frames(packet)
        packet=encapsulate(b'123',3,8,9)
        frame=frames(packet)[0]
        self.assertEqual((frame['payload'],frame['reliable_index'],frame['order_index']),(b'123',8,9))
        self.assertEqual(acknowledgements(acknowledge(0xffffff)),[(0xffffff,0xffffff)])


if __name__=='__main__':unittest.main()
