# starlingsintheslipstream.com
Repo for deployment of www.starlingsintheslipstream.com

## Adding a new post

New posts can be generated automatically from a Bandcamp track URL using the helper script:

```bash
python src/new_post.py <bandcamp_track_url>
```

**Example:**

```bash
python src/new_post.py https://brighteyes.bandcamp.com/track/stairwell-song
```

The script will:

1. Fetch the Bandcamp page and extract metadata (artist, track name, album, release year, embed code)
2. Generate tags from Bandcamp's genre tags, mapped to the blog's tag style
3. Add a decade tag (e.g. `90s`, `2020s`) and mark recent releases as `new`
4. Create a new post file in `content/posts/` with the next sequential number (e.g. `048.md`)
5. Set today's date automatically

No external dependencies are required — the script uses only the Python standard library.

### Requirements

- Python 3.10+
