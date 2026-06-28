"use client";

import { useEffect } from "react";

/**
 * Landing-page interactivity, ported verbatim from the Claude Design export
 * (Sourcebound v3). Runs after the markup is in the DOM. Accent/grain/glow are
 * fixed to the design defaults (amber, on, on) — the design's prop editor is an
 * authoring-only concern. Returns a cleanup that tears down timers/listeners.
 */
export default function LandingInteractions() {
  useEffect(() => {
    const reduced =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cleanups = [];
    const root = document.documentElement;

    // --- Theme (persisted) ---
    let theme = "dark";
    try {
      theme = localStorage.getItem("sb-theme") === "light" ? "light" : "dark";
    } catch (e) {}
    const applyTheme = () => {
      root.setAttribute("data-theme", theme);
      const moon = document.querySelector("#sb-theme-btn .ic-moon");
      const sun = document.querySelector("#sb-theme-btn .ic-sun");
      if (moon && sun) {
        moon.style.display = theme === "dark" ? "" : "none";
        sun.style.display = theme === "light" ? "" : "none";
      }
    };
    applyTheme();
    const btn = document.getElementById("sb-theme-btn");
    const onToggle = (e) => {
      e.preventDefault();
      theme = theme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("sb-theme", theme);
      } catch (err) {}
      applyTheme();
    };
    if (btn) {
      btn.addEventListener("click", onToggle);
      cleanups.push(() => btn.removeEventListener("click", onToggle));
    }

    // --- Settings (defaults: amber accent, grain on, glow on) ---
    const grain = document.getElementById("sb-grain");
    if (grain) grain.style.display = "";
    const glowEl = document.getElementById("sb-ctaglow");
    if (glowEl) glowEl.dataset.enabled = "1";

    // --- Logo marquee fallback: any logo image that fails to load becomes a
    // clean monospace wordmark (from its alt text), so the strip never shows a
    // broken image and stays visually consistent. ---
    document.querySelectorAll("img.sb-logo").forEach((img) => {
      const toWordmark = () => {
        if (img.dataset.fallback === "1") return;
        img.dataset.fallback = "1";
        const span = document.createElement("span");
        span.textContent = img.getAttribute("alt") || "";
        span.style.cssText =
          "font-family:'Geist Mono',ui-monospace,monospace;font-size:15px;" +
          "font-weight:500;letter-spacing:.2px;color:var(--text-2);white-space:nowrap";
        img.replaceWith(span);
      };
      img.addEventListener("error", toWordmark);
      // Catch images that already failed before this handler attached.
      if (img.complete && img.naturalWidth === 0) toWordmark();
    });

    // --- Reveal on scroll ---
    if (!reduced) {
      const els = [...document.querySelectorAll("[data-reveal]")];
      els.forEach((el) => {
        el.style.opacity = "0";
        el.style.transform = "translateY(22px) scale(0.985)";
        el.style.transition =
          "opacity .7s cubic-bezier(.2,.7,.2,1), transform .7s cubic-bezier(.2,.7,.2,1)";
        el.style.transitionDelay =
          parseInt(el.getAttribute("data-reveal-delay") || "0", 10) + "ms";
      });
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            if (e.isIntersecting) {
              e.target.style.opacity = "1";
              e.target.style.transform = "none";
              io.unobserve(e.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
      );
      els.forEach((el) => io.observe(el));
      cleanups.push(() => io.disconnect());
    }

    // --- Count-up numbers, bars, sparkline ---
    {
      const nums = [...document.querySelectorAll(".cu")];
      const fmt = (v, dec) => v.toFixed(dec);
      if (!reduced)
        nums.forEach((el) => {
          el.textContent = fmt(0, parseInt(el.getAttribute("data-dec") || "0", 10));
        });
      const run = (el) => {
        const target = parseFloat(el.getAttribute("data-count"));
        const dec = parseInt(el.getAttribute("data-dec") || "0", 10);
        if (reduced) {
          el.textContent = fmt(target, dec);
          return;
        }
        const dur = 1300;
        const t0 = performance.now();
        const tick = (t) => {
          const p = Math.min(1, (t - t0) / dur);
          const e = 1 - Math.pow(1 - p, 3);
          el.textContent = fmt(target * e, dec);
          if (p < 1) requestAnimationFrame(tick);
          else el.textContent = fmt(target, dec);
        };
        requestAnimationFrame(tick);
      };
      const io = new IntersectionObserver(
        (en) => {
          en.forEach((e) => {
            if (e.isIntersecting) {
              run(e.target);
              io.unobserve(e.target);
            }
          });
        },
        { threshold: 0.5 }
      );
      nums.forEach((el) => io.observe(el));
      cleanups.push(() => io.disconnect());

      const bio = new IntersectionObserver(
        (en) => {
          en.forEach((e) => {
            if (e.isIntersecting) {
              e.target.style.width = e.target.getAttribute("data-w") + "%";
              bio.unobserve(e.target);
            }
          });
        },
        { threshold: 0.5 }
      );
      document.querySelectorAll(".bar").forEach((b) => {
        if (reduced) b.style.width = b.getAttribute("data-w") + "%";
        else bio.observe(b);
      });
      cleanups.push(() => bio.disconnect());

      const spark = document.querySelector("[data-spark]");
      if (spark) {
        if (reduced) {
          spark.style.strokeDashoffset = "0";
        } else {
          spark.style.transition = "stroke-dashoffset 1.4s cubic-bezier(.2,.7,.2,1)";
          const sio = new IntersectionObserver(
            (en) => {
              en.forEach((e) => {
                if (e.isIntersecting) {
                  spark.style.strokeDashoffset = "0";
                  sio.unobserve(spark);
                }
              });
            },
            { threshold: 0.6 }
          );
          sio.observe(spark);
          cleanups.push(() => sio.disconnect());
        }
      }
    }

    // --- Micro checkmark draw ---
    {
      const wrap = document.getElementById("sb-check");
      const check = wrap && wrap.querySelector(".checkpath");
      if (check) {
        if (reduced) {
          check.style.strokeDashoffset = "0";
        } else {
          check.style.transition = "stroke-dashoffset .7s cubic-bezier(.2,.7,.2,1)";
          const cio = new IntersectionObserver(
            (en) => {
              en.forEach((e) => {
                if (e.isIntersecting) {
                  check.style.strokeDashoffset = "0";
                  cio.unobserve(wrap);
                }
              });
            },
            { threshold: 0.6 }
          );
          cio.observe(wrap);
          cleanups.push(() => cio.disconnect());
        }
      }
    }

    // --- Bento 3D tilt + spotlight ---
    if (!reduced) {
      document.querySelectorAll("[data-bento]").forEach((card) => {
        const spot = card.querySelector(".spot");
        const onMove = (ev) => {
          const r = card.getBoundingClientRect();
          const px = (ev.clientX - r.left) / r.width;
          const py = (ev.clientY - r.top) / r.height;
          card.style.transform = `perspective(900px) rotateX(${(0.5 - py) * 6}deg) rotateY(${
            (px - 0.5) * 6
          }deg) translateY(-3px)`;
          if (spot) {
            spot.style.setProperty("--mx", px * 100 + "%");
            spot.style.setProperty("--my", py * 100 + "%");
          }
        };
        const onLeave = () => {
          card.style.transform = "perspective(900px) rotateX(0) rotateY(0)";
        };
        card.addEventListener("mousemove", onMove);
        card.addEventListener("mouseleave", onLeave);
        cleanups.push(() => {
          card.removeEventListener("mousemove", onMove);
          card.removeEventListener("mouseleave", onLeave);
        });
      });
    }

    // --- Magnetic buttons ---
    if (!reduced) {
      document.querySelectorAll("[data-mag]").forEach((b) => {
        b.style.transition = "transform .25s cubic-bezier(.2,.7,.2,1)";
        const onMove = (ev) => {
          const r = b.getBoundingClientRect();
          const dx = ev.clientX - (r.left + r.width / 2);
          const dy = ev.clientY - (r.top + r.height / 2);
          b.style.transform = `translate(${dx * 0.25}px, ${dy * 0.3}px)`;
        };
        const onLeave = () => {
          b.style.transform = "translate(0,0)";
        };
        b.addEventListener("mousemove", onMove);
        b.addEventListener("mouseleave", onLeave);
        cleanups.push(() => {
          b.removeEventListener("mousemove", onMove);
          b.removeEventListener("mouseleave", onLeave);
        });
      });
    }

    // --- Rotating keywords ---
    {
      const kws = [...document.querySelectorAll("#sb-kw .kw")];
      if (kws.length && !reduced) {
        let i = 0;
        const timer = setInterval(() => {
          kws[i].style.opacity = "0";
          i = (i + 1) % kws.length;
          kws[i].style.opacity = "1";
        }, 1600);
        cleanups.push(() => clearInterval(timer));
      }
    }

    // --- Sticky nav shrink on scroll ---
    {
      const nav = document.getElementById("sb-nav");
      if (nav) {
        const apply = () => {
          const s = window.scrollY > 24;
          nav.style.height = s ? "60px" : "74px";
          nav.style.background = s ? "rgba(var(--bg-rgb),0.8)" : "rgba(var(--bg-rgb),0)";
          nav.style.backdropFilter = s ? "blur(14px)" : "none";
          nav.style.webkitBackdropFilter = s ? "blur(14px)" : "none";
          nav.style.borderBottomColor = s ? "rgba(var(--line-rgb),0.08)" : "transparent";
        };
        apply();
        window.addEventListener("scroll", apply, { passive: true });
        cleanups.push(() => window.removeEventListener("scroll", apply));
      }
    }

    // --- Logo marquee ---
    {
      const track = document.querySelector(".marquee-track");
      if (track && !reduced) {
        const anim = track.animate(
          [{ transform: "translateX(0)" }, { transform: "translateX(-50%)" }],
          { duration: 22000, iterations: Infinity, easing: "linear" }
        );
        const wrap = document.querySelector(".marquee");
        if (wrap) {
          const onEnter = () => anim.pause();
          const onLeave = () => anim.play();
          wrap.addEventListener("mouseenter", onEnter);
          wrap.addEventListener("mouseleave", onLeave);
          cleanups.push(() => {
            wrap.removeEventListener("mouseenter", onEnter);
            wrap.removeEventListener("mouseleave", onLeave);
          });
        }
        cleanups.push(() => anim.cancel());
      }
    }

    // --- Engine node hover focus ---
    {
      const nodes = [...document.querySelectorAll("#sb-engine [data-node]")];
      nodes.forEach((n) => {
        const onEnter = () => {
          nodes.forEach((o) => {
            if (o === n) {
              o.style.opacity = "1";
              o.style.transform = "translateY(-2px)";
              o.style.boxShadow = "0 12px 36px -10px rgba(var(--accent-rgb),0.4)";
              o.style.borderColor = "rgba(var(--accent-rgb),0.6)";
            } else {
              o.style.opacity = "0.35";
            }
          });
        };
        const onLeave = () => {
          nodes.forEach((o) => {
            o.style.opacity = "1";
            o.style.transform = "";
            o.style.boxShadow = "";
            o.style.borderColor = "";
          });
        };
        n.addEventListener("mouseenter", onEnter);
        n.addEventListener("mouseleave", onLeave);
        cleanups.push(() => {
          n.removeEventListener("mouseenter", onEnter);
          n.removeEventListener("mouseleave", onLeave);
        });
      });
    }

    // --- CTA glow on view ---
    {
      const glow = document.getElementById("sb-ctaglow");
      if (glow && glow.parentElement) {
        const io = new IntersectionObserver(
          (en) => {
            en.forEach((e) => {
              const on = glow.dataset.enabled !== "0";
              glow.style.opacity = e.isIntersecting && on ? "0.95" : on ? "0.4" : "0";
            });
          },
          { threshold: 0.3 }
        );
        io.observe(glow.parentElement);
        cleanups.push(() => io.disconnect());
      }
    }

    // --- Visibility failsafe: content must always end up visible ---
    {
      const revealAll = () => {
        document.querySelectorAll("[data-anim]").forEach((el) => {
          el.style.opacity = "1";
          el.style.filter = "none";
          el.style.transform = "none";
        });
        document.querySelectorAll("[data-reveal]").forEach((el) => {
          el.style.opacity = "1";
          el.style.transform = "none";
        });
      };
      if (reduced) {
        revealAll();
      } else {
        const failsafe = setTimeout(revealAll, 1400);
        const onVis = () => {
          if (!document.hidden) revealAll();
        };
        document.addEventListener("visibilitychange", onVis);
        cleanups.push(() => {
          clearTimeout(failsafe);
          document.removeEventListener("visibilitychange", onVis);
        });
      }
    }

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return null;
}
