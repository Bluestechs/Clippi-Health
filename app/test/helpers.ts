// Fixtures for the unit tests: a minimal ZIP writer (stored, no compression) and a Paths record
// built by hand — roots.ts imports electron, so tests must not load it at runtime.
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { crc32 } from "node:zlib";
import type { Paths } from "../main/roots";

/** Mirrors roots.paths() without importing it (that module pulls in electron). */
export function makePaths(root: string): Paths {
  return {
    root,
    raw: join(root, "raw"),
    rawApple: join(root, "raw", "apple"),
    rawImports: join(root, "raw", "imports"),
    rawOther: join(root, "raw", "other"),
    rawPrevious: join(root, "raw", "_previous"),
    data: join(root, "data"),
    db: join(root, "data", "health.db"),
    dashboard: join(root, "dashboard.html"),
    curatedEvents: join(root, "curated_events.csv"),
    notes: join(root, "case_study_notes.md"),
    topics: join(root, "topics.json"),
    builder: join(root, "healthpilot.py"),
    cli: join(root, "hp"),
    smartConnector: join(root, "smart_connect.py"),
  };
}

export type ZipEntry = { name: string; data?: string };

type Piece = { name: Buffer; crc: number; size: number; offset: number };

function localHeader(name: Buffer, crc: number, size: number): Buffer {
  const head = Buffer.alloc(30);
  head.writeUInt32LE(0x04034b50, 0);
  head.writeUInt16LE(20, 4); // version needed
  head.writeUInt16LE(0, 8); // flags
  head.writeUInt16LE(0, 10); // stored
  head.writeUInt32LE(crc, 14);
  head.writeUInt32LE(size, 18);
  head.writeUInt32LE(size, 22);
  head.writeUInt16LE(name.length, 26);
  return head;
}

function centralEntry(piece: Piece): Buffer {
  const head = Buffer.alloc(46);
  head.writeUInt32LE(0x02014b50, 0);
  head.writeUInt16LE(20, 4); // version made by
  head.writeUInt16LE(20, 6); // version needed
  head.writeUInt16LE(0, 10); // stored
  head.writeUInt32LE(piece.crc, 16);
  head.writeUInt32LE(piece.size, 20);
  head.writeUInt32LE(piece.size, 24);
  head.writeUInt16LE(piece.name.length, 28);
  head.writeUInt32LE(piece.offset, 42);
  return head;
}

function build(entries: ZipEntry[]): { body: Buffer; directory: Buffer; count: number } {
  const chunks: Buffer[] = [];
  const pieces: Piece[] = [];
  let offset = 0;
  for (const entry of entries) {
    const name = Buffer.from(entry.name, "utf8");
    const data = Buffer.from(entry.data ?? "", "utf8");
    const crc = crc32(data);
    const head = localHeader(name, crc, data.length);
    chunks.push(head, name, data);
    pieces.push({ name, crc, size: data.length, offset });
    offset += head.length + name.length + data.length;
  }
  const body = Buffer.concat(chunks);
  const directory = Buffer.concat(pieces.flatMap((piece) => [centralEntry(piece), piece.name]));
  return { body, directory, count: pieces.length };
}

/** A plain (non-ZIP64) archive with stored entries. */
export function writeZip(path: string, entries: ZipEntry[]): string {
  const { body, directory, count } = build(entries);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(count, 8);
  eocd.writeUInt16LE(count, 10);
  eocd.writeUInt32LE(directory.length, 12);
  eocd.writeUInt32LE(body.length, 16);
  writeFileSync(path, Buffer.concat([body, directory, eocd]));
  return path;
}

/**
 * Same entries, but the 32-bit EOCD carries the "look in the ZIP64 record" sentinels, so the entry
 * list is only reachable through the ZIP64 end-of-central-directory record — the shape a real
 * Apple Health export has once export.xml pushes it past 4 GB.
 */
export function writeZip64(path: string, entries: ZipEntry[]): string {
  const { body, directory, count } = build(entries);

  const record = Buffer.alloc(56);
  record.writeUInt32LE(0x06064b50, 0);
  record.writeBigUInt64LE(BigInt(44), 4); // size of the rest of this record
  record.writeUInt16LE(45, 12); // version made by
  record.writeUInt16LE(45, 14); // version needed
  record.writeBigUInt64LE(BigInt(count), 24);
  record.writeBigUInt64LE(BigInt(count), 32);
  record.writeBigUInt64LE(BigInt(directory.length), 40);
  record.writeBigUInt64LE(BigInt(body.length), 48);

  const locator = Buffer.alloc(20);
  locator.writeUInt32LE(0x07064b50, 0);
  locator.writeBigUInt64LE(BigInt(body.length + directory.length), 8);
  locator.writeUInt32LE(1, 16); // total disks

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0xffff, 8);
  eocd.writeUInt16LE(0xffff, 10);
  eocd.writeUInt32LE(directory.length, 12);
  eocd.writeUInt32LE(0xffffffff, 16);

  writeFileSync(path, Buffer.concat([body, directory, record, locator, eocd]));
  return path;
}
