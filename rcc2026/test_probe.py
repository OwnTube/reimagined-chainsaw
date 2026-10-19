import base64
import io
import json
import unittest

from PIL import Image

from windows_probe import collect_result, parse_events, validate_png
from inspect_studio import positions
from windows_server_probe import classify_startup
from windows_diagnostics import sanitize_log, omit_desktop_capture


class StartupEvidenceTests(unittest.TestCase):
    def test_signin_capture_is_omitted_before_a_quick_signin_code_is_generated(self):
        self.assertTrue(omit_desktop_capture('Authenticated : NO\nLoginPageOpenTime : 4 sec'))

    def test_quick_signin_metadata_alone_prevents_a_desktop_capture(self):
        self.assertTrue(omit_desktop_capture('[FLog::QuickSignInUtil] request completed'))

    def test_non_authentication_startup_errors_remain_capturable(self):
        self.assertFalse(omit_desktop_capture('This application failed to start because no Qt platform plugin could be initialized.'))

    def test_new_signin_page_does_not_need_the_legacy_dialog_message(self):
        text = "Constructing UIThreadNotifier for process '123'\nStudio Launch Intent is StartServer\nAuthenticated : NO\nLoginPageOpenTime : 4 sec\ninTreatment=true"
        result = classify_startup([text], 123)
        self.assertFalse(result['login_dialog_observed'])
        self.assertTrue(result['login_page_observed'])
        self.assertTrue(result['login_surface_observed'])

    def test_rollout_flag_alone_cannot_establish_an_unauthenticated_surface(self):
        result = classify_startup(["Constructing UIThreadNotifier for process '123'\ninTreatment=true\nLoginPageOpenTime : 4 sec"], 123)
        self.assertFalse(result['login_surface_observed'])

    def test_log_redaction_preserves_errors_but_removes_nested_authentication_data(self):
        text = ('[FLog::Error] Invalid Launch Intent! Validation failed\n'
                '[FLog::QuickSignInUtil] body={"code":"example-code","privateKey":"example-key"}\n'
                "Navigation https://www.roblox.com/login?returnUrl=https%3A%2F%2Fapis.roblox.com%3Fstate%3Dexample-state\n"
                'Authorization: Bearer example-token\n')
        clean = sanitize_log(text)
        self.assertIn('Invalid Launch Intent! Validation failed', clean)
        self.assertIn('https://www.roblox.com/login', clean)
        for secret in ('example-code', 'example-key', 'example-state', 'example-token'):
            self.assertNotIn(secret, clean)

    def test_unrelated_process_cannot_supply_failure_or_login_evidence(self):
        text = "Constructing UIThreadNotifier for process '1123'\nInvalid Launch Intent! Too many arguments provided\nAuthenticated : NO\nshow login dialog [end]"
        result = classify_startup([text], 123)
        self.assertFalse(result['native_log_identified'])
        self.assertIsNone(result['launch_arguments_rejected'])
        self.assertIsNone(result['login_dialog_observed'])

    def test_rejected_intent_and_login_are_both_retained(self):
        text = "Constructing UIThreadNotifier for process '123'\nStudio Launch Intent is StartServer\nInvalid Launch Intent! Too many arguments provided\nAuthenticated : NO\nshow login dialog [end]"
        result = classify_startup([text], 123)
        self.assertTrue(result['start_server_intent_observed'])
        self.assertTrue(result['launch_arguments_rejected'])
        self.assertTrue(result['login_dialog_observed'])

    def test_clean_intent_is_not_server_execution_or_login_proof(self):
        result = classify_startup(["Constructing UIThreadNotifier for process '123'\nStudio Launch Intent is StartServer"], 123)
        self.assertFalse(result['launch_arguments_rejected'])
        self.assertFalse(result['launch_values_rejected'])
        self.assertFalse(result['login_dialog_observed'])
        self.assertNotIn('server_hosting_validated', result)


class EvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        stream = io.BytesIO()
        Image.new('RGB', (256, 256), (23, 71, 101)).save(stream, format='PNG')
        self.png = stream.getvalue()
        encoded = base64.b64encode(self.png).decode()
        self.events = [
            {'kind': 'capabilities', 'data': {'version': 'test-fixture-only'}},
            {'kind': 'png_chunk', 'data': {'index': 1, 'base64': encoded}},
            {'kind': 'render_complete', 'data': {'chunks': 1, 'bytes': len(self.png)}},
            {'kind': 'probe_complete', 'data': True}]

    def test_complete_transfer_preserves_png_and_does_not_assert_join(self):
        marker = 'TEST:'
        text = '\n'.join('prefix ' + marker + json.dumps(e) for e in self.events)
        result, actual = collect_result(parse_events(text, marker), True)
        self.assertEqual(actual, self.png)
        self.assertFalse(result['client_join_validated'])
        self.assertFalse(result['server_hosting_validated'])
        Image.open(io.BytesIO(actual)).verify()

    def test_partial_transfer_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'did not complete'):
            collect_result([e for e in self.events if e['kind'] != 'png_chunk'], True)

    def test_missing_completion_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'did not complete'):
            collect_result(self.events[:-1], True)

    def test_reported_engine_failure_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'capture failed'):
            collect_result(self.events + [{'kind': 'render_failed', 'data': 'permission denied'}], True)

    def test_corrupted_png_rejected(self):
        bad = bytearray(self.png)
        bad[45] ^= 1
        with self.assertRaises(ValueError):
            validate_png(bad)

    def test_wildcard_patterns_include_overlaps_but_not_partial_tail(self):
        self.assertEqual(list(positions(b'\xAA\xAA\xAA\xAA', 'AA ? AA')), [0, 1])
        self.assertEqual(list(positions(b'\x00\xAA\x01', 'AA ? AA')), [])
        self.assertEqual(list(positions(b'\xAA\x10\xCC', 'AA ?? CC')), [0])


if __name__ == '__main__':
    unittest.main()
