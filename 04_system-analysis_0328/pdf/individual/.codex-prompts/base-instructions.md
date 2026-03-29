# El Croquis Diagram Insertion — Base Instructions

## TASK
You are adding SVG diagrams to an El Croquis-style HTML document (247mm x 340mm pages).

## IMPORTANT: FILE CREATION METHOD
1. Read the ORIGINAL file (e.g., `02_Beta.html`)
2. Create a NEW file with `_diag` suffix (e.g., `02_Beta_diag.html`) containing the full content WITH diagrams inserted
3. DO NOT modify the original file
4. The new file must contain the COMPLETE HTML — not just the diffs

## STEP 1: Read Reference Files
Before doing ANYTHING, read these files:
1. `01_Alpha.html` — GOLD STANDARD. Study how diagrams are inserted: SVG structure, positioning, styles, placement patterns.
2. `el-croquis.css` — Design system CSS.
3. Your TARGET file — Read ALL pages, understand every section's content.

## STEP 2: Plan Diagrams
- Create **6 to 8 diagrams** for your target file.
- Each diagram MUST be a **different type**. Choose from:
  1. **Classification** — matrix/grid rows showing categories
  2. **Flow** — vertical/horizontal process sequence
  3. **Statistics** — large numbers with labels, data-centric
  4. **Comparison** — side-by-side columns contrasting two things
  5. **Timeline** — horizontal chronological sequence
  6. **Hierarchy** — pyramid/stack showing levels
  7. **Transformation** — bidirectional arrows, conversion paths
  8. **Cycle** — circular/loop feedback structure
  9. **Network** — nodes connected by lines, graph
  10. **Radial** — center node with radiating spokes/quadrants

## STEP 3: SVG Design Rules (El Croquis Style)

### Colors
- Primary: `#000000`
- Secondary: `#666666` or `#999999`
- Faint: `#BBBBBB` or `#D8D8D8`
- Accent: `#CC0000` — max 1-2 elements per diagram
- Accent bg: `rgba(204,0,0,0.06)` — very rare

### Strokes
- Default: `0.5px #000`
- `stroke-linecap="butt"` (NEVER round)
- `stroke-linejoin="miter"`
- `shape-rendering="crispEdges"` on ALL `<line>` elements
- Dashed: `stroke-dasharray="2,2"` or `stroke-dasharray="4,4"`

### Typography
- Font: `font-family="Inter, sans-serif"`
- Labels: `9-11px`, weight `200-300`, UPPERCASE, letter-spacing `1-2px`
- Content: `10-12px`, weight `200-300`
- Large stats: `24-28px`, weight `200`
- ALL text must fit inside boxes with **6px padding minimum**

### Shapes
- Rectangles (NO border-radius) or circles ONLY
- `fill: none` default, `fill: #CC0000` accent (max 1-2 per diagram)
- NO shadows, gradients, rounded corners, icons, decorations

### Lines
- Straight lines ONLY
- Arrows: polygon triangle 3-6px, only when direction is critical

### ViewBox
- Right-margin: `viewBox="-5 -5 218 XXX"` — always add padding
- Bottom-flow: `viewBox="-5 -5 558 XXX"` — wide format
- Ensure NO text clips at edges

## STEP 4: Placement Rules

### Right-Margin Diagrams (most go here)
```html
<div style="position: absolute; right: 12mm; top: 35mm; width: 58mm;">
  <svg viewBox="-5 -5 218 XXX" width="58mm" xmlns="http://www.w3.org/2000/svg">
    ...
  </svg>
  <div style="font-size: 6px; color: #BBB; letter-spacing: 1px; text-transform: uppercase; margin-top: 2mm;">FIG. N — CAPTION</div>
</div>
```
Insert as child of `<div class="page">`, after `<span class="page-number">`.

### Bottom-Flow Diagrams (2-3 max per document)
```html
<div style="margin-top: 6mm; max-width: 145mm;">
  <svg viewBox="-5 -5 558 XXX" width="145mm" xmlns="http://www.w3.org/2000/svg">
    ...
  </svg>
  <div style="font-size: 6px; color: #BBB; letter-spacing: 1px; text-transform: uppercase; margin-top: 2mm;">FIG. N — CAPTION</div>
</div>
```
Place AFTER body content (after `.body-serif` or `.body-sans` closing `</div>`), BEFORE page closing `</div>`.

### Page Selection
- NOT cover page (page 1)
- NOT TOC page (page 2, if exists)
- NOT closing/colophon (last page)
- Choose pages where diagrams meaningfully illustrate content

## STEP 5: Output
1. Write the COMPLETE new HTML file as `{FILENAME}_diag.html`
2. Run: `node gen.js {FILENAME}_diag.html`
3. If gen.js fails (sandbox issue), that's OK — just make sure the HTML file is complete

## QUALITY CHECKLIST
- [ ] 6-8 diagrams, ALL different types
- [ ] No text clipped in SVG
- [ ] viewBox has -5,-5 padding
- [ ] shape-rendering="crispEdges" on all lines
- [ ] Font min: 9px labels, 10px content
- [ ] Accent sparingly (max 1-2 per diagram)
- [ ] Right-margin: width="58mm"
- [ ] Bottom-flow: max-width="145mm", in content flow
- [ ] Figure numbering sequential
- [ ] New file created (original untouched)
