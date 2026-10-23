import JDWorkspace from "@/features/jd-intelligence/jd-workspace";

export const metadata = {
  title: "JD Intelligence & Evidence Mapping | CareerProof",
  description:
    "Ground-truth requirement extraction anchored to verbatim quotes, with deterministic matching against approved Universal Evidence Catalog claims.",
};

export default function JDPage() {
  return (
    <main id="main-content">
      <JDWorkspace />
    </main>
  );
}
