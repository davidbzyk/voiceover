mod commands;
mod config;
mod elevenlabs;
mod ffmpeg;
mod google_drive;
mod local_tts;
mod models;
mod pipeline;
mod prerequisites;
mod secrets;
pub mod sidecar;
mod tts_provider;

use commands::recording;
use commands::window;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .build(),
            )?;

            // Check prerequisites on startup
            let ffmpeg_ok = prerequisites::check_ffmpeg();
            if !ffmpeg_ok {
                log::error!("ffmpeg not found on system PATH");
            }

            // Initialize sidecar state
            app.manage(sidecar::SidecarState::default());

            // Clean up stale recording artifacts from previous sessions (>1 hour old)
            commands::recording::cleanup_stale_recordings(
                std::time::Duration::from_secs(3600),
            );

            // Start TTS sidecar in background (don't block app launch)
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match sidecar::start_sidecar(&app_handle).await {
                    Ok(port) => log::info!("TTS sidecar started on port {}", port),
                    Err(e) => log::warn!("TTS sidecar not started: {} (local TTS unavailable)", e),
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            prerequisites::check_prerequisites,
            config::get_config,
            config::save_config,
            recording::save_recording_chunk,
            recording::finalize_recording,
            recording::get_temp_dir,
            recording::read_file_bytes,
            window::create_widget_window,
            window::close_widget_window,
            pipeline::process_recording,
            elevenlabs::test_api_key,
            local_tts::test_local_connection,
            local_tts::list_local_voices,
            local_tts::check_model_status,
            local_tts::extract_youtube_audio,
            local_tts::sidecar_fetch,
            local_tts::sidecar_upload,
            sidecar::get_sidecar_status,
            models::check_models_downloaded,
            models::download_model,
            models::get_models_disk_usage,
            google_drive::google_drive_connect,
            google_drive::google_drive_disconnect,
            google_drive::upload_to_drive,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
