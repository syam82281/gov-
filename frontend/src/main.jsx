import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Search, Landmark, BriefcaseBusiness, TrainFront, GraduationCap, ShieldCheck, Wallet, FileText, Menu, ExternalLink, BadgeCheck, Bell, MapPin, ArrowRight, Building2, X, CalendarDays } from "lucide-react";
import "./style.css";
import "./job-links.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const iconFor = (category = "") => {
  const c = category.toLowerCase();
  if (c.includes("rail")) return TrainFront;
  if (c.includes("bank")) return Wallet;
  if (c.includes("police") || c.includes("defence")) return ShieldCheck;
  if (c.includes("exam") || c.includes("education")) return GraduationCap;
  if (c.includes("service") || c.includes("certificate")) return FileText;
  if (c.includes("state")) return Building2;
  return BriefcaseBusiness;
};
const localDateString = (date = new Date()) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};
const formatDate = value => new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

function App() {
  const [items, setItems] = useState([]);
  const [jobLinks, setJobLinks] = useState([]);
  const [jobLinksLoading, setJobLinksLoading] = useState(true);
  const [jobLinksError, setJobLinksError] = useState("");
  const [jobLinkFormOpen, setJobLinkFormOpen] = useState(false);
  const [jobLinkNotice, setJobLinkNotice] = useState("");
  const [jobLinkForm, setJobLinkForm] = useState({ title: "", apply_url: "", start_date: "", end_date: "" });
  const [adminApiKey, setAdminApiKey] = useState("");
  const [categories, setCategories] = useState(["All"]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [state, setState] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/categories`).then(r => r.json()).then(data => setCategories(["All", ...data])).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    const loadJobLinks = () => fetch(`${API}/api/job-links`)
      .then(response => {
        if (!response.ok) throw new Error("Could not load job links.");
        return response.json();
      })
      .then(data => {
        if (active) {
          setJobLinks(data);
          setJobLinksError("");
        }
      })
      .catch(() => {
        if (active) setJobLinksError("Cannot load job links. Please try again later.");
      })
      .finally(() => {
        if (active) setJobLinksLoading(false);
      });
    loadJobLinks();
    const intervalId = window.setInterval(loadJobLinks, 60_000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const params = new URLSearchParams();
    if (search.trim()) params.set("search", search.trim());
    if (category !== "All") params.set("category", category);
    if (state !== "All") params.set("state", state);
    fetch(`${API}/api/opportunities?${params.toString()}`, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error("API request failed"); return r.json(); })
      .then(data => { setItems(data); setError(""); })
      .catch(e => { if (e.name !== "AbortError") setError("Cannot connect to the API. Make sure Docker services are running."); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [search, category, state]);

  const featured = useMemo(() => items.filter(x => x.featured), [items]);

  async function submitJobLink(event) {
    event.preventDefault();
    setJobLinksError("");
    setJobLinkNotice("");
    try {
      const response = await fetch(`${API}/api/job-links`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Key": adminApiKey,
        },
        body: JSON.stringify({
          title: jobLinkForm.title,
          apply_url: jobLinkForm.apply_url,
          start_date: jobLinkForm.start_date,
          end_date: jobLinkForm.end_date,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map(issue => issue.msg).join(" ")
          : data.detail;
        throw new Error(detail || "Unable to publish this job link.");
      }
      setJobLinks(current => [...current, data].sort((a, b) => a.start_date.localeCompare(b.start_date) || a.title.localeCompare(b.title)));
      setJobLinkForm(current => ({ ...current, title: "", apply_url: "", start_date: "", end_date: "" }));
      setJobLinkNotice("Job link published.");
    } catch (requestError) {
      setJobLinksError(requestError.message || "Unable to publish this job link. Check that the API is running.");
    }
  }

  return <div className="app">
    <header className="topbar">
      <a className="brand" href="#"><span className="brand-mark"><Landmark size={22}/></span><span>Bharat<span className="brand-accent">One</span><small>GOVERNMENT PORTAL</small></span></a>
      <nav><a href="#jobs">Government Jobs</a><a href="#job-links">Job Links</a><a href="#services">Services</a><a href="#how">How it works</a></nav>
      <a className="top-cta" href="#jobs">Explore opportunities <ArrowRight size={16}/></a>
    </header>

    <main>
      <section className="hero">
        <div className="hero-content">
          <div className="eyebrow"><span className="live-dot"></span> ONE PORTAL. INDIA-WIDE OPPORTUNITIES.</div>
          <h1>Your next government<br/><em>opportunity starts here.</em></h1>
          <p>Discover recruitment notifications, exam portals and essential government services — with official links in one place.</p>
          <div className="hero-search"><Search size={20}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search RRB, SSC, UPSC, Police, Banking..."/><button onClick={() => document.getElementById("jobs").scrollIntoView({behavior:"smooth"})}>Search</button></div>
          <div className="hero-meta"><span><BadgeCheck size={15}/> Official-source links</span><span><MapPin size={15}/> Central + State portals</span><span><Bell size={15}/> Deadline information</span></div>
        </div>
        <div className="hero-art" aria-hidden="true"><div className="orbit orbit-one"></div><div className="orbit orbit-two"></div><div className="hero-seal"><Landmark size={72}/><span>भारत</span></div><div className="float-card card-a"><TrainFront/><span><b>RRB</b><small>Railway recruitment</small></span></div><div className="float-card card-b"><GraduationCap/><span><b>UPSC</b><small>National examinations</small></span></div><div className="float-card card-c"><ShieldCheck/><span><b>State Jobs</b><small>Police & public service</small></span></div></div>
      </section>

      <section className="stats">
        <div><strong>{items.length.toString().padStart(2,"0")}</strong><span>Listed portals & opportunities</span></div>
        <div><strong>Central + State</strong><span>Government coverage</span></div>
        <div><strong>Direct</strong><span>Official website links</span></div>
      </section>

      <section className="section" id="jobs">
        <div className="section-heading"><div><div className="eyebrow dark">FIND YOUR OPPORTUNITY</div><h2>Featured government applications</h2><p>Explore popular recruitment boards and government portals.</p></div><span className="result-count">{items.length} results</span></div>
        <div className="filters">
          <label className="filter-search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search by job, board or keyword"/></label>
          <select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select>
          <select value={state} onChange={e=>setState(e.target.value)}><option>All</option><option>Andhra Pradesh</option></select>
        </div>
        {error && <div className="error">{error}</div>}
        {loading ? <div className="loading">Loading government portals…</div> : items.length === 0 ? <div className="empty">No matching portals found. Try another search.</div> :
          <div className="job-grid">{items.map(item => { const Icon = iconFor(item.category); return <article className="job-card" key={item.id}>
            <div className="card-top"><span className="card-icon"><Icon size={22}/></span><span className="category">{item.category}</span></div>
            <h3>{item.title}</h3><p className="org">{item.organization}</p>
            <div className="detail"><span>Qualification</span><b>{item.qualification}</b></div>
            <div className="detail"><span>Last date</span><b>{item.last_date}</b></div>
            <div className="card-bottom">{item.verified && <span className="verified"><BadgeCheck size={14}/> Source listed</span>}<a href={item.apply_url} target="_blank" rel="noopener noreferrer">Official website <ExternalLink size={14}/></a></div>
          </article>; })}</div>}
      </section>

      <section className="section job-links-section" id="job-links">
        <div className="section-heading">
          <div><div className="eyebrow dark">DIRECT APPLICATION LINKS</div><h2>Job Links</h2><p>Apply directly using the posted link during its application dates.</p></div>
          <div className="job-link-actions">
            <button className="post-link-toggle" type="button" onClick={() => { setJobLinkFormOpen(open => !open); setJobLinksError(""); setJobLinkNotice(""); }}>
              {jobLinkFormOpen ? <X size={16}/> : <BriefcaseBusiness size={16}/>}
              {jobLinkFormOpen ? "Close form" : "Post a job link"}
            </button>
          </div>
        </div>
        {jobLinkFormOpen && <form className="job-link-form" onSubmit={submitJobLink}>
          <div className="job-link-form-heading"><strong>Post a job link</strong><span>Enter the job name, application URL, and application dates.</span></div>
          <label>Job title<input required minLength="3" maxLength="200" value={jobLinkForm.title} onChange={event => setJobLinkForm(current => ({ ...current, title: event.target.value }))} placeholder="e.g. Junior Assistant Recruitment"/></label>
          <label>Application link<input required type="url" pattern="https?://.+" value={jobLinkForm.apply_url} onChange={event => setJobLinkForm(current => ({ ...current, apply_url: event.target.value }))} placeholder="https://example.gov.in/apply"/></label>
          <div className="job-link-dates">
            <label>Starting date<input required type="date" value={jobLinkForm.start_date} onChange={event => setJobLinkForm(current => ({ ...current, start_date: event.target.value }))}/></label>
            <label>Ending date<input required type="date" min={jobLinkForm.start_date || undefined} value={jobLinkForm.end_date} onChange={event => setJobLinkForm(current => ({ ...current, end_date: event.target.value }))}/></label>
          </div>
          <label>Admin API key<input required type="password" autoComplete="new-password" value={adminApiKey} onChange={event => setAdminApiKey(event.target.value)} placeholder="Enter the configured admin key"/></label>
          <button className="publish-link-button" type="submit">Publish job link <ArrowRight size={15}/></button>
        </form>}
        {jobLinkNotice && <div className="job-link-success" role="status">{jobLinkNotice}</div>}
        {jobLinksError && <div className="error" role="alert">{jobLinksError}</div>}
        {jobLinksLoading ? <div className="loading">Loading job links…</div> : jobLinks.length === 0 ? <div className="empty">No job links have been posted yet.</div> :
          <div className="job-link-grid">{jobLinks.map(link => {
            const today = localDateString();
            const isUpcoming = today < link.start_date;
            const isClosed = today > link.end_date;
            const isOpen = !isUpcoming && !isClosed;
            return <article className="job-link-card" key={link.id}>
              <div className="job-link-card-heading"><span className="job-link-icon"><BriefcaseBusiness size={20}/></span><span className={`job-link-status ${isOpen ? "is-open" : ""}`}>{isUpcoming ? "Opens soon" : isClosed ? "Applications closed" : "Applications open"}</span></div>
              <h3>{link.title}</h3>
              <div className="job-link-dates-display">
                <span><CalendarDays size={15}/> Starts <time dateTime={link.start_date}>{formatDate(link.start_date)}</time></span>
                <span><CalendarDays size={15}/> Ends <time dateTime={link.end_date}>{formatDate(link.end_date)}</time></span>
              </div>
              {isOpen
                ? <a className="job-link-apply" href={link.apply_url} target="_blank" rel="noopener noreferrer">Apply now <ExternalLink size={15}/></a>
                : <span className="job-link-apply is-disabled" aria-disabled="true">{isUpcoming ? "Apply when applications open" : "Application period ended"}</span>}
            </article>;
          })}</div>}
      </section>

      <section className="services" id="services"><div className="section-heading"><div><div className="eyebrow dark">MORE THAN RECRUITMENT</div><h2>Government services, simplified</h2><p>Quick access to useful citizen-service portals.</p></div></div>
        <div className="service-grid">
          <a href="https://www.digilocker.gov.in/" target="_blank" rel="noreferrer"><FileText/><b>DigiLocker</b><span>Digital documents & certificates <ExternalLink size={13}/></span></a>
          <a href="https://www.ncs.gov.in/" target="_blank" rel="noreferrer"><BriefcaseBusiness/><b>National Career Service</b><span>Employment and career services <ExternalLink size={13}/></span></a>
          <a href="https://www.india.gov.in/" target="_blank" rel="noreferrer"><Landmark/><b>National Portal of India</b><span>Government information and services <ExternalLink size={13}/></span></a>
          <a href="https://www.ap.gov.in/" target="_blank" rel="noreferrer"><Building2/><b>AP Government</b><span>Andhra Pradesh official portal <ExternalLink size={13}/></span></a>
        </div>
      </section>

      <section className="how" id="how"><div><div className="eyebrow">SIMPLE. CLEAR. DIRECT.</div><h2>Find information.<br/>Apply on the official portal.</h2></div><div className="steps"><div><b>01</b><span><strong>Search</strong><small>Find a recruitment board, exam or service.</small></span></div><div><b>02</b><span><strong>Review</strong><small>Check eligibility and dates in the official notification.</small></span></div><div><b>03</b><span><strong>Apply</strong><small>Continue securely on the government's official website.</small></span></div></div></section>
    </main>
    <footer><a className="brand footer-brand" href="#"><span className="brand-mark"><Landmark size={19}/></span><span>Bharat<span className="brand-accent">One</span></span></a><p>Independent information directory. Always verify eligibility, dates and fees on the official notification before applying.</p><span>© {new Date().getFullYear()} Bharat One</span></footer>
  </div>;
}

createRoot(document.getElementById("root")).render(<App/>);
