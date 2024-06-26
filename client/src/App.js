import './App.css'
import Views from './views/Views'
import { ContextWrapper } from './contexts/GlobalContext'
import { YamlContextWrapper } from './contexts/YamlContext'

function App () {
  return (
    <ContextWrapper>
      <YamlContextWrapper>
        <div className='App'>
          <Views />
        </div>
      </YamlContextWrapper>
    </ContextWrapper>
  )
}

export default App
