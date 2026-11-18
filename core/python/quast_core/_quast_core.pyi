from typing import List, Dict, Tuple, Optional

class FormulaSegment:
    is_math: bool
    is_block: bool
    text: str
    start_byte: usize
    end_byte: usize

class PyBatchResult:
    input_path: str
    output_path: str
    success: bool
    error_msg: Optional[str]

class PreprocessedImageResult:
    png_bytes: bytes
    width: int
    height: int
    crop_box: Tuple[int, int, int, int]

def scan_formulas(text: str) -> List[FormulaSegment]: ...
def extract_unique_formulas_from_text(text: str) -> List[str]: ...
def extract_unique_formulas_from_docx(docx_paths: List[str]) -> List[str]: ...
def convert_docx_batch_py(
    docx_paths: List[str],
    output_dir: str,
    omml_map: Dict[str, str],
) -> List[PyBatchResult]: ...
def patch_docx_preview_single(input_path: str, output_path: str) -> bool: ...
def patch_docx_preview_batch(
    docx_paths: List[str],
    temp_dir: str,
) -> List[Tuple[str, str, bool]]: ...
def preprocess_formula_image(
    image_bytes: bytes,
    window_size: int = 25,
    k: float = 0.18,
    padding: int = 12,
    denoise: bool = True,
) -> PreprocessedImageResult: ...
def init_thread_pool(num_threads: int) -> None: ...
