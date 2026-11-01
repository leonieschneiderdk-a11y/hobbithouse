# Hillside Hobbit House

A walkable 3D model of the hobbit house and its estate, built with [three.js](https://threejs.org) and free photo-scanned 3D models. It runs in any modern browser, with no install.

## Play it

Once GitHub Pages is switched on (see below), the game is at:

**https://leonieschneiderdk-a11y.github.io/hobbithouse/**

| Key | Action |
| --- | --- |
| W A S D / arrow keys | Walk |
| Mouse (click the view first) | Look around |
| Shift | Run |
| Space | Jump |
| M | Map: click anywhere to go there |
| Graphics button | Exposure, bloom, sun height and direction, lamp brightness, haze, shadows |

The lift in the entrance hall goes down to the garage: walk in and stand still.

## Turn on hosting (one time)

1. In this repository, open **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Push to `main` (or run the **Deploy to GitHub Pages** workflow from the Actions tab). The site goes live a minute or two later.

## Run it locally

The page loads models with `fetch`, so open it through a local web server rather than by double-clicking the file:

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000.

## How it is built

| Path | What it holds |
| --- | --- |
| `index.html` | The whole game: floor plan, rooms, grounds, lighting, post-processing and controls |
| `assets/models/` | Poly Haven models (furniture, chandeliers, barrels, trees, rocks), compressed to `.glb` |
| `assets/khronos/` | Models from the Khronos glTF sample library (velvet sofa, plant, lantern, coals, car) |
| `assets/hdri/` | Poly Haven sunset sky, used for realistic reflections |
| `assets/textures/` | Photo textures for wood floors and grass |

The floor plan is defined in pixels from the drawn plan (`room({... px:[x0,y0,x1,y1] ...})`), at 0.12 m per pixel. Every door and opening gets a keep-clear zone, and furniture that would block one is removed when the world is built.

Each piece of furniture is placed as a stand-in box first, then swapped for the matching scanned model once it loads. To use a different model, drop a `.glb` into `assets/models/` and add it to the `MODELS` list in `index.html`.

## Credits

See [CREDITS.md](CREDITS.md).
