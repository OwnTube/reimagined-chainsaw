"""Local native comment entities, authored from the observed guest contract.

Entity keys identify local UI records, not credentials or upstream tracking data.
Top-level creation and local voting are supported; replies remain unsupported.
"""
import base64
from datetime import datetime, timezone

CREATE_PREFIX = 'mewtube-comment-v1:'
VOTE_PREFIX = 'mewtube-comment-vote-v1:'


def vote_command(comment_id, action):
    return {'innertubeCommand': {
        'commandMetadata': {'webCommandMetadata': {'sendPost': True, 'apiUrl': '/youtubei/v1/comment/perform_comment_action'}},
        'performCommentActionEndpoint': {'action': VOTE_PREFIX + comment_id + ':' + action}}}


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
    arguments = (user['id'] if user else '', video['id']) + ((comment_id,) if comment_id is not None else ())
    rows = c.execute('''SELECT co.id,co.text,co.created,co.user_id,u.username,
        (SELECT count(*) FROM comment_votes cv WHERE cv.comment_id=co.id AND cv.value=1) likes,
        coalesce((SELECT value FROM comment_votes cv WHERE cv.comment_id=co.id AND cv.user_id=?),0) vote
        FROM comments co
        JOIN users u ON u.id=co.user_id WHERE co.video_id=?''' + predicate +
        ' ORDER BY co.created DESC,co.id DESC LIMIT 100', arguments).fetchall()
    mutations, threads = [], []
    shared = entity_key('', 43)

    def put(kind, value):
        mutations.append({'entityKey': value['key'], 'type': 'ENTITY_MUTATION_TYPE_REPLACE', 'payload': {kind: value}})

    put('commentSharedEntityPayload', {'key': shared,
        'strings': {'expandText': 'Read more', 'collapseText': 'Show less', 'replyButtonText': ''},
        'toolbarShared': {'unlikeButtonA11y': 'Unlike this comment',
            'dislikeCommentButtonA11y': 'Dislike this comment', 'undislikeButtonA11y': 'Remove dislike from this comment',
            'disabledLikeCommand': not bool(user), 'disabledDislikeCommand': not bool(user),
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
            'toolbar': {'likeButtonA11y': 'Like this comment',
                'likeCountLiked': str(row['likes'] + int(row['vote'] != 1)),
                'likeCountNotliked': str(row['likes'] - int(row['vote'] == 1)) if row['likes'] - int(row['vote'] == 1) else '',
                'likeInactiveTooltip': 'Like', 'likeActiveTooltip': 'Unlike',
                'dislikeInactiveTooltip': 'Dislike', 'dislikeActiveTooltip': 'Remove dislike'}})
        put('commentSurfaceEntityPayload', {'key': surface, 'inlineReadMoreButton': {'isExpanded': True},
            'relativeNestingLevel': 0, 'avatar': {'avatarViewModel': {
                'image': {'sources': [{'url': thumbnail, 'width': 80, 'height': 80}],
                          'processor': {'borderImageProcessor': {'circular': True}}},
                'endpoint': {'innertubeCommand': channel_endpoint(row['user_id'])},
                'accessibilityText': '@' + row['username']}}})
        put('engagementToolbarStateEntityPayload', {'key': toolbar,
            'likeState': {-1:'TOOLBAR_LIKE_STATE_DISLIKED', 0:'TOOLBAR_LIKE_STATE_INDIFFERENT', 1:'TOOLBAR_LIKE_STATE_LIKED'}[row['vote']],
            'heartState': 'TOOLBAR_HEART_STATE_UNHEARTED'})
        actions = {'likeCommand': vote_command(row['id'], 'like'), 'unlikeCommand': vote_command(row['id'], 'clear'),
                   'dislikeCommand': vote_command(row['id'], 'dislike'), 'undislikeCommand': vote_command(row['id'], 'clear')} if user else {}
        put('engagementToolbarSurfaceEntityPayload', {'key': toolbar_surface, **actions})
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
