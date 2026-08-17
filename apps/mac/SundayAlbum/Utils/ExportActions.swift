import AppKit
import Photos

/// Stateless export helpers shared across views.
enum ExportActions {

    // MARK: - Show in Finder

    /// Reveals the file in Finder and selects it.
    @MainActor
    static func showInFinder(_ url: URL) {
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    // MARK: - Add to Photos

    /// Saves the image at `url` to the user's Photos library.
    /// Requests authorization if not yet granted.
    static func addToPhotos(url: URL) async {
        let status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        guard status == .authorized || status == .limited else { return }
        try? await PHPhotoLibrary.shared().performChanges {
            PHAssetChangeRequest.creationRequestForAssetFromImage(atFileURL: url)
        }
    }

    // MARK: - Export to folder

    /// Opens a folder picker and copies `photos` into the chosen directory.
    /// After copying, reveals the exported files in Finder.
    @MainActor
    static func exportToFolder(_ photos: [ExtractedPhoto]) {
        guard !photos.isEmpty else { return }

        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.prompt = "Export Here"
        panel.message = "Choose a folder to save the exported photos"
        guard panel.runModal() == .OK, let dest = panel.url else { return }

        var exported: [URL] = []
        for photo in photos {
            let dst = dest.appendingPathComponent(photo.imageURL.lastPathComponent)
            // Overwrite if already present
            try? FileManager.default.removeItem(at: dst)
            if (try? FileManager.default.copyItem(at: photo.imageURL, to: dst)) != nil {
                exported.append(dst)
            }
        }
        if !exported.isEmpty {
            NSWorkspace.shared.activateFileViewerSelecting(exported)
        }
    }
}
