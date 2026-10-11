import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "../components/providers";

export const metadata: Metadata = {
  title: "Revora — Revenue Risk & Action Platform",
  description:
    "Evidence-backed revenue intelligence for modern revenue teams. Know why revenue is at risk. Act before it's too late.",
  icons: {
    icon: [
      { url: "/primary logo.png", type: "image/png" },
    ],
    apple: [
      { url: "/primary logo.png" },
    ],
    shortcut: ["/primary logo.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
      data-scroll-behavior="smooth"
    >
      <body className="min-h-full flex flex-col font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
