pub mod docx_engine;
pub mod error;
pub mod image_proc;
pub mod tokenizer;

use docx_engine::{
    convert_docx_batch_py, extract_unique_formulas_from_docx, patch_docx_preview_batch,
    patch_docx_preview_single, PyBatchResult,
};
use image_proc::{preprocess_formula_image, PreprocessedImageResult};
use pyo3::prelude::*;
use tokenizer::{
    extract_unique_formulas_from_text, is_latex_formula, scan_formulas, FormulaSegment,
};

/// Configure number of threads for Rayon thread pool (defaults to all logical CPU cores)
#[pyfunction]
pub fn init_thread_pool(num_threads: usize) -> PyResult<()> {
    if num_threads > 0 {
        let _ = rayon::ThreadPoolBuilder::new()
            .num_threads(num_threads)
            .build_global();
    }
    Ok(())
}

/// Native Rust extension module for QUAST LaTeX to OMML
#[pymodule]
fn _quast_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 1. Tokenizer / Regex block
    m.add_class::<FormulaSegment>()?;
    m.add_function(wrap_pyfunction!(scan_formulas, m)?)?;
    m.add_function(wrap_pyfunction!(is_latex_formula, m)?)?;
    m.add_function(wrap_pyfunction!(extract_unique_formulas_from_text, m)?)?;

    // 2. Docx Engine & Batch I/O block
    m.add_class::<PyBatchResult>()?;
    m.add_function(wrap_pyfunction!(extract_unique_formulas_from_docx, m)?)?;
    m.add_function(wrap_pyfunction!(convert_docx_batch_py, m)?)?;
    m.add_function(wrap_pyfunction!(patch_docx_preview_single, m)?)?;
    m.add_function(wrap_pyfunction!(patch_docx_preview_batch, m)?)?;

    // 3. Image Preprocessing block (IMAGE OCR)
    m.add_class::<PreprocessedImageResult>()?;
    m.add_function(wrap_pyfunction!(preprocess_formula_image, m)?)?;

    // Thread management utility
    m.add_function(wrap_pyfunction!(init_thread_pool, m)?)?;

    Ok(())
}
