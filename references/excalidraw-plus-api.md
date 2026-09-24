# Excalidraw+ API: pushing live editable scenes

Excalidraw+ (the hosted, paid workspace at app.excalidraw.com) exposes a public-beta REST API at `https://api.excalidraw.com/api/v1` with Bearer auth. `scripts/push_excalidraw.py` wraps it.

## Setup

1. Create an API key in your Excalidraw+ workspace settings.
2. `export EXCALIDRAW_API_KEY=...` (or put it in a gitignored file and set `EXCALIDRAW_ENV_FILE=/path/to/that/file`).
3. Find a collection ID: open a collection in the web app; the ID is in the URL. Needed only for `--new`.

## Commands

```bash
python3 scripts/push_excalidraw.py diagrams/x.excalidraw --new "My Diagram" <collectionId>   # create
python3 scripts/push_excalidraw.py diagrams/x.excalidraw <sceneId>                           # replace
python3 scripts/push_excalidraw.py --inspect <sceneId>                                       # count + url
```

## Schema quirks (each one causes a 400 if missed)

- `PUT /scenes/{id}/content` needs the full document shape, not a partial diff.
- Every element needs `version` (number), `index` (fractional-index string; zero-padded `a0000…` works), and an explicit `roundness` key (`null` is fine).
- Arrow bindings need `fixedPoint` and `mode: "orbit"` on both `startBinding` and `endBinding`.
- `line` elements are validated against the arrow schema, so binding/arrowhead keys must exist even when null.
- `POST /scenes` body: `{name, collectionId, pinned: false}`.
- The server rewrites element IDs on save and remaps bindings, so ID collisions across pushes are not a concern.

## Re-pushing merges, it does not replace

Because IDs are rewritten, a second push of the same file arrives as all-new elements and the scene keeps both copies. A `PUT` with `elements: []` does not clear anything (it is a no-op merge). The only working clear: `GET /scenes/{id}/content`, re-send every live element with `isDeleted: true` (IDs now match, so the server tombstones them), then `PUT` the new document. The script does this and verifies the live count afterwards. If a scene ever looks doubled, run `--inspect` and compare against the local file's element count.

## Z-order is array position

`normalize()` overwrites every element's `index` from its array position, so any custom index is discarded. Background zones appended after their cards will render on top and hide them. Build zones with a reserved slot (the builder's `zone()` + `fit_zone()` does this) or `insert()` them before their cards.

## Sharing is not available via the API

`PATCH /scenes/{id}` rejects `linkSharing` and `isPrivate`; the `/links`, `/readOnlyLinks` and `/share` sub-routes 404. The beta exposes content only. To change sharing, open the scene in the web app, click Share, and enable link sharing. `GET /scenes/{id}` → `metadata` reports the current state: `linkSharing: 0` with empty `readOnlyLinks` means workspace login is required; `isPrivate: false` means everyone in the workspace can see it.

## Keep a scene registry

Maintain a small table (in your project notes) of scene ID → name → owner. Automated pushes should only ever target scenes the automation created. Put hand-edited scene IDs in `EXCALIDRAW_PROTECTED_SCENES` so the script refuses them. Regenerate the local file and re-push to the same scene ID so the URL never changes; create a new scene only for a genuinely new diagram.
