import Foundation

/// File-based key/value store backed by a JSON file in Application Support.
/// Replaces Keychain for API key storage — simpler and fully transparent to the user.
///
/// File location: ~/Library/Application Support/SundayAlbum/settings.json
enum SettingsStorage {
    private static var fileURL: URL {
        let base = FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("SundayAlbum")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base.appendingPathComponent("settings.json")
    }

    // MARK: - Public API

    static func save(key: String, value: String) {
        var dict = load()
        dict[key] = value
        write(dict)
    }

    static func load(key: String) -> String? {
        load()[key]
    }

    static func delete(key: String) {
        var dict = load()
        dict.removeValue(forKey: key)
        write(dict)
    }

    // MARK: - Private

    private static func load() -> [String: String] {
        guard let data = try? Data(contentsOf: fileURL),
              let dict = try? JSONDecoder().decode([String: String].self, from: data) else {
            return [:]
        }
        return dict
    }

    private static func write(_ dict: [String: String]) {
        guard let data = try? JSONEncoder().encode(dict) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
