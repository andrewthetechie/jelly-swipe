import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

describe('global typography styles', () => {
  it('uses the Variable font families emitted by fontsource', () => {
    const cssPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'style.css');
    const css = fs.readFileSync(cssPath, 'utf8');

    expect(css).toContain('font-family: "Orbitron Variable"');
    expect(css).toContain('font-family: "Raleway Variable"');
  });
});
