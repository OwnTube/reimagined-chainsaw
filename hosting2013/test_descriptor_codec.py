"""Owned fixtures for wire integer boundaries and fixed Huffman codewords."""
import unittest
from descriptor_codec import Bits, compressed_string, read_tables


def packed(bits):
    return int(bits+'0'*(-len(bits)%8),2).to_bytes((len(bits)+7)//8,'big')


def word(value):return f'{value:032b}'


def descriptor(wire_id,name,encoded):
    # A nonzero final byte in network-endian memory prevents high-byte elision:
    # flag zero + all four integer bytes, then the Huffman bit region.
    return word(wire_id)+word(len(name))+'0'+word(len(encoded)*8)+''.join(f'{v:08b}' for v in encoded)


class DescriptorCodecTests(unittest.TestCase):
    def test_fixed_codewords_and_nonbyte_alignment(self):
        for text,data in ((b'Part','9d8d9b'),(b'Workspace','57232ff6a35015'),(b'Name','313681')):
            encoded=bytes.fromhex(data)
            stream=Bits(packed('0'+word(len(encoded)*8)+''.join(f'{v:08b}' for v in encoded)))
            self.assertEqual(compressed_string(stream),text)
            self.assertEqual(stream.offset,33+len(encoded)*8)

    def test_compressed_integer_branches(self):
        for bits,expected in (('1111'+'1010',10),('1110'+'00010000',16),
                              ('110'+'0011010000010010',0x1234),
                              ('0'+'01111000010101100011010000010010',0x12345678)):
            self.assertEqual(Bits(packed(bits)).compressed_u32('little'),expected)
        self.assertEqual(Bits(packed('0'+word(56))).compressed_u32('big'),56)

    def test_complete_synthetic_tables_and_truncation(self):
        bits='10000010'+word(1)+descriptor(0,'Part',bytes.fromhex('9d8d9b'))
        bits+=word(1)+descriptor(7,'Name',bytes.fromhex('313681'))+word(0)
        payload=packed(bits)
        result=read_tables(payload)
        self.assertFalse(result['schema_complete'])
        self.assertEqual(result['tables'][1]['entries'],[{'id':7,'name':'Name'}])
        self.assertFalse(result['application_handshake_implemented'])
        for end in range(len(payload)):
            with self.assertRaises(ValueError):read_tables(payload[:end])
        with self.assertRaises(ValueError):read_tables(payload,'little')

    def test_aligned_configuration_tail_values_are_redacted(self):
        bits='10000010'+word(0)*3+f'{1:016b}'
        for value in (b'DebugOwnedFixture',b'private_value'):
            bits+=f'{len(value):016b}'
            bits+='0'*(-len(bits)%8)
            bits+=''.join(f'{b:08b}' for b in value)
        payload=packed(bits)
        row=read_tables(payload,include_configuration=True)
        self.assertTrue(row['schema_complete'])
        self.assertEqual(row['configuration'][0]['name'],'DebugOwnedFixture')
        self.assertEqual(row['configuration'][0]['value_length'],13)
        self.assertNotIn('private_value',str(row))
        for end in range(13,len(payload)):
            with self.assertRaises(ValueError):read_tables(payload[:end],include_configuration=True)

    def test_fourth_dictionary_precedes_configuration(self):
        bits='10000010'+word(0)*3+word(1)+descriptor(0,'Name',bytes.fromhex('313681'))+'0'*16
        row=read_tables(packed(bits),table_count=4,include_configuration=True)
        self.assertTrue(row['schema_complete'])
        self.assertEqual(row['tables'][3]['entries'][0]['name'],'Name')
        self.assertFalse(read_tables(packed(bits),include_configuration=True)['schema_complete'])

    def test_invalid_lengths_counts_and_symbols(self):
        with self.assertRaises(ValueError):read_tables(b'\x82'+(4097).to_bytes(4,'big'))
        with self.assertRaises(ValueError):read_tables(packed('10000010'+word(1)+word(0)+word(256)))
        with self.assertRaises(ValueError):compressed_string(Bits(packed('0'+word(9000))))
        with self.assertRaises(ValueError):Bits(b'').uint(1)


if __name__=='__main__':unittest.main()
