import { useContext, useEffect, useState } from 'react'
import './App.css'
import Views from './views/Views'
import { AppContext, ContextWrapper } from './contexts/GlobalContext'
import UserContextWrapper from './contexts/UserContext'
import { YamlContextWrapper } from './contexts/YamlContext'

function CacheBootstrapper ({ children }) {
  const { resetFileState } = useContext(AppContext)
  const [isCacheCleared, setIsCacheCleared] = useState(false)

  useEffect(() => {
    let isMounted = true
    const clearCache = async () => {
      await resetFileState()
      if (isMounted) {
        setIsCacheCleared(true)
      }
    }

    clearCache()
    return () => {
      isMounted = false
    }
  }, [resetFileState])

  if (!isCacheCleared) {
    return null
  }

  return children
}

function MainContent () {
  return <Views />
}

function App () {
  return (
    <UserContextWrapper>
      <ContextWrapper>
        <YamlContextWrapper>
          <CacheBootstrapper>
            <div className='App'>
              <MainContent />
            </div>
          </CacheBootstrapper>
        </YamlContextWrapper>
      </ContextWrapper>
    </UserContextWrapper>
  )
}

export default App
