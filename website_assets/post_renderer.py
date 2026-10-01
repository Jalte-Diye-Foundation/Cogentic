"""Post HTML page rendering and template generation for reallyrealeducation.org."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def escape_html(value: Any) -> str:
    """Escape special characters for HTML output."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def format_post_date(iso_date: str) -> str:
    """Format ISO date (YYYY-MM-DD) to human-readable format (e.g. 1 October 2026)."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%B')} {dt.year}"
    except Exception:
        return iso_date


def is_meaningful_event_name(event_name: Any) -> bool:
    """Determine whether an event_name should be displayed on the post page.

    The event line appears only when:
    - event_name is present (not None/null)
    - event_name != 'General Awareness'
    - event_name != 'None'
    - event_name is not empty string
    """
    if event_name is None:
        return False
    clean = str(event_name).strip()
    if not clean:
        return False
    if clean.lower() in ("general awareness", "none", "null", "undefined"):
        return False
    return True


def render_post_page(
    post: dict[str, Any],
    site_url: str = "https://reallyrealeducation.org",
) -> str:
    """Render the full HTML document for a daily post page."""
    post_id = post.get("id") or f"post-{post.get('date', '')}"
    permalink = post.get("permalink") or f"{site_url}/posts/{post_id}.html"
    quote = post.get("quote") or post.get("title") or "AI Quote of the Day"
    title = f"{quote} | Really Real Education"
    description = post.get("explanation") or post.get("excerpt") or "Daily learning quote from Really Real Education."

    hashtags_val = post.get("hashtags", [])
    if isinstance(hashtags_val, list):
        hashtags_text = " ".join(hashtags_val)
    else:
        hashtags_text = str(hashtags_val or "")

    image_url = post.get("image", "")
    if not image_url.startswith("http"):
        date_str = post.get("date", "")
        if date_str:
            image_url = f"https://raw.githubusercontent.com/Jalte-Diye-Foundation/Cogentic/main/website_assets/archive/{date_str}/poster.jpg"
        else:
            image_url = f"https://raw.githubusercontent.com/Jalte-Diye-Foundation/Cogentic/main/website_assets/latest/poster.jpg"

    long_explanation = post.get("long_explanation", "")
    formatted_long_explanation = ""
    if long_explanation:
        escaped_long = escape_html(long_explanation)
        formatted_long_explanation = escaped_long.replace("\n\n", '</p><p class="post-long-explanation">').replace("\n", "<br>")

    theme = post.get("theme", "")
    event_name = post.get("event_name")

    # Conditional Event line rendering
    event_meta_html = ""
    if is_meaningful_event_name(event_name):
        event_meta_html = f'\n                        <p class="card-meta">Event: {escape_html(str(event_name).strip())}</p>'

    theme_meta_html = ""
    if theme:
        theme_meta_html = f'<p class="card-meta">Theme: {escape_html(theme)}</p>'

    formatted_date = format_post_date(post.get("date", ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(title)}</title>
    <meta name="description" content="{escape_html(description)}">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="Really Real Education">
    <meta property="og:title" content="{escape_html(title)}">
    <meta property="og:description" content="{escape_html(description)}">
    <meta property="og:image" content="{escape_html(image_url)}">
    <meta property="og:url" content="{escape_html(permalink)}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@JalteDiyeNPO">
    <meta name="twitter:title" content="{escape_html(title)}">
    <meta name="twitter:description" content="{escape_html(description)}">
    <meta name="twitter:image" content="{escape_html(image_url)}">
    <link rel="canonical" href="{escape_html(permalink)}">
    <link rel="stylesheet" href="../css/style.css">
    <link rel="icon" href="../assets/images/our mission.png" type="image/x-icon">
</head>
<body>
    <div class="page">
        <header class="site-header">
            <div class="site-header-inner">
                <div class="brand">
                    <div class="brand-title">Really Real Education</div>
                    <div class="brand-tagline">An Educational Initiative of <a href="https://jaltediyefoundation.org" target="_blank" rel="noopener noreferrer">Jalte Diye Foundation</a></div>
                </div>
                <nav class="site-nav">
                    <a href="../index.html">Home</a>
                    <a href="../books.html">Books</a>
                    <a href="../blog.html">Blogs</a>
                  <a href="../waking-up.html">Apply</a>
                </nav>
            </div>
        </header>

            <div class="projects-bar">
              <div class="projects-bar-inner">
                <span class="projects-label">Our Projects</span>
                <div class="projects-links">
                  <a href="../GVan.html">GVan</a>
                  <a href="../Cogentic.html" aria-current="page">Cogentic</a>
                  <a href="../Nurolab.html">Nurolab</a>
                </div>
              </div>
            </div>

        <main class="container">
            <section class="section">
                <div class="section-head posts-section-head">
                    <div>
                    <h1 class="section-title">Daily Posts Feed</h1>
                    <p class="section-desc">A fresh post is added every day</p>
                    </div>
                    <a class="btn secondary" href="../Cogentic.html">Back to all posts</a>
                </div>
              <article class="post-card" id="{escape_html(post_id)}">
                    <img class="post-image"
src="{escape_html(image_url)}" alt="{escape_html(quote)}" loading="eager">
                    <div class="post-body">
                        <h2 class="post-title">{escape_html(quote)}</h2>
                        {theme_meta_html}{event_meta_html}
                        <p class="card-meta">Last updated: {escape_html(formatted_date)}</p>
                        <p class="post-excerpt">{escape_html(description)}</p>
                        {f'<div class="post-long-explanation-block"><p class="post-long-explanation">{formatted_long_explanation}</p></div>' if formatted_long_explanation else ''}
                        {f'<p class="post-hashtags">{escape_html(hashtags_text)}</p>' if hashtags_text else ''}
                    </div>
                </article>
            </section>
        </main>

        <footer class="footer">
            <div>Built by Jalte Diye Foundation for Learners at reallyrealeducation.org.</div>
            <div class="footer-links">
                <a href="https://jaltediyefoundation.org" target="_blank" rel="noopener noreferrer">Privacy &amp; Terms</a>
                <a href="../compliance.html">Compliance</a>
                <a href="../founder.html">Founder's message</a>
            </div>
            <div class="footer-links">
              <a class="social-link" href="https://www.facebook.com/JalteDiyeFoundation/" target="_blank" rel="noopener noreferrer" aria-label="Jalte Diye Foundation on Facebook"><img class="social-icon" src="../assets/images/Facebook_Logo_Primary.png" alt="Facebook"></a>
              <a class="social-link" href="https://www.instagram.com/jalte_diye_foundation/" target="_blank" rel="noopener noreferrer" aria-label="Jalte Diye Foundation on Instagram"><img class="social-icon" src="../assets/images/Instagram_Glyph_Gradient.png" alt="Instagram"></a>
              <a class="social-link" href="https://www.linkedin.com/company/jalte-diye-foundation/" target="_blank" rel="noopener noreferrer" aria-label="Jalte Diye Foundation on LinkedIn"><img class="social-icon" src="../assets/images/LI-In-Bug.png" alt="LinkedIn"></a>
              <a class="social-link" href="https://x.com/JalteDiyeNPO" target="_blank" rel="noopener noreferrer" aria-label="Jalte Diye Foundation on X"><img class="social-icon" src="../assets/images/logo-black.png" alt="X"></a>
              <a class="social-link" href="https://www.youtube.com/@JalteDiyeNPO" target="_blank" rel="noopener noreferrer" aria-label="Jalte Diye Foundation on YouTube"><img class="social-icon" src="../assets/images/yt_icon_red_digital.png" alt="YouTube"></a>
            </div>
            <div class="fine-print">You can subscribe to us on social media for updates.</div>
        </footer>
    </div>
</body>
</html>
"""
