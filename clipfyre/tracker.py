from dataclasses import dataclass


@dataclass
class CropTracking:
    frame_width: int
    frame_height: int
    crop_width: int
    x_expression: str
    face_in_lower_third: bool


def track_faces(video_path, start, end, sample_rate=2, smoothing_window=5):
    try:
        import cv2
        from scipy.ndimage import uniform_filter1d
    except ImportError as error:
        raise RuntimeError(
            "Face tracking requires opencv-python-headless and scipy."
        ) from error

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("Could not open video for face tracking.")

    try:
        frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_width <= 0 or frame_height <= 0:
            raise RuntimeError("Video dimensions could not be read.")

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        if detector.empty():
            raise RuntimeError("OpenCV's face detection model could not be loaded.")

        crop_width = min(frame_width, round(frame_height * 9 / 16))
        if crop_width <= 0:
            raise RuntimeError("Video dimensions do not support a vertical crop.")

        interval = 1 / sample_rate
        sample_times = []
        centers = []
        previous_center = frame_width / 2
        face_in_lower_third = False
        timestamp = start

        while timestamp <= end:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if ok:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(max(24, frame_width // 30), max(24, frame_height // 30)),
                )
                if len(faces):
                    x, y, width, height = max(
                        faces, key=lambda face: face[2] * face[3]
                    )
                    previous_center = x + width / 2
                    face_in_lower_third |= y + height / 2 >= frame_height * 2 / 3
                sample_times.append(timestamp - start)
                centers.append(previous_center)
            timestamp += interval

        if not sample_times:
            raise RuntimeError("No video frames could be read for face tracking.")
        if sample_times[-1] < end - start:
            sample_times.append(end - start)
            centers.append(centers[-1])

        smoothed_centers = uniform_filter1d(
            centers, size=max(1, smoothing_window), mode="nearest"
        )
        crop_lefts = [
            min(
                max(0, center - crop_width / 2),
                frame_width - crop_width,
            )
            for center in smoothed_centers
        ]

        expression = f"{crop_lefts[-1]:.2f}"
        for index in range(len(sample_times) - 2, -1, -1):
            first_time = sample_times[index]
            second_time = sample_times[index + 1]
            duration = second_time - first_time
            if duration <= 0:
                continue
            first_x = crop_lefts[index]
            second_x = crop_lefts[index + 1]
            interpolation = (
                f"{first_x:.2f}+({second_x - first_x:.2f})"
                f"*(t-{first_time:.3f})/{duration:.3f}"
            )
            expression = (
                f"if(lt(t\\,{second_time:.3f})\\,"
                f"{interpolation}\\,{expression})"
            )

        return CropTracking(
            frame_width=frame_width,
            frame_height=frame_height,
            crop_width=crop_width,
            x_expression=expression,
            face_in_lower_third=face_in_lower_third,
        )
    finally:
        capture.release()
