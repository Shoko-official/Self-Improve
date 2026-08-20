import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ScientificFigureView, figureTemplates, type ScientificFigureData } from "./ScientificFigure";

describe("ScientificFigureView", () => {
  it.each(["scatter", "matrix", "sequence"] as const)("renders accessible %s selectors", kind => {
    const figure = JSON.parse(figureTemplates[kind]) as ScientificFigureData;
    const html = renderToStaticMarkup(<ScientificFigureView figure={figure} onSelect={() => undefined} />);

    expect(html).toContain('role="img"');
    expect(html).toContain('role="button"');
    expect(html).toContain("data-selector=");
    expect(html).toContain(`figure.${kind}/v1`);
  });

  it("keeps untrusted labels inert", () => {
    const figure = JSON.parse(figureTemplates.scatter) as ScientificFigureData;
    figure.title = "<script>alert(1)</script>";
    figure.points![0].label = "<img src=x onerror=alert(1)>";
    const html = renderToStaticMarkup(<ScientificFigureView figure={figure} onSelect={() => undefined} />);

    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;");
  });
});
