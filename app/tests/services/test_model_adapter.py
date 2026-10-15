import io
import json
import pytest
import pypdf
import numpy as np

from app.services.model_adapter import (
    AIHandwritingModelAdapter,
    ai_model_adapter,
    TORCH_AVAILABLE,
)
from app.services.pdf_writer import PDFWriterService, hex_to_rgb


def test_model_adapter_initialization():
    adapter = AIHandwritingModelAdapter()
    assert adapter.vocab_size == 77
    assert "A" in adapter.char_to_id
    assert " " in adapter.char_to_id
    assert adapter.device == "cpu"


def test_model_adapter_checkpoint_location():
    ckpt = ai_model_adapter.locate_checkpoint()
    assert ckpt is not None
    assert ckpt.exists()
    assert ckpt.suffix == ".pt"
    assert ai_model_adapter.is_available() is True


def test_model_adapter_singleton_caching():
    model1 = ai_model_adapter.load_model()
    assert model1 is not None
    model2 = ai_model_adapter.load_model()
    # Must be the identical object in memory (singleton pattern, no reload)
    assert model1 is model2


def test_canvas_strokes_conversion_valid():
    # Simulate calibration pad stroke data: 2 strokes, 3 points each
    raw_strokes = [
        [{"x": 10.0, "y": 20.0}, {"x": 15.0, "y": 25.0}, {"x": 20.0, "y": 30.0}],
        [{"x": 40.0, "y": 50.0}, {"x": 45.0, "y": 55.0}],
    ]
    json_str = json.dumps(raw_strokes)
    offsets = ai_model_adapter.convert_canvas_strokes_to_offsets(json_str)
    assert offsets is not None
    assert isinstance(offsets, np.ndarray)
    assert offsets.shape == (5, 3)
    # Pen lifts (eos): point index 2 (end of stroke 1) and index 4 (end of stroke 2) should have eos=1.0
    assert offsets[2, 0] == 1.0
    assert offsets[4, 0] == 1.0
    assert offsets[1, 0] == 0.0


def test_canvas_strokes_conversion_invalid():
    assert ai_model_adapter.convert_canvas_strokes_to_offsets(None) is None
    assert ai_model_adapter.convert_canvas_strokes_to_offsets("") is None
    assert ai_model_adapter.convert_canvas_strokes_to_offsets("[]") is None
    assert ai_model_adapter.convert_canvas_strokes_to_offsets("invalid json") is None
    # Too few points (< 5)
    assert ai_model_adapter.convert_canvas_strokes_to_offsets('[[]]') is None


def test_render_strokes_to_svg_paths():
    # Create synthetic stroke sequence: 10 points with one pen lift
    synthetic_strokes = np.array([
        [0.0, 1.0, -1.0],
        [0.0, 1.0, -1.0],
        [0.0, 1.0, -1.0],
        [1.0, 1.0, -1.0],
        [0.0, 2.0, 1.0],
        [0.0, 2.0, 1.0],
        [1.0, 2.0, 1.0],
    ], dtype=np.float32)

    svg_paths, segments, width = ai_model_adapter.render_strokes_to_svg_paths(
        stroke_points=synthetic_strokes,
        base_x=60.0,
        base_y=100.0,
        target_height=30.0,
        ink_color="#1a237e",
    )
    assert len(svg_paths) >= 1
    assert all("<path" in p and 'fill="none"' in p for p in svg_paths)
    assert len(segments) >= 1
    assert width > 0.0


def test_real_model_inference_on_cpu():
    if not ai_model_adapter.is_available():
        pytest.skip("PyTorch or lstm.pt checkpoint unavailable")

    strokes = ai_model_adapter.generate_stroke_sequence(
        text_line="AI",
        bias=2.0,
    )
    assert strokes is not None
    assert isinstance(strokes, np.ndarray)
    assert strokes.ndim == 2
    assert strokes.shape[1] == 3
    assert len(strokes) >= 5


def test_pdf_writer_with_vector_paths_and_searchable_text():
    # Test that PDFWriterService renders vector paths natively while preserving searchability
    vector_paths = [
        [
            [{"x": 100.0, "y": 150.0}, {"x": 120.0, "y": 160.0}, {"x": 140.0, "y": 155.0}],
            [{"x": 160.0, "y": 150.0}, {"x": 180.0, "y": 165.0}],
        ]
    ]
    pages_lines = [["Dear Board Members"]]

    pdf_bytes = PDFWriterService.generate_pdf_bytes(
        pages_lines=pages_lines,
        title="Test PDF Parity",
        profile_name="AI Signature",
        ink_color="#0d47a1",
        pages_vector_paths=vector_paths,
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4")

    # Verify PDF is valid and readable by pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
    extracted_text = reader.pages[0].extract_text()
    assert "Dear Board Members" in extracted_text
