from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import torch and numpy safely so the rest of the application never fails
# if PyTorch is not installed or if there's an import-time environment issue.
try:
    import numpy as np
    import torch
    import torch.nn as nn
    from torch.distributions import bernoulli
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    np = None  # type: ignore
    torch = None  # type: ignore
    nn = None  # type: ignore


# ---------------------------------------------------------------------------
# Graves (2013) Recurrent Neural Network for Handwriting Synthesis
# ---------------------------------------------------------------------------

if TORCH_AVAILABLE:
    def stable_softmax(X, dim=2):
        max_vec = torch.max(X, dim, keepdim=True)
        exp_X = torch.exp(X - max_vec[0])
        sum_exp_X = torch.sum(exp_X, dim, keepdim=True)
        return exp_X / sum_exp_X


    def sample_from_out_dist(y_hat: "torch.Tensor", bias: float) -> "torch.Tensor":
        split_sizes = [1] + [20] * 6
        y = torch.split(y_hat, split_sizes, dim=0)

        eos_prob = torch.sigmoid(y[0])
        mixture_weights = stable_softmax(y[1] * (1.0 + bias), dim=0)
        mu_1 = y[2]
        mu_2 = y[3]
        std_1 = torch.exp(y[4] - bias)
        std_2 = torch.exp(y[5] - bias)
        correlations = torch.tanh(y[6])

        bernoulli_dist = bernoulli.Bernoulli(probs=eos_prob)
        eos_sample = bernoulli_dist.sample()

        K = torch.multinomial(mixture_weights, 1)

        mu_k = y_hat.new_zeros(2)
        mu_k[0] = mu_1[K]
        mu_k[1] = mu_2[K]

        L = y_hat.new_zeros(2, 2)
        L[0, 0] = std_1[K]
        L[1, 0] = correlations[K] * std_2[K]
        L[1, 1] = std_2[K] * torch.sqrt(torch.clamp(1.0 - correlations[K].pow(2), min=1e-6))
        x = torch.normal(
            mean=torch.zeros(2, device=y_hat.device),
            std=torch.ones(2, device=y_hat.device),
        )
        Z = mu_k + torch.mv(L, x)

        sample = y_hat.new_zeros(1, 1, 3)
        sample[0, 0, 0] = eos_sample.item()
        sample[0, 0, 1:] = Z
        return sample


    class HandWritingSynthesisNet(nn.Module):
        """
        PyTorch Implementation of Alex Graves (2013) conditional handwriting synthesis net.
        3 LSTM layers with a soft window attention mechanism over one-hot text characters,
        and a 20-component Gaussian mixture density output layer.
        """

        def __init__(self, hidden_size: int = 400, n_layers: int = 3, output_size: int = 121, window_size: int = 77):
            super().__init__()
            self.vocab_size = window_size
            self.hidden_size = hidden_size
            self.output_size = output_size
            self.n_layers = n_layers
            self.EOS = False
            K = 10

            self.lstm_1 = nn.LSTM(3 + self.vocab_size, hidden_size, batch_first=True)
            self.lstm_2 = nn.LSTM(3 + self.vocab_size + hidden_size, hidden_size, batch_first=True)
            self.lstm_3 = nn.LSTM(3 + self.vocab_size + hidden_size, hidden_size, batch_first=True)

            self.window_layer = nn.Linear(hidden_size, 3 * K)
            self.output_layer = nn.Linear(n_layers * hidden_size, output_size)

        def init_hidden(self, batch_size: int, device: str | torch.device):
            initial_hidden = (
                torch.zeros(self.n_layers, batch_size, self.hidden_size, device=device),
                torch.zeros(self.n_layers, batch_size, self.hidden_size, device=device),
            )
            window_vector = torch.zeros(batch_size, 1, self.vocab_size, device=device)
            kappa = torch.zeros(batch_size, 10, 1, device=device)
            return initial_hidden, window_vector, kappa

        def one_hot_encoding(self, text: "torch.Tensor") -> "torch.Tensor":
            N = text.shape[0]
            U = text.shape[1]
            encoding = text.new_zeros((N, U, self.vocab_size))
            for i in range(N):
                encoding[i, torch.arange(U), text[i].long()] = 1.0
            return encoding

        def compute_window_vector(self, mix_params, prev_kappa, text, text_mask):
            encoding = self.one_hot_encoding(text)
            mix_params = torch.exp(mix_params)
            alpha, beta, kappa = mix_params.split(10, dim=1)
            kappa = kappa + prev_kappa
            prev_kappa = kappa

            u = torch.arange(text.shape[1], dtype=torch.float32, device=text.device)
            phi = torch.sum(alpha * torch.exp(-beta * (kappa - u).pow(2)), dim=1)
            if phi[0, -1] > torch.max(phi[0, :-1]):
                self.EOS = True
            phi = (phi * text_mask).unsqueeze(2)
            window_vec = torch.sum(phi * encoding, dim=1, keepdim=True)
            return window_vec, prev_kappa

        def forward(self, inputs, text, text_mask, initial_hidden, prev_window_vec, prev_kappa):
            hid_1 = []
            window_vec = []
            state_1 = (initial_hidden[0][0:1], initial_hidden[1][0:1])

            for t in range(inputs.shape[1]):
                inp = torch.cat((inputs[:, t : t + 1, :], prev_window_vec), dim=2)
                hid_1_t, state_1 = self.lstm_1(inp, state_1)
                hid_1.append(hid_1_t)

                mix_params = self.window_layer(hid_1_t)
                window, kappa = self.compute_window_vector(
                    mix_params.squeeze(dim=1).unsqueeze(2),
                    prev_kappa,
                    text,
                    text_mask,
                )
                prev_window_vec = window
                prev_kappa = kappa
                window_vec.append(window)

            hid_1 = torch.cat(hid_1, dim=1)
            window_vec = torch.cat(window_vec, dim=1)

            inp = torch.cat((inputs, hid_1, window_vec), dim=2)
            state_2 = (initial_hidden[0][1:2], initial_hidden[1][1:2])
            hid_2, state_2 = self.lstm_2(inp, state_2)

            inp = torch.cat((inputs, hid_2, window_vec), dim=2)
            state_3 = (initial_hidden[0][2:], initial_hidden[1][2:])
            hid_3, state_3 = self.lstm_3(inp, state_3)

            inp = torch.cat([hid_1, hid_2, hid_3], dim=2)
            y_hat = self.output_layer(inp)
            return y_hat, [state_1, state_2, state_3], window_vec, prev_kappa

        def generate(
            self,
            inp,
            text,
            text_mask,
            prime_text,
            prime_mask,
            hidden,
            window_vector,
            kappa,
            bias: float,
            prime: bool = False,
            max_seq_len: int = 1500,
        ):
            # Critical bugfix: reset EOS flag unconditionally at the beginning of generation
            self.EOS = False
            seq_len = 0
            gen_seq = []

            with torch.no_grad():
                batch_size = inp.shape[0]
                if prime and prime_text is not None and prime_mask is not None:
                    _, state, window_vector, kappa = self.forward(
                        inp, prime_text, prime_mask, hidden, window_vector, kappa
                    )
                    _hidden = torch.cat([s[0] for s in state], dim=0)
                    _cell = torch.cat([s[1] for s in state], dim=0)
                    hidden = (_hidden, _cell)
                    self.EOS = False
                    inp = inp.new_zeros(batch_size, 1, 3)
                    _, window_vector, kappa = self.init_hidden(batch_size, inp.device)

                while not self.EOS and seq_len < max_seq_len:
                    y_hat, state, window_vector, kappa = self.forward(
                        inp, text, text_mask, hidden, window_vector, kappa
                    )
                    _hidden = torch.cat([s[0] for s in state], dim=0)
                    _cell = torch.cat([s[1] for s in state], dim=0)
                    hidden = (_hidden, _cell)

                    y_hat = y_hat.squeeze()
                    Z = sample_from_out_dist(y_hat, bias)
                    inp = Z
                    gen_seq.append(Z)
                    seq_len += 1

            if not gen_seq:
                return np.zeros((batch_size, 0, 3), dtype=np.float32)

            res = torch.cat(gen_seq, dim=1).cpu().numpy()
            return res


# ---------------------------------------------------------------------------
# AI Handwriting Model Adapter Service
# ---------------------------------------------------------------------------

class AIHandwritingModelAdapter:
    """
    Decoupled adapter for loading and running the pretrained Graves (2013)
    handwriting synthesis neural network locally on CPU.
    """

    VOCAB_CHARS: str = " !\"#'()+,-./0123456789:;?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    # Precomputed global normalization constants from the 6,000 IAMOnDB training sequences
    TRAIN_MEAN: Tuple[float, float] = (0.22292781, -0.00327993)
    TRAIN_STD: Tuple[float, float] = (1.53072953, 1.36315215)

    def __init__(self):
        self._model: Optional[Any] = None
        self._is_loaded: bool = False
        self._load_error: Optional[str] = None
        self.device: str = "cpu"

        # Build vocabulary mappings
        self.char_to_id: Dict[str, int] = {c: i for i, c in enumerate(self.VOCAB_CHARS)}
        self.id_to_char: Dict[int, str] = {i: c for i, c in enumerate(self.VOCAB_CHARS)}
        self.vocab_size: int = len(self.VOCAB_CHARS)

    def locate_checkpoint(self) -> Optional[Path]:
        """Search standard candidate paths for the pretrained lstm.pt checkpoint."""
        candidate_paths = [
            os.getenv("AI_HANDWRITING_CHECKPOINT"),
            r"C:\Users\User\Desktop\ai-handwriting-generator\weights\lstm.pt",
            Path(__file__).resolve().parent.parent.parent / "weights" / "lstm.pt",
            Path(__file__).resolve().parent.parent / "assets" / "lstm.pt",
            Path("weights/lstm.pt"),
            Path("../ai-handwriting-generator/weights/lstm.pt"),
        ]
        for p in candidate_paths:
            if p:
                path = Path(p).resolve()
                if path.exists() and path.is_file():
                    return path
        return None

    def locate_default_style(self) -> Optional[Path]:
        """Search candidate paths for the reference default_style.npy stroke sequence."""
        candidate_paths = [
            os.getenv("AI_HANDWRITING_DEFAULT_STYLE"),
            Path(__file__).resolve().parent.parent / "assets" / "default_style.npy",
            r"C:\Users\User\Desktop\ai-handwriting-generator\app\static\uploads\default_style.npy",
            Path("app/assets/default_style.npy"),
            Path("../ai-handwriting-generator/app/static/uploads/default_style.npy"),
        ]
        for p in candidate_paths:
            if p:
                path = Path(p).resolve()
                if path.exists() and path.is_file():
                    return path
        return None

    def is_available(self) -> bool:
        """Returns True if PyTorch is installed and the pretrained checkpoint is accessible."""
        if not TORCH_AVAILABLE:
            return False
        ckpt = self.locate_checkpoint()
        return ckpt is not None

    def load_model(self) -> Optional[Any]:
        """Loads the HandWritingSynthesisNet checkpoint into memory once (singleton pattern)."""
        if self._is_loaded and self._model is not None:
            return self._model

        if not TORCH_AVAILABLE:
            self._load_error = "PyTorch is not installed in the environment."
            return None

        ckpt_path = self.locate_checkpoint()
        if not ckpt_path:
            self._load_error = "Checkpoint lstm.pt was not found."
            return None

        try:
            model = HandWritingSynthesisNet(window_size=self.vocab_size)
            state_dict = torch.load(str(ckpt_path), map_location=self.device)
            model.load_state_dict(state_dict)
            model.to(self.device)
            model.eval()
            self._model = model
            self._is_loaded = True
            self._load_error = None
            logger.info(f"Loaded pretrained HandWritingSynthesisNet from {ckpt_path}")
            return self._model
        except Exception as exc:
            self._load_error = f"Failed to load checkpoint: {exc}"
            logger.error(self._load_error)
            return None

    def convert_canvas_strokes_to_offsets(self, canvas_strokes_json: Optional[str]) -> Optional[Any]:
        """
        Convert user-recorded canvas strokes from the calibration pad into normalized
        [eos, dx, dy] offsets compatible with Graves conditioning.
        """
        if not canvas_strokes_json or not np:
            return None
        try:
            strokes_data = json.loads(canvas_strokes_json)
            if not isinstance(strokes_data, list) or not strokes_data:
                return None

            pts = []
            for stroke in strokes_data:
                if not isinstance(stroke, list) or not stroke:
                    continue
                for idx, pt in enumerate(stroke):
                    if isinstance(pt, dict) and "x" in pt and "y" in pt:
                        eos = 1.0 if idx == len(stroke) - 1 else 0.0
                        pts.append((float(pt["x"]), float(pt["y"]), eos))

            if len(pts) < 5:
                return None

            # Convert to offsets [eos, dx, dy]
            offsets = [[pts[0][2], 0.0, 0.0]]
            for i in range(1, len(pts)):
                dx = pts[i][0] - pts[i - 1][0]
                # HTML canvas y goes DOWN, while IAMOnDB / Graves model downward coordinate offset is negative.
                dy = -(pts[i][1] - pts[i - 1][1])
                eos = pts[i][2]
                offsets.append([eos, dx, dy])

            arr = np.array(offsets, dtype=np.float32)
            return arr
        except Exception as exc:
            logger.warning(f"Failed to convert canvas strokes: {exc}")
            return None

    def generate_stroke_sequence(
        self,
        text_line: str,
        bias: float = 2.0,
        style_offsets: Optional[Any] = None,
        priming_text: str = "copy monkey app",
    ) -> Optional[Any]:
        """
        Run inference on CPU for a single line of text.
        Returns a denormalized numpy array of shape (T, 3) where each row is [eos, dx, dy].
        """
        model = self.load_model()
        if model is None or not TORCH_AVAILABLE:
            return None

        # Clean text line against model vocabulary
        cleaned_chars = []
        for ch in text_line:
            if ch in self.char_to_id:
                cleaned_chars.append(ch)
            else:
                cleaned_chars.append(" ")
        clean_text = "".join(cleaned_chars).strip()
        if not clean_text:
            return None

        # Format input text tensor (padded with 2 spaces per Graves convention)
        char_seq = list(clean_text + "  ")
        text_indices = [self.char_to_id[c] for c in char_seq]
        text_tensor = torch.tensor([text_indices], dtype=torch.float32, device=self.device)
        text_mask = torch.ones(text_tensor.shape, device=self.device)

        # Style priming setup
        mean_arr = np.array(self.TRAIN_MEAN, dtype=np.float32)
        std_arr = np.array(self.TRAIN_STD, dtype=np.float32)

        prime = False
        prime_tensor = None
        prime_text_tensor = None
        prime_mask_tensor = None

        target_style = style_offsets
        if target_style is None:
            # Fallback to default style sequence if available
            default_style_path = self.locate_default_style()
            if default_style_path:
                try:
                    target_style = np.load(default_style_path, allow_pickle=True, encoding="bytes").astype(np.float32)
                    priming_text = "copy monkey app"
                except Exception:
                    target_style = None

        if target_style is not None and len(target_style) > 10 and priming_text:
            try:
                # Normalize style with global training statistics
                norm_style = target_style.copy()
                norm_style[:, 1:] -= mean_arr
                norm_style[:, 1:] /= std_arr
                prime_tensor = torch.from_numpy(norm_style).unsqueeze(0).to(self.device)

                prime_clean = [self.char_to_id.get(c, 0) for c in priming_text]
                prime_text_tensor = torch.tensor([prime_clean], dtype=torch.float32, device=self.device)
                prime_mask_tensor = torch.ones(prime_text_tensor.shape, device=self.device)
                prime = True
            except Exception as exc:
                logger.warning(f"Priming failed, generating unconditioned: {exc}")
                prime = False

        hidden, window_vector, kappa = model.init_hidden(1, self.device)
        inp = prime_tensor if prime else torch.zeros(1, 1, 3, device=self.device)

        try:
            gen_seq = model.generate(
                inp=inp,
                text=text_tensor,
                text_mask=text_mask,
                prime_text=prime_text_tensor,
                prime_mask=prime_mask_tensor,
                hidden=hidden,
                window_vector=window_vector,
                kappa=kappa,
                bias=bias,
                prime=prime,
                max_seq_len=1800,
            )

            if gen_seq is None or gen_seq.shape[1] == 0:
                return None

            # Denormalize generated coordinates back to physical stroke space
            gen_seq[:, :, 1:] *= std_arr
            gen_seq[:, :, 1:] += mean_arr
            return gen_seq[0]  # Shape (T, 3)
        except Exception as exc:
            logger.error(f"Inference error in HandWritingSynthesisNet: {exc}")
            return None

    def render_strokes_to_svg_paths(
        self,
        stroke_points: Any,
        base_x: float,
        base_y: float,
        target_height: float = 32.0,
        ink_color: str = "#1a237e",
        stroke_width: float = 1.4,
    ) -> Tuple[List[str], List[List[Dict[str, float]]], float]:
        """
        Converts (T, 3) stroke points [eos, dx, dy] into scaled SVG path tags and
        structured vector segments for faithful PDF export reproduction.
        """
        if stroke_points is None or len(stroke_points) < 2:
            return [], [], 0.0

        # Cumulative sum of offsets
        raw_x = np.cumsum(stroke_points[:, 1])
        # Downward strokes have negative dy in IAMOnDB; SVG y increases downwards.
        raw_y = -np.cumsum(stroke_points[:, 2])

        min_x, max_x = float(raw_x.min()), float(raw_x.max())
        min_y, max_y = float(raw_y.min()), float(raw_y.max())

        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)

        # Scale strokes to fit target line height while preserving aspect ratio
        scale = target_height / span_y
        rendered_width = span_x * scale

        # Position line at base_x and align baseline near base_y
        norm_x = base_x + (raw_x - min_x) * scale
        norm_y = (base_y - (target_height * 0.75)) + (raw_y - min_y) * scale

        cuts = np.where(stroke_points[:, 0] > 0.5)[0]
        all_cuts = list(cuts)
        if not all_cuts or all_cuts[-1] < len(stroke_points) - 1:
            all_cuts.append(len(stroke_points) - 1)

        svg_paths: List[str] = []
        structured_segments: List[List[Dict[str, float]]] = []
        start = 0

        for cut_idx in all_cuts:
            seg_x = norm_x[start : cut_idx + 1]
            seg_y = norm_y[start : cut_idx + 1]
            start = cut_idx + 1

            if len(seg_x) < 2:
                continue

            d_cmd = f"M {seg_x[0]:.2f} {seg_y[0]:.2f} " + " ".join(
                f"L {px:.2f} {py:.2f}" for px, py in zip(seg_x[1:], seg_y[1:])
            )

            svg_paths.append(
                f'<path d="{d_cmd}" fill="none" stroke="{ink_color}" stroke-width="{stroke_width:.2f}" '
                f'stroke-linecap="round" stroke-linejoin="round" />'
            )

            # Store structured points for exact PDF vector reproduction
            structured_segments.append(
                [{"x": round(float(px), 2), "y": round(float(py), 2)} for px, py in zip(seg_x, seg_y)]
            )

        return svg_paths, structured_segments, rendered_width


ai_model_adapter = AIHandwritingModelAdapter()
