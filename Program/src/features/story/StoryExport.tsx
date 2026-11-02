/** The story as a book, and the whole campaign as a file to keep or move (dungeon/book.py, dungeon/legacy.py). A
 * campaign file comes back from the Worlds page as a world of its own. */
export function StoryExport({ open }: { open?: boolean }) {
  return (
    <details className="story-people" open={open}>
      <summary>Export</summary>
      <p className="subtle">This branch as a book, chapter by chapter. Nothing hidden goes in.</p>
      <div className="form-actions">
        <a className="button" href="/api/story/export/book?format=md" download>Markdown</a>
        <a className="button" href="/api/story/export/book?format=epub" download>EPUB</a>
        <a className="button" href="/api/story/export/book?format=pdf" download>PDF</a>
      </div>
      <p className="subtle">The whole campaign, every branch and save, as one file. Import it on the Worlds page, here or on another machine.</p>
      <div className="form-actions">
        <a className="button" href="/api/story/export/campaign" download>Campaign file</a>
      </div>
    </details>
  )
}
