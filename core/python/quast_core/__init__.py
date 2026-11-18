r"""QUAST Core: High-performance Rust extension engine for QUAST LaTeX to OMML.

Provides:
- Blazing-fast parallel Word (.docx) batch processing without Python GIL bottlenecks.
- Zero-copy LaTeX formula tokenizer & scanner (supporting $..$, $$..$$, \[..\], \(..\), and raw LaTeX).
- Lightweight pure-Rust mathematical image preprocessing for OCR.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Tuple, Callable
import os
import sys

try:
    from ._quast_core import (
        FormulaSegment,
        PyBatchResult,
        PreprocessedImageResult,
        scan_formulas,
        is_latex_formula,
        extract_unique_formulas_from_text,
        extract_unique_formulas_from_docx,
        convert_docx_batch_py,
        patch_docx_preview_single,
        patch_docx_preview_batch,
        preprocess_formula_image,
        init_thread_pool,
    )
    HAS_RUST_CORE = True
except ImportError:
    try:
        from quast_core._quast_core import (
            FormulaSegment,
            PyBatchResult,
            PreprocessedImageResult,
            scan_formulas,
            is_latex_formula,
            extract_unique_formulas_from_text,
            extract_unique_formulas_from_docx,
            convert_docx_batch_py,
            patch_docx_preview_single,
            patch_docx_preview_batch,
            preprocess_formula_image,
            init_thread_pool,
        )
        HAS_RUST_CORE = True
    except ImportError:
        HAS_RUST_CORE = False

__all__ = [
    "HAS_RUST_CORE",
    "FormulaSegment",
    "PyBatchResult",
    "PreprocessedImageResult",
    "scan_formulas",
    "is_latex_formula",
    "extract_unique_formulas_from_text",
    "extract_unique_formulas_from_docx",
    "convert_docx_batch_py",
    "patch_docx_preview_single",
    "patch_docx_preview_batch",
    "preprocess_formula_image",
    "init_thread_pool",
    "batch_convert_docx_hybrid",
]


def batch_convert_docx_hybrid(
    docx_paths: List[str],
    output_dir: str,
    formula_compiler_fn: Callable[[str], Optional[str]],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[PyBatchResult]:
    """Batch convert .docx documents using the Hybrid architecture:

    Phase 1: Parallel scan of all .docx files using Rayon (without holding the GIL)
             to extract the set of unique LaTeX formulas (both delimited with $ and raw LaTeX).
    Phase 2: Compile the unique formula set into OMML XML and store in a dictionary.
    Phase 3: Repackage .docx files using Quick-XML Streaming + raw_copy
             in parallel across all CPU cores without GIL bottlenecks.
    """
    if not HAS_RUST_CORE:
        raise RuntimeError("Rust native extension 'quast_core._quast_core' is not available.")

    if not docx_paths:
        return []

    # Phase 1: Extract unique formulas from entire batch
    if progress_callback:
        progress_callback(18)

    unique_formulas = extract_unique_formulas_from_docx(docx_paths)

    if progress_callback:
        progress_callback(35)

    # Phase 2: Compile unique formulas to OMML XML
    omml_map: Dict[str, str] = {}
    total_formulas = len(unique_formulas)
    emitted_52 = False

    for i, formula in enumerate(unique_formulas):
        omml_xml = formula_compiler_fn(formula)
        if omml_xml:
            omml_map[formula] = omml_xml
        if progress_callback and total_formulas > 0:
            if not emitted_52 and (i + 1) >= total_formulas * 0.5:
                progress_callback(52)
                emitted_52 = True

    if progress_callback:
        progress_callback(70)

    # Phase 3: Concurrently convert and repackage using Rayon
    if progress_callback:
        progress_callback(85)

    results = convert_docx_batch_py(docx_paths, output_dir, omml_map)

    if progress_callback:
        progress_callback(100)

    return results
