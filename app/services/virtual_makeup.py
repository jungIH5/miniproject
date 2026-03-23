import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import mediapipe as mp

class VirtualMakeup:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        
        # 메디아파이프 입술 인덱스 (입술 안쪽+바깥쪽 전체)
        self.LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
        self.LIPS_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]

    def apply_lipstick(self, image_bytes, color_hex="#FF0000", opacity=0.4):
        """
        입술 영역에 지정된 색상을 투명하게 합성합니다.
        """
        try:
            # 1. 이미지 로드
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None: return None
            
            h, w = img.shape[:2]
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # 2. 얼굴 랜드마크 감지
            results = self.face_mesh.process(rgb_img)
            if not results.multi_face_landmarks:
                return None
            
            landmarks = results.multi_face_landmarks[0].landmark
            
            # 3. 입술 좌표 추출 (픽셀 단위 변환)
            def get_pts(indices):
                return np.array([(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in indices], np.int32)
            
            outer_pts = get_pts(self.LIPS_OUTER)
            inner_pts = get_pts(self.LIPS_INNER)
            
            # 4. 입술 마스크 생성
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask, [outer_pts], 255)
            cv2.fillPoly(mask, [inner_pts], 0) # 입 안쪽(치아 등)은 제외
            
            # 가우시안 블러로 입술 테두리 부드럽게 (중요!)
            mask = cv2.GaussianBlur(mask, (7, 7), 0)
            
            # 5. 색상 합성
            # HEX to BGR
            color_hex = color_hex.lstrip('#')
            r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
            lipstick_color = np.full(img.shape, (b, g, r), dtype=np.uint8)
            
            # 알파 블렌딩 (원본의 질감을 살리기 위해 원본 이미지와 합성)
            # 입술 영역만 overlay 스타일로 합성
            img_head = img.copy()
            
            # mask를 0~1 사이로 정규화
            mask_3d = cv2.merge([mask, mask, mask]) / 255.0
            
            # 최종 합성 로직: 원본 * (1 - mask*opacity) + 입술색 * (mask*opacity)
            res = cv2.addWeighted(img, 1.0, lipstick_color, opacity, 0)
            
            # 마스크가 있는 영역만 결과물에서 가져오기
            final_img = (img * (1 - mask_3d * opacity) + lipstick_color * (mask_3d * opacity)).astype(np.uint8)
            
            # 6. 인코딩하여 반환
            _, buffer = cv2.imencode('.jpg', final_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return buffer.tobytes()
            
        except Exception as e:
            print(f"[VirtualMakeup Error] {e}")
            return None
