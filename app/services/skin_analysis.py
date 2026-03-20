"""피부 상태 분석 서비스

CNN 모델(MobileNetV2) + OpenCV + MediaPipe 기반 피부 상태 진단

[개선사항 - 2026-03-20]
1. MediaPipe 피부 영역을 점수 계산에도 사용 (기존: CNN에만 사용)
2. HSV 기반 피부색 마스킹 — 머리카락/눈/배경 픽셀 제외
3. LAB 색공간 활용 — 밝기(L채널), 균일도, 붉은기(a채널)에 더 적합
4. 균일도 계수 재조정 (1.5 → 0.8) — 0점 문제 해결
5. Gray World 조명 보정 — 형광등/자연광 등 조명 환경 차이 제거
6. CNN 확신도 기반 가중 평균 — 확신도 50% 미만 시 CNN+OpenCV 블렌딩
7. CNN 진단 결과 내부 로그 전환 — 사용자에게 기술 수치 미노출
"""

import os
from io import BytesIO

import cv2
import mediapipe as mp
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageFilter
from torchvision import models, transforms


class SkinCNN(nn.Module):
    """MobileNetV2 기반 피부 상태 분류 모델"""
    def __init__(self, num_classes=3):
        super().__init__()
        self.model = models.mobilenet_v2(weights=None)
        self.model.classifier[1] = nn.Linear(1280, num_classes)

    def forward(self, x):
        return self.model(x)


class SkinAnalyzer:
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = SkinCNN(num_classes=3)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, "models", "skin_model.pth")

        self.model_loaded = False
        if os.path.exists(model_path):
            state_dict = torch.load(model_path, map_location=self.device, weights_only=True)
            first_key = next(iter(state_dict))
            if not first_key.startswith("model."):
                state_dict = {f"model.{k}": v for k, v in state_dict.items()}
            self.model.load_state_dict(state_dict)
            self.model_loaded = True

        self.model.eval()
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        self.trouble_labels = ["심함", "약간", "없음"]

        self.mp_face_mesh = None
        self.face_mesh = None
        try:
            if hasattr(mp, "solutions"):
                self.mp_face_mesh = mp.solutions.face_mesh
                self.face_mesh = self.mp_face_mesh.FaceMesh(
                    static_image_mode=True, max_num_faces=1, refine_landmarks=False
                )
        except Exception as e:
            print("MediaPipe FaceMesh initialization failed:", e)

    def extract_skin_region_mp(self, frame_bgr, landmarks):
        """MediaPipe 랜드마크로 볼 영역 크롭"""
        h, w, _ = frame_bgr.shape
        cheek_indices = [50, 101, 116, 117, 118, 119, 280, 330, 345, 346, 347, 348]
        points = []
        for idx in cheek_indices:
            if idx >= len(landmarks):
                continue
            lm = landmarks[idx]
            points.append((int(lm.x * w), int(lm.y * h)))

        if not points:
            return None

        points = np.array(points)
        x_min, y_min = points.min(axis=0)
        x_max, y_max = points.max(axis=0)

        pad = 20
        x_min = max(0, x_min - pad)
        y_min = max(0, y_min - pad)
        x_max = min(w, x_max + pad)
        y_max = min(h, y_max + pad)

        return frame_bgr[y_min:y_max, x_min:x_max]

    # ================================================================
    # [개선] Gray World 조명 보정 — 조명 색온도 차이 제거
    # ================================================================
    @staticmethod
    def _gray_world_correction(frame_bgr):
        """Gray World 가정 기반 화이트밸런스 보정

        형광등(노란빛), 자연광(파란빛) 등 조명 환경에 따른
        색온도 편향을 제거하여 일관된 분석 결과를 보장합니다.

        안전장치: 보정 계수가 너무 크면(0.5~2.0 범위 초과) 원본 유지
        """
        b, g, r = cv2.split(frame_bgr.astype(np.float64))
        avg_b, avg_g, avg_r = b.mean(), g.mean(), r.mean()
        avg_all = (avg_b + avg_g + avg_r) / 3

        # 보정 계수 계산
        if avg_b == 0 or avg_g == 0 or avg_r == 0:
            return frame_bgr

        scale_b = avg_all / avg_b
        scale_g = avg_all / avg_g
        scale_r = avg_all / avg_r

        # 안전장치: 보정 계수가 비정상적이면 원본 유지
        for s in [scale_b, scale_g, scale_r]:
            if s < 0.5 or s > 2.0:
                return frame_bgr

        b = np.clip(b * scale_b, 0, 255)
        g = np.clip(g * scale_g, 0, 255)
        r = np.clip(r * scale_r, 0, 255)

        return cv2.merge([b, g, r]).astype(np.uint8)

    # ================================================================
    # [개선] HSV 기반 피부색 마스킹 — 비피부 픽셀 제거
    # ================================================================
    @staticmethod
    def _extract_skin_pixels(region_bgr):
        """HSV 색공간에서 피부색 범위에 해당하는 픽셀만 추출

        피부색 HSV 범위: H(0~25), S(30~170), V(60~255)
        머리카락, 눈동자, 배경 등 비피부 픽셀이 제거됩니다.
        """
        hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
        # 피부색 범위 (아시아인 기준으로 조정)
        lower_skin = np.array([0, 30, 60], dtype=np.uint8)
        upper_skin = np.array([25, 170, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_skin, upper_skin)

        # 마스크에 해당하는 RGB 픽셀만 추출
        rgb_region = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2RGB)
        skin_pixels = rgb_region[mask > 0]

        # 피부 픽셀이 너무 적으면 (전체의 10% 미만) 마스킹 없이 전체 사용
        total_pixels = region_bgr.shape[0] * region_bgr.shape[1]
        if len(skin_pixels) < total_pixels * 0.1:
            return rgb_region.reshape(-1, 3).astype(float), mask

        return skin_pixels.astype(float), mask

    def analyze(self, image_bytes: bytes) -> dict:
        try:
            # 1) 이미지 로드
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            img = img.resize((300, 300))
            w, h = img.size

            # OpenCV용 프레임 준비
            frame_rgb = np.array(img)
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            # [개선] Gray World 조명 보정 적용 — 조명 환경 차이 제거
            frame_bgr = self._gray_world_correction(frame_bgr)

            # 2) MediaPipe 얼굴 랜드마크 → 볼 영역 크롭
            skin_region_bgr = None
            if self.face_mesh:
                results = self.face_mesh.process(frame_rgb)
                if results.multi_face_landmarks:
                    face_landmarks = results.multi_face_landmarks[0]
                    skin_region_bgr = self.extract_skin_region_mp(frame_bgr, face_landmarks.landmark)

            # fallback: 중앙 영역 크롭
            if skin_region_bgr is None or skin_region_bgr.size == 0:
                x_min, y_min = int(w * 0.2), int(h * 0.15)
                x_max, y_max = int(w * 0.8), int(h * 0.75)
                skin_region_bgr = frame_bgr[y_min:y_max, x_min:x_max]

            # ── CNN 트러블 판별 ──
            cnn_trouble_confidence = None
            cnn_trouble_label = None
            if self.model_loaded and skin_region_bgr is not None and skin_region_bgr.size > 0:
                rgb_region = cv2.cvtColor(skin_region_bgr, cv2.COLOR_BGR2RGB)
                tensor = self.transform(rgb_region).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    output = self.model(tensor)
                    prob = torch.softmax(output, dim=1)
                    pred = torch.argmax(prob, dim=1).item()
                    cnn_trouble_confidence = prob[0][pred].item()
                    cnn_trouble_label = self.trouble_labels[pred]

            # ================================================================
            # [개선] 피부 영역 픽셀로 점수 계산 (기존: fallback 영역 고정)
            # ================================================================
            skin_pixels, skin_mask = self._extract_skin_pixels(skin_region_bgr)

            # [개선] LAB 색공간 변환 — 밝기/균일도 분석에 더 적합
            lab_region = cv2.cvtColor(skin_region_bgr, cv2.COLOR_BGR2LAB)
            lab_skin = lab_region[skin_mask > 0] if skin_mask.any() else lab_region.reshape(-1, 3)
            lab_skin = lab_skin.astype(float)

            # 피부결 분석용 그레이스케일 (피부 영역 기준)
            gray_region = cv2.cvtColor(skin_region_bgr, cv2.COLOR_BGR2GRAY)

            # ── 점수 산출 ──

            # (1) 밝기 — [개선] LAB L채널 사용 (0~255 스케일)
            l_mean = lab_skin[:, 0].mean()  # L채널 평균
            brightness_score = self._clamp(int(l_mean / 255 * 100 * 1.3))

            # (2) 균일도 — [개선] LAB L채널 std 사용 + 계수 완화 (1.5 → 0.8)
            l_std = lab_skin[:, 0].std()
            evenness_score = self._clamp(int(100 - l_std * 0.8))

            # (3) 붉은기 (트러블) — CNN 결과 우선, OpenCV 폴백
            # [개선] LAB a채널로 붉은기 측정 (a > 128이면 붉은 쪽)
            a_mean = lab_skin[:, 1].mean()
            redness_ratio = max(0, (a_mean - 128)) / 127 * 100
            fallback_redness_score = self._clamp(int(100 - redness_ratio * 2.5))

            # [개선] CNN 확신도 기반 가중 평균 블렌딩
            # 확신도 50% 이상 → CNN 결과 신뢰, 미만 → CNN+OpenCV 가중 평균
            redness_score = fallback_redness_score
            if cnn_trouble_label is not None:
                cnn_score_map = {"심함": 30, "약간": 60, "없음": 90}
                cnn_redness = cnn_score_map[cnn_trouble_label]
                conf = cnn_trouble_confidence or 0

                if conf >= 0.5:
                    # 확신도 높음 → CNN 결과 그대로
                    redness_score = cnn_redness
                else:
                    # 확신도 낮음 → CNN 비율만큼만 반영, 나머지는 OpenCV
                    cnn_weight = conf  # 예: 0.36이면 CNN 36%, OpenCV 64%
                    redness_score = self._clamp(int(
                        cnn_redness * cnn_weight + fallback_redness_score * (1 - cnn_weight)
                    ))

            # (4) 피부결 — [개선] 피부 영역의 라플라시안 분산 사용
            laplacian = cv2.Laplacian(gray_region, cv2.CV_64F)
            texture_var = laplacian.var()
            # 분산이 낮을수록 매끄러움 (범위 대략 0~2000)
            texture_score = self._clamp(int(100 - texture_var * 0.05))

            # (5) 수분도 추정 — 다른 점수 조합
            moisture_score = self._clamp(int(
                evenness_score * 0.5
                + brightness_score * 0.3
                + texture_score * 0.2
            ))

            # (6) 유분 균형 — [개선] 피부 픽셀 기준 하이라이트 비율
            highlight_ratio = (skin_pixels > 200).mean() * 100
            oiliness_score = self._clamp(int(100 - highlight_ratio * 2))

            overall_score = int(
                brightness_score * 0.15
                + evenness_score * 0.25
                + redness_score * 0.20
                + texture_score * 0.20
                + moisture_score * 0.10
                + oiliness_score * 0.10
            )

            conditions = {
                "brightness": self._build_item("피부 밝기", brightness_score, self._brightness_detail),
                "evenness": self._build_item("피부 균일도", evenness_score, self._evenness_detail),
                "redness": self._build_item("트러블/붉은기", redness_score, self._redness_detail),
                "texture": self._build_item("피부결", texture_score, self._texture_detail),
                "moisture": self._build_item("수분도", moisture_score, self._moisture_detail),
                "oiliness": self._build_item("유분 균형", oiliness_score, self._oiliness_detail),
            }

            skin_type = self._determine_skin_type(conditions)
            recommendations = self._generate_recommendations(conditions)

            analysis_method = "deep_learning_api" if cnn_trouble_label else "basic_image_analysis"

            # [개선] CNN 결과는 내부 로그용으로만 기록, 사용자에게는 자연스러운 멘트만 노출
            if cnn_trouble_label:
                print(f"[CNN] 트러블 진단: {cnn_trouble_label} (확신도 {cnn_trouble_confidence*100:.1f}%)")

            return {
                "success": True,
                "overall_score": overall_score,
                "skin_type": skin_type,
                "conditions": conditions,
                "recommendations": recommendations,
                "analysis_method": analysis_method,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"피부 상태 분석 중 오류가 발생했습니다: {e}",
            }


    # ------------------------------------------------------------------ #
    #  내부 헬퍼                                                          #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
        return max(lo, min(hi, v))

    def _build_item(self, label, score, detail_fn):
        return {
            "label": label,
            "score": score,
            "status": self._status(score),
            "detail": detail_fn(score),
        }

    @staticmethod
    def _status(score):
        if score >= 80:
            return "excellent"
        if score >= 60:
            return "good"
        if score >= 40:
            return "average"
        return "needs_attention"

    # ── 상세 설명 ──────────────────────────────────────────────────── #
    @staticmethod
    def _brightness_detail(s):
        if s >= 70:
            return "피부가 전체적으로 밝고 화사한 상태입니다. 현재 스킨케어를 잘 유지하고 계세요."
        if s >= 50:
            return "피부 밝기가 보통 수준입니다. 비타민C 세럼이나 나이아신아마이드 제품으로 톤업 관리를 추천합니다."
        return "피부 톤이 다소 어두운 편입니다. 자외선 차단과 미백 기능성 제품 사용을 고려해보세요."

    @staticmethod
    def _evenness_detail(s):
        if s >= 70:
            return "피부톤이 균일하고 고르게 유지되고 있습니다."
        if s >= 50:
            return "부분적으로 색소 침착이나 톤 차이가 관찰됩니다. 꾸준한 각질 관리가 도움이 됩니다."
        return "피부톤의 편차가 큰 편입니다. 색소 침착 개선을 위한 전문 관리를 권장합니다."

    @staticmethod
    def _redness_detail(s):
        if s >= 70:
            return "붉은기 및 트러블이 적어 건강한 상태입니다."
        if s >= 50:
            return "약간의 트러블/붉은기가 감지됩니다. 진정 효과가 있는 시카(CICA) 제품이 도움이 될 수 있습니다."
        return "트러블 또는 붉은기가 다소 강한 편입니다. 민감성 피부 전용 제품과 집중 진정 케어를 추천합니다."

    @staticmethod
    def _texture_detail(s):
        if s >= 70:
            return "피부결이 매끄럽고 건강한 상태입니다."
        if s >= 50:
            return "약간의 피부결 불균형이 있습니다. 부드러운 각질 제거와 보습 관리를 추천합니다."
        return "피부결이 거친 편입니다. AHA/BHA 제품으로 부드러운 각질 관리를 시작해보세요."

    @staticmethod
    def _moisture_detail(s):
        if s >= 70:
            return "피부 수분 상태가 양호합니다. 보습 관리를 잘 하고 계시네요."
        if s >= 50:
            return "수분감이 보통 수준입니다. 히알루론산이 함유된 보습제로 수분을 보충해주세요."
        return "피부가 건조한 상태로 보입니다. 속보습 제품과 수분크림으로 집중 보습을 추천합니다."

    @staticmethod
    def _oiliness_detail(s):
        if s >= 70:
            return "유수분 밸런스가 잘 유지되고 있습니다."
        if s >= 50:
            return "약간의 유분기가 감지됩니다. 가벼운 수분 제품으로 밸런스를 맞춰주세요."
        return "유분기가 많은 편입니다. 논코메도제닉 제품과 가벼운 수분 케어를 추천합니다."

    # ── 피부 타입 판별 ─────────────────────────────────────────────── #
    @staticmethod
    def _determine_skin_type(cond):
        moisture = cond["moisture"]["score"]
        oiliness = cond["oiliness"]["score"]
        redness = cond["redness"]["score"]

        if redness < 50:
            return {"name": "민감성 피부", "emoji": "🌿",
                    "description": "외부 자극에 민감하게 반응하는 피부 타입입니다."}
        if oiliness < 50:
            return {"name": "지성 피부", "emoji": "💧",
                    "description": "피지 분비가 활발한 피부 타입입니다."}
        if moisture < 50:
            return {"name": "건성 피부", "emoji": "🏜️",
                    "description": "수분이 부족하여 건조해지기 쉬운 피부 타입입니다."}
        if oiliness < 65 and moisture < 65:
            return {"name": "복합성 피부", "emoji": "⚖️",
                    "description": "T존은 유분기가 많고 U존은 건조한 피부 타입입니다."}
        return {"name": "중성 피부", "emoji": "✨",
                "description": "유수분 밸런스가 잘 잡혀 있는 건강한 피부 타입입니다."}

    # ── 스킨케어 추천 ──────────────────────────────────────────────── #
    @staticmethod
    def _generate_recommendations(cond):
        recs = []

        if cond["moisture"]["score"] < 60:
            recs.append({
                "category": "보습", "icon": "💧",
                "tip": "히알루론산, 세라마이드 성분의 보습 제품을 아침저녁으로 사용해주세요.",
            })
        if cond["redness"]["score"] < 60:
            recs.append({
                "category": "진정", "icon": "🌿",
                "tip": "시카(CICA), 판테놀 성분의 진정 제품으로 피부 장벽을 강화해주세요.",
            })
        if cond["brightness"]["score"] < 60:
            recs.append({
                "category": "톤업", "icon": "✨",
                "tip": "비타민C 세럼과 자외선 차단제를 꾸준히 사용하면 피부톤 개선에 도움이 됩니다.",
            })
        if cond["texture"]["score"] < 60:
            recs.append({
                "category": "각질 관리", "icon": "🧴",
                "tip": "주 1-2회 부드러운 AHA/BHA 각질 제거제를 사용해 피부결을 개선해보세요.",
            })
        if cond["oiliness"]["score"] < 60:
            recs.append({
                "category": "유분 조절", "icon": "🍃",
                "tip": "논코메도제닉 제품을 선택하고, 클레이 마스크로 주기적 모공 관리를 해주세요.",
            })

        if not recs:
            recs.append({
                "category": "유지 관리", "icon": "💎",
                "tip": "현재 피부 상태가 좋습니다! 기존 스킨케어 루틴을 꾸준히 유지해주세요.",
            })

        recs.append({
            "category": "자외선 차단", "icon": "☀️",
            "tip": "SPF 50+ PA++++ 자외선 차단제를 매일 사용하는 것이 모든 피부 관리의 기본입니다.",
        })
        return recs
