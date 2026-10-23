import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Desk } from "./pages/Desk";
import { Home } from "./pages/Home";

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/desk" element={<Desk />} />
      </Routes>
    </BrowserRouter>
  );
}
