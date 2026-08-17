import SwiftUI

@main
struct SundayAlbumApp: App {

    @State private var appState: AppState = {
        #if DEBUG
        // Set MOCK_DATA=1 in the scheme's environment variables to use mock data during UI work.
        if ProcessInfo.processInfo.environment["MOCK_DATA"] == "1" {
            return AppState.withMockData()
        }
        #endif
        return AppState()
    }()

    private let appSettings = AppSettings.shared
    private let runtime     = RuntimeManager.shared

    var body: some Scene {
        WindowGroup {
            // Gate on setup: show SetupView until the Python runtime is installed,
            // then transition to the full app. In dev mode RuntimeManager.setupState
            // is immediately .ready so SetupView is never shown.
            Group {
                if runtime.setupState == .ready {
                    ContentView()
                        .environment(appState)
                        .environment(appSettings)
                        .task {
                            // Silently re-validate saved keys on every launch so status
                            // resolves before the user tries to process anything.
                            if appSettings.anthropicKey() != nil {
                                await appSettings.testAnthropicKey()
                            }
                            if appSettings.openaiKey() != nil {
                                await appSettings.testOpenAIKey()
                            }
                        }
                        .transition(.opacity.animation(.saStandard))
                } else {
                    SetupView()
                        .transition(.opacity.animation(.saStandard))
                }
            }
            .environment(runtime)
            .animation(.saStandard, value: runtime.setupState == .ready)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1280, height: 760)

        // ⌘, opens this automatically on macOS
        Settings {
            SettingsView()
                .environment(appSettings)
                .environment(appState)
        }

        // Help menu additions
        .commands {
            CommandGroup(replacing: .appInfo) {
                Button("About Sunday Album") {
                    NSApp.orderFrontStandardAboutPanel(options: [
                        NSApplication.AboutPanelOptionKey.applicationVersion: "1.0 (Built: \(BuildInfo.buildDate))"
                    ])
                }
            }
            CommandGroup(after: .help) {
                Divider()
                Button("Uninstall Sunday Album…") {
                    RuntimeManager.shared.promptAndUninstall()
                }
            }
        }
    }
}
