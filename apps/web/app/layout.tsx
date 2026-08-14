import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Reweave — codebase health for the AI era',
  description:
    'Find semantically duplicated logic, measure it, and fix it with test-verified consolidation pull requests.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
