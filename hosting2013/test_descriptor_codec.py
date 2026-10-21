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
        self.assertTrue(result['schema_complete'])
        self.assertEqual(result['tables'][1]['entries'],[{'id':7,'name':'Name'}])
        self.assertFalse(result['application_handshake_implemented'])
        for end in range(len(payload)):
            with self.assertRaises(ValueError):read_tables(payload[:end])
        with self.assertRaises(ValueError):read_tables(payload,'little')

    def test_invalid_lengths_counts_and_symbols(self):
        with self.assertRaises(ValueError):read_tables(b'\x82'+(4097).to_bytes(4,'big'))
        with self.assertRaises(ValueError):read_tables(packed('10000010'+word(1)+word(0)+word(256)))
        with self.assertRaises(ValueError):compressed_string(Bits(packed('0'+word(9000))))
        with self.assertRaises(ValueError):Bits(b'').uint(1)


if __name__=='__main__':unittest.main()
