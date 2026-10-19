"""Local native comment entities, authored from the observed guest contract.

Entity keys identify local UI records, not credentials or upstream tracking data.
Only top-level creation is supported; replies and voting remain unsupported.
"""
import base64
from datetime import datetime, timezone

CREATE_PREFIX = 'mewtube-comment-v1:'


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def entity_key(identifier, entity_type):
    raw = identifier.encode('utf-8')
    encoded = b'\x12' + varint(len(raw)) + raw + b'\x20' + varint(entity_type) + b'\x28\x01'
    return base64.urlsafe_b64encode(encoded).decode().rstrip('=')


def section(c, video, user, comment_id=None):
    from .innertube import channel_endpoint
    predicate = ' AND co.id=?' if comment_id is not None else ''
    arguments = (video['id'], comment_id) if comment_id is not None else (video['id'],)
    rows = c.execute('''SELECT co.id,co.text,co.created,co.user_id,u.username FROM comments co
        JOIN users u ON u.id=co.user_id WHERE co.video_id=?''' + predicate +
        ' ORDER BY co.created DESC,co.id DESC LIMIT 100', arguments).fetchall()
    mutations, threads = [], []
    shared = entity_key('', 43)

    def put(kind, value):
        mutations.append({'entityKey': value['key'], 'type': 'ENTITY_MUTATION_TYPE_REPLACE', 'payload': {kind: value}})

    put('commentSharedEntityPayload', {'key': shared,
        'strings': {'expandText': 'Read more', 'collapseText': 'Show less', 'replyButtonText': ''},
        'toolbarShared': {'likeButtonA11y': 'Comment voting unavailable',
                          'replyButtonA11y': 'Replies unavailable'}})
    thumbnail = '/media/' + video['id'] + '/thumb.jpg'
    for row in rows:
        key, surface = entity_key(row['id'], 40), entity_key(row['id'] + '_surface', 79)
        toolbar, toolbar_surface = entity_key(row['id'], 44), entity_key(row['id'] + '_toolbar', 70)
        put('commentEntityPayload', {'key': key,
            'properties': {'commentId': row['id'], 'content': {'content': row['text']},
                'publishedTime': datetime.fromtimestamp(row['created'], timezone.utc).strftime('%Y-%m-%d'),
                'replyLevel': 0, 'authorButtonA11y': '@' + row['username'], 'toolbarStateKey': toolbar},
            'author': {'channelId': row['user_id'], 'displayName': '@' + row['username'],
                'avatarThumbnailUrl': thumbnail, 'isVerified': False,
                'isCurrentUser': bool(user and user['id'] == row['user_id']),
                'isCreator': row['user_id'] == video['owner']},
            'toolbar': {}})
        put('commentSurfaceEntityPayload', {'key': surface, 'inlineReadMoreButton': {'isExpanded': True},
            'relativeNestingLevel': 0, 'avatar': {'avatarViewModel': {
                'image': {'sources': [{'url': thumbnail, 'width': 80, 'height': 80}],
                          'processor': {'borderImageProcessor': {'circular': True}}},
                'endpoint': {'innertubeCommand': channel_endpoint(row['user_id'])},
                'accessibilityText': '@' + row['username']}}})
        put('engagementToolbarStateEntityPayload', {'key': toolbar,
            'likeState': 'TOOLBAR_LIKE_STATE_INDIFFERENT', 'heartState': 'TOOLBAR_HEART_STATE_UNHEARTED'})
        # No actions/endpoints are emitted for unsupported voting or replies.
        put('engagementToolbarSurfaceEntityPayload', {'key': toolbar_surface})
        threads.append({'commentThreadRenderer': {'commentViewModel': {'commentViewModel': {
            'commentId': row['id'], 'commentKey': key, 'sharedKey': shared,
            'commentSurfaceKey': surface, 'toolbarStateKey': toolbar, 'toolbarSurfaceKey': toolbar_surface}}}})
    count = c.execute('SELECT count(*) FROM comments WHERE video_id=?', (video['id'],)).fetchone()[0]
    header = {'countText': {'simpleText': str(count) + ' comments'}}
    if user:
        header['createRenderer'] = {'commentSimpleboxRenderer': {
            'authorThumbnail': {'thumbnails': [{'url': thumbnail, 'width': 80, 'height': 80}]},
            'placeholderText': {'simpleText': 'Add a local comment…'},
            'submitButton': {'buttonRenderer': {'text': {'simpleText': 'Comment'}, 'style': 'STYLE_PRIMARY',
                'isDisabled': False, 'serviceEndpoint': {
                    'commandMetadata': {'webCommandMetadata': {'sendPost': True, 'apiUrl': '/youtubei/v1/comment/create_comment'}},
                    'createCommentEndpoint': {'createCommentParams': CREATE_PREFIX + video['id']}}}},
            'cancelButton': {'buttonRenderer': {'text': {'simpleText': 'Cancel'}, 'style': 'STYLE_DEFAULT'}}}}
    return {'itemSectionRenderer': {'sectionIdentifier': 'comment-item-section', 'targetId': 'comments-section',
        'header': {'commentsHeaderRenderer': header},
        'contents': threads}}, {'entityBatchUpdate': {'mutations': mutations}}
