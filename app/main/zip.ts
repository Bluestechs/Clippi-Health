// Just enough ZIP reading to classify Apple Health and local email/document exports: the central
// directory is parsed for entry names, nothing is decompressed. ZIP64 is handled because an Apple
// export's export.xml is far over 4 GB uncompressed.
import { closeSync, fstatSync, openSync, readSync } from "node:fs";

const EOCD = 0x06054b50;
const EOCD64_LOCATOR = 0x07064b50;
const EOCD64 = 0x06064b50;
const CENTRAL_ENTRY = 0x02014b50;

function readAt(fd: number, offset: number, length: number): Buffer {
  const buf = Buffer.alloc(length);
  const read = readSync(fd, buf, 0, length, offset);
  return read === length ? buf : buf.subarray(0, read);
}

/** Entry names in the archive, or null when the file is not a readable ZIP. */
export function zipEntryNames(path: string): string[] | null {
  let fd: number | null = null;
  try {
    fd = openSync(path, "r");
    const size = fstatSync(fd).size;
    const tailLength = Math.min(size, 66560); // 64 KiB comment + the records themselves
    const tail = readAt(fd, size - tailLength, tailLength);

    let eocd = -1;
    for (let i = tail.length - 22; i >= 0; i--) {
      if (tail.readUInt32LE(i) === EOCD) {
        eocd = i;
        break;
      }
    }
    if (eocd < 0) return null;

    let entries = tail.readUInt16LE(eocd + 10);
    let directoryOffset = tail.readUInt32LE(eocd + 16);
    let directorySize = tail.readUInt32LE(eocd + 12);

    if (directoryOffset === 0xffffffff || entries === 0xffff) {
      const locator = tail.lastIndexOf(Buffer.from([0x50, 0x4b, 0x06, 0x07]), eocd);
      if (locator < 0 || tail.readUInt32LE(locator) !== EOCD64_LOCATOR) return null;
      const eocd64Offset = Number(tail.readBigUInt64LE(locator + 8));
      const record = readAt(fd, eocd64Offset, 56);
      if (record.length < 56 || record.readUInt32LE(0) !== EOCD64) return null;
      entries = Number(record.readBigUInt64LE(32));
      directorySize = Number(record.readBigUInt64LE(40));
      directoryOffset = Number(record.readBigUInt64LE(48));
    }

    const directory = readAt(fd, directoryOffset, directorySize);
    const names: string[] = [];
    let at = 0;
    for (let i = 0; i < entries && at + 46 <= directory.length; i++) {
      if (directory.readUInt32LE(at) !== CENTRAL_ENTRY) break;
      const nameLength = directory.readUInt16LE(at + 28);
      const extraLength = directory.readUInt16LE(at + 30);
      const commentLength = directory.readUInt16LE(at + 32);
      names.push(directory.subarray(at + 46, at + 46 + nameLength).toString("utf8"));
      at += 46 + nameLength + extraLength + commentLength;
    }
    return names;
  } catch {
    return null;
  } finally {
    if (fd !== null) closeSync(fd);
  }
}
