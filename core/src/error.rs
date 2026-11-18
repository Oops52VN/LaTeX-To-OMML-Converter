use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3::PyErr;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum QuastError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("ZIP error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("XML parsing error: {0}")]
    Xml(#[from] quick_xml::Error),

    #[error("Image processing error: {0}")]
    Image(#[from] image::ImageError),

    #[error("Invalid argument: {0}")]
    InvalidArgument(String),

    #[error("Engine execution failure: {0}")]
    Internal(String),
}

impl From<QuastError> for PyErr {
    fn from(err: QuastError) -> PyErr {
        match err {
            QuastError::Io(e) => PyIOError::new_err(e.to_string()),
            QuastError::Zip(e) => PyIOError::new_err(format!("ZIP error: {e}")),
            QuastError::Xml(e) => PyValueError::new_err(format!("XML error: {e}")),
            QuastError::Image(e) => PyValueError::new_err(format!("Image error: {e}")),
            QuastError::InvalidArgument(msg) => PyValueError::new_err(msg),
            QuastError::Internal(msg) => PyRuntimeError::new_err(msg),
        }
    }
}

pub type QuastResult<T> = Result<T, QuastError>;
