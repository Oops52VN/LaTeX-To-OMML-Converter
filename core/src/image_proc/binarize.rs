use image::GrayImage;
use rayon::prelude::*;

/// Compute global Otsu threshold on grayscale image
pub fn compute_otsu_threshold(img: &GrayImage) -> u8 {
    let mut hist = [0u64; 256];
    for &p in img.iter() {
        hist[p as usize] += 1;
    }

    let total = img.len() as f64;
    if total == 0.0 {
        return 128;
    }

    let mut sum = 0.0;
    for (i, &count) in hist.iter().enumerate() {
        sum += (i as f64) * (count as f64);
    }

    let mut sum_b = 0.0;
    let mut w_b = 0.0;
    let mut max_var = 0.0;
    let mut threshold = 128u8;

    for (t, &count) in hist.iter().enumerate() {
        w_b += count as f64;
        if w_b == 0.0 {
            continue;
        }
        let w_f = total - w_b;
        if w_f == 0.0 {
            break;
        }

        sum_b += (t as f64) * (count as f64);
        let m_b = sum_b / w_b;
        let m_f = (sum - sum_b) / w_f;

        let var_between = w_b * w_f * (m_b - m_f) * (m_b - m_f);
        if var_between > max_var {
            max_var = var_between;
            threshold = t as u8;
        }
    }

    threshold
}

/// Otsu binarization
pub fn binarize_otsu(img: &GrayImage) -> GrayImage {
    let threshold = compute_otsu_threshold(img);
    let (w, h) = img.dimensions();
    let mut out = GrayImage::new(w, h);

    out.par_chunks_mut(w as usize)
        .zip(img.par_chunks(w as usize))
        .for_each(|(out_row, in_row)| {
            for (out_p, &in_p) in out_row.iter_mut().zip(in_row.iter()) {
                *out_p = if in_p > threshold { 255 } else { 0 };
            }
        });

    out
}

/// Adaptive Sauvola binarization using Integral Images in O(1) per pixel
/// Optimal for text/math formulas with uneven illumination or degraded backgrounds
pub fn binarize_sauvola(img: &GrayImage, window_size: u32, k: f32) -> GrayImage {
    let (w, h) = img.dimensions();
    if w == 0 || h == 0 {
        return GrayImage::new(w, h);
    }

    let w_usize = w as usize;
    let h_usize = h as usize;

    // Build Integral Images S1 (sum) and S2 (squared sum) with 1-pixel padding
    let stride = w_usize + 1;
    let mut s1 = vec![0i64; (w_usize + 1) * (h_usize + 1)];
    let mut s2 = vec![0i64; (w_usize + 1) * (h_usize + 1)];

    for y in 0..h_usize {
        let mut row_s1 = 0i64;
        let mut row_s2 = 0i64;
        for x in 0..w_usize {
            let val = img.get_pixel(x as u32, y as u32).0[0] as i64;
            row_s1 += val;
            row_s2 += val * val;

            let prev_idx = y * stride + (x + 1);
            let curr_idx = (y + 1) * stride + (x + 1);

            s1[curr_idx] = s1[prev_idx] + row_s1;
            s2[curr_idx] = s2[prev_idx] + row_s2;
        }
    }

    let r = (window_size / 2) as i32;
    let mut out = GrayImage::new(w, h);

    // Process pixel rows in parallel using Rayon
    out.par_chunks_mut(w_usize)
        .enumerate()
        .for_each(|(y_idx, out_row)| {
            let y = y_idx as i32;
            let y1 = (y - r).max(0) as usize;
            let y2 = (y + r).min(h as i32 - 1) as usize;

            for x_idx in 0..w_usize {
                let x = x_idx as i32;
                let x1 = (x - r).max(0) as usize;
                let x2 = (x + r).min(w as i32 - 1) as usize;

                let count = ((x2 - x1 + 1) * (y2 - y1 + 1)) as f64;

                // Compute rectangular area sum from Integral Image in O(1)
                // Sum = S(y2+1, x2+1) - S(y1, x2+1) - S(y2+1, x1) + S(y1, x1)
                let idx_br = (y2 + 1) * stride + (x2 + 1);
                let idx_tr = y1 * stride + (x2 + 1);
                let idx_bl = (y2 + 1) * stride + x1;
                let idx_tl = y1 * stride + x1;

                let sum1 = (s1[idx_br] - s1[idx_tr] - s1[idx_bl] + s1[idx_tl]) as f64;
                let sum2 = (s2[idx_br] - s2[idx_tr] - s2[idx_bl] + s2[idx_tl]) as f64;

                let mean = sum1 / count;
                let variance = (sum2 / count) - (mean * mean);
                let stddev = if variance > 0.0 { variance.sqrt() } else { 0.0 };

                // Sauvola threshold formula: T = mean * (1 + k * (stddev / 128.0 - 1.0))
                let threshold = mean * (1.0 + (k as f64) * ((stddev / 128.0) - 1.0));

                let pixel_val = img.get_pixel(x_idx as u32, y_idx as u32).0[0] as f64;
                out_row[x_idx] = if pixel_val > threshold { 255 } else { 0 };
            }
        });

    out
}
