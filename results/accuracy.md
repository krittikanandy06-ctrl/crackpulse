# Crack width accuracy

How well CrackPulse measures known widths, before and after the sub-pixel width change in
`inspect_crack.py` (October 2026). All runs use a 50 mm marker.

## What changed

**Before:** width = 2 × distance-transform value at each skeleton pixel of the binary crack mask. In the
rectified image 1 px = 0.1 mm, so results came only in 0.2 mm steps. A 3 px (0.3 mm) or 5 px (0.5 mm)
line always read one pixel too wide (0.4 / 0.6 mm). Blur also made the mask wider than the line, so
results on blurred photos were too high at every width.

**After:** the mask is still used to *find* the crack. The width comes from the grayscale image. At every
skeleton point the code samples a brightness profile across the crack (normal direction from the mask's
structure tensor, 0.25 px steps). The width is the distance between the two points where the darkness is
half-way between the crack core and the local background (full width at half maximum), with linear
interpolation between samples. Points with low contrast, or with no clear edge, keep the old
distance-transform width.

Check on perfect synthetic lines (mask + lightly blurred gray image):

| True width | Before | After |
|---|---|---|
| 0.3 mm | 0.40 | 0.303 |
| 0.5 mm | 0.60 | 0.500 |
| 1.0 mm | 1.00 | 1.000 |
| 2.0 mm | 2.00 | 2.000 |

## 1. Real photo of the printed calibration sheet

`20261010_185249.jpg` (phone camera, 4080 × 3060, no shadow), `measure_test_lines.py`, classical method.

| Line | True | Before | Error | After | Error |
|---|---|---|---|---|---|
| 1 | 0.30 mm | 0.40 | +33% | 0.25 | −17% |
| 2 | 0.50 mm | 0.60 | +20% | 0.44 | −12% |
| 3 | 1.00 mm | 1.00 | 0% | 0.95 | −5% |
| 4 | 2.00 mm | 2.00 | 0% | 1.96 | −2% |

After the change, all four lines read about 0.05 mm (half a pixel) below the nominal width. The edges in
this photo are very sharp (phone sharpening), and the brightness profile shows the 1 mm line about
9.5 px wide in the rectified image, so the printed lines are probably slightly thinner than nominal. The
old 0% on lines 3 and 4 came from the 0.2 mm rounding: the old method could not report a value between
0.8, 1.0 and 1.2 mm. The true printed width was not measured with a physical gauge, so this real photo
cannot prove which of the two numbers is closer.

The DL method finds none of the printed lines. The model treats sharp printed ink lines as non-cracks,
so the calibration sheet cannot test it.

## 2. Synthetic sheet photos (`test_photos/`)

Made by `make_fake_sheet_photos.py` from `calibration_sheet.pdf` (rotation, tilt, blur, noise, shadow,
JPEG). The true widths are known exactly. Classical method. On `sheet_lowres.jpg`, DL found line 3 only.

| Photo | Line | True | Before | Error | After | Error |
|---|---|---|---|---|---|---|
| sheet_mild (3024 px, ~11 px/mm) | 1 | 0.30 | 0.40 | +33% | 0.34 | +12% |
| | 2 | 0.50 | 0.60 | +20% | 0.51 | +3% |
| | 3 | 1.00 | 1.20 | +20% | 1.02 | +2% |
| | 4 | 2.00 | 2.20 | +10% | 2.01 | 0% |
| sheet_tilted (3024 px, 12° + strong tilt) | 1 | 0.30 | 0.44 | +46% | 0.40 | +32% |
| | 2 | 0.50 | 0.80 | +60% | 0.53 | +6% |
| | 3 | 1.00 | 1.20 | +20% | 1.03 | +3% |
| | 4 | 2.00 | 2.20 | +10% | 2.02 | +1% |
| sheet_lowres (1500 px, ~5.5 px/mm) | 1 | 0.30 | 0.60 | +100% | 0.58 | +92% |
| | 2 | 0.50 | 0.80 | +60% | 0.66 | +33% |
| | 3 | 1.00 | 1.40 | +40% | 1.04 | +4% |
| | 3 (DL) | 1.00 | 1.40 | +40% | 1.04 | +4% |
| | 4 | 2.00 | 2.20 | +20% | 2.02 | +1% |

## 3. `test_tilted.png` (website test image)

Made by `test_aruco.py`: one wavy crack on a grey wall, photographed at an angle. The script asks OpenCV
for a 1.5 mm (12 px at 8 px/mm) line, but `cv2.polylines` with thickness 12 draws 13 px. The true width
is therefore **1.625 mm**.

| Method | Before median / max | After median / max | Median error after |
|---|---|---|---|
| Classical | 1.60 / 1.68 mm | 1.60 / 1.67 mm | −1.5% |
| DL | 1.68 / 1.76 mm | 1.60 / 1.67 mm | −1.5% |

## 4. Three real photos combined (October 2026)

Same printed sheet on the wall, `measure_test_lines.py`, 50 mm marker, classical method (after the
sub-pixel change). Two new photos were sent through WhatsApp, which shrank them to 1280 × 960, so the
marker is only ~2.4 px/mm (the original phone photo is 12.3 px/mm).

| Photo | Scale | 0.3 mm | 0.5 mm | 1.0 mm | 2.0 mm |
|---|---|---|---|---|---|
| `20261010_185249.jpg` (phone original) | 12.3 px/mm | 0.25 (−17%) | 0.44 (−12%) | 0.95 (−5%) | 1.96 (−2%) |
| `WhatsApp … 10.20.30 (1).jpeg` | 2.4 px/mm | failed | failed | failed | failed |
| `WhatsApp … 10.20.30 (2).jpeg` | 2.5 px/mm | 0.61 (+102%) | 0.71 (+42%) | 0.79 (−21%) | 1.69 (−16%) |

WhatsApp (1) failed: the classical method found only 3 of the 4 lines, so the script could not tell
which line is which and gave no result. DL found no lines in any photo.

Final table, averaged over the photos that gave a result (n = 2):

| Line | True | Average measured | Average error | Average absolute error |
|---|---|---|---|---|
| 1 | 0.30 mm | 0.43 mm | +43% | 59% |
| 2 | 0.50 mm | 0.58 mm | +15% | 27% |
| 3 | 1.00 mm | 0.87 mm | −13% | 13% |
| 4 | 2.00 mm | 1.82 mm | −9% | 9% |

These averages are dominated by the WhatsApp photo. At 2.4 px/mm a 0.3 mm line is under one pixel and
JPEG compression blurs it, so it reads too wide. The 1 and 2 mm lines read too narrow because compression
softens their dark core. The original phone photo alone stays within 0.06 mm on every line. For accuracy
tests, send photos as a WhatsApp *document* (or copy the file directly) so the full resolution is kept.

## Limits

- Lines thinner than the blur in the photo still read too wide (FWHM cannot go below the blur width).
  On `sheet_lowres` a 0.3 mm line is only ~1.7 px in the original photo. For hairline cracks, take the
  photo closer, so the marker fills more of the frame.
- The error goes toward reading too wide, which is the safe side for crack assessment, except for the
  ~0.05 mm under-reading on the real phone photo described above.
- The DL model cannot be checked with the printed sheet.

Reproduce:

```
python measure_test_lines.py real_projects/20261010_185249.jpg.jpeg 50   # photos are not in the repo
python measure_test_lines.py "real_projects/WhatsApp Image 2026-10-24 at 10.20.30 (1).jpeg" 50
python measure_test_lines.py "real_projects/WhatsApp Image 2026-10-24 at 10.20.30 (2).jpeg" 50
python measure_test_lines.py test_photos 50
python inspect_crack.py test_tilted.png 50 --method classical
python inspect_crack.py test_tilted.png 50 --method dl
```
