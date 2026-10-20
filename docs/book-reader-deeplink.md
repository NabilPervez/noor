# F11: opening a Noor citation in Book Reader

Noor can link each book citation to the chapter in your Book Reader app:

```
<NOOR_BOOK_READER_URL>/?book=<book-id>&chapter=<chapter-id>&block=<first block index>
```

Set `NOOR_BOOK_READER_URL` in `.env`, for example `http://localhost:5173` for a local Book Reader, to turn
the links on in `noor ask` and in the web UI's source drawer. With it unset, no links are shown.

## The Book Reader side (not applied)

Book Reader doesn't read URL parameters yet. This change belongs in the separate
`NabilPervez/book-reader` repository and has **not** been applied, because that repository deploys
publicly. To enable it, add something like this near the top of `src/App.jsx`, using the app's
existing loaders in `src/lib/library.js`:

```jsx
// Open ?book=<id>&chapter=<id>&block=<n> from a Noor citation.
useEffect(() => {
  const p = new URLSearchParams(window.location.search);
  const book = p.get("book"), chapter = p.get("chapter");
  if (!book || !chapter) return;
  openBook(book).then(() => openChapter(chapter, { scrollToBlock: Number(p.get("block") || 0) }));
}, []);
```

`openBook`, `openChapter` and `scrollToBlock` stand in for whatever Book Reader's own navigation
functions are called. The block index matches `blocks[]` in `<book>/<chapter>.json`, which is the same
index Noor stores as `block_start`.
