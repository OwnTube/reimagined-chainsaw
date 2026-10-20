"""Prepare the owner's pinned RCC Lua templates for an owned local job.

Original attachments stay byte-for-byte intact in templates/. Only the job
copy receives parameters and the two documented source typo corrections.
These require a native ThumbnailGenerator; they are not viewport scripts.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

TEMPLATES = Path(__file__).with_name('templates')


def source(kind):
    name = {'headshot':'headshot.lua','full_body':'thumbnail.lua'}[kind]
    data = (TEMPLATES/name).read_bytes()
    manifest = json.loads((TEMPLATES/'manifest.json').read_text())
    if hashlib.sha256(data).hexdigest()!=manifest[name]['sha256']:
        raise ValueError('Owner template hash mismatch: '+name)
    return data.decode('utf-8')


def prepare(kind, *, width, height, base_url, upload_url, avatar, job_id, user_id=1, access_key='local-test'):
    if any(type(n) is not int or not 128<=n<=2048 for n in (width,height)):
        raise ValueError('Template size must be integer 128..2048')
    for url in (base_url,upload_url):
        parsed = urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('Template endpoints must use the owned numeric loopback HTTP backend')
    if type(user_id) is not int or not 0<=user_id<=2**53-1:raise ValueError('Invalid local user id')
    if not isinstance(avatar,dict) or not isinstance(avatar.get('assets'),list) or not isinstance(avatar.get('bodyColors'),dict):
        raise ValueError('Avatar requires assets and bodyColors')
    lua = source(kind)
    def quote(value):
        if not isinstance(value,str):raise ValueError('Job id and access key must be strings')
        # Lua 5.1 uses decimal byte escapes, not JSON's Unicode escapes.
        return '"'+''.join(chr(byte) if 32<=byte<=126 and byte not in (34,92)
                           else '\\'+str(byte).zfill(3) for byte in value.encode('utf-8'))+'"'
    lua = lua.replace('"InsertJobIdHere"',quote(job_id))
    lua = lua.replace('65789275746246',str(user_id))
    lua = lua.replace('"http://ech.qzz.io"',quote(base_url))
    lua = lua.replace("'http://ech.qzz.io'",quote(base_url))
    lua = lua.replace('"UPLOAD_URL_HERE"',quote(upload_url))
    lua = lua.replace("'JSON_AVATAR'",quote(json.dumps(avatar,separators=(',',':'))))
    lua = lua.replace('"AccessKey"',quote(access_key))
    lua = lua.replace('_X_RES_',str(width)).replace('_Y_RES_',str(height))
    # Two supplied typos, without changing camera math or Click arguments.
    lua = lua.replace('Instance.New(', 'Instance.new(')
    lua = lua.replace('SetAssetUrl(url ..', 'SetAssetUrl(baseURL ..')
    lua = lua.replace('render(1)', 'render(userId)')
    return lua


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=('headshot','full_body'))
    parser.add_argument('--job',type=Path,required=True,help='Owned job JSON parameters')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(prepare(args.kind,**json.loads(args.job.read_text())),encoding='utf-8')
