import "./landing.css";
import landingBody from "./landingBody";
import LandingInteractions from "./LandingInteractions";

export const metadata = {
  title: "Sourcebound — every answer, bound to its source",
  description:
    "Citation-grounded KnowledgeOps RAG. Connect your internal docs and code, ask a " +
    "question, get an answer with citations back to the source.",
};

export default function LandingPage() {
  // Body markup is the Claude Design export, rendered verbatim for full fidelity;
  // LandingInteractions wires up the theme toggle, reveals, tilt, and marquee.
  return (
    <>
      <div dangerouslySetInnerHTML={{ __html: landingBody }} />
      <LandingInteractions />
    </>
  );
}
