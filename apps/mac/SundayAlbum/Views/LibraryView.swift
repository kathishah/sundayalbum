import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @Environment(AppState.self) private var appState
    @Environment(AppSettings.self) private var appSettings
    @State private var isDropTargeted = false

    let columns = [GridItem(.adaptive(minimum: 280, maximum: 400), spacing: 16)]

    var body: some View {
        ZStack {
            // ── Scrollable grid ──────────────────────────────────────────────
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {

                    // ── API key banner (shown when Anthropic key is missing/invalid) ──
                    if !appSettings.canProcess {
                        APIKeyBanner()
                            .padding(.horizontal, 32)
                            .padding(.top, 20)
                    }

                    // Header
                    HStack(alignment: .center) {
                        Text("Library")
                            .font(.fraunces(32, weight: .semibold))
                            .foregroundStyle(Color.saTextPrimary)
                        Spacer()
                        Button {
                            let urls = FileImporter.openPanel()
                            appState.addFiles(urls)
                        } label: {
                            Label("Add Photos", systemImage: "plus")
                                .font(.dmSans(13, weight: .medium))
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.saAmber500)
                        .controlSize(.regular)
                        .keyboardShortcut("o", modifiers: .command)
                    }
                    .padding(.horizontal, 32)
                    .padding(.top, 32)
                    .padding(.bottom, 24)

                    if appState.jobs.isEmpty {
                        DropZoneView()
                            .frame(height: 320)
                            .padding(.horizontal, 32)
                    } else {
                        LazyVGrid(columns: columns, spacing: 16) {
                            ForEach(appState.jobs) { job in
                                AlbumPageCard(job: job)
                                    .opacity(appState.expandedJobID != nil && job.id != appState.expandedJobID ? 0.3 : 1.0)
                                    .scaleEffect(appState.expandedJobID != nil && job.id != appState.expandedJobID ? 0.95 : 1.0)
                                    .animation(.saSpring, value: appState.expandedJobID)
                                    .onTapGesture(count: 2) {
                                        withAnimation(.saSlide) {
                                            appState.navigate(to: .stepDetail(jobID: job.id))
                                        }
                                    }
                                    .onTapGesture(count: 1) {
                                        withAnimation(.saSpring) {
                                            appState.expandedJobID = (appState.expandedJobID == job.id) ? nil : job.id
                                        }
                                    }
                            }
                        }
                        .padding(.horizontal, 32)
                        .padding(.bottom, 40)
                    }
                }
            }
            .blur(radius: appState.expandedJobID != nil ? 3 : 0)
            .animation(.saStandard, value: appState.expandedJobID)

            // ── Expanded card overlay ────────────────────────────────────────
            if let jobID = appState.expandedJobID,
               let job = appState.jobFor(id: jobID) {

                // Dim backdrop — tap to dismiss
                Color.black.opacity(0.5)
                    .ignoresSafeArea()
                    .onTapGesture {
                        withAnimation(.saSpring) { appState.expandedJobID = nil }
                    }

                ExpandedAlbumCard(job: job) {
                    appState.navigate(to: .stepDetail(jobID: job.id))
                }
                .frame(maxWidth: 640)
                .padding(48)
                .transition(.scale(scale: 0.94).combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.saBackground)
        .overlay(alignment: .bottomTrailing) {
            Text("build \(BuildInfo.buildDate)")
                .font(.system(size: 10, weight: .regular, design: .monospaced))
                .foregroundStyle(Color.secondary.opacity(0.5))
                .padding(8)
        }
        // Drop target — active even when grid is populated (not just on DropZoneView)
        .onDrop(of: [UTType.fileURL], isTargeted: $isDropTargeted) { providers in
            handleDrop(providers)
        }
        .overlay {
            if isDropTargeted {
                RoundedRectangle(cornerRadius: 0)
                    .strokeBorder(Color.saAmber500, lineWidth: 3)
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }
        }
        .animation(.saStandard, value: isDropTargeted)
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        guard !providers.isEmpty else { return false }
        Task { @MainActor in
            var dropped: [URL] = []
            for provider in providers {
                if let url = await provider.loadFileURL() {
                    dropped.append(url)
                }
            }
            let resolved = FileImporter.resolveURLs(dropped)
            appState.addFiles(resolved)
        }
        return true
    }
}

// MARK: - API Key Banner

private struct APIKeyBanner: View {
    @Environment(AppSettings.self) private var appSettings
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "key.fill")
                .foregroundStyle(Color.saAmber600)
                .font(.system(size: 13))

            Text(bannerText)
                .font(.dmSans(12, weight: .medium))
                .foregroundStyle(Color.saAmber700)

            Spacer()

            Button("Open Settings →") {
                openSettings()
            }
            .buttonStyle(.plain)
            .font(.dmSans(12, weight: .semibold))
            .foregroundStyle(Color.saAmber600)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.saAmber100)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(Color.saAmber200, lineWidth: 1)
        }
    }

    private var bannerText: String {
        switch appSettings.anthropicKeyStatus {
        case .absent:   return "Add your Anthropic API key to start processing photos."
        case .invalid:  return "Anthropic API key is invalid — update it in Settings to resume processing."
        default:        return "Anthropic API key required to process photos."
        }
    }
}
