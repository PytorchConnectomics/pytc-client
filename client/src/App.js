import { useEffect, useState } from 'react'
import localforage from 'localforage'
import './App.css'
import Views from './views/Views'
import { ContextWrapper } from './contexts/GlobalContext'
import { YamlContextWrapper } from './contexts/YamlContext'

const FILE_CACHE_KEYS = [
  'files',
  'fileList',
  'imageFileList',
  'labelFileList',
  'currentImage',
  'currentLabel',
  'inputImage',
  'inputLabel'
]

function App () {
  const [isCacheCleared, setIsCacheCleared] = useState(false)

  useEffect(() => {
    const clearFileCache = async () => {
      try {
        await Promise.all(
          FILE_CACHE_KEYS.map((key) => localforage.removeItem(key))
        )
      } catch (error) {
        console.error('Failed to clear file cache on startup:', error)
      } finally {
        setIsCacheCleared(true)
      }
    }

    clearFileCache()
  }, [])

  if (!isCacheCleared) {
    return null
  }

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
