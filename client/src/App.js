import "./App.css";
import Views from "./views/Views";
import { ContextWrapper } from "./contexts/GlobalContext";

function App() {
  return (
    <ContextWrapper>
      <div className="App">
        <Views />
      </div>
    </ContextWrapper>
  );
}

export default App;
