import { defineTheme } from '@astryxdesign/core/theme';

// Design v2 (DEC-GM-062): Coolors 000000-586f7c-b8dbd9-f4f4f9-04724d plus one warm status hue; tuples are [light, dark].
const inter = "'Inter', 'Inter Fallback', system-ui, sans-serif";

export const gridmarketTheme = defineTheme({
  name: 'gridmarket',
  tokens: {
    '--color-accent': ['#04724d', '#04724d'],
    '--color-on-accent': ['#f4f4f9', '#f4f4f9'],
    '--color-text-accent': ['#036141', '#88baac'],
    '--color-background-body': ['#e8e9ef', '#000000'],
    '--color-background-surface': ['#f4f4f9', '#0e1214'],
    '--color-background-card': ['#f4f4f9', '#0e1214'],
    '--color-background-muted': ['#dfebee', '#191f23'],
    '--color-text-primary': ['#000000', '#f4f4f9'],
    '--color-text-secondary': ['#465963', '#9bbbbd'],
    '--color-border': ['#c8cfd6', '#2c383e'],
    '--font-family-body': inter,
    '--font-family-heading': inter,
    '--font-family-code': inter,
    '--radius-element': '4px',
  },
});
