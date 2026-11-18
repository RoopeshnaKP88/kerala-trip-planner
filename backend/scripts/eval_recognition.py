"""Measure recognition accuracy on your test photos.

Name files like  athirappilly_01.jpg, chembra_peak_02.jpg, lakkidi_03.jpg
(the text before the trailing number is the expected place name).

Run from the backend folder:  python -m scripts.eval_recognition
"""
import asyncio
import re
from pathlib import Path

from app import vlm

FOLDER = Path("testing_images")


def expected(path: Path) -> str:
    return re.sub(r"_?\d+$", "", path.stem).replace("_", " ").lower()


async def main():
    files = sorted(p for p in FOLDER.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if not files:
        print("Put 15-20 photos in backend/testing_images first.")
        return
    hits = 0
    for f in files:
        exp = expected(f)
        try:
            rec = await vlm.recognize(vlm.preprocess(f.read_bytes()))
            ok = exp.split()[0] in rec.location_name.lower()
            got = f"{rec.location_name} ({rec.district}) conf={rec.confidence:.2f}"
        except Exception as e:
            ok, got = False, f"ERROR {e}"
        hits += ok
        print(f"{'PASS' if ok else 'FAIL'}  expected={exp:<22} got={got}")
    print(f"\nAccuracy: {hits}/{len(files)} = {hits / len(files):.0%}")


asyncio.run(main())