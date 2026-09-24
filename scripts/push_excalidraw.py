#!/usr/bin/env python3
"""Push a local .excalidraw file into an Excalidraw+ scene as EDITABLE live content.

Usage:
  python3 push_excalidraw.py <file.excalidraw> <sceneId>                      # replace scene content
  python3 push_excalidraw.py <file.excalidraw> --new "Scene name" <collectionId>
  python3 push_excalidraw.py --inspect <sceneId>                             # live element count + url

Auth: EXCALIDRAW_API_KEY env var (or EXCALIDRAW_ENV_FILE pointing at a file
containing EXCALIDRAW_API_KEY=...). Get a key from Excalidraw+ workspace
settings. Never commit the key.

Protect hand-edited scenes: list their IDs in EXCALIDRAW_PROTECTED_SCENES
(comma-separated) and the script refuses to overwrite them unless
EXCALIDRAW_FORCE=1.

API quirks this script handles (api.excalidraw.com/api/v1, Bearer, public beta):
  - PUT /scenes/{id}/content needs the FULL doc {type,version,source,elements,appState,files}
  - every element needs version (number), index (fractional-index string), roundness key
  - arrow bindings need mode:'orbit' next to fixedPoint
  - the server rewrites element ids on save, so a re-push MERGES instead of replacing:
    the scene must be tombstoned (every live element re-sent with isDeleted=true) first
  - an empty-elements PUT is a no-op merge, NOT a clear
  - sharing/permissions are not exposed by the API; change them in the Excalidraw UI
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.excalidraw.com/api/v1"


def key() -> str:
    k = os.environ.get("EXCALIDRAW_API_KEY")
    if k:
        return k.strip()
    env_file = os.environ.get("EXCALIDRAW_ENV_FILE")
    if env_file and os.path.exists(env_file):
        for line in open(env_file):
            if line.startswith("EXCALIDRAW_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("EXCALIDRAW_API_KEY not set (or EXCALIDRAW_ENV_FILE has no key)")


def call(method: str, path: str, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}: {e.read().decode()[:800]}")


def normalize(doc: dict) -> dict:
    els = []
    for i, e in enumerate(doc["elements"]):
        e = dict(e)
        e.setdefault("version", 1)
        e["index"] = f"a{i:04d}"          # z-order = array position
        e.setdefault("roundness", None)
        if e.get("type") in ("line", "arrow"):
            for k in ("startBinding", "endBinding", "startArrowhead", "endArrowhead"):
                e.setdefault(k, None)
            e.setdefault("elbowed", False)
            e.setdefault("lastCommittedPoint", None)
        for k in ("startBinding", "endBinding"):
            if e.get(k):
                e[k].setdefault("mode", "orbit")
                if "fixedPoint" not in e[k]:
                    sys.exit(f"element {e.get('id')} {k} lacks fixedPoint (API will 400)")
        els.append(e)
    return {"type": "excalidraw", "version": 2, "source": "https://app.excalidraw.com",
            "elements": els,
            "appState": {"viewBackgroundColor": doc.get("appState", {}).get("viewBackgroundColor", "#ffffff")},
            "files": doc.get("files", {})}


def live_elements(scene: str) -> list:
    live = call("GET", f"/scenes/{scene}/content")
    return live.get("elements") or live.get("content", {}).get("elements", []) or []


def scene_url(scene: str) -> str:
    ws = call("GET", f"/scenes/{scene}")["metadata"]["workspace"]
    return f"https://app.excalidraw.com/s/{ws}/{scene}"


def guard(scene: str) -> None:
    protected = {s.strip() for s in os.environ.get("EXCALIDRAW_PROTECTED_SCENES", "").split(",") if s.strip()}
    if scene in protected and os.environ.get("EXCALIDRAW_FORCE") != "1":
        sys.exit(f"Refusing: {scene} is listed in EXCALIDRAW_PROTECTED_SCENES (hand-edited).\n"
                 f"Back it up first (GET /scenes/{scene}/content) then re-run with EXCALIDRAW_FORCE=1.")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--inspect":
        scene = args[1]
        n = len([e for e in live_elements(scene) if not e.get("isDeleted")])
        print(f"{scene}: {n} live elements  {scene_url(scene)}")
        return
    if len(args) < 2:
        sys.exit(__doc__)
    doc = normalize(json.load(open(args[0])))
    if args[1] == "--new":
        if len(args) < 4:
            sys.exit("--new needs: \"Scene name\" <collectionId>")
        meta = call("POST", "/scenes", {"name": args[2], "collectionId": args[3], "pinned": False})
        scene = meta["metadata"]["id"]
        print("created scene", scene, args[2])
    else:
        scene = args[1]
        guard(scene)
    live = live_elements(scene)
    if live:  # tombstone so the push replaces instead of merging
        call("PUT", f"/scenes/{scene}/content",
             {"type": "excalidraw", "version": 2, "source": doc["source"],
              "elements": [dict(e, isDeleted=True) for e in live],
              "appState": doc["appState"], "files": {}})
    call("PUT", f"/scenes/{scene}/content", doc)
    n = len([e for e in live_elements(scene) if not e.get("isDeleted")])
    if n != len(doc["elements"]):
        print(f"WARNING: scene holds {n} live elements, expected {len(doc['elements'])}")
    print(f"pushed {len(doc['elements'])} elements -> {scene_url(scene)}")


if __name__ == "__main__":
    main()
