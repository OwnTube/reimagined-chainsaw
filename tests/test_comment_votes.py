import gzip
import http.cookiejar
import json
import sqlite3
import urllib.request
import test_service


class NativeCommentVoteTests(test_service.ServiceCase):
    def test_native_votes_authorize_session_update_entities_and_cascade(self):
        first = self.account('vote_author')
        video = self.upload('Local comment votes')
        self.request('/api/videos/'+video['id']+'/comment', {'text':'Vote target'})
        comment = self.request('/api/videos/'+video['id'])[1]['comments'][0]
        path = '/youtubei/v1/comment/perform_comment_action'
        def action(kind, **extra):
            return {'actions':['mewtube-comment-vote-v1:'+comment['id']+':'+kind],**extra}
        self.assertEqual(self.request(path, action('like'), client=urllib.request.build_opener())[0],401)
        self.assertEqual(self.request(path, action('like'), headers={'Origin':'https://evil.test'})[0],403)
        for body in [{},{'actions':[]},{'actions':['opaque-upstream-action']},{'actions':[None]},
                     {'actions':action('like')['actions']*2},action('delete')]:
            self.assertEqual(self.request(path,body)[0],400)
        self.assertEqual(self.request(path, {'actions':['mewtube-comment-vote-v1:missing0001:like']})[0],404)
        def state(result):
            return next(item['payload']['engagementToolbarStateEntityPayload']['likeState']
                for item in result['frameworkUpdates']['entityBatchUpdate']['mutations']
                if 'engagementToolbarStateEntityPayload' in item['payload'])
        for _ in range(2):
            status, result, _ = self.request(path, raw=gzip.compress(json.dumps(action('like')).encode()),
                                            headers={'Content-Encoding':'gzip'})
            self.assertEqual(status,200)
            self.assertEqual(state(result),'TOOLBAR_LIKE_STATE_LIKED')
        first_client = self.client
        def stored(client=None):
            return self.request('/api/videos/'+video['id'],client=client)[1]['comments'][0]
        self.assertEqual((stored()['likes'],stored()['myVote']),(1,1))
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.account('vote_viewer')
        status,result,_=self.request(path,action('dislike',userId=first['id']))
        self.assertEqual(status,200)
        self.assertEqual(state(result),'TOOLBAR_LIKE_STATE_DISLIKED')
        self.assertEqual((stored()['likes'],stored()['myVote']),(1,-1))
        self.assertEqual(stored(first_client)['myVote'],1,'Body IDs must not vote on behalf of another local account')
        self.assertEqual(state(self.request(path,action('clear'))[1]),'TOOLBAR_LIKE_STATE_INDIFFERENT')
        self.request(path,action('like'))
        self.assertEqual(stored()['likes'],2)
        self.request(path,action('clear'),client=first_client)
        self.assertEqual((stored()['likes'],stored()['myVote']),(1,1))
        self.assertEqual(stored(first_client)['myVote'],0)
        self.assertEqual(stored(urllib.request.build_opener())['myVote'],0)
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            c.execute("UPDATE videos SET status='failed' WHERE id=?",(video['id'],))
        self.assertEqual(self.request(path,action('clear'))[0],404)
        self.assertEqual(self.request('/api/videos/'+video['id']+'/delete',{},client=first_client)[0],200)
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            self.assertEqual(c.execute('SELECT count(*) FROM comment_votes').fetchone()[0],0)
