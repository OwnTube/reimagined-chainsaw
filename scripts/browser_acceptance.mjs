/* A successful diagnostic process must also establish the verified native flows. */
export function browserFailures(diagnostics) {
  const paths = [
    'independentClient.playback', 'independentClient.interactions',
    'capturedClient.customElementDefined', 'capturedClient.sameOrigin',
    'capturedClient.localTitleVisible', 'capturedClient.watchLocalTitleVisible',
    'capturedClient.watchBootstrap.local', 'capturedClient.watchBootstrap.localAccount',
    'capturedClient.playback', 'capturedClient.controls.ok',
    'capturedClient.nativeLikes.unlike', 'capturedClient.nativeLikes.like', 'capturedClient.nativeLikes.persisted',
    'capturedClient.nativeComments.visible', 'capturedClient.nativeComments.localAuthor',
    'capturedClient.nativeComments.created', 'capturedClient.nativeComments.liveInsert', 'capturedClient.nativeComments.persisted',
    'capturedClient.nativeSubscriptions.subscribe', 'capturedClient.nativeSubscriptions.persisted',
    'capturedClient.nativeSubscriptions.feed', 'capturedClient.nativeSubscriptions.guide',
    'capturedClient.nativeSubscriptions.excludesUnfollowed', 'capturedClient.nativeSubscriptions.channel',
    'capturedClient.nativeSubscriptions.excludesOtherCreator', 'capturedClient.nativeSubscriptions.unsubscribe',
    'capturedClient.guestLocalSignIn', 'capturedClient.localAccountHandoff',
    'capturedClient.nativeAccountMenu.opened', 'capturedClient.nativeAccountMenu.localIdentity', 'capturedClient.nativeAccountMenu.ownChannel',
    'capturedClient.nativeSearch.submitted', 'capturedClient.nativeSearch.localResult', 'capturedClient.nativeSearch.excludesNonmatch',
    'capturedClient.nativeSearch.reload', 'capturedClient.nativeSearch.watchNavigation',
    'capturedClient.nativeChannelHeader.title', 'capturedClient.nativeChannelHeader.handle',
    'capturedClient.nativeChannelHeader.subscriberCount', 'capturedClient.nativeChannelHeader.readyVideoCount',
    'capturedClient.nativeLikedPlaylist.guide', 'capturedClient.nativeLikedPlaylist.localVideo',
    'capturedClient.nativeLikedPlaylist.excludesUnliked', 'capturedClient.nativeLikedPlaylist.reload',
    'capturedClient.nativeLikedPlaylist.watchNavigation', 'capturedClient.nativeLikedPlaylist.unlikeRemoves',
    'capturedClient.nativeLikedPlaylist.pagination', 'capturedClient.nativeLikedPlaylist.compactLayout',
    'capturedClient.nativeCommentAuthor.navigation', 'capturedClient.nativeCommentAuthor.localChannel'
  ];
  return paths.filter(path => path.split('.').reduce((value, key) => value?.[key], diagnostics) !== true);
}
