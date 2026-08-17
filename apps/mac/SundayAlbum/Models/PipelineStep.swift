import Foundation

enum PipelineStep: Int, CaseIterable, Identifiable {
    case load = 0
    case pageDetect
    case photoSplit
    case orientation
    case glareRemoval
    case colorCorrection
    case done

    var id: Int { rawValue }

    var title: String {
        switch self {
        case .load:            return "Load"
        case .pageDetect:      return "Page"
        case .photoSplit:      return "Split"
        case .orientation:     return "Orient"
        case .glareRemoval:    return "Glare"
        case .colorCorrection: return "Color"
        case .done:            return "Done"
        }
    }

    var description: String {
        switch self {
        case .load:            return "Loading and preparing image"
        case .pageDetect:      return "Detecting album page boundary — drag handles to adjust"
        case .photoSplit:      return "Detecting individual photos — adjust regions if needed"
        case .orientation:     return "Correcting photo orientation automatically"
        case .glareRemoval:    return "Removing glare from glossy surface — review the result"
        case .colorCorrection: return "Restoring colors, contrast, and sharpness"
        case .done:            return "Processing complete"
        }
    }

    var systemImage: String {
        switch self {
        case .load:            return "arrow.down.circle"
        case .pageDetect:      return "rectangle.dashed"
        case .photoSplit:      return "rectangle.split.3x1"
        case .orientation:     return "rotate.right"
        case .glareRemoval:    return "sparkles"
        case .colorCorrection: return "paintpalette"
        case .done:            return "checkmark.circle.fill"
        }
    }

    /// Steps where the AI result is shown and the user must confirm or manually correct
    var requiresReview: Bool {
        switch self {
        case .pageDetect, .photoSplit, .glareRemoval: return true
        default: return false
        }
    }

    var next: PipelineStep? { PipelineStep(rawValue: rawValue + 1) }

    // MARK: - Debug image mapping

    /// Returns the page-level or single-photo debug image for this step.
    ///
    /// Debug files live flat in `AppSettings.debugFolder` with the naming convention:
    ///   `{baseName}_{stepSuffix}`   e.g. `IMG_cave_normal_07_photo_01_deglared.jpg`
    @MainActor
    func debugImageURL(forInputName inputName: String) -> URL? {
        let baseName = (inputName as NSString).deletingPathExtension
        let suffix: String
        switch self {
        case .load:            suffix = "01_loaded.jpg"
        case .pageDetect:      suffix = "02_page_detected.jpg"
        case .photoSplit:      suffix = "04_photo_boundaries.jpg"
        case .orientation:     suffix = "05b_photo_01_oriented.jpg"
        case .glareRemoval:    suffix = "07_photo_01_deglared.jpg"
        case .colorCorrection: suffix = "13_photo_01_restored.jpg"
        case .done:            suffix = "14_photo_01_enhanced.jpg"
        }
        let url = AppSettings.shared.debugFolder.appendingPathComponent("\(baseName)_\(suffix)")
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }

    /// Returns the per-photo debug image for a given 1-based photo index.
    @MainActor
    func debugImageURL(forInputName inputName: String, photoIndex: Int) -> URL? {
        let baseName = (inputName as NSString).deletingPathExtension
        let idx = String(format: "%02d", photoIndex)
        switch self {
        case .load, .pageDetect, .photoSplit:
            return debugImageURL(forInputName: inputName)   // page-level image
        default: break
        }
        let suffix: String
        switch self {
        case .orientation:     suffix = "05b_photo_\(idx)_oriented.jpg"
        case .glareRemoval:    suffix = "07_photo_\(idx)_deglared.jpg"
        case .colorCorrection: suffix = "13_photo_\(idx)_restored.jpg"
        case .done:            suffix = "14_photo_\(idx)_enhanced.jpg"
        default:               return nil
        }
        let url = AppSettings.shared.debugFolder.appendingPathComponent("\(baseName)_\(suffix)")
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }
}

enum StepStatus: Equatable {
    case pending
    case running
    case awaitingReview   // AI done, user sees the result and must confirm or fix
    case complete
}
