import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agentic Vector Search API",
  description: "Multi-query planning, fusion, reranking, critique, and corrective retrieval",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
