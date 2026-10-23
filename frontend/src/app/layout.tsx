import type { Metadata } from "next";
import { PRODUCT_NAME } from "@/lib/careerproof/types";
import "./globals.css";
export const metadata: Metadata = {
  title: `${PRODUCT_NAME} — Your experience, clearly represented`,
  description:
    "An evidence-based resume workspace. Bring your career together, clarify your contribution, and tailor a resume you can stand behind.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to workspace
        </a>
        {children}
      </body>
    </html>
  );
}
