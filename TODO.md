# TODO

## 1. Agent should reuse the existing result, not run the measurement again

When "Generate AI inspection report" is pressed, `/report` in `app.py` runs `agent.py`, and the agent runs
`inspect_crack.py` / `vibration.py` again on the same file. The website already has that result from
`/inspect` or `/vibration`, so this repeats 15-20 s of work.

Idea: save the result JSON next to the upload (for example `static/results/<uid>_result.json`) and let the
agent's tool return that saved result when it exists, running the script only when it does not.

## 2. Fix the "~1 s per photo" stat on the website

`templates/index.html` shows "~1 s - Per photo on a laptop CPU". Only the model inference takes about 1 s.
The full process (marker detection, rectification, U-Net on all tiles, measurement) takes about 15 s per
photo (14-21 s on `test_tilted.png` in the agent logs). Change the stat to show the full time, or label it
clearly as model inference only.

## 3. Test a real AI report once the Bedrock daily limit is lifted

Bedrock currently returns `ThrottlingException: Too many tokens per day` (HTTP 429) for both Claude Haiku 4.5
and Nova Lite, so every report so far came from the offline fallback.

When the limit is raised:

```
python agent.py --photo test_tilted.png --video test_vibration.mp4 --marker-mm 50
```

Then test the button on the website. Check that the report has no "Generated offline" note, that the draft
line is at the top, that the numbers match the tool results, and that the steps show tokens. To try another
model, set `BEDROCK_MODEL_ID` before starting the server (for example `apac.amazon.nova-lite-v1:0`).
