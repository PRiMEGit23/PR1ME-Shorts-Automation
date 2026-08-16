//! IPC commands — thin, stateless bridges to engine artifacts.

pub mod app;
pub mod layout;
pub mod process;
pub mod providers;
pub mod settings;

use serde::Serialize;

/// `{ok}` ack for mutating commands (IPC contract, PRODUCT_LAYER §6).
#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct OkPayload {
    pub ok: bool,
}