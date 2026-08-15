import Foundation
import Observation
import AppKit

/// Manages the production Python runtime lifecycle.
///
/// **Dev mode** (running from Xcode): detects an existing `.venv/` by walking up
/// from the bundle URL. In dev mode the state is immediately `.ready` — no setup needed.
///
/// **Production mode** (distributed .app): the venv lives at
/// `~/Library/Application Support/SundayAlbum/venv/`. On first launch the venv
/// doesn't exist; `SetupView` calls `startInstallation()` to bootstrap it.
///
/// All state mutations happen on `@MainActor` so SwiftUI observation works correctly.
@MainActor
@Observable
final class RuntimeManager {

    static let shared = RuntimeManager()

    // MARK: - Setup state

    enum SetupState: Equatable {
        case needsSetup     // venv absent — show SetupView
        case installing     // setup script running
        case ready          // venv present and usable
        case failed(String) // setup failed — error message to display

        static func == (lhs: SetupState, rhs: SetupState) -> Bool {
            switch (lhs, rhs) {
            case (.needsSetup, .needsSetup), (.installing, .installing), (.ready, .ready):
                return true
            case (.failed(let a), .failed(let b)):
                return a == b
            default:
                return false
            }
        }
    }

    /// Current state of the Python runtime.
    var setupState: SetupState

    /// Lines streamed from pip during installation.
    var installLog: [String] = []

    /// 0.0–1.0 estimated install progress.
    var installProgress: Double = 0.0

    private var setupProcess: Process?

    // MARK: - Path helpers

    /// Production venv root: `~/Library/Application Support/SundayAlbum/venv/`
    static var productionVenvURL: URL {
        appSupportBase.appendingPathComponent("venv")
    }

    static var productionPythonURL: URL {
        productionVenvURL.appendingPathComponent("bin/python")
    }

    static var appSupportBase: URL {
        FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("SundayAlbum")
    }

    /// Dev project root: walk up from the Xcode bundle looking for `.venv/`.
    /// Returns `nil` when running as a production `.app`.
    static var devProjectRoot: URL? {
        var url = Bundle.main.bundleURL
        for _ in 0..<8 {
            url = url.deletingLastPathComponent()
            if FileManager.default.fileExists(atPath: url.appendingPathComponent(".venv").path) {
                return url
            }
        }
        // Explicit fallback for the dev machine
        let fallback = URL(fileURLWithPath: "/Users/dev/dev/sundayalbum")
        if FileManager.default.fileExists(atPath: fallback.appendingPathComponent(".venv").path) {
            return fallback
        }
        return nil
    }

    /// `true` when running inside Xcode with a local `.venv/`.
    static var isDevBuild: Bool { devProjectRoot != nil }

    /// Absolute path to the Python interpreter the subprocess should use.
    var pythonURL: URL? {
        if let devRoot = Self.devProjectRoot {
            return devRoot.appendingPathComponent(".venv/bin/python")
        }
        let prod = Self.productionPythonURL
        return FileManager.default.fileExists(atPath: prod.path) ? prod : nil
    }

    /// Working directory for `python -m src.cli …` invocations.
    /// - Dev: project root (contains `src/` as a package on the Python path).
    /// - Production: bundle `Contents/Resources/` (where `src/` was copied).
    var cliWorkingDirectory: URL {
        if let devRoot = Self.devProjectRoot {
            return devRoot
        }
        return Bundle.main.resourceURL ?? URL(fileURLWithPath: NSTemporaryDirectory())
    }

    /// Extra `PYTHONPATH` to inject in production so the bundled `src/` is importable.
    /// Returns `nil` in dev (CWD already covers it).
    var extraPythonPath: String? {
        Self.isDevBuild ? nil : Bundle.main.resourceURL?.path
    }

    // MARK: - Init

    private init() {
        // Determine state synchronously so the first view render shows the correct screen.
        if Self.isDevBuild {
            setupState = .ready
        } else {
            let exists = FileManager.default.fileExists(atPath: Self.productionPythonURL.path)
            setupState = exists ? .ready : .needsSetup
        }
    }

    // MARK: - Installation

    /// Kick off the one-time setup. No-op if not in `.needsSetup` state.
    func startInstallation() {
        guard setupState == .needsSetup else { return }
        Task { await runSetup() }
    }

    /// Reset from `.failed` back to `.needsSetup` so the user can retry.
    func retrySetup() {
        installLog = []
        installProgress = 0
        setupState = .needsSetup
    }

    /// Abort the running install and delete any partial venv.
    func cancelInstallation() {
        setupProcess?.terminate()
        setupProcess = nil
        try? FileManager.default.removeItem(at: Self.productionVenvURL)
        installLog = []
        installProgress = 0
        setupState = .needsSetup
    }

    private func runSetup() async {
        setupState = .installing
        installLog = []
        installProgress = 0.0

        guard
            let scriptURL       = Bundle.main.url(forResource: "setup-runtime",         withExtension: "sh"),
            let requirementsURL = Bundle.main.url(forResource: "requirements-runtime",  withExtension: "txt")
        else {
            setupState = .failed("Setup resources not found in app bundle.\nPlease re-install Sunday Album.")
            return
        }

        // Ensure the parent Application Support directory exists.
        try? FileManager.default.createDirectory(at: Self.appSupportBase, withIntermediateDirectories: true)

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/bash")
        proc.arguments     = [scriptURL.path, Self.productionVenvURL.path, requirementsURL.path]

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError  = pipe      // merge stderr so errors appear in the log

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor [weak self] in self?.appendInstallLog(text) }
        }

        setupProcess = proc

        do {
            try proc.run()
        } catch {
            setupState = .failed("Failed to launch setup script: \(error.localizedDescription)")
            return
        }

        // Wait for completion off the main thread, then resume here.
        let exitCode: Int32 = await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                proc.waitUntilExit()
                continuation.resume(returning: proc.terminationStatus)
            }
        }

        pipe.fileHandleForReading.readabilityHandler = nil
        setupProcess = nil

        // Guard against cancel() having already changed state while we were waiting.
        guard setupState == .installing else { return }

        if exitCode == 0 {
            installProgress = 1.0
            setupState = .ready
        } else {
            setupState = .failed("Installation failed (exit \(exitCode)).\nSee the log above for details.")
            try? FileManager.default.removeItem(at: Self.productionVenvURL)
        }
    }

    private func appendInstallLog(_ text: String) {
        let lines = text
            .components(separatedBy: "\n")
            .map    { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        installLog.append(contentsOf: lines)

        // Rough progress: count Downloading + Successfully installed lines.
        // ~15 packages total; each "Downloading" ≈ 3%, each "Successfully installed" ≈ 5%.
        let downloads  = installLog.filter { $0.hasPrefix("Downloading") }.count
        let installed  = installLog.filter { $0.hasPrefix("Successfully installed") }.count
        let estimated  = Double(downloads) * 0.03 + Double(installed) * 0.50
        installProgress = min(estimated, 0.95)
    }

    // MARK: - Uninstall

    /// Shows a confirmation alert then removes all app data and quits.
    func promptAndUninstall() {
        let alert = NSAlert()
        alert.messageText     = "Uninstall Sunday Album?"
        alert.informativeText = """
            This will permanently remove:

            • Python runtime  (\u{007E}200 MB)
            • All processed photos
            • Debug images
            • App preferences and API keys

            Your original photos are not affected.
            """
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Uninstall")
        alert.addButton(withTitle: "Cancel")

        guard alert.runModal() == .alertFirstButtonReturn else { return }

        performUninstall()
    }

    private func performUninstall() {
        // Remove everything under ~/Library/Application Support/SundayAlbum/
        try? FileManager.default.removeItem(at: Self.appSupportBase)

        // Clear UserDefaults for this bundle
        if let bundleID = Bundle.main.bundleIdentifier {
            UserDefaults.standard.removePersistentDomain(forName: bundleID)
        }

        let done = NSAlert()
        done.messageText     = "All Data Removed"
        done.informativeText = "All Sunday Album data has been removed.\n\nDrag Sunday Album from Applications to Trash to complete uninstallation."
        done.alertStyle = .informational
        done.addButton(withTitle: "Quit Sunday Album")
        done.runModal()

        NSApp.terminate(nil)
    }
}
