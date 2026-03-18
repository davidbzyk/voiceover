use tauri::Manager;

#[tauri::command]
pub async fn create_widget_window(app: tauri::AppHandle) -> Result<(), String> {
    // Check if widget already exists
    if app.get_webview_window("widget").is_some() {
        return Ok(());
    }

    tauri::WebviewWindowBuilder::new(&app, "widget", tauri::WebviewUrl::App("/widget".into()))
        .title("Recording")
        .inner_size(340.0, 80.0)
        .resizable(false)
        .decorations(false)
        .always_on_top(true)
        .center()
        .build()
        .map_err(|e: tauri::Error| e.to_string())?;

    Ok(())
}

#[tauri::command]
pub async fn close_widget_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("widget") {
        window.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}
