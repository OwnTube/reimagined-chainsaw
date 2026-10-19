"""Experimental WEB renderer subset, not a claim of YouTube client parity."""
from .store import videos, video
from . import comments
from urllib.parse import urlencode


def text(value):
    return {'simpleText': str(value)}


def sign_in_url(watch_id=None):
    return '/?' + urlencode({'signin': '1', 'return_to': '/official' + ('?v=' + watch_id if watch_id else '')})


def endpoint(v):
    return {'watchEndpoint': {'videoId': v['id']},
            'commandMetadata': {'webCommandMetadata': {'url': '/watch?v=' + v['id'], 'webPageType': 'WEB_PAGE_TYPE_WATCH'}}}


def browse_endpoint(browse_id, url):
    return {'browseEndpoint': {'browseId': browse_id}, 'commandMetadata': {'webCommandMetadata': {
        'url': url, 'webPageType': 'WEB_PAGE_TYPE_BROWSE', 'apiUrl': '/youtubei/v1/browse'}}}


def channel_endpoint(channel):
    destination = browse_endpoint(channel, '/channel/' + channel)
    destination['commandMetadata']['webCommandMetadata']['webPageType'] = 'WEB_PAGE_TYPE_CHANNEL'
    return destination


def renderer(v):
    return {'videoRenderer': {
        'videoId': v['id'], 'title': {'runs': [{'text': v['title']}]},
        'thumbnail': {'thumbnails': [{'url': '/media/' + v['id'] + '/thumb.jpg', 'width': 640, 'height': 360}]},
        'ownerText': {'runs': [{'text': v['username'], 'navigationEndpoint': channel_endpoint(v['owner'])}]},
        'shortBylineText': {'runs': [{'text': v['username']}]},
        'viewCountText': text(str(v['views']) + ' views'),
        'lengthText': text(f"{int(v['duration']) // 60}:{int(v['duration']) % 60:02}"),
        'navigationEndpoint': endpoint(v)}}


def like_button(c, v, user):
    liked = bool(user and c.execute('SELECT 1 FROM likes WHERE user_id=? AND video_id=?',
                                   (user['id'], v['id'])).fetchone())
    def command(enabled):
        return {'commandMetadata': {'webCommandMetadata': {'sendPost': True,
                    'apiUrl': '/youtubei/v1/like/' + ('like' if enabled else 'removelike')}},
                'likeEndpoint': {'status': 'LIKE' if enabled else 'INDIFFERENT', 'target': {'videoId': v['id']}}}
    button = {'style': {'styleType': 'STYLE_TEXT'}, 'size': {'sizeType': 'SIZE_DEFAULT'},
              'isToggled': liked, 'isDisabled': False, 'targetId': 'mewtube-like',
              'defaultIcon': {'iconType': 'LIKE'}, 'toggledIcon': {'iconType': 'LIKE'},
              'defaultText': text(v['likes'] - int(liked)), 'toggledText': text(v['likes'] + int(not liked)),
              'defaultTooltip': 'Like', 'toggledTooltip': 'Unlike',
              'accessibilityData': {'accessibilityData': {'label': 'Like this video'}},
              'toggledAccessibilityData': {'accessibilityData': {'label': 'Unlike this video'}}}
    if user:
        button.update(defaultServiceEndpoint=command(True), toggledServiceEndpoint=command(False))
    else:
        destination = sign_in_url(v['id'])
        button['defaultNavigationEndpoint'] = {'urlEndpoint': {'url': destination},
            'commandMetadata': {'webCommandMetadata': {'url': destination}}}
    return {'toggleButtonRenderer': button}


def subscription_button(c, v, user):
    if not user:
        destination = sign_in_url(v['id'])
        return {'buttonRenderer': {'text': text('Subscribe'), 'style': 'STYLE_MONO_FILLED',
            'navigationEndpoint': {'urlEndpoint': {'url': destination},
                'commandMetadata': {'webCommandMetadata': {'url': destination}}}}}
    subscribed = bool(c.execute('SELECT 1 FROM subscriptions WHERE user_id=? AND channel_id=?',
                               (user['id'], v['owner'])).fetchone())
    def command(enabled):
        action = 'subscribe' if enabled else 'unsubscribe'
        return {'commandMetadata': {'webCommandMetadata': {'sendPost': True,
            'apiUrl': '/youtubei/v1/subscription/' + action}}, action + 'Endpoint': {'channelIds': [v['owner']]}}
    return {'subscribeButtonRenderer': {
        'buttonText': {'runs': [{'text': 'Subscribe'}]}, 'subscribed': subscribed,
        'enabled': True, 'type': 'FREE', 'channelId': v['owner'], 'showPreferences': False,
        'subscribedButtonText': {'runs': [{'text': 'Subscribed'}]},
        'unsubscribedButtonText': {'runs': [{'text': 'Subscribe'}]},
        'unsubscribeButtonText': {'runs': [{'text': 'Unsubscribe'}]},
        'subscribeAccessibility': {'accessibilityData': {'label': 'Subscribe'}},
        'unsubscribeAccessibility': {'accessibilityData': {'label': 'Unsubscribe'}},
        'onSubscribeEndpoints': [command(True)], 'onUnsubscribeEndpoints': [command(False)]}}


def owner_info(c, v, user):
    count = c.execute('SELECT count(*) FROM subscriptions WHERE channel_id=?', (v['owner'],)).fetchone()[0]
    return {'videoSecondaryInfoRenderer': {
        'owner': {'videoOwnerRenderer': {'title': {'runs': [{'text': v['username']}]},
            'navigationEndpoint': channel_endpoint(v['owner']),
            'thumbnail': {'thumbnails': [{'url': '/media/' + v['id'] + '/thumb.jpg', 'width': 80, 'height': 80}]},
            'subscriberCountText': text(str(count) + ' subscribers')}},
        'subscribeButton': subscription_button(c, v, user),
        'description': {'runs': [{'text': v['description']}]}}}


def response(c, operation, body, origin, user=None):
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
    if operation == 'guide':
        entries = [('Home', 'WHAT_TO_WATCH', browse_endpoint('FEwhat_to_watch', '/'))]
        subscriptions = browse_endpoint('FEsubscriptions', '/feed/subscriptions') if user else {
            'urlEndpoint': {'url': sign_in_url()}, 'commandMetadata': {'webCommandMetadata': {'url': sign_in_url()}}}
        entries.append(('Subscriptions', 'SUBSCRIPTIONS', subscriptions))
        if user:
            entries.append(('Your channel', 'ACCOUNT_BOX', channel_endpoint(user['id'])))
        return {**context, 'items': [{'guideSectionRenderer': {'items': [
            {'guideEntryRenderer': {'formattedTitle': text(title), 'icon': {'iconType': icon},
                'isPrimary': True, 'navigationEndpoint': destination}} for title, icon, destination in entries]}}]}
    browse_id = body.get('browseId', '') if operation == 'browse' else ''
    channel = c.execute('SELECT id,username FROM users WHERE id=?', (browse_id,)).fetchone() if browse_id else None
    rows = videos(c, body.get('query', '')[:200], channel=channel['id'] if channel else None,
                  subscriber=user['id'] if user and browse_id == 'FEsubscriptions' else None)
    if browse_id == 'FEsubscriptions' and not user:
        rows = []
    elif browse_id and browse_id not in ('FEwhat_to_watch', 'FEsubscriptions') and not channel:
        return None
    items = [renderer(v) for v in rows]
    if operation == 'search':
        return {**context, 'contents': {'twoColumnSearchResultsRenderer': {'primaryContents': {
            'sectionListRenderer': {'contents': [{'itemSectionRenderer': {'contents': items}}]}}}}}
    if operation == 'browse':
        title = channel['username'] if channel else ('Subscriptions' if browse_id == 'FEsubscriptions' else 'Home')
        if channel:
            context['header'] = {'c4TabbedHeaderRenderer': {'channelId': channel['id'], 'title': channel['username']}}
        return {**context, 'contents': {'twoColumnBrowseResultsRenderer': {'tabs': [{'tabRenderer': {
            'selected': True, 'title': title, 'content': {'richGridRenderer': {
                'contents': [{'richItemRenderer': {'content': item}} for item in items]}}}}]}}}
    if operation == 'next':
        v = video(c, body.get('videoId', ''))
        if v and v['status'] != 'ready':
            v = None
        main = [] if not v else [{'videoPrimaryInfoRenderer': {'title': {'runs': [{'text': v['title']}]},
                    'videoActions': {'menuRenderer': {'topLevelButtons': [like_button(c, v, user)]}}}},
                                owner_info(c, v, user)]
        if v and v['status'] == 'ready':
            comment_section, entities = comments.section(c, v, user)
            main.append(comment_section)
            context['frameworkUpdates'] = entities
        return {**context, 'contents': {'twoColumnWatchNextResults': {'results': {'results': {'contents': main}},
                   'secondaryResults': {'secondaryResults': {'results': items}}}}}
    return None
