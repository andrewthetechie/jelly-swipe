import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const readSource = (file: string): string =>
  fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), file), 'utf8');

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

describe('design token foundation (issue #347)', () => {
  const css = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'style.css'),
    'utf8',
  );

  it('declares the palette, radius and z-index tokens on :root', () => {
    expect(css).toContain('--color-accent:');
    expect(css).toContain('--color-destructive:');
    expect(css).toContain('--radius-pill:');
    expect(css).toContain('--radius-card:');
    expect(css).toContain('--radius-badge:');
    expect(css).toContain('--radius-round:');
    expect(css).toContain('--z-stamp:');
    expect(css).toContain('--z-modal:');
  });

  it('desaturates the accent from the old neon cyan', () => {
    const accentDecl = css.match(/--color-accent:\s*([^;]+);/)?.[1];
    expect(accentDecl, '--color-accent declaration').toBeTruthy();
    expect(accentDecl!.trim()).not.toBe('#35D6FF');
  });

  it('confines the palette hex literals to the :root token block', () => {
    // Strip every token declaration (colour, radius, z-index, type scale) so
    // only the rules remain; none of the palette hexes may survive there.
    const withoutTokenDecls = css.replace(/^\s*--(color|radius|z|font|text)-[^:]*:.*$/gm, '');
    const paletteHexes = [
      '#35D6FF', '#FF7ACF',
      '#c9f8ff', '#7EEBFF', '#1B7BFF', '#5FE2FF', '#4BE0FF', '#63E5FF',
      '#dff8ff', '#bfefff', '#98F1FF', '#6ADFFF', '#28CFFF', '#2B8BFF',
      '#156AE0', '#1452B8', '#082E73',
      '#071426', '#0A1F3D', '#0A3D91', '#0A357C',
      '#1C4273', '#9BF2FF', '#12246e', '#3a67ed',
      '#f0f4f8', '#fdfdfe', '#ffffff',
    ];
    for (const hex of paletteHexes) {
      expect(withoutTokenDecls, `palette hex ${hex} must stay in :root`).not.toContain(hex);
    }
  });

  it('confines the accent rgba literals to the :root token block', () => {
    // Companion to the hex guard above. The four accent rgba families must not
    // survive outside :root either, in any spacing or casing variant (the file
    // historically contained both `rgba(53, 214, 255, 0.30)` and
    // `rgba(53,214,255,0.3)` spellings). An explicit allowlist holds deliberate
    // exceptions; it is empty after the color-mix migration.
    const withoutTokenDecls = css.replace(/^\s*--(color|radius|z|font|text)-[^:]*:.*$/gm, '');
    const accentFamilies = [
      /rgba\(\s*53\s*,\s*214\s*,\s*255/,
      /rgba\(\s*95\s*,\s*226\s*,\s*255/,
      /rgba\(\s*155\s*,\s*242\s*,\s*255/,
      /rgba\(\s*27\s*,\s*123\s*,\s*255/,
    ];
    const allowlisted: string[] = [];
    for (const family of accentFamilies) {
      const survivors = (withoutTokenDecls.match(new RegExp(family.source, 'gi')) ?? []).filter(
        (m) => !allowlisted.includes(m),
      );
      expect(survivors.length, `accent rgba family ${family} must stay in :root`).toBe(0);
    }
  });
});

describe('button roles (issue #347)', () => {
  const css = readSource('style.css');

  it('defines the three button roles as classes', () => {
    // Each role selector may be grouped with aliases, so allow a comma after it.
    expect(css).toMatch(/\.btn-primary\s*[,{]/);
    expect(css).toMatch(/\.btn-secondary\s*[,{]/);
    expect(css).toMatch(/\.btn-destructive\s*[,{]/);
  });

  it('keeps role/appearance classes width-neutral (issue #347)', () => {
    // The shared .btn-primary/.jelly-button--compact rule must not bake a
    // modal-layout width into the reusable compact jelly treatment.
    const sharedRule = css.match(/\.btn-primary\s*,\s*\.jelly-button--compact\s*\{[^}]*\}/)![0];
    expect(sharedRule).not.toMatch(/width\s*:/);
    // The flat roles stay width-neutral too.
    const secondaryRule = css.match(/\.btn-secondary\s*\{[^}]*\}/)![0];
    expect(secondaryRule).not.toMatch(/width\s*:/);
    const destructiveRule = css.match(/\.btn-destructive\s*,\s*button\.end-session\s*\{[^}]*\}/)![0];
    expect(destructiveRule).not.toMatch(/width\s*:/);
    // The width still exists, scoped to the modal usage.
    expect(css).toMatch(/\.modal-inner \.btn-primary\s*\{[^}]*width:\s*70%/);
    expect(css).toMatch(/\.modal-inner \.btn-primary\s*\{[^}]*width:\s*40%/);
  });

  it('derives the compact jelly from the intro button, dialed down', () => {
    const primaryRule = css.match(/\.btn-primary[^{]*\{[^}]*\}/)![0];
    const jellyRule = css.match(/\.jelly-button\s*\{[^}]*\}/)![0];
    // Same gradient logic as .jelly-button.
    expect(primaryRule).toContain('var(--color-accent-tint)');
    expect(primaryRule).toContain('var(--color-accent-deep)');
    // Ring idea present but quieter: 4px vs the intro button's 7px.
    expect(primaryRule).toContain('box-shadow: 0 0 0 4px var(--color-text-bright)');
    expect(jellyRule).toContain('box-shadow: 0 0 0 7px');
    // Smaller padding than the intro button (1.5rem base, 2rem desktop).
    expect(primaryRule).not.toMatch(/padding:\s*(1\.5rem|2rem)/);
  });

  it('keeps the destructive pink confined to the token and on end-session', () => {
    const destructiveRule = css.match(/\.btn-destructive\s*,\s*button\.end-session\s*\{[^}]*\}/)![0];
    expect(destructiveRule).toContain('var(--color-destructive)');
    // The literal pink appears only in the :root token declaration.
    const withoutTokenDecls = css.replace(/^\s*--(color|radius|z|font|text)-[^:]*:.*$/gm, '');
    expect(withoutTokenDecls).not.toContain('#FF6B9D');
    // The end-session button is aliased onto the destructive role.
    expect(css).toMatch(/\.btn-destructive[^{]*button\.end-session\s*\{/);
  });

  it('leaves no non-role button rule with its own background/border/colour', () => {
    // Every `button.*` rule is either grouped into a role selector (the only
    // documented alias is button.end-session on the destructive role) or is a
    // layout-only rule. No button rule may carry its own background/border/
    // colour; the contract at style.css:429-439 reserves those for the roles.
    const offenders: string[] = [];
    const buttonRule = /button\.([a-z-]+)(?::[a-z-]+)?\s*\{[^}]*\}/g;
    for (const match of css.matchAll(buttonRule)) {
      const [rule] = match;
      if (rule.includes('button.end-session')) continue;
      if (/background|border|color\s*:/.test(rule)) {
        offenders.push(rule.trim());
      }
    }
    expect(offenders).toEqual([]);
  });

  it('applies the compact jelly to exactly the four named primaries', () => {
    const host = readSource('HostModal.tsx');
    const join = readSource('JoinModal.tsx');
    const genre = readSource('GenreModal.tsx');
    const match = readSource('MatchFoundModal.tsx');
    const swipe = readSource('SwipePage.tsx');

    // Create Session, Join Session, Confirm and the match modal's Open in
    // Jellyfin (link + disabled fallback) carry the primary role.
    expect(host).toMatch(/btn-primary[^>]*>\s*\{isSubmitting[^}]*Create Session/);
    expect(join).toMatch(/btn-primary[^>]*>\s*\{isSubmitting[^}]*Join Session/);
    expect(genre).toMatch(/btn-primary[^>]*>\s*Confirm/);
    // The match modal carries the primary on Open in Jellyfin twice: once as
    // the deep-link (btn-primary-link) and once as the disabled fallback.
    expect(match).toMatch(/btn-primary btn-primary-link[^>]*>/);
    expect(match).toMatch(/className="btn-primary" disabled/);

    // Cancel, Keep Swiping and the session toolbar controls stay secondary;
    // end-session takes the destructive role.
    expect(host).toMatch(/btn-secondary[^>]*>\s*Cancel/);
    expect(join).toMatch(/btn-secondary[^>]*>\s*Cancel/);
    expect(genre).toMatch(/btn-secondary[^>]*>\s*Cancel/);
    expect(match).toMatch(/btn-secondary[^>]*>\s*Keep Swiping/);
    expect(swipe).toMatch(/btn-destructive end-session/);
    expect(swipe).toMatch(/btn-secondary genres/);
    expect(swipe).toMatch(/btn-secondary undo-button/);
    expect(swipe).toMatch(/btn-secondary matches/);
  });

  it('defines a visible :focus-visible indicator for each button role (WCAG 2.4.7)', () => {
    const primaryRule = css.match(/\.btn-primary[^{}]*:focus-visible[^{]*\{[^}]*\}/)?.[0];
    const secondaryRule = css.match(/\.btn-secondary[^{}]*:focus-visible[^{]*\{[^}]*\}/)?.[0];
    const destructiveRule = css.match(/\.btn-destructive[^{}]*:focus-visible[^{]*\{[^}]*\}/)?.[0];
    expect(primaryRule, '.btn-primary:focus-visible').toBeTruthy();
    expect(secondaryRule, '.btn-secondary:focus-visible').toBeTruthy();
    expect(destructiveRule, '.btn-destructive:focus-visible').toBeTruthy();
    // Each indicator must be token-drawn (no raw palette literal) and must not
    // be a blanket suppression of the platform focus ring. The roles now draw
    // from the shared --focus-* tokens (issue #353) instead of individual
    // --color-* literals, so accept either token family.
    for (const rule of [primaryRule!, secondaryRule!, destructiveRule!]) {
      expect(rule).toMatch(/var\(--(?:focus|color)-/);
      expect(rule).not.toContain('outline: none');
    }
  });
});

describe('shared keyboard-focus treatment (issue #353)', () => {
  const css = readSource('style.css');

  it('defines the focus tokens on :root composed from existing color tokens', () => {
    const rootBlock = css.match(/:root\s*\{[^}]*\}/)?.[0] ?? '';
    expect(rootBlock, ':root block').toBeTruthy();
    expect(rootBlock).toContain('--focus-ring: var(--color-');
    expect(rootBlock).toContain('--focus-ring-offset:');
    expect(rootBlock).toContain('--focus-glow:');
    // The focus tokens must be composed from tokens, never a raw palette hex.
    const focusDecls = rootBlock.match(/--focus-[^;]+;/g)?.join('\n') ?? '';
    expect(focusDecls).not.toMatch(/#[0-9a-fA-F]{6}\b/);
  });

  it('draws one shared :focus-visible ring from the focus token for every plain family', () => {
    const sharedBlock = css.match(/\.jelly-button:focus-visible[^{]*\{[^}]*\}/)?.[0];
    expect(sharedBlock, 'shared :focus-visible rule').toBeTruthy();
    expect(sharedBlock!).toContain('var(--focus-ring)');
    expect(sharedBlock!).toContain('var(--focus-ring-offset)');
    expect(sharedBlock!).toContain('var(--focus-glow)');

    const families = [
      '.jelly-button:focus-visible',
      '.btn-primary:focus-visible',
      '.btn-primary-link:focus-visible',
      '.jelly-button--compact:focus-visible',
      '.btn-secondary:focus-visible',
      '.btn-destructive:focus-visible',
      'button.end-session:focus-visible',
      '.error-dismiss:focus-visible',
      '.retry-deck:focus-visible',
      '.jelly-toggle input:focus-visible + .slider',
      '.jelly-check input:focus-visible + .checkmark',
    ];
    for (const selector of families) {
      expect(sharedBlock, `shared rule covers ${selector}`).toContain(selector);
    }
  });

  it('isolates the genre radio family in its own :has() rule drawing the same tokens', () => {
    const radioBlock = css.match(/\.custom-radio:has\(input:focus-visible\)\s*\{[^}]*\}/)?.[0];
    expect(radioBlock, '.custom-radio:has(input:focus-visible) rule').toBeTruthy();
    expect(radioBlock!).toContain('var(--focus-ring)');
    expect(radioBlock!).toContain('var(--focus-ring-offset)');
    expect(radioBlock!).toContain('var(--focus-glow)');
  });

  it('keeps :has() out of the shared :focus-visible selector list', () => {
    // A single unsupported selector invalidates the whole comma-separated rule,
    // so the shared list must never grow a :has() member again — that coupling
    // would silently drop every control's focus ring on engines without :has().
    const sharedBlock = css.match(/\.jelly-button:focus-visible[^{]*\{[^}]*\}/)?.[0] ?? '';
    const selectorList = sharedBlock.slice(0, sharedBlock.indexOf('{'));
    expect(selectorList).not.toContain(':has(');
  });

  it('never suppresses the keyboard focus ring with outline: none', () => {
    const sharedBlock = css.match(/\.jelly-button:focus-visible[^{]*\{[^}]*\}/)?.[0] ?? '';
    expect(sharedBlock).not.toContain('outline: none');
  });
});

describe('materiality discipline (issue #347)', () => {
  const css = readSource('style.css');

  it('leaves no four-offset text-shadow outline pattern', () => {
    // The ±1px quad hack spelled with --color-navy-base must be gone entirely;
    // the specular jelly text-shadows on .jelly-button/.btn-primary are a
    // different, deliberate treatment and are not matched by this pattern.
    const quadPattern =
      /text-shadow:\s*-1px -1px 2px var\(--color-navy-base\),\s*1px -1px 2px var\(--color-navy-base\),\s*-1px 1px 2px var\(--color-navy-base\),\s*1px 1px 2px var\(--color-navy-base\)/;
    expect(css).not.toMatch(quadPattern);
  });

  it('leaves no transition: all', () => {
    expect(css).not.toMatch(/transition:\s*all\b/);
  });


  it('confines cyan outer glows to the three allowlisted rules', () => {
    // The token-derived outer-glow spelling (0 0 Npx color-mix(var(--color-accent)))
    // may appear only in the compact-jelly primary hover and the two checked-state
    // rules. Scoped to the accent token so the 0 0 0 2px border-light ring stops
    // (a different pattern) don't match. Gradient stops in background declarations
    // are also a different pattern and don't match.
    const glowPattern = /0 0 \d+px color-mix\(in srgb, var\(--color-accent\)/;
    const glowMatches = css.match(/0 0 \d+px color-mix\(in srgb, var\(--color-accent\)/g) ?? [];
    expect(glowMatches.length).toBe(3);

    const allowlisted = [
      /\.btn-primary:hover,\s*\.jelly-button--compact:hover\s*\{[^}]*\}/,
      /\.jelly-check input:checked \+ \.checkmark\s*\{[^}]*\}/,
      /\.jelly-toggle input:checked \+ \.slider\s*\{[^}]*\}/,
    ];
    for (const rule of allowlisted) {
      const block = css.match(rule)?.[0] ?? '';
      expect(block, `allowlisted rule ${rule} must carry the outer glow`).toMatch(glowPattern);
    }
  });

  it('routes every border-radius through the radius scale', () => {
    const decls = css.match(/border-radius:\s*[^;]+;/g) ?? [];
    expect(decls.length).toBeGreaterThan(0);
    for (const decl of decls) {
      expect(decl).toMatch(/border-radius:\s*var\(--radius-/);
    }
  });

  it('routes every z-index through the z-index scale', () => {
    const decls = css.match(/z-index:\s*[^;]+;/g) ?? [];
    expect(decls.length).toBeGreaterThan(0);
    for (const decl of decls) {
      expect(decl).toMatch(/z-index:\s*var\(--z-/);
    }
  });
});

describe('reduced-motion support (issue #353)', () => {
  const css = readSource('style.css');
  // The only @media (prefers-reduced-motion: reduce) block ends the file, so
  // everything from the query to EOF is the block.
  const reduceBlock = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'));

  it('stops the looping waiting animation entirely', () => {
    const waitingRule = reduceBlock.match(/\.waiting-text\s*\{[^}]*\}/);
    expect(waitingRule, '.waiting-text rule inside the media block').toBeTruthy();
    expect(waitingRule![0]).toContain('animation: none');
  });

  it('turns the card detail flip into a crossfade (no rotateY, faces swapped by opacity)', () => {
    // No 3D flip machinery under reduce: the flipped inner and the back face
    // must not carry a rotateY transform.
    expect(reduceBlock).toMatch(/\.card-item-container\.flipped \.card-item-inner\s*\{[^}]*transform:\s*none/);
    expect(reduceBlock).toMatch(/div\.back\s*\{[^}]*transform:\s*none/);
    // Backface visibility is restored so the later-in-DOM back face no longer
    // relies on backface-culling to hide itself.
    expect(reduceBlock).toMatch(/div\.card-item\s*\{[^}]*backface-visibility:\s*visible/);
    // The inactive face is invisible and non-interactive (visibility hidden
    // alongside opacity 0) in both flip states.
    expect(reduceBlock).toMatch(/\.card-item-container:not\(\.flipped\) div\.card-item\.back[^{]*\{[^}]*visibility:\s*hidden/);
    expect(reduceBlock).toMatch(/\.card-item-container\.flipped div\.card-item\.front[^{]*\{[^}]*visibility:\s*hidden/);
  });

  it('shortens decorative hover/state transitions, not removes them', () => {
    // Targeted selectors, never the blanket `*` pattern (which would clobber
    // the swipe-stamp/rim feedback and the inline drag rules). Comments are
    // stripped first so the literal pattern in a comment can't trip the guard.
    const rulesOnly = reduceBlock.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(rulesOnly).not.toMatch(/\*,\s*\*::before[^{]*\{[^}]*transition-duration/);
    // A representative sample of the interactive families gets a shortened
    // duration inside the block.
    expect(reduceBlock).toMatch(/\.jelly-button[^{]*\{[^}]*transition-duration:\s*0\.15s/);
    expect(reduceBlock).toMatch(/\.btn-secondary[^{]*\{[^}]*transition-duration:\s*0\.15s/);
    expect(reduceBlock).toMatch(/\.custom-radio[^{]*\{[^}]*transition-duration:\s*0\.15s/);
  });

  it('leaves the swipe-stamp/rim 60ms feedback untouched by the block', () => {
    expect(reduceBlock).not.toContain('.swipe-stamp');
    expect(reduceBlock).not.toContain('.swipe-rim');
  });
});

describe('dynamic viewport units (issue #351)', () => {
  const css = readSource('style.css');

  it('sizes the shared modal overlay to the visible viewport height', () => {
    const modalRule = css.match(/\.modal\s*\{[^}]*\}/)?.[0];
    expect(modalRule, '.modal rule').toBeTruthy();
    expect(modalRule!).toContain('height: 100dvh');
    // Width is unaffected by browser chrome and must stay viewport-width based.
    expect(modalRule!).toContain('width: 100vw');
  });

  it('sets the body min-height to the visible viewport height', () => {
    const bodyRule = css.match(/body\s*\{[^}]*\}/)?.[0];
    expect(bodyRule, 'body rule').toBeTruthy();
    expect(bodyRule!).toContain('min-height: 100dvh');
  });

  it('leaves no 100vh declaration anywhere in the file', () => {
    expect(css).not.toMatch(/100vh/);
  });
});

describe('swipe deck sizes from the viewport (issue #351)', () => {
  const css = readSource('style.css');

  it('derives the deck height from the available viewport space', () => {
    const deckRule = css.match(/\.swipe-deck\s*\{[^}]*\}/)?.[0];
    expect(deckRule, '.swipe-deck rule').toBeTruthy();
    expect(deckRule!).toMatch(/height:\s*min\(650px,\s*62dvh\)/);
  });

  it('leaves no bare fixed pixel height on the swipe deck anywhere', () => {
    // The deck must be sized from viewport space, not a fixed pixel height
    // keyed to viewport width (issue #351, coordinating with #278).
    expect(css).not.toMatch(/\.swipe-deck[^{]*\{[^}]*height:\s*\d+px/);
  });

  it('keeps the poster frame at a 2:3 aspect ratio', () => {
    const frameRule = css.match(/div\.poster-frame\s*\{[^}]*\}/)?.[0];
    expect(frameRule, 'div.poster-frame rule').toBeTruthy();
    expect(frameRule!).toContain('aspect-ratio: 2 / 3');
  });

  it('reserves top clearance for the media-type chip on the front face', () => {
    // The absolutely-positioned div.media-type chip sits at top:10px and is
    // ~34px tall (16px text at line-height 1.5 + 8px padding + 2px border),
    // so its bottom edge is ~44px. The calc and margin keep the frame below
    // it: the -20px term cancels margin-top, so the centred frame's margin box
    // is 52px shorter than the card and justify-content: center splits that
    // evenly — frame top = 26px free space + 20px margin = ~46px, with a
    // ~26px gap at the card's bottom (review follow-up on #351).
    const frameRule = css.match(/div\.poster-frame\s*\{[^}]*\}/)?.[0];
    expect(frameRule, 'div.poster-frame rule').toBeTruthy();
    expect(frameRule!).toContain('height: calc(100% - 20px - 52px)');
    expect(frameRule!).toContain('margin-top: 20px');
  });

  it('lets the details back face scroll so cast and trailer stay reachable', () => {
    // The details face is taller than a short viewport-derived deck (issue
    // #351 review follow-up), so it must declare an internal scroll mechanism
    // instead of letting the card's overflow: hidden clip the lower content.
    const backRule = css.match(/div\.back\s*\{[^}]*\}/)?.[0];
    expect(backRule, 'div.back rule').toBeTruthy();
    expect(backRule!).toContain('overflow-y: auto');
  });
});
