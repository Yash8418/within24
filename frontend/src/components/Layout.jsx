import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Layout() {
  const { user, signOut } = useAuth();
  return (
    <>
      <header className="topbar">
        <div className="topbar__inner">
          <NavLink to="/" className="wordmark" end>
            Within<span>24</span>
          </NavLink>
          <nav aria-label="Main">
            <NavLink to="/" end>
              This week
            </NavLink>
            <NavLink to="/shifts">Shifts</NavLink>
            <NavLink to="/jobs">Jobs</NavLink>
            <NavLink to="/breaks">Breaks</NavLink>
          </nav>
          <div className="topbar__user">
            <span className="topbar__email">{user.full_name || user.email}</span>
            <button type="button" className="link-button" onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
      <footer className="footnote">
        Within24 helps you track your own hours. It isn't legal or immigration advice — check{" "}
        <a href="https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/work/work-off-campus.html">
          IRCC's official rules
        </a>{" "}
        or ask your international student office if you're unsure.
      </footer>
    </>
  );
}
