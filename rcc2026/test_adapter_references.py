import struct
import unittest

from inspect_adapter_references import instruction_sizes, relative_references


class RelativeReferenceTests(unittest.TestCase):
    def test_opcode_inside_an_immediate_is_not_an_instruction_boundary(self):
        base, target = 0x1000, 0x1200
        data = b'\x48\xb8\xe8' + struct.pack('<i', target-(base+2+5)) + b'\x00\x00\x00\xc3'
        refs = list(relative_references(data, base, {target}))
        self.assertEqual(len(refs), 1)
        self.assertNotIn(refs[0]['rva'], instruction_sizes(data, base))

    def test_real_call_has_the_expected_instruction_boundary(self):
        base, target = 0x1000, 0x0800
        data = b'\xe8' + struct.pack('<i', target-(base+5)) + b'\xc3'
        ref, = relative_references(data, base, {target})
        self.assertEqual(ref['target_rva'], target)
        self.assertEqual(instruction_sizes(data, base)[ref['rva']], ref['bytes'])

    def test_truncated_relative_operands_do_not_become_references(self):
        self.assertEqual(list(relative_references(b'\xe8\x00\x00', 0x1000, {0x1005})), [])

    def test_rip_relative_memory_uses_signed_displacement_and_seven_byte_length(self):
        base, target = 0x1000, 0x0900
        data = b'\x48\x8d\x0d' + struct.pack('<i', target-(base+7)) + b'\xc3'
        ref, = relative_references(data, base, {target})
        self.assertEqual(ref['kind'], 'rip_relative_memory')
        self.assertEqual(ref['target_rva'], target)
        self.assertEqual(instruction_sizes(data, base)[ref['rva']], ref['bytes'])


if __name__ == '__main__':
    unittest.main()
