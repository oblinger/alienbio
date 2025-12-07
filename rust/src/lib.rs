// Alien Biology Rust Simulator
// Placeholder - to be implemented in Milestone 12

use pyo3::prelude::*;

/// A Python module implemented in Rust.
#[pymodule]
fn alienbio_sim(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add("__version__", "0.1.0")?;
    Ok(())
}
