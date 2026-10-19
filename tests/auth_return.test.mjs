import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const context=vm.createContext({window:{},URLSearchParams});
vm.runInContext(await readFile(new URL('../web/auth-return.js',import.meta.url),'utf8'),context);
const target=value=>context.window.mewtubeAuthReturn('?signin=1&return_to='+encodeURIComponent(value));
assert.equal(target('/official'),'/official');
assert.equal(target('/official?v=abcdefghijk'),'/official?v=abcdefghijk');
for(const unsafe of ['https://evil.test/official','//evil.test/official','/official?next=https://evil.test',
  '/official?v=short','/official?v=abcdefghijk&extra=1','/official#fragment','/official/../admin',
  '/admin','javascript:alert(1)','%2Fofficial','\\evil.test\\official','/official\n','/official\r'])assert.equal(target(unsafe),null);
assert.equal(context.window.mewtubeAuthReturn(''),null);
console.log('Authentication returns permit only the exact local captured-client home/watch routes');
