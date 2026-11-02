export class WrittenChangelogNotes {
  constructor(writtenNotes, standardNotes) {
    this.writtenNotes = writtenNotes;
    this.standardNotes = standardNotes;
  }

  async buildNotes(commits, options) {
    const standard = await this.standardNotes.buildNotes(commits, options);
    const lines = standard.split('\n');
    // release-please skips the release when its notes are one line long, so a
    // release with nothing to show has to keep the bare heading it would write.
    if (lines.length <= 1) {
      return standard;
    }
    return `${lines[0]}\n\n${this.writtenNotes.trim()}\n`;
  }
}
