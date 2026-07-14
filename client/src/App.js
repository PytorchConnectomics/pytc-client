import "./App.css";
import Views from "./views/Views";
import { ContextWrapper } from "./contexts/GlobalContext";
import { YamlContextWrapper } from "./contexts/YamlContext";
import { WorkflowProvider } from "./contexts/WorkflowContext";

function MainContent() {
  return <Views />;
}

function App() {
  return (
    <ContextWrapper>
      <YamlContextWrapper>
        <WorkflowProvider>
          <div className="App">
            <MainContent />
          </div>
        </WorkflowProvider>
      </YamlContextWrapper>
    </ContextWrapper>
  );
}

export default App;
