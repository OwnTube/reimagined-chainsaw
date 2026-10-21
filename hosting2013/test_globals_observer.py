import hashlib
import json
import unittest
from globals_observer import observe_globals,read_globals
from test_descriptor_codec import packed,word


def fixture():
    bits='10000001'+'01'+'10000001'+word(4)+'0'+word(24)
    bits+=''.join(f'{b:08b}' for b in bytes.fromhex('313681'))  # fixed Name codeword
    bits+=''.join(f'{b:08b}' for b in (0x01020304).to_bytes(4,'little'))
    bits+='00000001'+''.join(f'{b:08b}' for b in (80).to_bytes(4,'little'))
    return packed(bits),len(bits)


class GlobalsObservationTests(unittest.TestCase):
    def test_literal_cached_scope_and_raw_x86_index(self):
        payload,bits=fixture();row=read_globals(payload,bits,2)
        self.assertEqual(row['flags'],[0,1])
        self.assertEqual([r['index'] for r in row['references']],[0x01020304,80])
        self.assertEqual([r['scope_source'] for r in row['references']],['literal','cached'])
        self.assertEqual(row['scopes'][0]['sha256'],hashlib.sha256(b'Name').hexdigest())
        self.assertNotIn('Name',json.dumps(row))
        self.assertFalse(row['service_names_identified'])

    def test_no_ticket_or_other_direction_inspection(self):
        payload,bits=fixture()
        self.assertIsNone(observe_globals('client_to_server',payload,bits))
        self.assertIsNone(observe_globals('server_to_client',b'\x8aPRIVATE_TICKET',100))
        row=observe_globals('server_to_client',payload,bits)
        self.assertEqual(len(row['candidates']),1)
        self.assertFalse(row['body_exported'])

    def test_service_names_require_unique_agreement_on_both_peers(self):
        from correlate_service_guids import correlate
        trace={'globals_observations':[{'candidates':[{'remaining_bits':0,
            'cpp_encoder':{'native_wire_validated':True},'references':[{'index':17}]}]}]}
        result={'peers':{role:{'engine_marker_lines':['owned|SERVICE_GUID_INDEX|Workspace|17']} for role in ('host','client')}}
        self.assertTrue(correlate(trace,result)['all_service_classes_identified'])
        result['peers']['client']['engine_marker_lines']=['owned|SERVICE_GUID_INDEX|Players|17']
        self.assertFalse(correlate(trace,result)['all_service_classes_identified'])
        result['peers']['host']['engine_marker_lines'].append('owned|SERVICE_GUID_INDEX|Players|17')
        self.assertEqual(correlate(trace,result)['matched_count'],0)

    def test_undefined_cache_truncation_and_exact_bit_limit(self):
        payload,bits=fixture()
        for end in range(len(payload)):
            with self.assertRaises(ValueError):read_globals(payload[:end],min(bits,end*8),2)
        with self.assertRaises(ValueError):read_globals(payload,bits-1,2)
        with self.assertRaises(ValueError):read_globals(packed('10000001'+'00'+'00000101'+'0'*32),50,2)


if __name__=='__main__':unittest.main()
