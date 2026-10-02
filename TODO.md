# TODO

## 1. [x] Agent should reuse the existing result, not run the measurement again

Done. `/inspect` and `/vibration` save each result to `measurements/<uid>.json`. `/report` passes it to
`agent.py` with `--crack-json` / `--vib-json`, and the agent uses it when the file, marker size and method
match. The step list on the website shows "Reused earlier measurement". The tool runs only when no saved
result exists.

## 2. [x] Fix the "~1 s per photo" stat on the website

Done. The stat now says "~20 s - Full analysis of one photo on a laptop CPU".

Measured on `test_tilted.png` (2400 x 1600 photo), DL method, 3 runs each:

- U-Net inference only: 13.0 / 15.2 / 18.6 s
- Full `python inspect_crack.py test_tilted.png 50 --method dl`: 19.6 / 24.5 / 18.5 s

The earlier guess that inference takes ~1 s was wrong. Inference is most of the time: the photo is
rectified to 3213 x 2128 px (10 px/mm) and the model runs on 70 tiles of 384 x 384 at ~0.17 s each.
Everything else (Python start-up, marker, rectify, measurement, saving PNGs) is about 2 s.

Possible speedups (not done yet):

- Run the model only on the part of the image that matters (around the marker / user-selected area), or
  skip tiles that are plain background, instead of the whole rectified image.
- Reduce tile overlap (64 px -> 32 px) for about 20% fewer tiles.
- Send several tiles in one forward pass (batching) and check OpenCV DNN thread settings.
- Try ONNX Runtime or an INT8-quantised model, which are often faster than OpenCV DNN on CPU.
- Keep the model loaded in the Flask process instead of starting a new Python process per photo
  (saves ~1 s).

## 3. [ ] Test a real AI report once the Bedrock daily limit is lifted

Bedrock currently returns `ThrottlingException: Too many tokens per day` (HTTP 429) for both Claude Haiku 4.5
and Nova Lite, so every report so far came from the offline fallback.

When the limit is raised:

```
python agent.py --photo test_tilted.png --video test_vibration.mp4 --marker-mm 50
```

Then test the button on the website. Check that the report has no "Generated offline" note, that the draft
line is at the top, that the numbers match the tool results, and that the steps show tokens. To try another
model, set `BEDROCK_MODEL_ID` before starting the server (for example `apac.amazon.nova-lite-v1:0`).
