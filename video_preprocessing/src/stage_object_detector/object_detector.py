import onnxruntime
import cv2
import os
import sys
import numpy as np
from pathlib import Path

_STAGE_DIR = Path(__file__).parent


def _postprocess():
    """
    Lazy import of postprocess so its module-level default arg
    read_class_names("onnx/coco.names") is evaluated after CWD is set to _STAGE_DIR.
    """
    if "postprocess" not in sys.modules:
        if str(_STAGE_DIR) not in sys.path:
            sys.path.insert(0, str(_STAGE_DIR))
        import postprocess  # noqa: F401 — registers in sys.modules
    return sys.modules["postprocess"]


def post_processing(image_source, detections):
    pp = _postprocess()
    STRIDES = np.array([8, 16, 32])
    XYSCALE = [1.2, 1.1, 1.05]
    ANCHORS = pp.get_anchors()
    input_size = 416

    pred_bbox = pp.postprocess_bbbox(detections, ANCHORS, STRIDES, XYSCALE)
    bboxes = pp.postprocess_boxes(pred_bbox, (416, 416), input_size, 0.25)
    bboxes = pp.nms(bboxes, 0.213, method='nms')
    return pp.alternative_draw_bbox(image_source, bboxes)


def process_frame(image_path, onnx_model_path):
    image_source = cv2.imread(image_path)
    if image_source is None:
        print(f"  [WARNING] Could not read image: {image_path}, skipping.")
        return None

    image_resized = cv2.resize(image_source, (416, 416))
    img_in = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB).astype(np.float32)
    img_in = np.expand_dims(img_in, axis=0) / 255.0

    session = onnxruntime.InferenceSession(onnx_model_path)
    input_name = session.get_inputs()[0].name
    detections = session.run(None, {input_name: img_in})

    return post_processing(image_source, detections)


def main(shared_dir: str, video_name: str, onnx_file: str) -> None:
    input_video_dir = os.path.join(shared_dir, 'ffmpeg3out', video_name)
    output_video_dir = os.path.join(shared_dir, 'objectdetectorout', video_name)

    if not os.path.isdir(input_video_dir):
        raise FileNotFoundError(f"Input directory not found: {input_video_dir}")

    scene_dirs = sorted(os.listdir(input_video_dir))
    print(f"Found {len(scene_dirs)} scene(s) under '{input_video_dir}'")

    for scene_name in scene_dirs:
        scene_input_dir = os.path.join(input_video_dir, scene_name)
        if not os.path.isdir(scene_input_dir):
            continue

        scene_output_dir = os.path.join(output_video_dir, scene_name)
        os.makedirs(scene_output_dir, exist_ok=True)

        frame_files = sorted([
            f for f in os.listdir(scene_input_dir)
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ])

        print(f"  Scene '{scene_name}': {len(frame_files)} frame(s)")

        for frame_file in frame_files:
            frame_input_path = os.path.join(scene_input_dir, frame_file)
            frame_output_path = os.path.join(scene_output_dir, frame_file)

            print(f"    Processing: {frame_input_path}")
            result_image = process_frame(frame_input_path, onnx_file)
            if result_image is not None:
                cv2.imwrite(frame_output_path, result_image)
                print(f"    Saved:      {frame_output_path}")

    print("Done.")


def run(shared_dir: str, video_name: str) -> None:
    prev_cwd = os.getcwd()
    os.chdir(_STAGE_DIR)  # needed before _postprocess() loads onnx/coco.names
    try:
        main(shared_dir, video_name, str(_STAGE_DIR / "onnx" / "yolov4.onnx"))
    finally:
        os.chdir(prev_cwd)
