import assert from 'node:assert/strict';
import { test } from 'node:test';

import { WrittenChangelogNotes } from '../src/written-changelog-notes.js';

const HEADING = '## [1.1.0](https://github.com/o/r/compare/v1.0.0...v1.1.0) (2026-01-02)';

function standardNotes(text) {
  return { buildNotes: async () => text };
}

test('puts the written notes under the heading release-please builds', async () => {
  const notes = new WrittenChangelogNotes('### Bug fixes\n\n- Fix.\n', standardNotes(`${HEADING}\n\n### Fixes\n\n* fix`));
  assert.equal(await notes.buildNotes([], {}), `${HEADING}\n\n### Bug fixes\n\n- Fix.\n`);
});

test('keeps the bare heading that tells release-please to skip the release', async () => {
  const notes = new WrittenChangelogNotes('### Bug fixes\n\n- Fix.\n', standardNotes(HEADING));
  assert.equal(await notes.buildNotes([], {}), HEADING);
});
