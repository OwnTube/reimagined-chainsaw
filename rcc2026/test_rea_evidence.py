import json
import unittest

from record_rea_resources import validate_evidence
from windows_probe import STUDIO_SHA256


class ReaEvidenceTests(unittest.TestCase):
    def evidence(self):
        return {'operation': 'inspect_pe_resources',
                'subject': {'digest': {'sha256': STUDIO_SHA256}},
                'normalized_result': {'resources': []}}

    def test_exact_operation_and_digest_are_required_even_with_a_zero_exit_code(self):
        self.assertEqual(validate_evidence('\ufeff'+json.dumps(self.evidence())), self.evidence())
        for key, value in (('operation', 'other'), ('subject', None), ('subject', {'digest': None}),
                           ('subject', {'digest': {'sha256': 'wrong'}}),
                           ('normalized_result', None)):
            evidence = self.evidence()
            evidence[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_evidence(json.dumps(evidence))

    def test_empty_or_error_output_cannot_count_as_validated_resources(self):
        for text in ('', 'null', '{}', '{"error":"timed out"}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_evidence(text)


if __name__ == '__main__':
    unittest.main()
