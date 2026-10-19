import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {browserFailures} from '../scripts/browser_acceptance.mjs';

// Prior false positives: the independent interface or a merely advancing media
// element must never turn a failed official-client run into a green check.
assert.ok(browserFailures({independentClient:{playback:true,interactions:true},
  capturedClient:{status:'capture-unavailable'}}).includes('capturedClient.playback'));
assert.ok(browserFailures({capturedClient:{media:{ok:true},playback:false}})
  .includes('capturedClient.playback'));
const fixture=JSON.parse(await readFile(new URL('./fixtures/browser_verified.json',import.meta.url),'utf8'));
assert.deepEqual(browserFailures(fixture),[]);
fixture.capturedClient.nativeComments.persisted=false;
assert.deepEqual(browserFailures(fixture),['capturedClient.nativeComments.persisted']);
delete fixture.capturedClient.nativeSubscriptions;
assert.ok(browserFailures(fixture).includes('capturedClient.nativeSubscriptions.excludesOtherCreator'));
console.log('Browser acceptance rejects independent-only, partial and regressed native evidence');
