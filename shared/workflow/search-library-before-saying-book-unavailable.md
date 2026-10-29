# Search the library and mlr before saying a book is unavailable

Before a reply says a reference book cannot be reached, is unavailable, or was not checked,
search both places that hold the lab's books:

- the project library, `/mnt/project-files/books/`,
- the private `Morrison-Lab/mlr` repository, which keeps copyrighted PDFs.

If the book is in either place, read it there.
If it is in neither, say which two places you searched.
A book missing from one of the two is added to both.

Ezra stated this on 2026-10-23 and repeated it on 2026-10-28 ("did you check mlr?"),
after a reply listed ESL, Murphy, Bishop and the patsy docs as unreachable
when the project library held them.

## Mechanism

`hooks/flag-book-unavailable-without-library-search.py` is a Stop hook.
It warns once when a reply says a book is unreachable, unavailable or unchecked
and the transcript shows no search of either place.
It never decides: a book may really be missing from both.

See also [`track-useful-resources`](track-useful-resources.md),
which covers recording resources once found.
