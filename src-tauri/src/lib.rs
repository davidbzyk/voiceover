mod commands;
mod config;
mod elevenlabs;
mod ffmpeg;
mod google_drive;
mod pipeline;
mod prerequisites;

use commands::recording;
use commands::window;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Check prerequisites on startup
            let ffmpeg_ok = prerequisites::check_ffmpeg();
            if !ffmpeg_ok {
                log::error!("ffmpeg not found on system PATH");
            }

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
            google_drive::google_drive_connect,
            google_drive::google_drive_disconnect,
            google_drive::upload_to_drive,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
