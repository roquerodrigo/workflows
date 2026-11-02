import assert from 'node:assert/strict';
import { test } from 'node:test';

import { PullRequestBody } from 'release-please/build/src/util/pull-request-body.js';
import { Version } from 'release-please/build/src/version.js';

import { ReleaseNotesPlugin } from '../src/release-notes-plugin.js';

const HEADING = '## [1.1.0](https://github.com/o/r/compare/v1.0.0...v1.1.0) (2026-01-02)';
const DIGEST = 'a'.repeat(64);
const SUPPORT = '### Apoio\n\nApoie o projeto.\n';

function publishedNotes() {
  return {
    digest: DIGEST,
    support: SUPPORT,
    changelogs: [
      { language: 'pt-BR', path: '', notes: '### Correções\n\n- Corrige.\n' },
      { language: 'en', path: 'docs/CHANGELOG.en.md', notes: '### Bug fixes\n\n- Fixes.\n' },
    ],
  };
}

async function published(notes = publishedNotes()) {
  const version = Version.parse('1.1.0');
  const pullRequest = {
    version,
    updates: [],
    body: new PullRequestBody([{ version, notes: `${HEADING}\n\n### Correções\n\n- Corrige.\n` }]),
  };
  const plugin = new ReleaseNotesPlugin({}, 'main', {}, notes);
  await plugin.run([{ path: '.', pullRequest, config: {} }]);
  return pullRequest;
}

test('keeps each release of a language in its own file, without the support section', async () => {
  const notes = publishedNotes();
  notes.changelogs[0].release_path = 'docs/releases/pt-BR/{version}.md';
  notes.changelogs[1].release_path = 'docs/releases/en/{version}.md';
  const { updates } = await published(notes);
  assert.deepEqual(updates.map(update => update.path), [
    'docs/releases/pt-BR/1.1.0.md',
    'docs/CHANGELOG.en.md',
    'docs/releases/en/1.1.0.md',
  ]);
  const portuguese = updates[0].updater.updateContent('an earlier write');
  assert.equal(portuguese, `${HEADING}\n\n### Correções\n\n- Corrige.\n`);
  assert.equal(updates[2].updater.updateContent(undefined), `${HEADING}\n\n### Bug fixes\n\n- Fixes.\n`);
});

test('a translation can live only in the files of its releases', async () => {
  const notes = publishedNotes();
  notes.changelogs[1] = { ...notes.changelogs[1], path: '', release_path: 'docs/releases/en/{version}.md' };
  const { updates } = await published(notes);
  assert.deepEqual(updates.map(update => update.path), ['docs/releases/en/1.1.0.md']);
});

test('leaves the banner of release-please out and keeps the digest out of sight', async () => {
  const body = (await published()).body.toString();
  assert.ok(!body.includes('beep'));
  assert.ok(!body.includes('generated with'));
  assert.ok(body.endsWith(`---\n<!-- release-notes: ${DIGEST} -->`));
});

test('publishes the release from the notes and the support section, without the digest', async () => {
  const body = (await published()).body.toString();
  const [release] = PullRequestBody.parse(body).releaseData;
  assert.equal(release.version.toString(), '1.1.0');
  assert.equal(release.notes, `${HEADING}\n\n### Correções\n\n- Corrige.\n\n### Apoio\n\nApoie o projeto.`);
});

test('adds each translation to its own file under the same heading', async () => {
  const { updates } = await published();
  assert.deepEqual(updates.map(update => update.path), ['docs/CHANGELOG.en.md']);
  const first = updates[0].updater.updateContent(undefined);
  assert.ok(first.includes(`${HEADING}\n\n### Bug fixes\n\n- Fixes.`));
  const second = updates[0].updater.updateContent('# Changelog\n\n## [1.0.0] older\n\n- Old.\n');
  assert.ok(second.indexOf('### Bug fixes') < second.indexOf('[1.0.0] older'));
});
