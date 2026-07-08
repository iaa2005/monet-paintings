# Monet Paintings

All 1353 Claude Monet paintings from [wikiart.org](https://www.wikiart.org/en/claude-monet), compressed to 700–800 KB, with face detection avatars.

## Structure

```
artworks/                  # 1353 paintings (.jpg)
avatars/                   # 95 face avatars 256×256 (.jpg)
python/                    # scraping & detection scripts
  models/                  # YuNet face detection model
  download_monet.py        # scraper
  compress_monet.py        # JPEG compressor
  detect_faces.py          # face detection + avatar crop
monet_paintings.json       # metadata for all 1353 paintings
```

## `monet_paintings.json`

```json
{
  "title": "View At Rouelles Le Havre",
  "year": "1858",
  "filename": "artworks/view-at-rouelles-le-havre.jpg",
  "width": 1280,
  "height": 797,
  "aspect_ratio": 1.606
}
```

| Field | Description |
|-------|-------------|
| `title` | Painting name |
| `year` | Year created |
| `filename` | Path to image |
| `width`, `height` | Dimensions in px |
| `aspect_ratio` | width / height |

## `avatars/avatars.json`

```json
{
  "filename": "camille-with-a-small-dog_face1.jpg",
  "source": "artworks/camille-with-a-small-dog.jpg",
  "gender": "female",
  "title": "Camille with a Small Dog",
  "year": "1866",
  "confidence": 0.87,
  "bbox": { "x": 135, "y": 120, "w": 52, "h": 58 }
}
```

| Field | Description |
|-------|-------------|
| `filename` | Avatar file name |
| `source` | Original painting |
| `gender` | `male` / `female` / `unknown` (title heuristic) |
| `title`, `year` | From parent painting |
| `confidence` | Face detector score (0–1) |
| `bbox` | Face bounding box in original image |
