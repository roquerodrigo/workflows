import { ManifestPlugin } from 'release-please/build/src/plugin.js';
import { Changelog } from 'release-please/build/src/updaters/changelog.js';

export class ReleaseNotesPlugin extends ManifestPlugin {
  constructor(github, targetBranch, repositoryConfig, publishedNotes) {
    super(github, targetBranch, repositoryConfig);
    this.publishedNotes = publishedNotes;
  }

  async run(candidates) {
    for (const { pullRequest } of candidates) {
      this.publish(pullRequest);
    }
    return candidates;
  }

  publish(pullRequest) {
    const { digest, support, changelogs } = this.publishedNotes;
    const [release] = pullRequest.body.releaseData;
    const [heading] = release.notes.split('\n');
    const [, ...translations] = changelogs;
    for (const { path, notes } of translations) {
      pullRequest.updates.push({
        path,
        createIfMissing: true,
        updater: new Changelog({ changelogEntry: `${heading}\n\n${notes.trim()}\n`, version: pullRequest.version }),
      });
    }
    // The release is published from this body, so the sponsorship invitation
    // reaches it without repeating under every version of the changelog.
    release.notes = `${release.notes.trim()}\n\n${support.trim()}`;
    pullRequest.body.header = '';
    pullRequest.body.footer = `<!-- release-notes: ${digest} -->`;
  }
}
