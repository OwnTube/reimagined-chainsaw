import base64
import json
import sqlite3
import unittest
from mewtube.comments import entity_key, section, varint
from mewtube.snapshot import replace_json_assignment


class CommentContractTests(unittest.TestCase):
    def test_local_entity_keys_threads_and_safe_bootstrap(self):
        identifier = 'comment0001'
        key = entity_key(identifier, 40)
        self.assertEqual(base64.urlsafe_b64decode(key + '=' * (-len(key) % 4)),
                         b'\x12\x0bcomment0001\x20\x28\x28\x01')
        self.assertEqual(varint(255), b'\xff\x01')
        c = sqlite3.connect(':memory:')
        c.row_factory = sqlite3.Row
        self.addCleanup(c.close)
        c.executescript('CREATE TABLE users(id TEXT,username TEXT);'
                       'CREATE TABLE comments(id TEXT,text TEXT,created INT,user_id TEXT,video_id TEXT);')
        c.execute('CREATE TABLE comment_votes(user_id TEXT,comment_id TEXT,value INT)')
        c.execute('INSERT INTO users VALUES(?,?)', ('author00001', 'local_author'))
        c.execute('INSERT INTO comments VALUES(?,?,?,?,?)',
                  (identifier, '</script><script>not executable</script>', 1, 'author00001', 'localvid001'))
        c.execute('INSERT INTO comments VALUES(?,?,?,?,?)', ('other000001', 'Other video', 2, 'author00001', 'othervid001'))
        view, framework = section(c, {'id':'localvid001', 'owner':'author00001'}, {'id':'author00001'})
        rows = view['itemSectionRenderer']['contents']
        self.assertEqual(len(rows), 1)
        mutations = framework['entityBatchUpdate']['mutations']
        self.assertEqual(len(mutations), 5)
        entities = {mutation['entityKey']: next(iter(mutation['payload'].values())) for mutation in mutations}
        model = rows[0]['commentThreadRenderer']['commentViewModel']['commentViewModel']
        self.assertTrue(all(model[name] in entities for name in ('commentKey','sharedKey','commentSurfaceKey','toolbarStateKey','toolbarSurfaceKey')))
        self.assertTrue(entities[model['commentKey']]['author']['isCurrentUser'])
        self.assertEqual(entities[model['commentKey']]['author']['displayName'], '@local_author')
        author_endpoint = entities[model['commentSurfaceKey']]['avatar']['avatarViewModel']['endpoint']['innertubeCommand']
        self.assertEqual(author_endpoint['browseEndpoint']['browseId'], 'author00001')
        self.assertEqual(author_endpoint['commandMetadata']['webCommandMetadata']['url'], '/channel/author00001')
        encoded = replace_json_assignment('<script>var ytInitialData={};</script>', 'ytInitialData', framework)
        self.assertEqual(encoded.count('</script>'), 1)
        self.assertNotIn('Other video', json.dumps(framework))
        self.assertNotIn('createCommentEndpoint', json.dumps(framework))
        for i in range(101):
            c.execute('INSERT INTO comments VALUES(?,?,?,?,?)', (f'bound{i:06}', 'Bounded item', i+2, 'author00001', 'localvid001'))
        bounded, guest_entities = section(c, {'id':'localvid001', 'owner':'author00001'}, None)
        self.assertEqual(len(bounded['itemSectionRenderer']['contents']), 100)
        self.assertEqual(bounded['itemSectionRenderer']['header']['commentsHeaderRenderer']['countText']['simpleText'], '102 comments')
        self.assertNotIn('createRenderer', bounded['itemSectionRenderer']['header']['commentsHeaderRenderer'])
        self.assertNotIn('performCommentActionEndpoint', json.dumps(guest_entities))
        shared = guest_entities['entityBatchUpdate']['mutations'][0]['payload']['commentSharedEntityPayload']['toolbarShared']
        self.assertTrue(shared['disabledLikeCommand'])
        self.assertTrue(shared['disabledDislikeCommand'])
