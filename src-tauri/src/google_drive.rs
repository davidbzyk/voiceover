use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use rand::Rng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::path::Path;
use tauri::ipc::Channel;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DriveTokens {
    pub access_token: String,
    pub refresh_token: String,
    pub email: String,
    pub connected: bool,
    pub expires_at: u64,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase", tag = "event", content = "data")]
pub enum DriveEvent {
    Progress { percent: f32 },
    Complete { url: String },
    Error { message: String },
}

/// Generate a random code verifier for PKCE.
fn generate_code_verifier() -> String {
    let bytes: Vec<u8> = (0..32).map(|_| rand::thread_rng().gen()).collect();
    URL_SAFE_NO_PAD.encode(&bytes)
}

/// Create the S256 code challenge from a verifier.
fn code_challenge(verifier: &str) -> String {
    let hash = Sha256::digest(verifier.as_bytes());
    URL_SAFE_NO_PAD.encode(hash)
}

/// Start OAuth2 flow: open browser, listen for callback, exchange code for tokens.
#[tauri::command]
pub async fn google_drive_connect(client_id: String, client_secret: String) -> Result<DriveTokens, String> {
    let verifier = generate_code_verifier();
    let challenge = code_challenge(&verifier);

    // Find an available port for the loopback redirect
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let redirect_uri = format!("http://127.0.0.1:{port}");

    let auth_url = format!(
        "https://accounts.google.com/o/oauth2/v2/auth?\
        client_id={client_id}&\
        redirect_uri={redirect_uri}&\
        response_type=code&\
        scope=https://www.googleapis.com/auth/drive.file%20email&\
        code_challenge={challenge}&\
        code_challenge_method=S256&\
        access_type=offline&\
        prompt=consent",
    );

    // Open browser for consent
    open::that(&auth_url).map_err(|e| format!("Failed to open browser: {e}"))?;

    // Wait for the OAuth callback with a 120-second timeout
    use std::time::{Duration, Instant};
    listener.set_nonblocking(true).map_err(|e| e.to_string())?;
    let start = Instant::now();
    let timeout = Duration::from_secs(120);
    let (mut stream, _) = loop {
        match listener.accept() {
            Ok(conn) => break conn,
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                if start.elapsed() > timeout {
                    return Err("OAuth timed out — no callback received within 2 minutes".to_string());
                }
                std::thread::sleep(Duration::from_millis(200));
                continue;
            }
            Err(e) => return Err(format!("OAuth callback failed: {e}")),
        }
    };

    let mut reader = BufReader::new(&stream);
    let mut request_line = String::new();
    reader
        .read_line(&mut request_line)
        .map_err(|e| e.to_string())?;

    // Extract authorization code from the request
    let code = request_line
        .split_whitespace()
        .nth(1)
        .and_then(|path| url::Url::parse(&format!("http://localhost{path}")).ok())
        .and_then(|url| {
            url.query_pairs()
                .find(|(k, _)| k == "code")
                .map(|(_, v)| v.to_string())
        })
        .ok_or("No authorization code in callback")?;

    // Send success response to browser
    let response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n\
        <html><body style='font-family:sans-serif;text-align:center;padding:60px'>\
        <h2>Connected to Google Drive!</h2><p>You can close this tab.</p></body></html>";
    stream.write_all(response.as_bytes()).ok();

    // Exchange code for tokens
    let client = reqwest::Client::new();
    let token_response = client
        .post("https://oauth2.googleapis.com/token")
        .form(&[
            ("client_id", client_id.as_str()),
            ("client_secret", client_secret.as_str()),
            ("code", &code),
            ("code_verifier", &verifier),
            ("grant_type", "authorization_code"),
            ("redirect_uri", &redirect_uri),
        ])
        .send()
        .await
        .map_err(|e| format!("Token exchange failed: {e}"))?;

    if !token_response.status().is_success() {
        let body = token_response.text().await.unwrap_or_default();
        return Err(format!("Token exchange error: {body}"));
    }

    let token_data: serde_json::Value = token_response.json().await.map_err(|e| e.to_string())?;

    let access_token = token_data["access_token"]
        .as_str()
        .unwrap_or_default()
        .to_string();
    let refresh_token = token_data["refresh_token"]
        .as_str()
        .unwrap_or_default()
        .to_string();

    // Calculate token expiry (Google tokens last 3600s, subtract 60s buffer)
    let expires_in = token_data["expires_in"].as_u64().unwrap_or(3600);
    let expires_at = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        + expires_in
        - 60;

    // Get user email
    let email = get_user_email(&client, &access_token).await.unwrap_or_default();

    Ok(DriveTokens {
        access_token,
        refresh_token,
        email,
        connected: true,
        expires_at,
    })
}

async fn get_user_email(client: &reqwest::Client, access_token: &str) -> Result<String, String> {
    let resp = client
        .get("https://www.googleapis.com/oauth2/v2/userinfo")
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let data: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
    Ok(data["email"].as_str().unwrap_or("").to_string())
}

/// Refresh an expired access token.
pub async fn refresh_access_token(
    client_id: &str,
    client_secret: &str,
    refresh_token: &str,
) -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post("https://oauth2.googleapis.com/token")
        .form(&[
            ("client_id", client_id),
            ("client_secret", client_secret),
            ("refresh_token", refresh_token),
            ("grant_type", "refresh_token"),
        ])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let data: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
    data["access_token"]
        .as_str()
        .map(|s| s.to_string())
        .ok_or("No access token in refresh response".to_string())
}

/// Upload a file to Google Drive and return a shareable link.
#[tauri::command]
pub async fn upload_to_drive(
    access_token: String,
    file_path: String,
    on_event: Channel<DriveEvent>,
) -> Result<String, String> {
    let path = Path::new(&file_path);
    let filename = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("voiceover.mp4");

    let file_bytes = std::fs::read(path).map_err(|e| format!("Failed to read file: {e}"))?;

    on_event
        .send(DriveEvent::Progress { percent: 10.0 })
        .ok();

    let client = reqwest::Client::new();

    // Create file metadata
    let metadata = serde_json::json!({
        "name": filename,
        "mimeType": "video/mp4"
    });

    // Simple upload (for files under 5MB use simple, otherwise resumable)
    let response = client
        .post("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink")
        .bearer_auth(&access_token)
        .header("Content-Type", "multipart/related; boundary=voiceover_boundary")
        .body(build_multipart_body(&metadata.to_string(), &file_bytes, filename))
        .send()
        .await
        .map_err(|e| format!("Upload failed: {e}"))?;

    on_event
        .send(DriveEvent::Progress { percent: 80.0 })
        .ok();

    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        on_event
            .send(DriveEvent::Error {
                message: format!("Upload error: {body}"),
            })
            .ok();
        return Err(format!("Drive upload error: {body}"));
    }

    let file_data: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;
    let file_id = file_data["id"].as_str().unwrap_or_default();

    // Make file publicly readable
    client
        .post(format!(
            "https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
        ))
        .bearer_auth(&access_token)
        .json(&serde_json::json!({
            "type": "anyone",
            "role": "reader"
        }))
        .send()
        .await
        .ok();

    on_event
        .send(DriveEvent::Progress { percent: 95.0 })
        .ok();

    let share_link = file_data["webViewLink"]
        .as_str()
        .unwrap_or_default()
        .to_string();

    on_event
        .send(DriveEvent::Complete {
            url: share_link.clone(),
        })
        .ok();

    Ok(share_link)
}

fn build_multipart_body(metadata_json: &str, file_bytes: &[u8], _filename: &str) -> Vec<u8> {
    let mut body = Vec::new();
    // Metadata part
    body.extend_from_slice(b"--voiceover_boundary\r\n");
    body.extend_from_slice(b"Content-Type: application/json; charset=UTF-8\r\n\r\n");
    body.extend_from_slice(metadata_json.as_bytes());
    body.extend_from_slice(b"\r\n");
    // File part
    body.extend_from_slice(b"--voiceover_boundary\r\n");
    body.extend_from_slice(format!("Content-Type: video/mp4\r\n").as_bytes());
    body.extend_from_slice(b"\r\n");
    body.extend_from_slice(file_bytes);
    body.extend_from_slice(b"\r\n");
    body.extend_from_slice(b"--voiceover_boundary--\r\n");
    body
}

/// Disconnect Google Drive (just clears tokens, no API call needed).
#[tauri::command]
pub fn google_drive_disconnect() -> Result<(), String> {
    Ok(())
}
