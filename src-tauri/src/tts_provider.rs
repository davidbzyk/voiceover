use serde::{Deserialize, Serialize};

/// Which TTS provider to use for voice transformation.
#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub enum Provider {
    #[default]
    #[serde(rename = "elevenlabs")]
    ElevenLabs,
    #[serde(rename = "local")]
    Local,
}

impl Provider {
    /// Return the string tag that matches the serde serialization.
    #[allow(dead_code)]
    pub fn as_str(&self) -> &'static str {
        match self {
            Provider::ElevenLabs => "elevenlabs",
            Provider::Local => "local",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_provider_is_elevenlabs() {
        assert_eq!(Provider::default(), Provider::ElevenLabs);
    }

    #[test]
    fn serializes_elevenlabs_as_lowercase() {
        let json = serde_json::to_string(&Provider::ElevenLabs).unwrap();
        assert_eq!(json, "\"elevenlabs\"");
    }

    #[test]
    fn serializes_local_as_lowercase() {
        let json = serde_json::to_string(&Provider::Local).unwrap();
        assert_eq!(json, "\"local\"");
    }

    #[test]
    fn deserializes_elevenlabs_from_lowercase() {
        let provider: Provider = serde_json::from_str("\"elevenlabs\"").unwrap();
        assert_eq!(provider, Provider::ElevenLabs);
    }

    #[test]
    fn deserializes_local_from_lowercase() {
        let provider: Provider = serde_json::from_str("\"local\"").unwrap();
        assert_eq!(provider, Provider::Local);
    }

    #[test]
    fn as_str_matches_serialization() {
        assert_eq!(Provider::ElevenLabs.as_str(), "elevenlabs");
        assert_eq!(Provider::Local.as_str(), "local");
    }
}
