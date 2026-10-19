"""Experimental WEB renderer subset, not a claim of YouTube client parity."""
from .store import videos, video


def text(value):
    return {'simpleText': str(value)}


def endpoint(v):
    return {'watchEndpoint': {'videoId': v['id']},
            'commandMetadata': {'webCommandMetadata': {'url': '/watch?v=' + v['id'], 'webPageType': 'WEB_PAGE_TYPE_WATCH'}}}


def renderer(v):
    return {'videoRenderer': {
        'videoId': v['id'], 'title': {'runs': [{'text': v['title']}]},
        'thumbnail': {'thumbnails': [{'url': '/media/' + v['id'] + '/thumb.jpg', 'width': 640, 'height': 360}]},
        'ownerText': {'runs': [{'text': v['username'], 'navigationEndpoint': {'browseEndpoint': {'browseId': v['owner']}}}]},
        'shortBylineText': {'runs': [{'text': v['username']}]},
        'viewCountText': text(str(v['views']) + ' views'),
        'lengthText': text(f"{int(v['duration']) // 60}:{int(v['duration']) % 60:02}"),
        'navigationEndpoint': endpoint(v)}}


def response(c, operation, body, origin):
    context = {'responseContext': {'serviceTrackingParams': [], 'mainAppWebResponseContext': {'loggedOut': True}}}
    if operation == 'player':
        v = video(c, body.get('videoId', ''))
        if not v or v['status'] != 'ready':
            return {**context, 'playabilityStatus': {'status': 'ERROR', 'reason': 'Video unavailable'}}
        context['responseContext']['mainAppWebResponseContext']['mewtubeLocalResponse'] = True
        return {**context, 'playabilityStatus': {'status': 'OK'},
                'videoDetails': {'videoId': v['id'], 'title': v['title'], 'author': v['username'],
                                 'channelId': v['owner'], 'lengthSeconds': str(int(v['duration'])),
                                 'viewCount': str(v['views']), 'shortDescription': v['description'],
                                 'isLiveContent': False, 'isOwnerViewing': False,
                                 'thumbnail': {'thumbnails': [{'url': origin + '/media/' + v['id'] + '/thumb.jpg',
                                                              'width': 640, 'height': 360}]}},
                'streamingData': {'expiresInSeconds': '3600', 'formats': [{
                    'itag': 22, 'url': origin + '/media/' + v['id'] + '/video.mp4',
                    'mimeType': 'video/mp4; codecs="avc1.64001F, mp4a.40.2"',
                    'quality': 'hd720', 'qualityLabel': '720p', 'approxDurationMs': str(int(v['duration'] * 1000))}]}}
    items = [renderer(v) for v in videos(c, body.get('query', '')[:200])]
    if operation == 'search':
        return {**context, 'contents': {'twoColumnSearchResultsRenderer': {'primaryContents': {
            'sectionListRenderer': {'contents': [{'itemSectionRenderer': {'contents': items}}]}}}}}
    if operation == 'browse':
        return {**context, 'contents': {'twoColumnBrowseResultsRenderer': {'tabs': [{'tabRenderer': {
            'selected': True, 'title': 'Home', 'content': {'richGridRenderer': {
                'contents': [{'richItemRenderer': {'content': item}} for item in items]}}}}]}}}
    if operation == 'next':
        v = video(c, body.get('videoId', ''))
        main = [] if not v else [{'videoPrimaryInfoRenderer': {'title': {'runs': [{'text': v['title']}]}}},
                                {'videoSecondaryInfoRenderer': {'description': {'runs': [{'text': v['description']}]}}}]
        return {**context, 'contents': {'twoColumnWatchNextResults': {'results': {'results': {'contents': main}},
                   'secondaryResults': {'secondaryResults': {'results': items}}}}}
    return None
