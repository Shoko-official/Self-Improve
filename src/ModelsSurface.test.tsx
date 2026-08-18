import { describe, expect, it } from "vitest";
import { formatBytes, formatNanoseconds, latestProgress, parseOptionalInteger } from "./ModelsSurface";

describe("model transfer presentation", () => {
  it("formats binary sizes without inventing precision", () => {
    expect(formatBytes(null)).toBe("Unknown");
    expect(formatBytes(1024)).toBe("1.00 KiB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.00 MiB");
  });

  it("uses the most recent measured progress event", () => {
    const detail = latestProgress({
      events: [
        { sequence_number: 0, kind: "progress", detail: { received_bytes: 4, total_bytes: 10, percent: 40, bytes_per_second: 8 } },
        { sequence_number: 1, kind: "note", detail: { received_bytes: 0, total_bytes: null, percent: null, bytes_per_second: 0 } },
        { sequence_number: 2, kind: "progress", detail: { received_bytes: 8, total_bytes: 10, percent: 80, bytes_per_second: 12 } },
      ],
    } as never);
    expect(detail?.percent).toBe(80);
    expect(detail?.bytes_per_second).toBe(12);
  });

  it("keeps optional profile values explicit", () => {
    expect(parseOptionalInteger("")).toBeNull();
    expect(parseOptionalInteger(" 4096 ")).toBe(4096);
    expect(formatNanoseconds(1_250_000_000)).toBe("1.25 s");
  });
});
