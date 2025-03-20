import "./css/style.css";
import { Inter } from "next/font/google";
import { Providers } from "./provider";


const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata = {
  title: "Pyxis: O&G Data Platform",
  description: "Pyxis is a data platform for the oil and gas industry.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${inter.variable} bg-gray-50 font-inter tracking-tight text-gray-900 antialiased`}
      >
        <div className="flex min-h-screen flex-col overflow-hidden supports-[overflow:clip]:overflow-clip">
          <Providers>
            {children}
          </Providers>
        </div>
      </body>
    </html>
  );
}
