import SwiftUI
import AppKit

struct SettingsView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(AppState.self)    private var appState

    var body: some View {
        @Bindable var settings = settings
        Form {
            // ── API Keys ─────────────────────────────────────────────────────
            Section("API Keys") {
                APIKeyRow(
                    label: "Anthropic",
                    sublabel: "Required",
                    placeholder: "sk-ant-api03-...",
                    footnote: "Get a key at console.anthropic.com",
                    status: settings.anthropicKeyStatus,
                    loadKey:   { settings.anthropicKey() },
                    onSave:    { settings.saveAnthropicKey($0) },
                    onDelete:  { settings.deleteAnthropicKey() },
                    onTest:    { Task { await settings.testAnthropicKey() } }
                )

                APIKeyRow(
                    label: "OpenAI",
                    sublabel: "Optional",
                    placeholder: "sk-...",
                    footnote: "Get a key at platform.openai.com — enables higher-quality glare removal",
                    status: settings.openaiKeyStatus,
                    loadKey:   { settings.openaiKey() },
                    onSave:    { settings.saveOpenAIKey($0) },
                    onDelete:  { settings.deleteOpenAIKey() },
                    onTest:    { Task { await settings.testOpenAIKey() } }
                )

                Toggle("Use OpenCV fallback (skip OpenAI glare removal)", isOn: $settings.useOpenCVFallback)
                    .font(.dmSans(12))
                    .foregroundStyle(Color.saTextSecondary)
            }

            // ── Storage ───────────────────────────────────────────────────────
            Section("Storage") {
                FolderPickerRow(
                    label: "Output folder",
                    url: $settings.outputFolder,
                    defaultURL: AppSettings.defaultOutputFolder
                )

                // The debug folder is the library source: changing it reloads all jobs.
                FolderPickerRow(
                    label: "Debug folder",
                    footnote: "Processed images are loaded from this folder on every launch.",
                    url: $settings.debugFolder,
                    defaultURL: AppSettings.defaultDebugFolder,
                    onChange: { appState.reloadJobs() }
                )

                Toggle("Save debug images at each pipeline step", isOn: $settings.debugOutputEnabled)
            }
        }
        .formStyle(.grouped)
        .frame(width: 560)
        .padding(.vertical, 8)
    }
}

// MARK: - API Key Row

private struct APIKeyRow: View {
    let label: String
    let sublabel: String
    let placeholder: String
    let footnote: String
    let status: KeyStatus
    let loadKey: () -> String?
    let onSave: (String) -> Void
    let onDelete: () -> Void
    let onTest: () -> Void

    @State private var draft: String = ""
    @State private var originalKey: String = ""   // what was in Keychain when view appeared

    private var isDirty: Bool { draft != originalKey }
    private var canSave: Bool { isDirty && !draft.trimmingCharacters(in: .whitespaces).isEmpty }
    private var canTest: Bool { !isDirty && status != .absent && status != .testing }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .center, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(label)
                            .font(.dmSans(13, weight: .semibold))
                            .foregroundStyle(Color.saTextPrimary)
                        Text(sublabel)
                            .font(.dmSans(11))
                            .foregroundStyle(Color.saTextTertiary)
                    }
                }
                .frame(width: 100, alignment: .leading)

                TextField(placeholder, text: $draft)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity)

                Button("Test") { onTest() }
                    .disabled(!canTest)
                    .buttonStyle(.bordered)
                    .controlSize(.small)

                Button("Save") {
                    let trimmed = draft.trimmingCharacters(in: .whitespaces)
                    onSave(trimmed)
                    originalKey = trimmed
                    draft = trimmed
                    onTest()
                }
                .disabled(!canSave)
                .buttonStyle(.borderedProminent)
                .tint(Color.saAmber500)
                .controlSize(.small)

                Button("Discard") {
                    draft = originalKey
                }
                .disabled(!isDirty)
                .buttonStyle(.bordered)
                .controlSize(.small)
            }

            // Status badge + footnote
            HStack(spacing: 12) {
                KeyStatusBadge(status: status)
                Spacer()
                Text(footnote)
                    .font(.dmSans(11))
                    .foregroundStyle(Color.saTextTertiary)
            }
            .padding(.leading, 108)  // align under text field
        }
        .padding(.vertical, 4)
        .onAppear {
            let saved = loadKey() ?? ""
            draft = saved
            originalKey = saved
        }
    }
}

// MARK: - Key Status Badge

private struct KeyStatusBadge: View {
    let status: KeyStatus

    var body: some View {
        HStack(spacing: 4) {
            switch status {
            case .absent:
                Circle().fill(Color.saError).frame(width: 6, height: 6)
                Text("No key saved").foregroundStyle(Color.saError)
            case .untested:
                Circle().fill(Color.saStone400).frame(width: 6, height: 6)
                Text("Not tested").foregroundStyle(Color.saTextSecondary)
            case .testing:
                ProgressView().controlSize(.mini)
                Text("Testing…").foregroundStyle(Color.saAmber500)
            case .valid:
                Image(systemName: "checkmark.circle.fill").foregroundStyle(Color.saSuccess)
                Text("Valid").foregroundStyle(Color.saSuccess)
            case .invalid(let reason):
                Image(systemName: "xmark.circle.fill").foregroundStyle(Color.saError)
                Text("Invalid — \(reason)").foregroundStyle(Color.saError)
            }
        }
        .font(.dmSans(11, weight: .medium))
    }
}

// MARK: - Folder Picker Row

private struct FolderPickerRow: View {
    let label: String
    var footnote: String? = nil
    @Binding var url: URL
    let defaultURL: URL
    /// Called after the user picks a new folder or resets to the default.
    var onChange: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Text(label)
                    .font(.dmSans(13))
                    .frame(width: 100, alignment: .leading)

                Text(url.path)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(Color.saTextSecondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Button("Choose…") {
                    let panel = NSOpenPanel()
                    panel.canChooseFiles = false
                    panel.canChooseDirectories = true
                    panel.canCreateDirectories = true
                    panel.prompt = "Select"
                    if panel.runModal() == .OK, let chosen = panel.url {
                        url = chosen
                        onChange?()
                    }
                }
                .controlSize(.small)

                if url != defaultURL {
                    Button("Reset") {
                        url = defaultURL
                        onChange?()
                    }
                    .controlSize(.small)
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.saTextTertiary)
                }
            }

            if let note = footnote {
                Text(note)
                    .font(.dmSans(11))
                    .foregroundStyle(Color.saTextTertiary)
                    .padding(.leading, 108)
            }
        }
    }
}
