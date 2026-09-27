// @vitest-environment jsdom
/* S63-T red test: UX-05 primary-button contrast. Astryx ships Button colour
   inside `@layer astryx-base`, so any unlayered `button{color}` rule in
   styles.css wins the cascade and replaces the on-accent token with inherited
   text. This test resolves that effective pair per theme and asserts WCAG AA.
   Reads stylesheets as text (packet guidance for UX-05); no wall clock. */
// @ts-ignore TS2307: Node types are absent from the frozen tsconfig; Vitest resolves this import.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

function readFirst(paths: string[]): string {
  for (const path of paths) {
    try {
      return readFileSync(path, 'utf8');
    } catch {
      /* try the next root */
    }
  }
  throw new Error(`none of ${paths.join(', ')} readable`);
}

const styles = readFirst(['src/styles.css', 'dashboard/src/styles.css']);
const theme = readFirst(['src/theme.ts', 'dashboard/src/theme.ts']);
const astryx = readFirst([
  'node_modules/@astryxdesign/core/dist/astryx.css',
  'dashboard/node_modules/@astryxdesign/core/dist/astryx.css',
]);

/** Drop @media/@layer/@keyframes blocks so only unlayered top-level rules remain. */
function topLevel(css: string): string {
  let out = '';
  let i = 0;
  while (i < css.length) {
    const at = css.indexOf('@', i);
    if (at < 0) {
      out += css.slice(i);
      break;
    }
    out += css.slice(i, at);
    const open = css.indexOf('{', at);
    if (open < 0) break;
    let depth = 0;
    let j = open;
    for (; j < css.length; j++) {
      if (css[j] === '{') depth++;
      else if (css[j] === '}') {
        depth--;
        if (depth === 0) {
          j++;
          break;
        }
      }
    }
    i = j;
  }
  return out;
}

const luminance = (hex: string): number => {
  const rgb = [1, 3, 5].map(i => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
};

const ratio = (a: string, b: string): number => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

/** light-dark(light, dark) custom property halves from styles.css :root. */
function halves(name: string): [string, string] {
  const match = styles.match(new RegExp(`${name}:\\s*light-dark\\((#[0-9a-fA-F]{6})\\s*,\\s*(#[0-9a-fA-F]{6})\\)`));
  if (!match) {
    const flat = styles.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
    if (!flat) throw new Error(`${name} not found in styles.css`);
    return [flat[1].toLowerCase(), flat[1].toLowerCase()];
  }
  return [match[1].toLowerCase(), match[2].toLowerCase()];
}

/** [light, dark] tuple token from theme.ts. */
function tuple(name: string): [string, string] {
  const match = theme.match(new RegExp(`'${name}':\\s*\\['(#[0-9a-fA-F]{6})'\\s*,\\s*'(#[0-9a-fA-F]{6})'\\]`));
  if (!match) throw new Error(`${name} tuple not found in theme.ts`);
  return [match[1].toLowerCase(), match[2].toLowerCase()];
}

describe('S63-T UX-05 primary-button contrast', () => {
  it('UX-05 every enabled primary-button state reaches 4.5:1 in light and dark', () => {
    // Astryx primary: background var(--color-accent), text var(--color-on-accent).
    expect(astrxHas('.x1ewilqj', 'background-color:var(--color-accent)')).toBe(true);
    expect(astrxHas('.x17wrial', 'color:var(--color-on-accent)')).toBe(true);
    // That colour rule is layered, so an unlayered button colour rule wins.
    expect(astrxLayered('.x17wrial')).toBe(true);
    const override = topLevel(styles).match(/(^|[;}])\s*button\s*\{[^}]*?color\s*:\s*([^;}]*)/);
    // Effective foreground: the override when present, else the theme token.
    const text = halves('--text');
    const onAccent = tuple('--color-on-accent');
    const fill = tuple('--color-accent');
    const fg: [string, string] = override
      ? [resolveOverride(override[2].trim(), text[0]), resolveOverride(override[2].trim(), text[1])]
      : onAccent;
    // No state rule may swap in a weaker pair.
    expect(topLevel(styles).match(/button\s*:\s*(hover|focus|active|focus-visible)\s*\{[^}]*color\s*:/)).toBeNull();
    expect(astrxHas('.x17wrial:hover', 'color:')).toBe(false);
    expect(astrxHas('.x17wrial:focus', 'color:')).toBe(false);
    expect(astrxHas('.x17wrial:active', 'color:')).toBe(false);
    // The intended token pair itself must pass, and the effective pair too.
    expect(ratio(onAccent[0], fill[0])).toBeGreaterThanOrEqual(4.5);
    expect(ratio(onAccent[1], fill[1])).toBeGreaterThanOrEqual(4.5);
    expect({ theme: 'light', fg: fg[0], fill: fill[0], ratio: ratio(fg[0], fill[0]) }.ratio).toBeGreaterThanOrEqual(4.5);
    expect({ theme: 'dark', fg: fg[1], fill: fill[1], ratio: ratio(fg[1], fill[1]) }.ratio).toBeGreaterThanOrEqual(4.5);
  });
});

function astrxHas(selector: string, declaration: string): boolean {
  const at = astryx.indexOf(selector);
  return at >= 0 && astryx.slice(at, astryx.indexOf('}', at)).includes(declaration);
}

function astrxLayered(selector: string): boolean {
  const layer = astryx.indexOf('@layer');
  const at = astryx.indexOf(selector);
  return layer >= 0 && layer < at && at < astryx.lastIndexOf('}');
}

/** `inherit` on a button takes the body text colour; anything else must be a literal here. */
function resolveOverride(value: string, bodyText: string): string {
  if (value === 'inherit' || value === 'currentColor') return bodyText;
  const hex = value.match(/#[0-9a-fA-F]{6}/);
  if (hex) return hex[0].toLowerCase();
  const token = value.match(/var\((--[\w-]+)\)/);
  if (token) {
    if (token[1] === '--text') return bodyText;
    const [light] = halves(token[1]);
    return light;
  }
  throw new Error(`cannot resolve button colour override: ${value}`);
}
