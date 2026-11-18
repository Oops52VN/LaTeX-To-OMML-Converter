pub mod binarize;
pub mod crop;
pub mod denoise;

use crate::error::QuastResult;
use binarize::binarize_sauvola;
use crop::auto_crop_formula;
use denoise::median_filter_3x3;
use image::{load_from_memory, ImageFormat};
use pyo3::prelude::*;
use std::io::Cursor;

#[pyclass(get_all)]
pub struct PreprocessedImageResult {
    pub png_bytes: Py<pyo3::types::PyBytes>,
    pub width: u32,
    pub height: u32,
    pub crop_box: (u32, u32, u32, u32), // (x, y, w, h)
}

#[pymethods]
impl PreprocessedImageResult {
    fn __repr__(&self) -> String {
        format!(
            "PreprocessedImageResult(width={}, height={}, crop_box={:?})",
            self.width, self.height, self.crop_box
        )
    }
}

pub struct RawProcessedImage {
    pub png_data: Vec<u8>,
    pub width: u32,
    pub height: u32,
    pub crop_box: (u32, u32, u32, u32),
}

/// Lightweight mathematical image processing pipeline: Decode -> Grayscale -> Denoise -> Sauvola -> Auto Crop -> Encode PNG
pub fn run_image_pipeline(
    image_bytes: &[u8],
    window_size: u32,
    k: f32,
    padding: u32,
    denoise: bool,
) -> QuastResult<RawProcessedImage> {
    let dynamic_img = load_from_memory(image_bytes)?;
    let mut gray = dynamic_img.to_luma8();

    // 0. Automatically detect dark mode screenshots and invert colors
    let (w, h) = gray.dimensions();
    if w > 0 && h > 0 {
        let mut border_sum = 0u64;
        let mut border_count = 0u64;
        for x in 0..w {
            border_sum += gray.get_pixel(x, 0).0[0] as u64;
            border_sum += gray.get_pixel(x, h - 1).0[0] as u64;
            border_count += 2;
        }
        for y in 1..(h - 1) {
            border_sum += gray.get_pixel(0, y).0[0] as u64;
            border_sum += gray.get_pixel(w - 1, y).0[0] as u64;
            border_count += 2;
        }
        let avg_border = border_sum / border_count.max(1);
        if avg_border < 128 {
            for p in gray.iter_mut() {
                *p = 255 - *p;
            }
        }
    }

    // 1. Denoise if enabled
    let denoised = if denoise {
        median_filter_3x3(&gray)
    } else {
        gray
    };

    // 2. Adaptive Sauvola binarization
    let binarized = binarize_sauvola(&denoised, window_size, k);

    // 3. Auto crop white borders
    let (cropped, crop_box) = auto_crop_formula(&binarized, padding);
    let (w, h) = cropped.dimensions();

    // 4. Encode to PNG buffer
    let mut png_data = Vec::with_capacity((w * h) as usize / 4 + 1024);
    cropped.write_to(&mut Cursor::new(&mut png_data), ImageFormat::Png)?;

    Ok(RawProcessedImage {
        png_data,
        width: w,
        height: h,
        crop_box,
    })
}

/// Exported Python function: Receives raw image bytes (zero-copy), returns preprocessed result
#[pyfunction]
#[pyo3(signature = (image_bytes, window_size=25, k=0.18, padding=12, denoise=true))]
pub fn preprocess_formula_image<'py>(
    py: Python<'py>,
    image_bytes: &[u8],
    window_size: u32,
    k: f32,
    padding: u32,
    denoise: bool,
) -> PyResult<PreprocessedImageResult> {
    // 1. Release Python GIL to maximize multithreading performance in Rust Rayon
    let processed = py.allow_threads(|| {
        run_image_pipeline(image_bytes, window_size, k, padding, denoise)
    })?;

    // 2. Write directly into Python PyBytes buffer (avoids double copying)
    let py_bytes = pyo3::types::PyBytes::new_bound_with(py, processed.png_data.len(), |buf| {
        buf.copy_from_slice(&processed.png_data);
        Ok(())
    })?;

    Ok(PreprocessedImageResult {
        png_bytes: py_bytes.unbind(),
        width: processed.width,
        height: processed.height,
        crop_box: processed.crop_box,
    })
}
