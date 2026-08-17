import Foundation

/// Reads API keys from secrets.json at the project root.
/// Falls back to environment variables if the file is absent or a key is missing.
struct SecretsLoader {

    /// Loaded key map, e.g. ["ANTHROPIC_API_KEY": "sk-ant-...", "OPENAI_API_KEY": "sk-..."]
    private let keys: [String: String]

    /// Loads secrets from `projectRoot/secrets.json`.
    /// - Parameter projectRoot: Directory that contains `secrets.json` and `.venv/`.
    init(projectRoot: URL) {
        let file = projectRoot.appendingPathComponent("secrets.json")
        var loaded: [String: String] = [:]

        if let data = try? Data(contentsOf: file),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: String] {
            loaded = json
        }

        // Merge environment variables as fallback (file wins if both present)
        for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"] {
            if loaded[key] == nil, let envVal = ProcessInfo.processInfo.environment[key], !envVal.isEmpty {
                loaded[key] = envVal
            }
        }

        self.keys = loaded
    }

    /// Returns the value for a given key.
    /// Read order: Keychain (user-entered in Settings) → secrets.json (dev) → env vars.
    func value(for key: String) -> String? {
        SettingsStorage.load(key: key) ?? keys[key]
    }

    /// Builds the environment dictionary to inject into a subprocess.
    ///
    /// Priority (highest → lowest):
    /// 1. Keys stored via `AppSettings` / `SettingsStorage` (user entered in ⌘, Settings)
    /// 2. Keys from `secrets.json` at the project root  (dev convenience file)
    /// 3. Inherited process environment variables
    func environment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        // Layer 2: secrets.json (dev)
        for (k, v) in keys { env[k] = v }
        // Layer 1: user-configured keys from Settings take priority over secrets.json
        for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"] {
            if let stored = SettingsStorage.load(key: key), !stored.isEmpty {
                env[key] = stored
            }
        }
        env["PYTHONUNBUFFERED"] = "1"
        return env
    }
}
