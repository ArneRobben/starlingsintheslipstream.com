#!/usr/bin/env python3
"""
Generate a new blog post from a Bandcamp track URL.

Usage:
    python src/new_post.py <bandcamp_track_url>

Example:
    python src/new_post.py https://brighteyes.bandcamp.com/track/stairwell-song
"""

import sys
import re
import os
import json
import html
from datetime import date
from urllib.request import urlopen, Request
from urllib.error import URLError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(REPO_ROOT, "content", "posts")

# Common genre tag mappings from Bandcamp tags to blog-style tags
TAG_MAP = {
    "alternative": "alterative",  # matches existing spelling in the blog
    "alt-rock": "alterative",
    "alternative rock": "alterative",
    "indie": "indie",
    "indie rock": "indie-rock",
    "indie-rock": "indie-rock",
    "indie pop": "indie",
    "indie-pop": "indie",
    "lo-fi": "lo-fi",
    "lofi": "lo-fi",
    "rock": "rock",
    "folk": "folk",
    "punk": "punk",
    "post-punk": "post-punk",
    "shoegaze": "shoegaze",
    "dream pop": "dream-pop",
    "electronic": "electronic",
    "experimental": "experimental",
    "singer-songwriter": "singer-songwriter",
    "emo": "emo",
    "ambient": "ambient",
    "noise": "noise",
    "psychedelic": "psychedelic",
    "garage": "garage",
    "garage rock": "garage",
    "pop": "pop",
    "americana": "americana",
    "country": "country",
    "blues": "blues",
    "jazz": "jazz",
    "soul": "soul",
    "r&b": "r&b",
    "hip-hop": "hip-hop",
    "hip hop": "hip-hop",
    "metal": "metal",
    "hardcore": "hardcore",
    "math rock": "math-rock",
    "post-rock": "post-rock",
    "slowcore": "slowcore",
    "sadcore": "sadcore",
    "noise pop": "noise-pop",
    "art rock": "art-rock",
    "new wave": "new-wave",
    "synth-pop": "synth-pop",
    "synthpop": "synth-pop",
    "grunge": "grunge",
    "surf": "surf",
    "power pop": "power-pop",
    "britpop": "britpop",
    "chamber pop": "chamber-pop",
    "baroque pop": "baroque-pop",
    "alternative folk": "folk",
}


def get_decade_tag(year: int) -> str:
    """Return a decade tag string like '90s', '2000s', etc."""
    if year < 1970:
        return "60s"
    elif year < 1980:
        return "70s"
    elif year < 1990:
        return "80s"
    elif year < 2000:
        return "90s"
    elif year < 2010:
        return "2000s"
    elif year < 2020:
        return "2010s"
    else:
        return "2020s"


def is_recent(year: int) -> bool:
    """Check if the release is from the last ~2 years (considered 'new')."""
    return year >= date.today().year - 1


def fetch_page(url: str) -> str:
    """Fetch the raw HTML of a Bandcamp page."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"Error fetching {url}: {e}")
        sys.exit(1)


def extract_tralbum_data(page_html: str) -> dict:
    """Extract the TralbumData JSON object embedded in the page."""
    match = re.search(r"var\s+TralbumData\s*=\s*(\{.*?\})\s*;", page_html, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)

    # Bandcamp's JS object isn't strict JSON – clean it up
    # Remove single-line JS comments
    raw = re.sub(r"//[^\n]*", "", raw)
    # Remove trailing commas before closing braces/brackets
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Replace single-quoted strings with double-quoted
    # Handle property names without quotes
    raw = re.sub(r"(\w+)\s*:", r'"\1":', raw)
    # Fix double-double-quoted keys that were already quoted
    raw = re.sub(r'""(\w+)""', r'"\1"', raw)
    # Remove any JS expressions like `new Date(...)` – replace with null
    raw = re.sub(r"new\s+Date\([^)]*\)", "null", raw)
    # Handle url: "..." + "..." string concatenation (keep first string)
    raw = re.sub(r'"\s*\+\s*"', "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def extract_embedded_json_ld(page_html: str) -> dict:
    """Extract JSON-LD structured data from the page."""
    match = re.search(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        page_html,
        re.DOTALL,
    )
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def extract_tags_from_html(page_html: str) -> list[str]:
    """Extract Bandcamp tags from the page HTML."""
    # Tags appear as <a class="tag" href="...">tag name</a>
    tags = re.findall(r'<a[^>]*class="tag"[^>]*>([^<]+)</a>', page_html)
    if not tags:
        # Fallback: look for tags in the data-blob or tralbum
        blob_match = re.search(r'"tags"\s*:\s*\[([^\]]*)\]', page_html)
        if blob_match:
            tags = re.findall(r'"([^"]+)"', blob_match.group(1))
    return [html.unescape(t.strip().lower()) for t in tags]


def extract_embed_info(page_html: str) -> dict:
    """Extract album_id and track_id from the data-embed attribute."""
    info = {}

    # Primary: parse the data-embed JSON attribute (most reliable source)
    m = re.search(r'data-embed="([^"]+)"', page_html)
    if m:
        try:
            data_embed = json.loads(html.unescape(m.group(1)))

            # If there's album_embed_data, use it (track within an album)
            album_data = data_embed.get("album_embed_data")
            if album_data:
                album_param = album_data.get("tralbum_param", {})
                if album_param.get("name") == "album":
                    info["album_id"] = str(album_param["value"])
                if album_data.get("track_id"):
                    info["track_id"] = str(album_data["track_id"])
                if album_data.get("linkback"):
                    info["album_linkback"] = album_data["linkback"]
            else:
                # Standalone track
                tralbum = data_embed.get("tralbum_param", {})
                if tralbum.get("name") == "track":
                    info["track_id"] = str(tralbum["value"])

            if data_embed.get("linkback"):
                info["linkback"] = data_embed["linkback"]

        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: scrape from the EmbeddedPlayer URLs on the page
    if not info.get("track_id"):
        embed_match = re.search(r'EmbeddedPlayer/[^"]*track=(\d+)', page_html)
        if embed_match:
            info["track_id"] = embed_match.group(1)
    if not info.get("album_id"):
        embed_match = re.search(r'EmbeddedPlayer/[^"]*album=(\d+)', page_html)
        if embed_match:
            info["album_id"] = embed_match.group(1)

    return info


def parse_bandcamp_page(url: str) -> dict:
    """Parse a Bandcamp track page and return all relevant metadata."""
    page_html = fetch_page(url)

    # --- Extract structured data ---
    json_ld = extract_embedded_json_ld(page_html)
    tralbum = extract_tralbum_data(page_html)

    # --- Artist ---
    artist = ""
    if json_ld.get("byArtist", {}).get("name"):
        artist = json_ld["byArtist"]["name"]
    elif tralbum.get("artist"):
        artist = tralbum["artist"]
    else:
        m = re.search(r'<span\s+itemprop="byArtist"[^>]*>.*?<a[^>]*>([^<]+)</a>', page_html, re.DOTALL)
        if m:
            artist = html.unescape(m.group(1).strip())

    # --- Track name ---
    track_name = ""
    if json_ld.get("name"):
        track_name = json_ld["name"]
    elif tralbum.get("current", {}).get("title"):
        track_name = tralbum["current"]["title"]
    else:
        m = re.search(r'<h2\s+class="trackTitle"[^>]*>\s*([^<]+)', page_html)
        if m:
            track_name = html.unescape(m.group(1).strip())

    # --- Album name ---
    album_name = ""
    if json_ld.get("inAlbum", {}).get("name"):
        album_name = json_ld["inAlbum"]["name"]
    else:
        m = re.search(
            r'<span\s+class="fromAlbum"[^>]*>([^<]+)</span>', page_html
        )
        if m:
            album_name = html.unescape(m.group(1).strip())
        if not album_name:
            m = re.search(r'"album_title"\s*:\s*"([^"]+)"', page_html)
            if m:
                album_name = html.unescape(m.group(1).strip())

    # If album name is the same as track name, it's likely a single — skip album
    if album_name and track_name and album_name.strip().lower() == track_name.strip().lower():
        album_name = ""

    # --- Release year ---
    year = None
    if json_ld.get("datePublished"):
        m = re.search(r"(\d{4})", json_ld["datePublished"])
        if m:
            year = int(m.group(1))
    if not year:
        # Look for "released <Month> <Day>, <Year>" pattern
        m = re.search(r"released\s+\w+\s+\d{1,2},\s+(\d{4})", page_html)
        if m:
            year = int(m.group(1))
    if not year:
        m = re.search(r'"date_published"\s*:\s*"[^"]*(\d{4})', page_html)
        if m:
            year = int(m.group(1))

    # --- Tags ---
    bc_tags = extract_tags_from_html(page_html)

    # --- Embed info ---
    embed = extract_embed_info(page_html)

    # --- Bandcamp link for the iframe <a> tag ---
    # Determine if album or track link
    if album_name and embed.get("album_id"):
        # Prefer the exact album linkback URL from data-embed
        if embed.get("album_linkback"):
            link_url = embed["album_linkback"]
        else:
            album_url_match = re.search(
                r'href="(https://[^"]*bandcamp\.com/album/[^"]*)"', page_html
            )
            if album_url_match:
                link_url = album_url_match.group(1)
            else:
                artist_slug = url.split("//")[1].split(".bandcamp.com")[0]
                album_slug = re.sub(r"[^a-z0-9]+", "-", album_name.lower()).strip("-")
                link_url = f"https://{artist_slug}.bandcamp.com/album/{album_slug}"
        link_text = f"{album_name} by {artist}"
    else:
        link_url = embed.get("linkback", url)
        link_text = f"{track_name} by {artist}"

    return {
        "artist": artist,
        "track_name": track_name,
        "album_name": album_name,
        "year": year,
        "bandcamp_tags": bc_tags,
        "embed": embed,
        "link_url": link_url,
        "link_text": link_text,
    }


def build_embed_iframe(data: dict) -> str:
    """Build the Bandcamp embed iframe HTML."""
    embed = data["embed"]
    parts = []
    if embed.get("album_id"):
        parts.append(f"album={embed['album_id']}")
    parts.append("size=large")
    parts.append("bgcol=ffffff")
    parts.append("linkcol=0687f5")
    parts.append("tracklist=false")
    parts.append("artwork=small")
    if embed.get("track_id") and embed.get("album_id"):
        parts.append(f"track={embed['track_id']}")
    elif embed.get("track_id"):
        # Single track (no album)
        parts = [f"track={embed['track_id']}"] + parts[1:]  # replace album with track
    parts.append("transparent=true")

    src = "https://bandcamp.com/EmbeddedPlayer/" + "/".join(parts) + "/"

    link_url = data["link_url"]
    link_text = data["link_text"]

    return (
        f'<iframe style="border: 0; width: 100%; height: 120px;" '
        f'src="{src}" seamless>'
        f'<a href="{link_url}">{link_text}</a></iframe>'
    )


def generate_tags(data: dict) -> list[str]:
    """Generate blog tags from Bandcamp tags and metadata."""
    tags = set()
    for bc_tag in data["bandcamp_tags"]:
        if bc_tag in TAG_MAP:
            tags.add(TAG_MAP[bc_tag])

    # If we got no genre tags at all, add some sensible defaults
    if not tags:
        tags.add("alterative")
        tags.add("indie")

    # Add decade tag
    if data["year"]:
        tags.add(get_decade_tag(data["year"]))

    # Add "new" tag if recent
    if data["year"] and is_recent(data["year"]):
        tags.add("new")

    return sorted(tags)


def generate_keywords(data: dict) -> list[str]:
    """Generate blog keywords from metadata."""
    keywords = ["blog"]
    if data["year"]:
        keywords.append(get_decade_tag(data["year"]))
    if data["artist"]:
        keywords.append(data["artist"])
    return keywords


def get_next_post_number() -> int:
    """Find the next sequential post number."""
    existing = []
    for f in os.listdir(POSTS_DIR):
        m = re.match(r"^(\d+)\.md$", f)
        if m:
            existing.append(int(m.group(1)))
    return max(existing) + 1 if existing else 1


def create_post(data: dict) -> str:
    """Create the markdown post file and return its path."""
    post_num = get_next_post_number()
    filename = f"{post_num:03d}.md"
    filepath = os.path.join(POSTS_DIR, filename)

    today = date.today().isoformat()
    tags = generate_tags(data)
    keywords = generate_keywords(data)
    title = f'{data["artist"]} - {data["track_name"]}'
    iframe = build_embed_iframe(data)

    # Build the front matter
    tags_str = json.dumps(tags)
    kw_str = json.dumps(keywords)
    kw_comment = json.dumps(
        ["indie-rock", "alterative", "rock", "lo-fi", "new",
         "60s", "70s", "80s", "90s", "2000s", "2010s", "2020s"]
    )

    lines = [
        "---",
        f'title: "{title} "',
        f"date: {today}",
        f"tags: {tags_str} ",
        f"keywords: {kw_str} #{kw_comment}",
        "layout: single_about",
        "---",
        "",
        f"**Artist**: {data['artist']} \\",
        f"**Song**: {data['track_name']}  \\",
    ]

    if data["album_name"]:
        lines.append(f"**Album**: {data['album_name']}\\")

    lines += [
        f"**Year**: {data['year'] or 'Unknown'}",
        "",
        iframe,
    ]

    content = "\n".join(lines) + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python new_post.py <bandcamp_track_url>")
        print("Example: python new_post.py https://brighteyes.bandcamp.com/track/stairwell-song")
        sys.exit(1)

    url = sys.argv[1].strip()

    if "bandcamp.com" not in url:
        print("Error: Please provide a valid Bandcamp URL.")
        sys.exit(1)

    print(f"Fetching {url} ...")
    data = parse_bandcamp_page(url)

    print(f"\n  Artist:  {data['artist']}")
    print(f"  Track:   {data['track_name']}")
    print(f"  Album:   {data['album_name'] or '(single)'}")
    print(f"  Year:    {data['year']}")
    print(f"  BC Tags: {', '.join(data['bandcamp_tags'])}")
    print(f"  Tags:    {generate_tags(data)}")
    print(f"  Keywords:{generate_keywords(data)}")

    filepath = create_post(data)
    print(f"\n✅ Created: {filepath}")


if __name__ == "__main__":
    main()
