import gzip
import http.cookiejar
import json
import sqlite3
import urllib.request
import test_service


class NativeCommentVoteTests(test_service.ServiceCase):
    def test_delete_checks_author_creator_operator_and_cascades_votes(self):
        creator=self.account('delete_creator')
        video=self.upload('Native comment deletion')
        self.request('/api/videos/'+video['id']+'/comment',{'text':'Creator target'})
        creator_comment=self.request('/api/videos/'+video['id'])[1]['comments'][0]['id']
        creator_client=self.client
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        viewer=self.account('delete_viewer')
        def post(text):
            self.request('/api/videos/'+video['id']+'/comment',{'text':text})
            return next(row['id'] for row in self.request('/api/videos/'+video['id'])[1]['comments'] if row['text']==text)
        own_comment=post('Viewer target')
        path='/youtubei/v1/comment/perform_comment_action'
        def remove(identifier,client=None,**extra):
            return self.request(path,{'actions':['mewtube-comment-action-v1:'+identifier+':delete'],**extra},client=client)
        def menu(identifier,client=None):
            result=self.request('/youtubei/v1/next',{'videoId':video['id']},client=client)[1]
            sections=result['contents']['twoColumnWatchNextResults']['results']['results']['contents']
            threads=next(item['itemSectionRenderer']['contents'] for item in sections if 'itemSectionRenderer' in item)
            model=next(item['commentThreadRenderer']['commentViewModel']['commentViewModel'] for item in threads
                       if item['commentThreadRenderer']['commentViewModel']['commentViewModel']['commentId']==identifier)
            surface=next(item['payload']['engagementToolbarSurfaceEntityPayload']
                         for item in result['frameworkUpdates']['entityBatchUpdate']['mutations']
                         if item['entityKey']==model['toolbarSurfaceKey'])
            return surface.get('menuCommand')
        self.assertIsNone(menu(creator_comment))
        self.assertIsNotNone(menu(own_comment))
        self.assertIsNotNone(menu(own_comment,creator_client))
        self.assertIsNone(menu(own_comment,urllib.request.build_opener()))
        self.assertEqual(remove(creator_comment,userId=creator['id'])[0],403)
        self.assertEqual(remove(own_comment,urllib.request.build_opener())[0],401)
        self.request(path,{'actions':['mewtube-comment-vote-v1:'+own_comment+':like']})
        status,result,_=remove(own_comment)
        self.assertEqual(status,200)
        self.assertEqual(result['actions'][0]['removeCommentAction']['commentId'],own_comment)
        self.assertEqual(result['actions'][0]['removeCommentAction']['actionResult']['status'],'STATUS_SUCCEEDED')
        self.assertEqual(remove(own_comment)[0],404)
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            self.assertEqual(c.execute('SELECT count(*) FROM comment_votes WHERE comment_id=?',(own_comment,)).fetchone()[0],0)
        third=post('Video owner can moderate')
        self.assertEqual(remove(third,creator_client)[0],200)
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            c.execute('UPDATE users SET admin=1 WHERE id=?',(viewer['id'],))
        self.assertIsNotNone(menu(creator_comment))
        self.assertEqual(remove(creator_comment)[0],200)
        self.assertEqual(self.request('/api/videos/'+video['id']+'/delete',{},client=creator_client)[0],200)

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
