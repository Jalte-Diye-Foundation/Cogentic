# Website Assets

This directory exposes the latest Cogentic AI generated educational post for frontend consumption.

## Structure

```text
website_assets/
└── latest/
    ├── poster.jpg      # Latest generated poster image
    └── metadata.json   # Latest post metadata
```

## Frontend Integration

The website at [reallyrealeducation.org/posts.html](https://reallyrealeducation.org/posts.html) can fetch assets from this folder after each daily pipeline run.

### Example: Load metadata

```javascript
const response = await fetch("/website_assets/latest/metadata.json");
const post = await response.json();

document.getElementById("quote").textContent = post.quote;
document.getElementById("explanation").textContent = post.explanation;
document.getElementById("poster").src = `/website_assets/${post.image}`;
```

### metadata.json schema

```json
{
  "date": "2026-06-22",
  "theme": "Quality Education",
  "quote": "...",
  "explanation": "...",
  "caption": "...",
  "hashtags": ["#CogenticAI", "#Education"],
  "image": "latest/poster.jpg",
  "source": "Cogentic AI"
}
```

## Update Flow

After each successful daily generation:

1. `output/YYYY-MM-DD/poster.jpg` is created by the PIL rendering pipeline.
2. `website_assets/update_assets.py` copies the poster to `website_assets/latest/poster.jpg`.
3. `metadata.json` is rewritten with the latest quote, theme, and caption.

## Future Support

This static asset layout is designed to evolve toward:

- **CMS API** — push metadata and media to a headless CMS
- **Cloud Storage** — sync `latest/` to S3, GCS, or Azure Blob
- **CDN** — serve posters through a global edge network
- **Database** — store post history with query APIs for archives and analytics
