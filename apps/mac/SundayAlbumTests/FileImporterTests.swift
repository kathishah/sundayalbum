import Testing
import Foundation
@testable import SundayAlbum

@Suite("FileImporter")
struct FileImporterTests {

    // MARK: - isSupportedFile

    @Test("accepts supported extensions case-insensitively")
    func acceptsSupportedExtensions() {
        let supported = ["photo.heic", "photo.HEIC", "photo.dng", "photo.DNG",
                         "photo.jpg", "photo.JPG", "photo.jpeg", "photo.JPEG",
                         "photo.png", "photo.PNG", "photo.heif"]
        for name in supported {
            let url = URL(fileURLWithPath: "/tmp/\(name)")
            #expect(FileImporter.isSupportedFile(url), "\(name) should be supported")
        }
    }

    @Test("rejects unsupported extensions")
    func rejectsUnsupportedExtensions() {
        let unsupported = ["doc.pdf", "movie.mp4", "archive.zip", "file.txt", "noext"]
        for name in unsupported {
            let url = URL(fileURLWithPath: "/tmp/\(name)")
            #expect(!FileImporter.isSupportedFile(url), "\(name) should not be supported")
        }
    }

    // MARK: - resolveURLs (file inputs)

    @Test("passes through supported file URLs unchanged")
    func passesThroughSupportedFiles() throws {
        let dir = try tempDir()
        let file = dir.appendingPathComponent("photo.heic")
        try Data().write(to: file)

        let result = FileImporter.resolveURLs([file])
        #expect(result == [file])
    }

    @Test("filters out unsupported file types")
    func filtersUnsupportedFiles() throws {
        let dir = try tempDir()
        let good = dir.appendingPathComponent("photo.jpg")
        let bad = dir.appendingPathComponent("doc.pdf")
        try Data().write(to: good)
        try Data().write(to: bad)

        let result = FileImporter.resolveURLs([good, bad])
        #expect(result == [good])
    }

    @Test("returns empty for empty input")
    func emptyInput() {
        #expect(FileImporter.resolveURLs([]).isEmpty)
    }

    // MARK: - resolveURLs (folder inputs)

    @Test("walks folder and returns supported files sorted by name")
    func walksFolder() throws {
        let dir = try tempDir()
        let b = dir.appendingPathComponent("b.heic")
        let a = dir.appendingPathComponent("a.jpg")
        let skip = dir.appendingPathComponent("readme.txt")
        for f in [a, b, skip] { try Data().write(to: f) }

        let result = FileImporter.resolveURLs([dir])
        #expect(result == [a, b])   // sorted alphabetically, txt excluded
    }

    @Test("walks nested folders recursively")
    func walksNestedFolders() throws {
        let root = try tempDir()
        let sub = root.appendingPathComponent("sub", isDirectory: true)
        try FileManager.default.createDirectory(at: sub, withIntermediateDirectories: true)
        let top = root.appendingPathComponent("top.heic")
        let nested = sub.appendingPathComponent("nested.jpg")
        try Data().write(to: top)
        try Data().write(to: nested)

        let result = FileImporter.resolveURLs([root])
        #expect(result.count == 2)
        #expect(result.contains(top))
        #expect(result.contains(nested))
    }

    @Test("mixes files and folders in one call")
    func mixedFilesAndFolders() throws {
        let dir = try tempDir()
        let sub = dir.appendingPathComponent("sub", isDirectory: true)
        try FileManager.default.createDirectory(at: sub, withIntermediateDirectories: true)
        let direct = dir.appendingPathComponent("direct.heic")
        let inSub = sub.appendingPathComponent("nested.png")
        try Data().write(to: direct)
        try Data().write(to: inSub)

        let result = FileImporter.resolveURLs([direct, sub])
        #expect(result.count == 2)
        #expect(result.contains(direct))
        #expect(result.contains(inSub))
    }

    // MARK: - AppState.addFiles

    @Test("addFiles creates queued jobs")
    @MainActor func addFilesCreatesJobs() throws {
        let dir = try tempDir()
        let file = dir.appendingPathComponent("photo.heic")
        try Data().write(to: file)

        let state = AppState(loadDebugJobs: false)
        state.addFiles([file], startProcessing: false)

        #expect(state.jobs.count == 1)
        #expect(state.jobs[0].inputURL == file)
        #expect(state.jobs[0].inputName == "photo.heic")
        #expect(state.jobs[0].state == .queued)
    }

    @Test("addFiles deduplicates by URL")
    @MainActor func addFilesDeduplicates() throws {
        let dir = try tempDir()
        let file = dir.appendingPathComponent("photo.heic")
        try Data().write(to: file)

        let state = AppState(loadDebugJobs: false)
        state.addFiles([file], startProcessing: false)
        state.addFiles([file], startProcessing: false)   // second call — same URL

        #expect(state.jobs.count == 1)
    }

    @Test("addFiles appends multiple new files")
    @MainActor func addFilesMultiple() throws {
        let dir = try tempDir()
        let a = dir.appendingPathComponent("a.heic")
        let b = dir.appendingPathComponent("b.jpg")
        try Data().write(to: a)
        try Data().write(to: b)

        let state = AppState(loadDebugJobs: false)
        state.addFiles([a, b], startProcessing: false)

        #expect(state.jobs.count == 2)
    }

    // MARK: - Helpers

    private func tempDir() throws -> URL {
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .standardizedFileURL
        try FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        return tmp
    }
}
