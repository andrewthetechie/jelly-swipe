import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

describe('global typography styles', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'style.css'),
    'utf8',
  );

  it('declares the fontsource Variable families as role tokens', () => {
    expect(css).toContain('--font-display: "Orbitron Variable"');
    expect(css).toContain('--font-body: "Raleway Variable"');
  });

  it('sets the body font to the body token and opts display elements in', () => {
    const bodyRule = css.match(/body\s*\{[^}]*\}/);
    expect(bodyRule, 'body rule').toBeTruthy();
    expect(bodyRule![0]).toContain('font-family: var(--font-body)');
    expect(bodyRule![0]).not.toContain('Orbitron');
    // Display uses must opt in explicitly via the display token.
    expect(css).toContain('font-family: var(--font-display)');
  });

  it('routes every font-family through a token (no bare family names in rules)', () => {
    // Only the two :root token declarations may contain the literal family
    // names. This actually enforces the AC: a new rule adding Orbitron/Raleway
    // as a bare font-family (i.e. not opting in via var(--font-display)) fails.
    const withoutTokenDecls = css.replace(/^\s*--font-(display|body):.*$/gm, '');
    expect(withoutTokenDecls).not.toContain('"Orbitron Variable"');
    expect(withoutTokenDecls).not.toContain('"Raleway Variable"');
  });

  it('defines a type scale as custom properties and maps sizes onto it', () => {
    for (const token of [
      '--text-xs',
      '--text-sm',
      '--text-md',
      '--text-lg',
      '--text-xl',
      '--text-2xl',
      '--text-3xl',
    ]) {
      expect(css).toContain(`${token}:`);
    }
    expect(css).toMatch(/font-size:\s*var\(--text-/);
    // No font-size may escape the scale with a hard-coded length.
    expect(css).not.toMatch(/font-size:\s*\d/);
  });

  it('keeps the media type badge on the body face', () => {
    const mediaTypeRule = css.match(/div\.media-type\s*\{[^}]*\}/);
    expect(mediaTypeRule, 'div.media-type rule').toBeTruthy();
    expect(mediaTypeRule![0]).not.toContain('font-family');
  });

  it('sets the LIKE/NOPE jelly buttons in the display face', () => {
    const jellyRule = css.match(/\.jelly-button\s*\{[^}]*\}/);
    expect(jellyRule, '.jelly-button rule').toBeTruthy();
    expect(jellyRule![0]).toContain('font-family: var(--font-display)');
  });

  it('keeps the genre modal heading on the body face', () => {
    // "Select Genre" (h2 in .modal-inner) is intentionally Raleway, not Orbitron.
    const modalH2Rule = css.match(/\.modal-inner h2\s*\{[^}]*\}/);
    expect(modalH2Rule, '.modal-inner h2 rule').toBeTruthy();
    expect(modalH2Rule![0]).not.toContain('font-family');
  });

  it('sets a readable weight on the metadata pills', () => {
    // Scoped to the pill rules (not the whole file) so a legitimate weight-200
    // elsewhere could never break this, and so it can't pass vacuously.
    const pillRules = [
      css.match(/div\.card-item-score,[^}]*\}/),
      css.match(/\.match-list-score,[^}]*\}/),
    ];
    expect(pillRules[0], 'card pill rule').toBeTruthy();
    expect(pillRules[1], 'match-list pill rule').toBeTruthy();
    for (const rule of pillRules) {
      expect(rule![0]).toContain('font-weight: 400');
      expect(rule![0]).not.toMatch(/font-weight:\s*200/);
    }
  });
});

describe('swipe verdict feedback styles (issue #345)', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'style.css'),
    'utf8',
  );

  it('declares the LIKE/NOPE verdict colour tokens on :root', () => {
    expect(css).toContain('--color-like:');
    expect(css).toContain('--color-nope:');
  });

  it('paints each stamp in its own verdict colour via the token', () => {
    const likeRule = css.match(/\.swipe-stamp-like\s*\{[^}]*\}/);
    const nopeRule = css.match(/\.swipe-stamp-nope\s*\{[^}]*\}/);
    expect(likeRule, '.swipe-stamp-like rule').toBeTruthy();
    expect(nopeRule, '.swipe-stamp-nope rule').toBeTruthy();
    expect(likeRule![0]).toContain('var(--color-like)');
    expect(nopeRule![0]).toContain('var(--color-nope)');
  });

  it('differentiates LIKE and NOPE by shape, not colour alone (colourblind guard)', () => {
    // The five non-colour cues are glyph, word, border-style, corner radius and
    // tilt/edge. This asserts the two that a "simplify to colour-only" change
    // would drop: border-style and a differing border-radius.
    const likeRule = css.match(/\.swipe-stamp-like\s*\{[^}]*\}/)![0];
    const nopeRule = css.match(/\.swipe-stamp-nope\s*\{[^}]*\}/)![0];
    expect(likeRule).toContain('border: 4px solid');
    expect(nopeRule).toContain('border: 4px dashed');
    const likeRadius = likeRule.match(/border-radius:\s*([^;]+);/)?.[1];
    const nopeRadius = nopeRule.match(/border-radius:\s*([^;]+);/)?.[1];
    expect(likeRadius).toBeTruthy();
    expect(nopeRadius).toBeTruthy();
    expect(likeRadius).not.toBe(nopeRadius);
  });

  it('keeps the stamp/rim transition tight (60ms, not the old 0.2s lag)', () => {
    // The single shared rule is the only transition these elements carry, so one
    // assertion guards both against reintroducing the finger-chasing lag.
    const shared = css.match(/\.swipe-stamp,\s*\.swipe-rim\s*\{[^}]*\}/);
    expect(shared, '.swipe-stamp, .swipe-rim rule').toBeTruthy();
    expect(shared![0]).toContain('60ms');
    expect(shared![0]).not.toContain('0.2s');
  });

  it('removes the old full-screen edge glow', () => {
    expect(css).not.toContain('.glow');
  });
});
