"""Synthetic wire fixtures, not recorded Roblox engine payloads."""
import json
import unittest
import zlib
from schema_observer import MAX_BODY, MAX_EXPANDED, observe, shifted
from transport_trace import Trace


def frame(payload, index=0, count=1):
    header = b'\x84\0\0\0' + bytes([0x70]) + (len(payload)*8).to_bytes(2,'big')
    header += index.to_bytes(3,'little') + b'\0\0\0\0'
    header += count.to_bytes(4,'big') + b'\0\x01' + index.to_bytes(4,'big')
    return header + payload


class SchemaObservationTests(unittest.TestCase):
    def test_sensitive_and_unknown_messages_excluded(self):
        for direction in ('client_to_server','server_to_client'):
            for packet in (b'\x81Workspace', b'\x8aWorkspace SECRET_TICKET', b'\x83Part',b'\x8fName'):
                self.assertIsNone(observe(direction,packet))
        self.assertIsNone(observe('client_to_server',b'\x82Workspace'))
        row=observe('server_to_client',b'\x82\x09Workspace\0\x04Part\0PRIVATE_UNKNOWN_WORLD_BODY')
        exported=json.dumps(row)
        self.assertNotIn('PRIVATE_UNKNOWN',exported)
        self.assertEqual([r['symbol'] for r in row['symbols']],['Workspace','Part'])
        self.assertFalse(row['body_exported'])
        self.assertFalse(row['layout_validated'])

    def test_native_prefix_hash_masks_only_padding(self):
        import hashlib
        from test_descriptor_codec import packed,word
        # Four empty owned dictionaries followed by a zero configuration count.
        payload=packed('10000010'+word(0)*4+'0'*16)
        row=observe('server_to_client',payload)
        candidate=next(c for c in row['descriptor_candidates'] if c['schema_complete'])
        self.assertEqual(candidate['dictionary_prefix_bits'],136)
        self.assertEqual(candidate['dictionary_prefix_sha256'],hashlib.sha256(payload[:17]).hexdigest())

    def test_shifted_bit_positions(self):
        # Prefix 3 zero bits, then exactly the ASCII symbol and a zero byte.
        bits='000'+''.join(f'{b:08b}' for b in b'Workspace\0')
        bits+='0'*(-len(bits)%8)
        payload=b'\x82'+int(bits,2).to_bytes(len(bits)//8,'big')
        row=observe('server_to_client',payload)
        self.assertEqual(row['symbols'][0]['bit_offset'],3)
        self.assertEqual(shifted(payload[1:],3)[:9],b'Workspace')

    def test_bounded_checked_compression(self):
        row=observe('server_to_client',b'\x82'+b'\0\0'+zlib.compress(b'\x09Workspace\0\x04Part\0'))
        self.assertEqual(row['zlib_candidates'][0]['offset'],2)
        self.assertEqual(row['zlib_candidates'][0]['symbols'][0]['symbol'],'Workspace')
        for body in (zlib.compress(b'A'*(MAX_EXPANDED+1)), zlib.compress(b'Workspace')+b'trailer'):
            self.assertEqual(observe('server_to_client',b'\x82'+body)['zlib_candidates'],[])
        self.assertIn('error',observe('server_to_client',b'\x82'* (MAX_BODY+1)))

    def test_fragmented_schema_out_of_order_and_deduplication(self):
        trace=Trace()
        payload=b'\x82\x09Workspace\0\x04Part\0'
        for index in (1,0):
            trace.packet('server_to_client',frame(payload[:8] if index==0 else payload[8:],index,2))
        trace.message('server_to_client',payload)
        trace.message('client_to_server',b'\x8aSECRET_TICKET')
        report=trace.report()
        self.assertEqual(len(report['schema_observations']),1)
        self.assertEqual(len(report['schema_observations'][0]['symbols']),2)
        self.assertFalse(report['decode_errors'])
        self.assertNotIn('SECRET_TICKET',json.dumps(report))


if __name__=='__main__':unittest.main()
