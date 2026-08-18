import AppKit
import UniformTypeIdentifiers

/// Handles file selection via NSOpenPanel and resolves dropped/selected URLs
/// to a flat list of supported image files.
enum FileImporter {

    static let supportedExtensions: Set<String> = ["heic", "heif", "dng", "jpg", "jpeg", "png"]

    // MARK: - NSOpenPanel

    /// Shows a modal NSOpenPanel for file/folder selection.
    /// Returns resolved, supported image URLs (folders are expanded automatically).
    @MainActor
    static func openPanel() -> [URL] {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseFiles = true
        panel.canChooseDirectories = true
        panel.canCreateDirectories = false
        panel.message = "Select album page photos or a folder containing them"
        panel.prompt = "Add"
        // Allow any file/folder — we filter by extension ourselves so the user
        // can select a folder without the panel blocking it for "wrong type".
        panel.allowedContentTypes = []
        guard panel.runModal() == .OK else { return [] }
        return resolveURLs(panel.urls)
    }

    // MARK: - URL Resolution

    /// Expands folders recursively and filters to supported extensions.
    /// Input may be a mix of files and directories.
    static func resolveURLs(_ urls: [URL]) -> [URL] {
        var result: [URL] = []
        for url in urls {
            let canonical = url.standardizedFileURL
            var isDir: ObjCBool = false
            FileManager.default.fileExists(atPath: canonical.path, isDirectory: &isDir)
            if isDir.boolValue {
                result += walkFolder(canonical)
            } else if isSupportedFile(canonical) {
                result.append(canonical)
            }
        }
        return result
    }

    /// Returns whether a URL points to a file with a supported image extension.
    static func isSupportedFile(_ url: URL) -> Bool {
        supportedExtensions.contains(url.pathExtension.lowercased())
    }

    // MARK: - Private

    private static func walkFolder(_ folder: URL) -> [URL] {
        guard let enumerator = FileManager.default.enumerator(
            at: folder,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return [] }
        return enumerator
            .compactMap { $0 as? URL }
            .map { $0.standardizedFileURL }
            .filter { isSupportedFile($0) }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }
}

// MARK: - NSItemProvider async helper

extension NSItemProvider {
    /// Loads a file URL from a drop provider asynchronously.
    func loadFileURL() async -> URL? {
        await withCheckedContinuation { continuation in
            self.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let data = item as? Data,
                   let url = URL(dataRepresentation: data, relativeTo: nil) {
                    continuation.resume(returning: url)
                } else {
                    continuation.resume(returning: nil)
                }
            }
        }
    }
}
