"""Eye Tracker for Touchless HID Digitizer.

This module provides eye tracking functionality using the pre-trained GazeNet
neural network model. It handles model loading, gaze vector prediction, and
face normalization for accurate gaze estimation.

"""

import logging
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "neural_nets" / "gaze_vector"
sys.path.insert(0, str(_MODEL_DIR))

from gazenet import GazeNet
from mtcnn.detector import FaceDetector


class EyeTracker:
    """Eye tracking system using pre-trained GazeNet model.

    Attributes:
        model_dir (Path): Path to directory containing GazeNet model files.
        device (torch.device): PyTorch device (cuda or cpu) for inference.
        model: Loaded GazeNet model instance.
        logger (logging.Logger): Logger instance for this tracker.
    """

    def __init__(self) -> None:
        """Initialize eye tracker and load pre-trained GazeNet model.

        Args:
            model_dir: Path to directory containing gazenet.py and gazenet.pth.
                The directory must contain both the model definition file
                (gazenet.py) and the trained weights file (gazenet.pth).

        Raises:
            FileNotFoundError: If model_dir, gazenet.py, or gazenet.pth
                does not exist.
            ImportError: If gazenet module cannot be imported.
            RuntimeError: If model weights cannot be loaded.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.logger.info(f"Using device: {self.device}")

        try:
            self.model = GazeNet(self.device)
            self.logger.info("GazeNet model instantiated")
        except Exception as e:
            self.logger.error(f"Failed to instantiate GazeNet: {e}")
            raise RuntimeError(
                f"Could not instantiate GazeNet model: {e}"
            ) from e

        try:
            weights_path = str(_MODEL_DIR / "gazenet.pth")
            state_dict = torch.load(
                weights_path,
                map_location=self.device,
                weights_only=True
            )
            self.model.load_state_dict(state_dict)
            self.logger.info(f"Loaded model weights from {weights_path}")
        except Exception as e:
            self.logger.error(f"Failed to load model weights: {e}")
            raise RuntimeError(
                f"Could not load model weights from {weights_path}: {e}"
            ) from e

        # Set model to evaluation mode (disables dropout, batch norm, etc.)
        self.model.eval()

        self.face_detector = FaceDetector(self.device)

        # Calibration state
        self._calibration_gaze_vectors: list[np.ndarray] = []
        self._calibration_origins: list[np.ndarray] = []
        self._calibration_screen_points: list[tuple[float, float]] = []
        self._coeff_x: np.ndarray | None = None
        self._coeff_y: np.ndarray | None = None

    def get_gaze_vector(self, frame: np.ndarray) -> tuple[torch.Tensor, np.ndarray] | None:
        """Detect face in frame and predict gaze vector.

        Runs face detection, normalizes the detected face, and predicts
        the gaze vector using the GazeNet model.

        Args:
            frame: Input video frame as numpy array (BGR format from OpenCV).

        Returns:
            Tuple of (gaze_vector, gaze_origin) where gaze_vector is a PyTorch
            tensor of shape (1, 2) and gaze_origin is a numpy array of shape (2,)
            in frame pixel coordinates, or None if no face is detected.
        """
        faces, landmarks = self.face_detector.detect(Image.fromarray(frame))

        if len(faces) == 0:
            return None

        for f, lm in zip(faces, landmarks):
            if f[-1] > 0.98:
                face, gaze_origin, _ = self.normalize_face(lm, frame)

                with torch.no_grad():
                    gaze = self.model.get_gaze(face)
                    gaze = gaze[0].data.cpu()

                origin = np.array(gaze_origin, dtype=np.float64)
                return (gaze, gaze_origin)

        return None

    def normalize_face(self, landmarks, frame):
        left_eye_coord=(0.70, 0.35)
        
        lcenter = tuple([landmarks[0],landmarks[5]])
        rcenter = tuple([landmarks[1],landmarks[6]])
        
        gaze_origin = (int((lcenter[0]+rcenter[0])/2), int((lcenter[1]+rcenter[1])/2))

        dY = rcenter[1] - lcenter[1]
        dX = rcenter[0] - lcenter[0]
        angle = np.degrees(np.arctan2(dY, dX)) - 180
        
        right_eye_x = 1.0 - left_eye_coord[0]

        dist = np.sqrt((dX ** 2) + (dY ** 2))
        new_dist = (right_eye_x - left_eye_coord[0])
        new_dist *= 112
        scale = new_dist / dist

        M = cv2.getRotationMatrix2D(gaze_origin, angle, scale)

        tX = 112 * 0.5
        tY = 112 * left_eye_coord[1]
        M[0, 2] += (tX - gaze_origin[0])
        M[1, 2] += (tY - gaze_origin[1])

        face = cv2.warpAffine(frame, M, (112, 112),
            flags=cv2.INTER_CUBIC)
        return face, gaze_origin, M

    def _polynomial_features(self, gaze: np.ndarray, origin: np.ndarray) -> np.ndarray:
        """Compute 2nd degree polynomial features from gaze vector and origin.

        Args:
            gaze: Gaze vector as numpy array of shape (2,) (pitch, yaw).
            origin: Gaze origin as numpy array of shape (2,) in frame pixel coordinates.

        Returns:
            Feature vector of shape (15,): [1, g0, g1, o0, o1, g0², g0*g1,
            g0*o0, g0*o1, g1², g1*o0, g1*o1, o0², o0*o1, o1²].
        """
        g0, g1 = gaze
        o0, o1 = origin
        return np.array([
            1.0,
            g0, g1, o0, o1,
            g0**2, g0*g1, g0*o0, g0*o1,
            g1**2, g1*o0, g1*o1,
            o0**2, o0*o1,
            o1**2
        ])

    def add_calibration_point(
        self, gaze_vector: torch.Tensor, gaze_origin: np.ndarray,
        screen_point: tuple[float, float]
    ) -> None:
        """Record a calibration point mapping gaze vector to screen coordinates.

        Args:
            gaze_vector: Gaze vector tensor of shape (1, 2) (pitch, yaw).
            gaze_origin: Normalized gaze origin as numpy array of shape (2,) [0, 1].
            screen_point: Screen coordinates (x_pixels, y_pixels).
        """
        gaze_np = gaze_vector.cpu().numpy().squeeze()  # Convert to (2,)
        self._calibration_gaze_vectors.append(gaze_np)
        self._calibration_origins.append(gaze_origin)
        self._calibration_screen_points.append(screen_point)
        self.logger.debug(
            f"Added calibration point: gaze={gaze_np}, origin={gaze_origin}, "
            f"screen={screen_point}"
        )

    def calibrate(self) -> None:
        """Fit polynomial regression from gaze vectors to screen coordinates.

        Uses 2nd degree polynomial features and least squares to compute
        mapping coefficients for both X and Y screen coordinates.

        Raises:
            ValueError: If fewer than 15 calibration points have been collected.
        """
        n_points = len(self._calibration_gaze_vectors)
        if n_points < 15:
            raise ValueError(
                f"Need at least 15 calibration points, got {n_points}"
            )

        # Build feature matrix: each row is polynomial features of gaze vector + origin
        X = np.array(
            [self._polynomial_features(g, o)
             for g, o in zip(self._calibration_gaze_vectors, self._calibration_origins)]
        )

        # Build target matrices for screen X and Y coordinates
        screen_x = np.array([pt[0] for pt in self._calibration_screen_points])
        screen_y = np.array([pt[1] for pt in self._calibration_screen_points])

        # Solve least squares for X and Y independently
        self._coeff_x, _, _, _ = np.linalg.lstsq(X, screen_x, rcond=None)
        self._coeff_y, _, _, _ = np.linalg.lstsq(X, screen_y, rcond=None)

        self.logger.info(
            f"Calibration complete with {n_points} points. "
            f"Coefficients computed for X and Y mappings."
        )

    def predict_screen_position(
        self, gaze_vector: torch.Tensor, gaze_origin: np.ndarray
    ) -> tuple[float, float]:
        """Map gaze vector to screen coordinates using calibration.

        Args:
            gaze_vector: Gaze vector tensor of shape (1, 2) (pitch, yaw).
            gaze_origin: Normalized gaze origin as numpy array of shape (2,) [0, 1].

        Returns:
            Screen coordinates (x_pixels, y_pixels) as floats.

        Raises:
            RuntimeError: If calibration has not been performed yet.
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibration has not been performed. Call calibrate() first.")

        gaze_np = gaze_vector.cpu().numpy().squeeze()  # Convert to (2,)
        features = self._polynomial_features(gaze_np, gaze_origin)

        screen_x = np.dot(features, self._coeff_x)
        screen_y = np.dot(features, self._coeff_y)

        return (float(screen_x), float(screen_y))

    def clear_calibration(self) -> None:
        """Reset all calibration data and fitted coefficients."""
        self._calibration_gaze_vectors.clear()
        self._calibration_origins.clear()
        self._calibration_screen_points.clear()
        self._coeff_x = None
        self._coeff_y = None
        self.logger.info("Calibration data cleared")

    @property
    def is_calibrated(self) -> bool:
        """Check if calibration has been fitted.

        Returns:
            True if calibration coefficients are available, False otherwise.
        """
        return self._coeff_x is not None and self._coeff_y is not None
