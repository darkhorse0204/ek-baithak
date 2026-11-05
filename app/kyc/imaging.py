"""Image quality gate and local OCR. Documents never leave our server for this step."""
from __future__ import annotations

import io
import threading

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks

BLUR_THRESHOLD = 60.0  # Laplacian variance; clean scans here score ~900-1900, the blurred one scores ~1
SKEW_THRESHOLD = 1.0  # degrees

_ocr = None
_lock = threading.Lock()


def _engine():
    global _ocr
    with _lock:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR()
    return _ocr


def load(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    return im.convert("RGB")


def sharpness(im: Image.Image) -> float:
    g = np.asarray(im.convert("L"), dtype=float)
    return float(ndimage.laplace(g).var())


def skew_angle(im: Image.Image) -> float:
    """Dominant near-horizontal line angle in degrees (positive = text rises to the right)."""
    small = im.convert("L").resize((max(im.width // 2, 1), max(im.height // 2, 1)))
    edges = canny(np.asarray(small, dtype=float), sigma=2)
    thetas = np.deg2rad(np.linspace(-20, 20, 161)) + np.pi / 2
    h, th, d = hough_line(edges, theta=thetas)
    _, angs, _ = hough_line_peaks(h, th, d, num_peaks=7)
    if not len(angs):
        return 0.0
    return float(np.median(np.rad2deg(angs - np.pi / 2)))


def quality(im: Image.Image) -> dict:
    s = sharpness(im)
    k = skew_angle(im)
    return {
        "sharpness": round(s, 1), "skew_degrees": round(k, 1), "width": im.width, "height": im.height,
        "blurry": s < BLUR_THRESHOLD, "skewed": abs(k) >= SKEW_THRESHOLD,
        "too_small": min(im.width, im.height) < 500,
    }


def deskew(im: Image.Image, angle: float) -> Image.Image:
    return im.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))


def remove_watermark(im: Image.Image) -> Image.Image:
    """The specimen watermark is pink; real text is dark. Whiting out pink pixels stops the
    watermark from swallowing values it crosses (it hid the GSTIN on K02)."""
    a = np.asarray(im.convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    pink = (r > 140) & (r - g > 25) & (r - b > 25)
    out = a.copy()
    out[pink] = 255
    return Image.fromarray(out.astype("uint8"))


def ocr(im: Image.Image, clean: bool = True) -> list[dict]:
    if clean:
        im = remove_watermark(im)
    res, _ = _engine()(np.asarray(im))
    out = []
    for box, txt, conf in res or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append({"text": txt, "conf": float(conf), "x": min(xs), "y": (min(ys) + max(ys)) / 2, "x2": max(xs)})
    return out
