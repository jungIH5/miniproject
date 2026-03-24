"""퍼스널컬러 분석 서비스

이미지에서 피부 톤을 추출하고 퍼스널컬러 시즌(봄/여름/가을/겨울)을 분류합니다.

[개선사항 - 2026-03-20]
1. MediaPipe 볼 영역 샘플링 (기존: 중앙 영역 고정 크롭)
2. Gray World 조명 보정 적용
3. LAB 색공간 기반 언더톤 판별 (a값+b값 종합)
4. HSV 피부색 마스킹 — 비피부 픽셀 제외
5. 이상치 제거 (상하 10% 트리밍)
6. OpenCV Cascade 얼굴 감지 검증 — 얼굴 없는 사진 분석 차단
7. fallback 개선 — MediaPipe 실패 시 Cascade 감지 영역 사용
"""

from io import BytesIO

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image


class PersonalColorAnalyzer:

    SEASONS = {
        "spring_warm": {
            "name": "봄 웜톤",
            "emoji": "🌸",
            "subtitle": "밝고 화사한 봄의 따뜻함",
            "description": (
                "따뜻하고 밝은 톤이 특징인 봄 웜톤은 "
                "살구색, 코랄, 아이보리처럼 부드럽고 화사한 색상이 잘 어울립니다. "
                "피부가 맑고 투명한 느낌을 줄 때 가장 빛나는 타입입니다."
            ),
            "best_colors": [
                "코랄 핑크", "살구색", "아이보리",
                "워밍 골드", "라이트 오렌지", "피치",
            ],
            "worst_colors": ["블랙", "다크 네이비", "차가운 회색", "버건디"],
            "worst_color_codes": ["#1a1a1a", "#1b2540", "#8e9aaf", "#800020"],
            "color_codes": [
                "#FF7F7F", "#FFDAB9", "#FFFFF0",
                "#FFD700", "#FFA07A", "#FFCBA4",
            ],
            "makeup_tip": (
                "코랄, 피치 계열의 블러셔와 립을 활용하면 "
                "혈색 있고 생기 넘치는 메이크업이 완성됩니다."
            ),
            "fashion_tip": (
                "밝은 베이지, 크림색 등 따뜻한 라이트 톤의 의상이 "
                "얼굴을 환하게 밝혀줍니다."
            ),
        },
        "summer_cool": {
            "name": "여름 쿨톤",
            "emoji": "🌊",
            "subtitle": "부드럽고 우아한 여름의 시원함",
            "description": (
                "차갑고 부드러운 톤이 특징인 여름 쿨톤은 "
                "라벤더, 로즈핑크, 스카이블루처럼 쿨하면서도 경쾌한 색상이 잘 어울립니다. "
                "은은하고 우아한 분위기를 연출할 때 가장 매력적인 타입입니다."
            ),
            "best_colors": [
                "라벤더", "로즈 핑크", "스카이 블루",
                "소프트 화이트", "라일락", "베이비 핑크",
            ],
            "worst_colors": ["오렌지", "머스타드", "카키", "다크 브라운"],
            "worst_color_codes": ["#FF8C00", "#E1AD01", "#6B6B3D", "#3E2723"],
            "color_codes": [
                "#B57EDC", "#FF007F", "#87CEEB",
                "#F5F5F5", "#C8A2C8", "#FFB6C1",
            ],
            "makeup_tip": (
                "로즈, 핑크 계열의 립과 블러셔로 "
                "자연스럽고 우아한 메이크업을 연출해보세요."
            ),
            "fashion_tip": (
                "파스텔 톤의 블루, 핑크, 라벤더 의상이 "
                "피부를 맑고 깨끗하게 보이게 합니다."
            ),
        },
        "autumn_warm": {
            "name": "가을 웜톤",
            "emoji": "🍂",
            "subtitle": "깊고 풍성한 가을의 따뜻함",
            "description": (
                "따뜻하고 깊은 톤이 특징인 가을 웜톤은 "
                "테라코타, 올리브, 머스타드처럼 자연에서 온 풍성한 색상이 잘 어울립니다. "
                "고급스럽고 세련된 분위기를 연출할 때 가장 돋보이는 타입입니다."
            ),
            "best_colors": [
                "테라코타", "올리브 그린", "머스타드",
                "버건디", "카멜", "브라운",
            ],
            "worst_colors": ["파스텔 핑크", "네온 컬러", "차가운 회색", "로얄 블루"],
            "worst_color_codes": ["#FFB6C1", "#39FF14", "#8e9aaf", "#4169E1"],
            "color_codes": [
                "#CC4E3C", "#808000", "#FFDB58",
                "#800020", "#C19A6B", "#8B4513",
            ],
            "makeup_tip": (
                "브라운, 테라코타 계열의 아이섀도우와 브릭 레드 립으로 "
                "깊이감 있는 메이크업을 완성하세요."
            ),
            "fashion_tip": (
                "카키, 올리브, 브라운 등 어스 톤 의상이 "
                "고급스럽고 세련된 분위기를 연출합니다."
            ),
        },
        "winter_cool": {
            "name": "겨울 쿨톤",
            "emoji": "❄️",
            "subtitle": "선명하고 강렬한 겨울의 시원함",
            "description": (
                "차갑고 선명한 톤이 특징인 겨울 쿨톤은 "
                "블랙, 화이트, 레드, 로얄 블루처럼 강렬하고 대비가 뚜렷한 색상이 잘 어울립니다. "
                "시크하고 모던한 분위기를 연출할 때 가장 매력적인 타입입니다."
            ),
            "best_colors": [
                "퓨어 화이트", "블랙", "로얄 블루",
                "와인 레드", "에메랄드", "핫 핑크",
            ],
            "worst_colors": ["베이지", "살구색", "카키", "머스타드"],
            "worst_color_codes": ["#D2B48C", "#FFDAB9", "#6B6B3D", "#E1AD01"],
            "color_codes": [
                "#FFFFFF", "#000000", "#4169E1",
                "#722F37", "#50C878", "#FF69B4",
            ],
            "makeup_tip": (
                "레드, 와인 계열의 립과 블랙 아이라인으로 "
                "시크하고 강렬한 메이크업이 잘 어울립니다."
            ),
            "fashion_tip": (
                "블랙 & 화이트 대비, 선명한 컬러의 의상이 "
                "세련되고 모던한 이미지를 만들어줍니다."
            ),
        },
    }

    # ------------------------------------------------------------------ #
    #  공개 API                                                           #
    # ------------------------------------------------------------------ #
    def __init__(self):
        # [개선] MediaPipe FaceMesh 초기화 — 볼 영역 정밀 샘플링
        self.face_mesh = None
        try:
            if hasattr(mp, "solutions"):
                self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True, max_num_faces=1, refine_landmarks=False
                )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # [개선] Gray World 조명 보정
    # ------------------------------------------------------------------ #
    @staticmethod
    def _gray_world(frame_bgr):
        b, g, r = cv2.split(frame_bgr.astype(np.float64))
        avg_b, avg_g, avg_r = b.mean(), g.mean(), r.mean()
        avg_all = (avg_b + avg_g + avg_r) / 3
        if avg_b == 0 or avg_g == 0 or avg_r == 0:
            return frame_bgr
        sb, sg, sr = avg_all / avg_b, avg_all / avg_g, avg_all / avg_r
        for s in [sb, sg, sr]:
            if s < 0.5 or s > 2.0:
                return frame_bgr
        return cv2.merge([
            np.clip(b * sb, 0, 255),
            np.clip(g * sg, 0, 255),
            np.clip(r * sr, 0, 255),
        ]).astype(np.uint8)

    # ------------------------------------------------------------------ #
    # [개선] MediaPipe 볼 영역 추출
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_cheek_pixels(frame_bgr, landmarks):
        """양쪽 볼 영역에서 피부 픽셀 샘플링 (11x11 패치)"""
        h, w, _ = frame_bgr.shape
        # 왼쪽 볼, 오른쪽 볼 랜드마크
        cheek_indices = [50, 101, 116, 117, 118, 119, 280, 330, 345, 346, 347, 348]
        samples = []
        patch_size = 5  # 11x11 패치 (중심 ± 5)

        for idx in cheek_indices:
            if idx >= len(landmarks):
                continue
            lm = landmarks[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            y1 = max(0, cy - patch_size)
            y2 = min(h, cy + patch_size + 1)
            x1 = max(0, cx - patch_size)
            x2 = min(w, cx + patch_size + 1)
            patch = frame_bgr[y1:y2, x1:x2]
            if patch.size > 0:
                samples.append(patch.reshape(-1, 3))

        if not samples:
            return None
        return np.vstack(samples)

    # ------------------------------------------------------------------ #
    # [개선] HSV 피부색 필터링 + 이상치 제거
    # ------------------------------------------------------------------ #
    @staticmethod
    def _filter_skin_pixels(pixels_bgr):
        """HSV 마스킹으로 피부색만 추출 + 상하 10% 트리밍"""
        if len(pixels_bgr) < 10:
            return pixels_bgr.astype(float)

        # HSV 변환 (1xN 이미지로 변환)
        pixels_3d = pixels_bgr.reshape(1, -1, 3).astype(np.uint8)
        hsv = cv2.cvtColor(pixels_3d, cv2.COLOR_BGR2HSV).reshape(-1, 3)

        # 피부색 범위
        mask = (hsv[:, 0] <= 25) & (hsv[:, 1] >= 30) & (hsv[:, 1] <= 170) & (hsv[:, 2] >= 60)
        skin = pixels_bgr[mask]

        if len(skin) < 10:
            skin = pixels_bgr

        # 이상치 제거: 밝기 기준 상하 10% 트리밍
        brightness = skin.astype(float).mean(axis=1)
        low = np.percentile(brightness, 10)
        high = np.percentile(brightness, 90)
        trimmed = skin[(brightness >= low) & (brightness <= high)]

        return trimmed.astype(float) if len(trimmed) > 10 else skin.astype(float)

    # ------------------------------------------------------------------ #
    #  공개 API
    # ------------------------------------------------------------------ #
    def analyze(self, image_bytes: bytes) -> dict:
        """이미지를 분석하여 퍼스널컬러 결과를 반환합니다."""
        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            img = img.resize((300, 300))
            w, h = img.size
            frame_rgb = np.array(img)
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            # [개선] 조명 보정 적용
            frame_bgr = self._gray_world(frame_bgr)

            # [개선] 얼굴 감지 검증 — 허공/배경 사진 차단 (Docker 호환)
            gray_check = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray_check, 1.3, 5)
            if len(faces) == 0:
                return {
                    "success": False,
                    "error": "얼굴을 인식하지 못했습니다. 얼굴이 잘 보이는 정면 사진으로 다시 시도해주세요.",
                    "face_detected": False,
                }

            # [개선] MediaPipe 볼 영역 샘플링 (기존: 중앙 영역 고정 크롭)
            skin_pixels_bgr = None
            if self.face_mesh:
                results = self.face_mesh.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
                if results.multi_face_landmarks:
                    skin_pixels_bgr = self._extract_cheek_pixels(
                        frame_bgr, results.multi_face_landmarks[0].landmark
                    )

            # fallback: MediaPipe 실패 시 Cascade 감지 영역 사용
            if skin_pixels_bgr is None or len(skin_pixels_bgr) < 10:
                fx, fy, fw, fh = faces[0]
                skin_pixels_bgr = frame_bgr[fy:fy+fh, fx:fx+fw].reshape(-1, 3)

            # [개선] HSV 마스킹 + 이상치 제거
            skin_filtered = self._filter_skin_pixels(skin_pixels_bgr)

            # [개선] LAB 색공간으로 변환 — 언더톤 판별에 더 정확
            skin_3d = skin_filtered.reshape(1, -1, 3).astype(np.uint8)
            lab_pixels = cv2.cvtColor(skin_3d, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(float)

            l_mean = lab_pixels[:, 0].mean()  # 밝기 (0~255)
            a_mean = lab_pixels[:, 1].mean()  # 붉은기-초록 축 (128 = 중립)
            b_mean = lab_pixels[:, 2].mean()  # 노란기-파란 축 (128 = 중립)

            # RGB 평균도 추출 (결과 표시용)
            rgb_pixels = cv2.cvtColor(skin_3d, cv2.COLOR_BGR2RGB).reshape(-1, 3).astype(float)
            avg_r, avg_g, avg_b = rgb_pixels.mean(axis=0)

            # HSV 채도 평균
            hsv_pixels = cv2.cvtColor(skin_3d, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float)
            sat_mean = hsv_pixels[:, 1].mean()

            # ── [개선] 언더톤 판별 (LAB a+b 종합, 한국인 보정) ──
            # a값: 128 이상 = 붉은 쪽 (쿨), 이하 = 초록 쪽 (웜은 아님)
            # b값: 128 이상 = 노란 쪽 (웜), 이하 = 파란 쪽 (쿨)
            a_offset = a_mean - 128  # 양수=붉은, 음수=초록
            b_offset = b_mean - 128  # 양수=노란, 음수=파란

            # 한국인 피부는 b값(황색)이 높은 경향 → 보정
            warmth_score = (b_offset * 1.2) - (a_offset * 0.8)
            is_warm = warmth_score > 3

            # ── 명도 판별 (LAB L채널) ──
            is_light = l_mean > 155

            # ── 채도 판별 (HSV S채널) ──
            is_bright = sat_mean > 40

            # ── 시즌 분류 ──
            if is_warm and is_light:
                season_key = "spring_warm"
            elif not is_warm and is_light:
                season_key = "summer_cool"
            elif is_warm and not is_light:
                season_key = "autumn_warm"
            else:
                season_key = "winter_cool"

            season = self.SEASONS[season_key]

            # ── 판단 근거 ──
            undertone_text = "따뜻한 (웜)" if is_warm else "차가운 (쿨)"
            depth_text = "밝은 (라이트)" if is_light else "깊은 (딥)"
            clarity_text = "선명한 (브라이트)" if is_bright else "부드러운 (뮤트)"

            reasoning = [
                {
                    "factor": "언더톤",
                    "value": undertone_text,
                    "detail": (
                        "피부의 황색기와 붉은기를 LAB 색공간에서 정밀 분석한 결과, "
                        + ("따뜻한 황색 기반의 웜 언더톤" if is_warm
                           else "차가운 청색 기반의 쿨 언더톤")
                        + "이 감지되었습니다."
                    ),
                },
                {
                    "factor": "명도",
                    "value": depth_text,
                    "detail": (
                        "피부의 전체적인 밝기를 측정한 결과, "
                        + ("밝고 환한 톤" if is_light else "깊고 차분한 톤")
                        + "으로 분류되었습니다."
                    ),
                },
                {
                    "factor": "채도",
                    "value": clarity_text,
                    "detail": (
                        "피부 색상의 선명도를 분석한 결과, "
                        + ("또렷하고 맑은 느낌" if is_bright
                           else "부드럽고 은은한 느낌")
                        + "의 피부톤입니다."
                    ),
                },
            ]

            return {
                "success": True,
                "season_key": season_key,
                "season": season["name"],
                "emoji": season["emoji"],
                "subtitle": season["subtitle"],
                "description": season["description"],
                "best_colors": season["best_colors"],
                "worst_colors": season["worst_colors"],
                "color_codes": season["color_codes"],
                "worst_color_codes": season["worst_color_codes"],
                "makeup_tip": season["makeup_tip"],
                "fashion_tip": season["fashion_tip"],
                "reasoning": reasoning,
                "skin_tone_rgb": [int(avg_r), int(avg_g), int(avg_b)],
                "analysis_method": "advanced_color_analysis",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"퍼스널컬러 분석 중 오류가 발생했습니다: {e}",
            }
