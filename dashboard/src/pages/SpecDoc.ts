/// <reference types="vite/client" />
const documents = import.meta.glob('../../../spec/GridMarket-Specification.md', { eager: true, query: '?raw', import: 'default' });
export const specification = Object.values(documents)[0] as string | undefined;
