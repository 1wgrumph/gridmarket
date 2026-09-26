/** Inline stroke icons in place of arrow glyphs that Inter's latin subset lacks. */
const paths = {
  'up-right': 'M4 12 12 4M6 4h6v6',
  'down-right': 'M4 4l8 8M12 6v6H6',
  'left-right': 'M2 8h12M5 5 2 8l3 3M11 5l3 3-3 3',
  plus: 'M8 3v10M3 8h10',
} as const;

export default function Icon({ name }: { name: keyof typeof paths }) {
  return <svg className="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d={paths[name]}/></svg>;
}
