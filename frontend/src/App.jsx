import { Route, Routes } from "react-router-dom";

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<p>Within24</p>} />
    </Routes>
  );
}
