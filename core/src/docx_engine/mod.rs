pub mod batch_runner;
pub mod preview_patch;
pub mod xml_stream;

use batch_runner::{
    convert_batch_parallel, extract_unique_formulas_from_batch, patch_preview_batch_parallel,
};
use preview_patch::patch_docx_settings;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::atomic::AtomicUsize;
use std::sync::Arc;

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct PyBatchResult {
    pub input_path: String,
    pub output_path: String,
    pub success: bool,
    pub error_msg: Option<String>,
}

#[pymethods]
impl PyBatchResult {
    fn __repr__(&self) -> String {
        format!(
            "PyBatchResult(input={:?}, output={:?}, success={}, error={:?})",
            self.input_path, self.output_path, self.success, self.error_msg
        )
    }
}

/// Extract unique formulas from hundreds of .docx files in parallel without GIL bottlenecks
#[pyfunction]
pub fn extract_unique_formulas_from_docx(
    py: Python<'_>,
    docx_paths: Vec<String>,
) -> PyResult<Vec<String>> {
    let result = py.allow_threads(|| extract_unique_formulas_from_batch(&docx_paths));
    Ok(result)
}

/// Convert batch of .docx files in parallel using precompiled OMML hash map
#[pyfunction]
pub fn convert_docx_batch_py(
    py: Python<'_>,
    docx_paths: Vec<String>,
    output_dir: String,
    omml_map: HashMap<String, String>,
) -> PyResult<Vec<PyBatchResult>> {
    let counter = Arc::new(AtomicUsize::new(0));

    let raw_results = py.allow_threads(|| {
        convert_batch_parallel(&docx_paths, &output_dir, &omml_map, Some(counter))
    });

    let results = raw_results
        .into_iter()
        .map(|r| PyBatchResult {
            input_path: r.input_path,
            output_path: r.output_path,
            success: r.success,
            error_msg: r.error_msg,
        })
        .collect();

    Ok(results)
}

/// Preprocess preview settings (Print View + Read Only) for a single .docx file
#[pyfunction]
pub fn patch_docx_preview_single(
    py: Python<'_>,
    input_path: String,
    output_path: String,
) -> PyResult<bool> {
    let res = py.allow_threads(|| patch_docx_settings(&input_path, &output_path))?;
    Ok(res)
}

/// Preprocess preview settings for multiple .docx files in parallel
#[pyfunction]
pub fn patch_docx_preview_batch(
    py: Python<'_>,
    docx_paths: Vec<String>,
    temp_dir: String,
) -> PyResult<Vec<(String, String, bool)>> {
    let res = py.allow_threads(|| patch_preview_batch_parallel(&docx_paths, &temp_dir));
    Ok(res)
}
