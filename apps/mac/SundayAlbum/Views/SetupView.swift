import SwiftUI

/// Full-window first-launch screen shown when the production Python venv hasn't been
/// installed yet.  Walks the user through the one-time ~200 MB download.
///
/// Shown by `SundayAlbumApp` when `RuntimeManager.setupState != .ready`.
struct SetupView: View {

    @Environment(RuntimeManager.self) private var runtime

    var body: some View {
        ZStack {
            Color.saBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // ── Branding ──────────────────────────────────────────────────
                VStack(spacing: 6) {
                    Text("Sunday Album")
                        .font(.fraunces(40, weight: .semibold))
                        .foregroundStyle(Color.saTextPrimary)

                    Text("One-time setup")
                        .font(.dmSans(17))
                        .foregroundStyle(Color.saTextSecondary)
                }

                // ── State-specific body ───────────────────────────────────────
                Group {
                    switch runtime.setupState {
                    case .needsSetup:
                        NeedsSetupBody()
                    case .installing:
                        InstallingBody()
                    case .failed(let message):
                        FailedBody(message: message)
                    case .ready:
                        // Transition handled by SundayAlbumApp — nothing to show here.
                        EmptyView()
                    }
                }
                .padding(.top, 40)

                Spacer()
            }
            .frame(maxWidth: 540)
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Needs Setup ──────────────────────────────────────────────────────────

private struct NeedsSetupBody: View {
    @Environment(RuntimeManager.self) private var runtime

    var body: some View {
        VStack(spacing: 28) {
            VStack(spacing: 12) {
                Text(
                    "Sunday Album needs to download its Python image-processing engine " +
                    "(≈\u{00A0}200\u{00A0}MB). " +
                    "This happens once — future launches start instantly."
                )
                .font(.dmSans(15))
                .foregroundStyle(Color.saTextSecondary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)

                Text("An internet connection is required.")
                    .font(.dmSans(13))
                    .foregroundStyle(Color.saTextTertiary)
            }

            Button {
                runtime.startInstallation()
            } label: {
                Text("Set Up Sunday Album")
                    .font(.dmSans(16, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 28)
                    .padding(.vertical, 13)
                    .background(Color.saAmber500)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Installing ───────────────────────────────────────────────────────────

private struct InstallingBody: View {
    @Environment(RuntimeManager.self) private var runtime

    var body: some View {
        VStack(spacing: 20) {

            // Progress bar
            VStack(spacing: 8) {
                ProgressView(value: runtime.installProgress)
                    .progressViewStyle(.linear)
                    .tint(Color.saAmber500)
                    .frame(width: 420)

                Text(progressLabel)
                    .font(.dmSans(13))
                    .foregroundStyle(Color.saTextSecondary)
            }

            // Scrollable pip output
            ScrollViewReader { proxy in
                ScrollView(.vertical) {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(runtime.installLog.enumerated()), id: \.offset) { _, line in
                            Text(line)
                                .font(.jetbrainsMono(11))
                                .foregroundStyle(Color.saTextTertiary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        // Invisible anchor for auto-scroll
                        Color.clear.frame(height: 1).id("log-bottom")
                    }
                    .padding(12)
                }
                .background(Color.saCard)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.saBorder, lineWidth: 1)
                )
                .frame(width: 460, height: 210)
                .onChange(of: runtime.installLog.count) {
                    withAnimation(.saStandard) {
                        proxy.scrollTo("log-bottom")
                    }
                }
            }

            Button("Cancel") {
                runtime.cancelInstallation()
            }
            .font(.dmSans(13))
            .foregroundStyle(Color.saTextSecondary)
            .buttonStyle(.plain)
        }
    }

    private var progressLabel: String {
        let pct = Int(runtime.installProgress * 100)
        switch pct {
        case 0..<5:   return "Starting…"
        case 5..<95:  return "Installing packages… \(pct)%"
        default:      return "Almost done…"
        }
    }
}

// MARK: - Failed ──────────────────────────────────────────────────────────────

private struct FailedBody: View {
    let message: String
    @Environment(RuntimeManager.self) private var runtime

    var body: some View {
        VStack(spacing: 20) {

            // Error header
            VStack(spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 34))
                    .foregroundStyle(Color.saError)

                Text("Setup failed")
                    .font(.dmSans(17, weight: .semibold))
                    .foregroundStyle(Color.saTextPrimary)

                Text(message)
                    .font(.dmSans(13))
                    .foregroundStyle(Color.saTextSecondary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }

            // Last install log (if any)
            if !runtime.installLog.isEmpty {
                ScrollView(.vertical) {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(runtime.installLog.suffix(60).enumerated()), id: \.offset) { _, line in
                            Text(line)
                                .font(.jetbrainsMono(11))
                                .foregroundStyle(Color.saTextTertiary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding(12)
                }
                .background(Color.saCard)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.saBorder, lineWidth: 1)
                )
                .frame(width: 460, height: 150)
            }

            Button {
                runtime.retrySetup()
            } label: {
                Text("Try Again")
                    .font(.dmSans(16, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 28)
                    .padding(.vertical, 13)
                    .background(Color.saAmber500)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Preview ─────────────────────────────────────────────────────────────

#Preview("Needs Setup") {
    SetupView()
        .environment(RuntimeManager.shared)
        .frame(width: 760, height: 540)
}
