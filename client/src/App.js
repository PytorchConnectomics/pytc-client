import { useContext, useEffect, useState } from 'react'
import './App.css'
import Views from './views/Views'
import { AppContext, ContextWrapper } from './contexts/GlobalContext'
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

function App () {
  return (
    <ContextWrapper>
      <YamlContextWrapper>
        <CacheBootstrapper>
          <div className='App'>
            <Views />
          </div>
        </CacheBootstrapper>
      </YamlContextWrapper>
    </ContextWrapper>
  )
}

export default App
