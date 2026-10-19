import struct
import unittest

from inspect_unwind_groups import parse_unwind_info, resolve_root


class UnwindMetadataTests(unittest.TestCase):
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
