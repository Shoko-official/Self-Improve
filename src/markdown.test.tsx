import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ArtifactPreviewPanel, MarkdownContent, mcpMarkdown } from "./App";

describe("MarkdownContent", () => {
  it("renders GitHub-flavored Markdown structures", () => {
    const html = renderToStaticMarkup(
      <MarkdownContent content={'# Result\n\n- [x] verified\n\n| metric | value |\n| --- | ---: |\n| score | 42 |\n\n~~old~~ and `code`'} />,
    );

    expect(html).toContain("<h1>Result</h1>");
    expect(html).toContain('type="checkbox"');
    expect(html).toContain("<table>");
    expect(html).toContain("<del>old</del>");
    expect(html).toContain("<code>code</code>");
  });

  it("keeps raw HTML inert and hardens external links", () => {
    const html = renderToStaticMarkup(
      <MarkdownContent content={'<script>alert("no")</script>\n\n[Source](https://example.com)'} />,
    );

    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noreferrer"');
  });
});

describe("ArtifactPreviewPanel", () => {
  it("uses the safe GFM renderer for versioned Markdown source", () => {
    const html = renderToStaticMarkup(
      <ArtifactPreviewPanel preview={{ artifact_version_id: "version-123", renderer_id: "markdown.basic", renderer_version: "1", source_sha256: "a".repeat(64), html: "<p>fallback</p>", markdown: "- [x] rendered\n\n<script>blocked</script>" }} />,
    );

    expect(html).toContain('type="checkbox"');
    expect(html).toContain("&lt;script&gt;blocked&lt;/script&gt;");
    expect(html).not.toContain("<p>fallback</p>");
  });
});

describe("mcpMarkdown", () => {
  it("extracts the first text block from an MCP result", () => {
    expect(mcpMarkdown({ content: [{ type: "image", data: "ignored" }, { type: "text", text: "## Verified\n\n- safe" }] })).toBe("## Verified\n\n- safe");
  });

  it("ignores malformed or non-text content", () => {
    expect(mcpMarkdown({ content: [{ type: "image", data: "ignored" }] })).toBeNull();
    expect(mcpMarkdown({ content: "not-an-array" })).toBeNull();
  });
});
