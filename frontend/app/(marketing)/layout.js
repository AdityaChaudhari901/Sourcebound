// Root layout for the public marketing group (the landing page). Separate from the
// authenticated app layout so the landing renders standalone — no app shell, no
// auth gate — with its own fonts and self-contained design CSS.

export const metadata = {
  title: "Sourcebound",
  description: "Citation-grounded KnowledgeOps — every answer traceable to a source.",
};

// Set the persisted theme before first paint to avoid a dark/light flash.
const noFlashTheme = `(function(){try{var t=localStorage.getItem('sb-theme');document.documentElement.setAttribute('data-theme',t==='light'?'light':'dark');}catch(e){}})();`;

export default function MarketingLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        <script dangerouslySetInnerHTML={{ __html: noFlashTheme }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
