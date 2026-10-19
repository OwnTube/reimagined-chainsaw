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
    'capturedClient.guestLocalSignIn', 'capturedClient.localAccountHandoff'
  ];
  return paths.filter(path => path.split('.').reduce((value, key) => value?.[key], diagnostics) !== true);
}
