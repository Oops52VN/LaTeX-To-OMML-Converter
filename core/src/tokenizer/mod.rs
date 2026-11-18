pub mod normalizer;
pub mod scanner;

pub use normalizer::normalize_latex;
pub use scanner::{is_pure_latex_formula, scan_text_zero_copy, FormulaSegment};

use pyo3::prelude::*;

/// Python wrapper for Scanner & Tokenizer
#[pyfunction]
pub fn scan_formulas(py: Python<'_>, text: &str) -> PyResult<Vec<FormulaSegment>> {
    Ok(py.allow_threads(|| scan_text_zero_copy(text)))
}

/// Check whether a string is raw LaTeX mathematical formula code
#[pyfunction]
pub fn is_latex_formula(text: &str) -> bool {
    is_pure_latex_formula(text)
}

/// Extract list of all unique mathematical formulas in text
#[pyfunction]
pub fn extract_unique_formulas_from_text(py: Python<'_>, text: &str) -> PyResult<Vec<String>> {
    let formulas = py.allow_threads(|| {
        let segments = scan_text_zero_copy(text);
        let mut set = std::collections::BTreeSet::new();
        for seg in segments {
            if seg.is_math {
                set.insert(seg.text);
            }
        }
        set.into_iter().collect::<Vec<_>>()
    });
    Ok(formulas)
}
