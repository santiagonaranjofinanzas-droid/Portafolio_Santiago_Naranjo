import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: '--font-sans',
  display: 'swap',
  weight: ['400', '500', '600', '700', '800']
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: '--font-mono',
  display: 'swap',
  weight: ['400', '500', '600']
});

export const metadata: Metadata = {
  title: "Black Knight Quant Terminal",
  description: "Inteligencia de Trading de Grado Institucional — Plataforma SaaS",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans bg-[var(--bg-base)] text-[var(--text-primary)] antialiased`}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
