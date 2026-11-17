// Local Vision bridge. No network, downloads, shell, file writes or identities.
import Foundation
import Vision
import ImageIO

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).resolvingSymlinksInPath().path + "/"
var rows: [[String: Any]] = []
for argument in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: argument).resolvingSymlinksInPath()
    guard url.path.hasPrefix(root), let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        fputs("Invalid local image\n", stderr); exit(2)
    }
    do {
        let request = VNDetectHumanRectanglesRequest()
        request.upperBodyOnly = false
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        try handler.perform([request])
        let boxes: [[String: Any]] = (request.results ?? []).map { item in
            let r = item.boundingBox
            return ["x": r.minX, "y": 1.0-r.maxY, "width": r.width, "height": r.height,
                    "confidence": Double(item.confidence)]
        }
        rows.append(["path": url.path, "detector": "Apple Vision VNDetectHumanRectanglesRequest",
                     "revision": request.revision, "boxes": boxes])
    } catch {
        rows.append(["path": url.path, "error": "VisionUnavailable", "boxes": []])
    }
}
let result = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
FileHandle.standardOutput.write(result)
