"""Configure only a disposable copy of the exact pinned Player for local service.

Repoint data literals and the script-signing public key. Executable sections,
signature verification, and URL validation code are left intact. No private
key or proprietary executable is exported by this module.
"""
import base64
import hashlib
import re
import struct

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

PLAYER_SHA256 = '30502f062f428d3d808e7119ddb991865c91eb4beeed9f2c6b983198c007ea41'
LOCAL_DOMAIN = 'rcc13.test'


def data_section_for(blob, offset, size):
    pe = struct.unpack_from('<I',blob,0x3c)[0]
    count = struct.unpack_from('<H',blob,pe+6)[0]
    optional_size = struct.unpack_from('<H',blob,pe+20)[0]
    for i in range(count):
        start = pe+24+optional_size+40*i
        raw_size, raw_offset = struct.unpack_from('<II',blob,start+16)
        flags = struct.unpack_from('<I',blob,start+36)[0]
        if raw_offset<=offset and offset+size<=raw_offset+raw_size:
            if flags & 0x20000000:raise ValueError('Refusing an edit in executable code')
            return blob[start:start+8].rstrip(b'\0').decode('ascii')
    raise ValueError('Replacement is outside an initialized PE data section')


class LocalSigner:
    def __init__(self, key):self.key = key

    def sign(self, source):
        # The legacy wrapper signs the CRLF and exact script bytes after it.
        body = b'\r\n'+source.encode('utf-8')
        signature = self.key.sign(body,padding.PKCS1v15(),hashes.SHA1())
        self.key.public_key().verify(signature,body,padding.PKCS1v15(),hashes.SHA1())
        return b'--rbxsig%'+base64.b64encode(signature)+b'%'+body


def configure(executable):
    original = executable.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    if before!=PLAYER_SHA256:raise ValueError('Local configuration requires the exact pinned original Player')
    candidates = list(re.finditer(rb'BgIAAA[A-Za-z0-9+/=]{60,}',original))
    if len(candidates)!=1:raise ValueError('Expected one legacy RSA public-key literal')
    match = candidates[0]
    old_blob = base64.b64decode(match.group(),validate=True)
    if len(old_blob)!=148 or old_blob[8:12]!=b'RSA1' or struct.unpack_from('<I',old_blob,12)[0]!=1024:
        raise ValueError('Unexpected legacy public-key encoding')
    key = rsa.generate_private_key(public_exponent=65537,key_size=1024)
    numbers = key.public_key().public_numbers()
    new_blob = old_blob[:12]+struct.pack('<II',1024,numbers.e)+numbers.n.to_bytes(128,'little')
    replacement_key = base64.b64encode(new_blob)
    if len(replacement_key)!=len(match.group()):raise ValueError('Public-key size changed')
    changes = [(match.start(),match.group(),replacement_key,'local script public key')]
    pe = struct.unpack_from('<I',original,0x3c)[0]
    certificate_offset, certificate_size = struct.unpack_from('<II',original,pe+24+96+4*8)
    certificate_domains_unchanged = 0
    for encoding in ('ascii','utf-16le'):
        old = 'roblox.com'.encode(encoding); new = LOCAL_DOMAIN.encode(encoding)
        if len(old)!=len(new):raise ValueError('Local domain must preserve literal length')
        offsets = [m.start() for m in re.finditer(re.escape(old),original)]
        if len(offsets)!=(20 if encoding=='ascii' else 1):raise ValueError('Original domain inventory changed')
        for offset in offsets:
            if certificate_offset<=offset and offset+len(old)<=certificate_offset+certificate_size:
                # Keep original Authenticode certificate metadata unchanged.
                certificate_domains_unchanged += 1
                continue
            changes.append((offset,old,new,'local domain '+encoding))
    result = bytearray(original); records = []
    for offset,old,new,kind in sorted(changes):
        section = data_section_for(original,offset,len(old))
        if result[offset:offset+len(old)]!=old:raise ValueError('Overlapping or mismatched data edit')
        result[offset:offset+len(old)] = new
        records.append({'offset':offset,'size':len(old),'section':section,'kind':kind})
    if len(result)!=len(original):raise ValueError('Player file length changed')
    executable.write_bytes(result)
    public_der = key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    return LocalSigner(key), {'original_sha256':before,'configured_sha256':hashlib.sha256(result).hexdigest(),
        'domain':LOCAL_DOMAIN,'public_key_sha256':hashlib.sha256(public_der).hexdigest(),
        'signature_format':'--rbxsig, RSA1024 PKCS1v1.5 SHA1 over CRLF plus exact source',
        'certificate_domain_literals_unchanged':certificate_domains_unchanged,
        'data_edits':records,'executable_code_modified':False,'private_key_exported':False}
