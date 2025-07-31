import Navbar from "./components/Navbar.jsx"
import VB6Converter from "./components/VB6Converter.jsx"
import Footer from "./components/Footer.jsx"

function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <Navbar />
      <VB6Converter />
      <Footer />
    </div>
  )
}

export default App
