/**
 * Cross-language parity check.
 *
 * The Python reply_guard is the tested reference. This runs replyGuard.gs
 * against the same fixtures and fails if it disagrees on any one of them, so a
 * fix applied to one implementation can never silently miss the other.
 *
 *   node --test apps-script/parity.test.mjs
 *
 * Regenerate the golden file after changing the Python:
 *   PYTHONPATH=src python3 -c "..."   # see README
 */

import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { strict as assert } from 'node:assert';
import test from 'node:test';
import vm from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const FIXTURES = join(ROOT, 'tests', 'fixtures');

// Load replyGuard.gs into a sandbox. Apps Script has no modules, so the file
// declares globals; eval is how we reach them without altering the source.
const sandbox = {};
vm.createContext(sandbox);
new vm.Script(readFileSync(join(HERE, 'replyGuard.gs'), 'utf8')).runInContext(sandbox);
const { classifyReply } = sandbox;

/** Minimal RFC822 split — enough for these fixtures. */
function parseEml(raw) {
  const split = raw.indexOf('\n\n');
  const headerBlock = split === -1 ? raw : raw.slice(0, split);
  const body = split === -1 ? '' : raw.slice(split + 2);

  const headers = {};
  let current = null;
  for (const line of headerBlock.split('\n')) {
    if (/^\s/.test(line) && current) {
      headers[current] += ' ' + line.trim();      // folded continuation
      continue;
    }
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    current = line.slice(0, idx).toLowerCase();
    headers[current] = line.slice(idx + 1).trim();
  }

  return {
    from: headers['from'] || '',
    to: headers['to'] || '',
    subject: headers['subject'] || '',
    contentType: headers['content-type'] || '',
    autoSubmitted: headers['auto-submitted'] || '',
    xAutoreply: headers['x-autoreply'] || '',
    precedence: headers['precedence'] || '',
    body
  };
}

const golden = JSON.parse(
  readFileSync(join(FIXTURES, 'expected_verdicts.json'), 'utf8')
);

const fixtures = readdirSync(FIXTURES).filter((f) => f.endsWith('.eml'));

test('every fixture has a golden verdict', () => {
  assert.equal(
    fixtures.length,
    Object.keys(golden).length,
    'fixture count and golden count differ — regenerate expected_verdicts.json'
  );
});

for (const name of fixtures) {
  test(`parity: ${name}`, () => {
    const expected = golden[name];
    assert.ok(expected, `no golden verdict for ${name}`);

    const actual = classifyReply(parseEml(readFileSync(join(FIXTURES, name), 'utf8')));

    assert.equal(actual.kind, expected.kind, 'kind differs from Python');
    assert.equal(actual.alert, expected.alert, 'alert differs from Python');
    assert.equal(actual.optOut, expected.optOut, 'optOut differs from Python');
    assert.equal(actual.responder, expected.responder, 'responder differs from Python');
  });
}

// The two cases worth naming explicitly, because they are the bug and its trap.

test('the Oct 12 Duke message never alerts', () => {
  const v = classifyReply(parseEml(readFileSync(join(FIXTURES, 'outbound_duke_step4.eml'), 'utf8')));
  assert.equal(v.kind, 'outbound_self');
  assert.equal(v.alert, false);
});

test('our own opt-out line is not read as the prospect opting out', () => {
  const v = classifyReply(parseEml(readFileSync(join(FIXTURES, 'outbound_duke_step4.eml'), 'utf8')));
  assert.equal(v.optOut, false);
});
