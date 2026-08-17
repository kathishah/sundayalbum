import SwiftUI

struct ContentView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        Group {
            switch appState.currentScreen {
            case .library:
                LibraryView()
                    .transition(.asymmetric(
                        insertion: .move(edge: .leading).combined(with: .opacity),
                        removal:   .move(edge: .leading).combined(with: .opacity)
                    ))

            case .stepDetail(let jobID):
                if let job = appState.jobFor(id: jobID) {
                    StepDetailView(job: job)
                        .transition(.asymmetric(
                            insertion: .move(edge: .trailing).combined(with: .opacity),
                            removal:   .move(edge: .trailing).combined(with: .opacity)
                        ))
                }
            }
        }
        .frame(minWidth: 960, minHeight: 640)
        .animation(.saSlide, value: appState.currentScreen)
    }
}
