import struct
import unittest

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from inspect_unwind_groups import (parse_unwind_info, resolve_root,
                                   byte_constant_observation, classify_result_consumer)


class UnwindMetadataTests(unittest.TestCase):
    def decode(self, data):
        decoder = Cs(CS_ARCH_X86, CS_MODE_64)
        decoder.detail = True
        return next(decoder.disasm(data, 0x1000))

    def test_low_byte_assignments_are_distinct_from_full_register_writes(self):
        self.assertEqual(byte_constant_observation(self.decode(b'\x30\xc0')), 0)
        self.assertEqual(byte_constant_observation(self.decode(b'\xb0\x01')), 1)
        self.assertIsNone(byte_constant_observation(self.decode(b'\x31\xc0')))

    def test_low_byte_consumers_do_not_accept_full_register_tests(self):
        self.assertEqual(classify_result_consumer(self.decode(b'\x84\xc0')), 'test_low_return_byte')
        self.assertEqual(classify_result_consumer(self.decode(b'\x0f\xb6\xd8')), 'zero_extend_low_return_byte')
        self.assertIsNone(classify_result_consumer(self.decode(b'\x48\x85\xc0')))

    def test_odd_slot_count_has_two_byte_padding_before_chain(self):
        parent = (0x1000, 0x1021, 0x3000)
        header = bytes((1 | (4 << 3), 0, 1, 0))
        self.assertEqual(parse_unwind_info(header+b'\0'*4+struct.pack('<III', *parent))['chain'], parent)

    def test_even_slot_count_and_primary_record(self):
        self.assertIsNone(parse_unwind_info(bytes((1, 0, 2, 0))+b'\0'*4)['chain'])

    def test_missing_padding_or_chain_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_unwind_info(bytes((33, 0, 1, 0))+b'\0'*2+struct.pack('<III', 1, 2, 3))

    def test_invalid_flags_and_versions_are_rejected(self):
        for first in (0, 2, 1 | (5 << 3), 1 | (8 << 3)):
            with self.subTest(first=first), self.assertRaises(ValueError):
                parse_unwind_info(bytes((first, 0, 0, 0))+b'\0'*12)

    def test_nested_chain_resolves_to_primary(self):
        root, middle, leaf = (1, 2, 3), (4, 5, 6), (7, 8, 9)
        parents = {root: None, middle: root, leaf: middle}
        self.assertEqual(resolve_root(leaf, parents, set(parents)), root)

    def test_cycles_missing_records_and_depth_limits_are_rejected(self):
        a, b = (1, 2, 3), (4, 5, 6)
        for parents, entries, depth in (({a:b, b:a}, {a,b}, 32),
                                         ({a:b}, {a}, 32),
                                         ({a:b, b:None}, {a,b}, 1)):
            with self.subTest(parents=parents), self.assertRaises(ValueError):
                resolve_root(a, parents, entries, max_depth=depth)


if __name__ == '__main__':
    unittest.main()
