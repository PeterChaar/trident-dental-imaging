"""Dental X-ray image processing filters and tools."""

import numpy as np
import cv2
from PIL import Image, ImageEnhance


def load_image(path):
    """Load image as numpy array (grayscale for X-rays)."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path}")
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def adjust_brightness_contrast(img, brightness=0, contrast=0):
    """Adjust brightness (-100 to 100) and contrast (-100 to 100)."""
    img = img.astype(np.float64)
    # Contrast: scale around mean
    factor = (contrast + 100) / 100.0
    img = img * factor + (1 - factor) * 128
    # Brightness: shift
    img = img + brightness
    return np.clip(img, 0, 255).astype(np.uint8)


def invert(img):
    """Negative/invert filter — common in dental radiography."""
    return 255 - img


def sharpen(img, strength=1.0):
    """Sharpen the image."""
    blurred = cv2.GaussianBlur(img, (0, 0), 3)
    return cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)


def emboss(img):
    """Emboss filter for surface detail."""
    kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]])
    return cv2.filter2D(img, -1, kernel)


def edge_enhance(img):
    """Edge enhancement for caries/fracture detection."""
    edges = cv2.Canny(img, 50, 150)
    return cv2.addWeighted(img, 0.8, edges, 0.2, 0)


def clahe_enhance(img, clip_limit=2.0, grid_size=8):
    """CLAHE (Contrast Limited Adaptive Histogram Equalization) —
    excellent for dental X-rays to reveal hidden detail."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
    return clahe.apply(img)


def histogram_equalize(img):
    """Standard histogram equalization."""
    return cv2.equalizeHist(img)


def denoise(img, strength=10):
    """Non-local means denoising."""
    return cv2.fastNlMeansDenoising(img, None, strength, 7, 21)


def pseudo_color(img, colormap="jet"):
    """Apply pseudocolor mapping for density visualization."""
    colormaps = {
        "jet": cv2.COLORMAP_JET,
        "hot": cv2.COLORMAP_HOT,
        "bone": cv2.COLORMAP_BONE,
        "rainbow": cv2.COLORMAP_RAINBOW,
        "cool": cv2.COLORMAP_COOL,
    }
    cm = colormaps.get(colormap, cv2.COLORMAP_JET)
    return cv2.applyColorMap(img, cm)


def zoom_region(img, x, y, width, height):
    """Extract a region of interest."""
    h, w = img.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(w, x + width)
    y2 = min(h, y + height)
    return img[y1:y2, x1:x2]


def rotate_image(img, angle):
    """Rotate image by given angle."""
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h))


def flip_horizontal(img):
    return cv2.flip(img, 1)


def flip_vertical(img):
    return cv2.flip(img, 0)


# Preset filters matching Deep-View's standard filters
FILTER_PRESETS = {
    "Original": lambda img: img,
    "Enhanced": lambda img: clahe_enhance(img, 3.0),
    "Sharpened": lambda img: sharpen(img, 1.5),
    "Inverted": invert,
    "High Contrast": lambda img: adjust_brightness_contrast(img, 0, 50),
    "Edge Enhanced": edge_enhance,
    "Denoised": lambda img: denoise(img, 10),
    "Emboss": emboss,
    "Pseudo Color (Jet)": lambda img: pseudo_color(img, "jet"),
    "Pseudo Color (Hot)": lambda img: pseudo_color(img, "hot"),
    "Pseudo Color (Bone)": lambda img: pseudo_color(img, "bone"),
}
