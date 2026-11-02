import { writeOutput } from './action-outputs.js';
import { ReleasePleaseRunner } from './release-please-runner.js';

const runner = new ReleasePleaseRunner({
  repository: process.env.REPOSITORY,
  token: process.env.RELEASE_TOKEN,
  configurationFile: process.env.CONFIGURATION,
  manifestFile: process.env.MANIFEST,
  notesFile: process.env.NOTES_FILE,
});

const phases = {
  async releases() {
    const release = await runner.createReleases();
    writeOutput('release-created', String(release !== undefined));
    writeOutput('tag-name', release?.tagName ?? '');
  },
  async 'pull-requests'() {
    const pullRequest = await runner.createPullRequests();
    writeOutput('release-pr', pullRequest ? JSON.stringify(pullRequest) : '');
  },
};

await phases[process.env.PHASE]();
