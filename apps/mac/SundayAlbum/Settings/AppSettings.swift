import Foundation
import Observation

enum KeyStatus: Equatable {
    case absent
    case untested
    case testing
    case valid
    case invalid(String)   // API error message
}

@MainActor
@Observable
final class AppSettings {
    static let shared = AppSettings()

    // MARK: - Key statuses (in-memory, reflect Keychain state)

    var anthropicKeyStatus: KeyStatus = .absent
    var openaiKeyStatus: KeyStatus = .absent

    // MARK: - Storage (UserDefaults)

    private let defaults = UserDefaults.standard

    var outputFolder: URL {
        get {
            defaults.string(forKey: "outputFolder")
                .map { URL(fileURLWithPath: $0) } ?? Self.defaultOutputFolder
        }
        set { defaults.set(newValue.path, forKey: "outputFolder") }
    }

    var debugFolder: URL {
        get {
            defaults.string(forKey: "debugFolder")
                .map { URL(fileURLWithPath: $0) } ?? Self.defaultDebugFolder
        }
        set { defaults.set(newValue.path, forKey: "debugFolder") }
    }

    var debugOutputEnabled: Bool {
        get { defaults.bool(forKey: "debugOutputEnabled") }
        set { defaults.set(newValue, forKey: "debugOutputEnabled") }
    }

    /// When true, CLI is called with --no-openai-glare (uses OpenCV fallback).
    var useOpenCVFallback: Bool {
        get { defaults.bool(forKey: "useOpenCVFallback") }
        set { defaults.set(newValue, forKey: "useOpenCVFallback") }
    }

    /// True when processing is allowed. Untested/testing keys are treated optimistically —
    /// only .absent and .invalid block the pipeline.
    var canProcess: Bool {
        switch anthropicKeyStatus {
        case .absent, .invalid: return false
        default: return true
        }
    }

    // MARK: - Default paths

    static var defaultOutputFolder: URL {
        appSupportBase.appendingPathComponent("output")
    }

    static var defaultDebugFolder: URL {
        // In dev builds, default to the project's own debug/ folder so the library
        // is populated automatically without any configuration.
        if let devRoot = RuntimeManager.devProjectRoot {
            return devRoot.appendingPathComponent("debug")
        }
        return appSupportBase.appendingPathComponent("debug")
    }

    private static var appSupportBase: URL {
        FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("SundayAlbum")
    }

    // MARK: - Init

    init() {
        if SettingsStorage.load(key: "ANTHROPIC_API_KEY") != nil {
            anthropicKeyStatus = .untested
        }
        if SettingsStorage.load(key: "OPENAI_API_KEY") != nil {
            openaiKeyStatus = .untested
        }
    }

    // MARK: - Key accessors (read raw value for subprocess injection)

    func anthropicKey() -> String? { SettingsStorage.load(key: "ANTHROPIC_API_KEY") }
    func openaiKey() -> String?    { SettingsStorage.load(key: "OPENAI_API_KEY") }

    // MARK: - Save / delete

    func saveAnthropicKey(_ key: String) {
        SettingsStorage.save(key: "ANTHROPIC_API_KEY", value: key)
        anthropicKeyStatus = .untested
    }

    func saveOpenAIKey(_ key: String) {
        SettingsStorage.save(key: "OPENAI_API_KEY", value: key)
        openaiKeyStatus = .untested
    }

    func deleteAnthropicKey() {
        SettingsStorage.delete(key: "ANTHROPIC_API_KEY")
        anthropicKeyStatus = .absent
    }

    func deleteOpenAIKey() {
        SettingsStorage.delete(key: "OPENAI_API_KEY")
        openaiKeyStatus = .absent
    }

    // MARK: - API key tests (direct URLSession — no subprocess)

    func testAnthropicKey() async {
        guard let key = anthropicKey(), !key.isEmpty else {
            anthropicKeyStatus = .absent
            return
        }
        anthropicKeyStatus = .testing
        do {
            var req = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
            req.httpMethod = "POST"
            req.setValue(key,          forHTTPHeaderField: "x-api-key")
            req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let body: [String: Any] = [
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [["role": "user", "content": "hi"]]
            ]
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
            let (_, response) = try await URLSession.shared.data(for: req)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            // 200 = success; 400 = malformed but authenticated; 429 = rate-limited but valid
            anthropicKeyStatus = (code == 401) ? .invalid("Invalid API key") :
                                 (code >= 200 && code < 500) ? .valid :
                                 .invalid("HTTP \(code)")
        } catch {
            anthropicKeyStatus = .invalid(error.localizedDescription)
        }
    }

    func testOpenAIKey() async {
        guard let key = openaiKey(), !key.isEmpty else {
            openaiKeyStatus = .absent
            return
        }
        openaiKeyStatus = .testing
        do {
            var req = URLRequest(url: URL(string: "https://api.openai.com/v1/models")!)
            req.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            let (_, response) = try await URLSession.shared.data(for: req)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            openaiKeyStatus = (code == 401) ? .invalid("Invalid API key") :
                              (code == 200) ? .valid :
                              .invalid("HTTP \(code)")
        } catch {
            openaiKeyStatus = .invalid(error.localizedDescription)
        }
    }
}
