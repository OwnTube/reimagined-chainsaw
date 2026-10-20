import base64
from pathlib import Path
import tempfile
import unittest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from local_player import LocalSigner, configure


class LocalPlayerTests(unittest.TestCase):
    def test_signed_script_verifies_exact_bytes_and_rejects_tampering(self):
        key = rsa.generate_private_key(public_exponent=65537,key_size=1024)
        for legacy in (False,True):
            with self.subTest(legacy=legacy):
                signed = LocalSigner(key).sign('print("owned local script")\n',legacy=legacy)
                prefix, encoded, body = signed.split(b'%',2)
                self.assertEqual(prefix,b'' if legacy else b'--rbxsig')
                self.assertTrue(body.startswith(b'\r\n'))
                signature = base64.b64decode(encoded)
                key.public_key().verify(signature,body,padding.PKCS1v15(),hashes.SHA1())
                with self.assertRaises(InvalidSignature):
                    key.public_key().verify(signature,body+b' ',padding.PKCS1v15(),hashes.SHA1())

    def test_configuration_rejects_unknown_input_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'unsupported.exe';path.write_bytes(b'not the pinned Player')
            with self.assertRaises(ValueError):configure(path)
            self.assertEqual(path.read_bytes(),b'not the pinned Player')


if __name__=='__main__':unittest.main()
