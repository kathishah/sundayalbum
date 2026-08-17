import Foundation

/// Persists per-photo user overrides (rotationOverride, sceneDescription) across app launches.
///
/// Storage: `~/Library/Application Support/SundayAlbum/overrides.json`
///
/// Key format: `"inputName:photoIndex"` — e.g. `"IMG_cave_normal.HEIC:1"`.
/// Only non-nil / non-empty values are written to disk; entries are removed automatically
/// when both fields are cleared.
struct OverridesStore {

    // MARK: - Types

    struct PhotoOverrides: Codable {
        var rotationOverride: Int?
        var sceneDescription: String?

        var isEmpty: Bool {
            rotationOverride == nil &&
            (sceneDescription == nil || sceneDescription!.isEmpty)
        }
    }

    // MARK: - File location

    /// Computed directly (not via RuntimeManager) so this struct stays nonisolated
    /// and can be called from any context without requiring @MainActor.
    static var fileURL: URL {
        FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("SundayAlbum")
            .appendingPathComponent("overrides.json")
    }

    // MARK: - Key helpers

    static func key(inputName: String, photoIndex: Int) -> String {
        "\(inputName):\(photoIndex)"
    }

    static func key(for photo: ExtractedPhoto) -> String {
        key(inputName: photo.jobInputName, photoIndex: photo.photoIndex)
    }

    // MARK: - Load / Save

    static func load() -> [String: PhotoOverrides] {
        guard let data = try? Data(contentsOf: fileURL),
              let map  = try? JSONDecoder().decode([String: PhotoOverrides].self, from: data)
        else { return [:] }
        return map
    }

    private static func save(_ map: [String: PhotoOverrides]) {
        // Filter out empty entries before writing
        let filtered = map.filter { !$0.value.isEmpty }
        guard let data = try? JSONEncoder().encode(filtered) else { return }
        let dir = fileURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try? data.write(to: fileURL, options: .atomic)
    }

    // MARK: - Apply on startup

    /// Read overrides from disk and apply them to all extracted photos in the job list.
    /// Call once after `DebugFolderScanner.loadJobs()` on every app launch and reload.
    static func apply(to jobs: [ProcessingJob]) {
        let map = load()
        guard !map.isEmpty else { return }
        for job in jobs {
            for photo in job.extractedPhotos {
                let k = key(for: photo)
                guard let overrides = map[k] else { continue }
                photo.rotationOverride = overrides.rotationOverride
                photo.sceneDescription = overrides.sceneDescription
            }
        }
    }

    // MARK: - Update on user action

    /// Persist a single photo's current overrides.
    /// Call whenever the user commits a change to `rotationOverride` or `sceneDescription`.
    static func update(for photo: ExtractedPhoto) {
        var map = load()
        let k = key(for: photo)
        let overrides = PhotoOverrides(
            rotationOverride: photo.rotationOverride,
            sceneDescription: photo.sceneDescription
        )
        if overrides.isEmpty {
            map.removeValue(forKey: k)
        } else {
            map[k] = overrides
        }
        save(map)
    }
}
