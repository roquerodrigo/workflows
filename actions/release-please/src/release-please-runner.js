import { readFileSync } from 'node:fs';

import releasePlease from 'release-please';
import { DefaultChangelogNotes } from 'release-please/build/src/changelog-notes/default.js';

import { ReleaseNotesPlugin } from './release-notes-plugin.js';
import { WrittenChangelogNotes } from './written-changelog-notes.js';

const { GitHub, Manifest, registerChangelogNotes } = releasePlease;
const ROOT_PACKAGE = '.';

export class ReleasePleaseRunner {
  constructor({ repository, token, configurationFile, manifestFile, notesFile }) {
    this.repository = repository;
    this.token = token;
    this.configurationFile = configurationFile;
    this.manifestFile = manifestFile;
    this.notesFile = notesFile;
  }

  async createReleases() {
    const manifest = await this.manifest();
    const releases = await manifest.createReleases();
    return releases.find(release => release !== undefined);
  }

  async createPullRequests() {
    const publishedNotes = this.notesFile ? JSON.parse(readFileSync(this.notesFile, 'utf8')) : undefined;
    if (publishedNotes) {
      registerChangelogNotes(
        'default',
        options => new WrittenChangelogNotes(publishedNotes.changelogs[0].notes, new DefaultChangelogNotes(options)),
      );
    }
    const manifest = await this.manifest();
    if (publishedNotes) {
      this.applyNotes(manifest, publishedNotes);
    }
    const pullRequests = await manifest.createPullRequests();
    return pullRequests.find(pullRequest => pullRequest !== undefined);
  }

  applyNotes(manifest, publishedNotes) {
    const primaryPath = publishedNotes.changelogs[0].path;
    if (primaryPath) {
      manifest.repositoryConfig[ROOT_PACKAGE].changelogPath = primaryPath;
    }
    manifest.plugins.push(
      new ReleaseNotesPlugin(this.github, this.github.repository.defaultBranch, manifest.repositoryConfig, publishedNotes),
    );
  }

  async manifest() {
    const [owner, repo] = this.repository.split('/');
    this.github = await GitHub.create({ owner, repo, token: this.token });
    return Manifest.fromManifest(
      this.github,
      this.github.repository.defaultBranch,
      this.configurationFile,
      this.manifestFile,
    );
  }
}
