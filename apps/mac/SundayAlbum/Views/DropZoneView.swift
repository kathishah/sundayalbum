import SwiftUI
import UniformTypeIdentifiers

struct DropZoneView: View {
    @Environment(AppState.self) private var appState
    @State private var isTargeted = false

    var body: some View {
        ZStack {
            Color.saAmber50

            VStack(spacing: 20) {
                ZStack {
                    Circle()
                        .fill(Color.saAmber100)
                        .frame(width: 88, height: 88)

                    Image(systemName: "photo.stack")
                        .font(.system(size: 38, weight: .light))
                        .foregroundStyle(Color.saAmber600)
                }
                .scaleEffect(isTargeted ? 1.12 : 1.0)
                .animation(.saSpring, value: isTargeted)

                VStack(spacing: 6) {
                    Text("Drop album page photos here")
                        .font(.fraunces(20, weight: .medium))
                        .foregroundStyle(Color.saStone700)

                    Text("HEIC · DNG · JPG · PNG")
                        .font(.dmSans(13))
                        .foregroundStyle(Color.saStone400)
                }

                Text("or")
                    .font(.dmSans(13))
                    .foregroundStyle(Color.saStone400)

                Button("Choose Files…") {
                    let urls = FileImporter.openPanel()
                    appState.addFiles(urls)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.saAmber500)
                .controlSize(.large)
                .font(.dmSans(15, weight: .medium))
            }

            // Dashed border
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(
                    isTargeted ? Color.saAmber500 : Color.saStone200,
                    style: StrokeStyle(lineWidth: 2, dash: [8, 5])
                )
                .padding(32)
                .animation(.saStandard, value: isTargeted)
        }
        .onDrop(of: [UTType.fileURL], isTargeted: $isTargeted) { providers in
            handleDrop(providers)
        }
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
