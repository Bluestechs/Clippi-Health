// Prints the text layer of a PDF using macOS PDFKit. Used by healthpilot.py.
import PDFKit

let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1]))
print(doc?.string ?? "")
