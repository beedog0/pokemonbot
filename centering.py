"""
MUKSCAN Centering Module
========================
Uses OpenCV to detect the card border and compute centering ratios.
Returns structured data to inject into the Gemini grading prompt.

Requirements:
    pip install opencv-python-headless numpy

How it works:
    1. Convert image to grayscale
    2. Apply Gaussian blur to reduce noise
    3. Use Canny edge detection to find edges
    4. Find the largest rectangular contour (the card border)
    5. Apply perspective correction to get a flat top-down view
    6. Detect the inner artwork/border boundary
    7. Measure the 4 border widths (top, bottom, left, right)
    8. Compute centering ratios in PSA format (e.g., 55/45)
"""

import cv2
import numpy as np
from io import BytesIO


def order_points(pts):
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left has smallest sum
    rect[2] = pts[np.argmax(s)]      # bottom-right has largest sum
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]      # top-right has smallest difference
    rect[3] = pts[np.argmax(d)]      # bottom-left has largest difference
    return rect


def four_point_transform(image, pts):
    """Warp a quadrilateral region to a flat rectangle."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxW = max(int(widthA), int(widthB))

    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxH = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxW - 1, 0],
        [maxW - 1, maxH - 1],
        [0, maxH - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxW, maxH))
    return warped


def find_card_contour(image):
    """
    Find the largest rectangular contour in the image (the card).
    Returns the 4-point contour or None.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)

    # Try multiple thresholding approaches for robustness
    contour_candidates = []

    # Method 1: Canny edge detection
    for low, high in [(30, 100), (50, 150), (20, 80)]:
        edges = cv2.Canny(blurred, low, high)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.erode(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour_candidates.extend(contours)

    # Method 2: Adaptive threshold
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.dilate(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_candidates.extend(contours)

    if not contour_candidates:
        return None

    # Sort by area, largest first
    contour_candidates.sort(key=cv2.contourArea, reverse=True)

    img_area = image.shape[0] * image.shape[1]

    for contour in contour_candidates[:10]:
        area = cv2.contourArea(contour)
        # Card should be at least 10% of image and no more than 98%
        if area < img_area * 0.10 or area > img_area * 0.98:
            continue

        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) == 4:
            # Check that it's roughly rectangular (aspect ratio ~1.4 for Pokemon cards)
            rect = cv2.minAreaRect(contour)
            w, h = rect[1]
            if w == 0 or h == 0:
                continue
            aspect = max(w, h) / min(w, h)
            if 1.1 < aspect < 2.0:  # Pokemon cards are ~1.4 aspect ratio
                return approx.reshape(4, 2)

    # Fallback: use the minimum area rectangle of the largest valid contour
    for contour in contour_candidates[:5]:
        area = cv2.contourArea(contour)
        if area < img_area * 0.10:
            continue
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        w, h = rect[1]
        if w == 0 or h == 0:
            continue
        aspect = max(w, h) / min(w, h)
        if 1.1 < aspect < 2.0:
            return box.astype(np.float32)

    return None


def measure_borders(warped_card):
    """
    Detect the inner border (where artwork/holo pattern meets the yellow/colored border)
    and measure the 4 border widths.

    Returns dict with border measurements or None if detection fails.
    """
    h, w = warped_card.shape[:2]

    if h < 100 or w < 100:
        return None

    gray = cv2.cvtColor(warped_card, cv2.COLOR_BGR2GRAY)

    # Use edge detection on the warped card to find the inner frame
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)

    # Look for the inner rectangle by scanning from each edge inward
    # We sample multiple horizontal/vertical lines and take the median transition point

    def find_border_width(scan_lines, axis='horizontal'):
        """
        Given scan lines (1D arrays from edge inward), find where the border ends.
        Returns median border width in pixels.
        """
        widths = []
        for line in scan_lines:
            # Find first significant edge (gradient spike) after at least 3% into the card
            min_border = max(3, int(len(line) * 0.03))
            max_border = int(len(line) * 0.20)  # Border shouldn't be more than 20% of card

            # Look for a strong gradient change
            gradient = np.abs(np.diff(line.astype(np.float64)))
            # Smooth the gradient slightly
            if len(gradient) > 5:
                kernel = np.ones(3) / 3
                gradient = np.convolve(gradient, kernel, mode='same')

            for i in range(min_border, min(max_border, len(gradient))):
                if gradient[i] > 15:  # threshold for edge detection
                    widths.append(i)
                    break

        if len(widths) < 3:
            return None
        # Use median to be robust against outliers
        return int(np.median(widths))

    # Sample scan lines from left edge (for left border)
    sample_positions = np.linspace(int(h * 0.25), int(h * 0.75), 20).astype(int)
    left_lines = [edges[y, :w // 2] for y in sample_positions]
    right_lines = [edges[y, w // 2:][::-1] for y in sample_positions]  # reversed

    sample_positions_h = np.linspace(int(w * 0.25), int(w * 0.75), 20).astype(int)
    top_lines = [edges[:h // 2, x] for x in sample_positions_h]
    bottom_lines = [edges[h // 2:, x][::-1] for x in sample_positions_h]  # reversed

    left_w = find_border_width(left_lines)
    right_w = find_border_width(right_lines)
    top_w = find_border_width(top_lines)
    bottom_w = find_border_width(bottom_lines)

    if any(v is None for v in [left_w, right_w, top_w, bottom_w]):
        return None

    return {
        "left_px": left_w,
        "right_px": right_w,
        "top_px": top_w,
        "bottom_px": bottom_w,
        "card_width": w,
        "card_height": h
    }


def compute_centering_ratios(borders):
    """
    Convert pixel border measurements to PSA-style centering ratios.
    Returns dict like {"lr": "52/48", "tb": "55/45", "lr_ratio": 52.0, "tb_ratio": 55.0}
    """
    if borders is None:
        return None

    lr_total = borders["left_px"] + borders["right_px"]
    tb_total = borders["top_px"] + borders["bottom_px"]

    if lr_total == 0 or tb_total == 0:
        return None

    left_pct = (borders["left_px"] / lr_total) * 100
    top_pct = (borders["top_px"] / tb_total) * 100

    # Normalize to the larger/smaller format (e.g., 55/45)
    lr_larger = max(left_pct, 100 - left_pct)
    lr_smaller = 100 - lr_larger
    tb_larger = max(top_pct, 100 - top_pct)
    tb_smaller = 100 - tb_larger

    return {
        "lr": f"{lr_larger:.0f}/{lr_smaller:.0f}",
        "tb": f"{tb_larger:.0f}/{tb_smaller:.0f}",
        "lr_ratio": round(lr_larger, 1),
        "tb_ratio": round(tb_larger, 1),
        "left_px": borders["left_px"],
        "right_px": borders["right_px"],
        "top_px": borders["top_px"],
        "bottom_px": borders["bottom_px"],
    }


def centering_grade_hint(ratios):
    """
    Based on measured centering, return a PSA-grade hint string.
    PSA 10: 60/40 or better on front
    PSA 9:  65/35 or better
    PSA 8:  70/30 or better
    """
    if ratios is None:
        return None

    worst = max(ratios["lr_ratio"], ratios["tb_ratio"])

    if worst <= 55:
        return "excellent (well within PSA 10 tolerances)"
    elif worst <= 60:
        return "good (within PSA 10 tolerances, but tight)"
    elif worst <= 65:
        return "acceptable (PSA 9 range — centering alone likely prevents a 10)"
    elif worst <= 70:
        return "below average (PSA 8 range due to centering)"
    else:
        return "poor (centering may limit grade to PSA 7 or below)"


def analyze_centering(image_bytes: bytes) -> dict:
    """
    Main entry point. Takes raw image bytes, returns centering analysis.

    Returns dict with keys:
        - success: bool
        - ratios: centering ratio dict or None
        - grade_hint: string description or None
        - prompt_injection: string to inject into Gemini prompt
        - error: error message if failed
    """
    try:
        # Decode image
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return {
                "success": False,
                "error": "Could not decode image",
                "prompt_injection": "Centering measurement failed — assess centering visually."
            }

        # Resize if too large (speeds up processing, reduces noise)
        max_dim = 1500
        h, w = image.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            image = cv2.resize(image, None, fx=scale, fy=scale)

        # Step 1: Find the card
        card_contour = find_card_contour(image)
        if card_contour is None:
            return {
                "success": False,
                "error": "Could not detect card edges",
                "prompt_injection": "Centering measurement failed (card edges not detected) — assess centering visually but note measurement was attempted."
            }

        # Step 2: Perspective-correct the card
        warped = four_point_transform(image, card_contour)

        # Ensure card is in portrait orientation (taller than wide)
        wh, ww = warped.shape[:2]
        if ww > wh:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

        # Step 3: Measure borders
        borders = measure_borders(warped)
        if borders is None:
            return {
                "success": False,
                "error": "Could not measure inner borders",
                "prompt_injection": "Centering measurement partially failed (card detected but inner border unclear) — assess centering visually."
            }

        # Step 4: Compute ratios
        ratios = compute_centering_ratios(borders)
        if ratios is None:
            return {
                "success": False,
                "error": "Could not compute ratios",
                "prompt_injection": "Centering measurement failed at ratio computation — assess centering visually."
            }

        grade_hint = centering_grade_hint(ratios)

        prompt_text = (
            f"CENTERING MEASUREMENT (computed via image analysis — use as primary centering data):\n"
            f"  Left/Right: {ratios['lr']} ({ratios['left_px']}px / {ratios['right_px']}px)\n"
            f"  Top/Bottom: {ratios['tb']} ({ratios['top_px']}px / {ratios['bottom_px']}px)\n"
            f"  Assessment: Centering is {grade_hint}\n"
            f"  NOTE: These measurements are from the FRONT of the card only. "
            f"If the image shows glare, a sleeve, or an angled shot, measurements may have minor error — "
            f"use your visual judgment to confirm or adjust slightly."
        )

        return {
            "success": True,
            "ratios": ratios,
            "grade_hint": grade_hint,
            "prompt_injection": prompt_text,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "prompt_injection": f"Centering measurement encountered an error ({str(e)}) — assess centering visually."
        }
