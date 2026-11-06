import { useEffect, useState } from "react";
import { EventExplorer } from "./event-explorer/EventExplorer";
import { RegimeIntel } from "./regime-intel/RegimeIntel";
import { Analog2018 } from "./analog/Analog2018";

type View = "explorer" | "regime" | "analog";

function viewFromHash(): View {
  const h = window.location.hash.replace("#", "");
  if (h === "regime") return "regime";
  if (h === "analog") return "analog";
  return "explorer";
}

export function App() {
  const [view, setView] = useState<View>(viewFromHash());

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (v: View) => {
    window.location.hash = v;
    setView(v);
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">FOMC</span>
          <span className="brand-sub">Event Explorer &amp; Regime Intelligence</span>
        </div>
        <nav className="tabs" role="tablist">
          <button
            role="tab"
            aria-selected={view === "explorer"}
            className={view === "explorer" ? "tab active" : "tab"}
            onClick={() => go("explorer")}
          >
            Event Explorer
          </button>
          <button
            role="tab"
            aria-selected={view === "regime"}
            className={view === "regime" ? "tab active" : "tab"}
            onClick={() => go("regime")}
          >
            Regime Intelligence
          </button>
          <button
            role="tab"
            aria-selected={view === "analog"}
            className={view === "analog" ? "tab active" : "tab"}
            onClick={() => go("analog")}
          >
            <span className="tab-long">What if 4Q'26 looks like 4Q'18?</span>
            <span className="tab-short">4Q'18 analog</span>
          </button>
        </nav>
      </header>

      <main className="content">
        {view === "explorer" ? <EventExplorer /> : view === "regime" ? <RegimeIntel /> : <Analog2018 />}
      </main>

      <footer className="footer">
        Evidence and regime-risk assessment only — <strong>not investment advice</strong>. The
        Event Explorer is the historical empirical layer; Regime Intelligence is the
        forward-looking evidence layer. Every claim links to its source.
        <div className="copyright">
          © 2026 Elendil Labs. Code: PolyForm Noncommercial 1.0.0. Data: CC BY 4.0. Not investment advice.
        </div>
      </footer>
    </div>
  );
}
